import os
import sqlite3
from flask import Flask, g, jsonify, request

from .models import Ambulance
from .services import (RoadGraph, NoRouteError, NoAmbulanceAvailable, NoHospitalAvailable,
                       dispatch_incident, advance_dispatch, update_road_conditions,
                       calls_from_db, clean_calls, find_hotspots, demand_by_hour,
                       recommend_positions, build_map_html)
from .services.dispatch import load_junctions, queued_incidents
from .services.automation import after_change
from .services.traffic import effective_rows
from .services.ops import notify, log_road_change, save_hotspots, record_completed_call


def create_app():
    app = Flask(__name__)
    app.config["DATABASE"] = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dispatch.db"
    )
    # --- Week 7: login, sessions ---------------------------------------------------------
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    app.config["AUTH_REQUIRED"] = os.environ.get("AUTH_REQUIRED", "1") != "0"
    app.config["SHOW_DEMO_LOGINS"] = os.environ.get("SHOW_DEMO_LOGINS", "1") != "0"
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("RENDER"))      # https on Render

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    from .auth import bp as auth_bp               # Week 7: login and roles
    from .manage import bp as manage_bp           # Week 7: registration, notifications, driver
    from .dashboard import bp as dashboard_bp     # Week 6: dashboard at /
    app.register_blueprint(auth_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(dashboard_bp)

    # ---------------------------------------------------------------- Week 1-3
    @app.route("/api/ambulances")
    def ambulances():
        rows = get_db().execute("SELECT * FROM ambulances").fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/ambulances/objects")
    def ambulance_objects():
        rows = get_db().execute("SELECT * FROM ambulances").fetchall()
        return jsonify([Ambulance.from_row(r).to_dict() for r in rows])

    @app.route("/api/hospitals")
    def hospitals():
        rows = get_db().execute("SELECT * FROM hospitals").fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/route")
    def route():
        """Example: /api/route?source=1&target=6"""
        try:
            source = int(request.args["source"])
            target = int(request.args["target"])
        except (KeyError, ValueError):
            return jsonify({"error": "Use /api/route?source=1&target=6"}), 400
        rows = effective_rows(get_db())
        if not rows:
            return jsonify({"error": "No roads found. Run python seed_roads.py"}), 404
        city = RoadGraph.from_rows(rows)
        try:
            path, cost, km = city.shortest_route(source, target)
        except NoRouteError as e:
            return jsonify({"error": str(e)}), 404
        return jsonify({"path": path, "total_distance_km": km, "travel_cost": cost})

    # ------------------------------------------------------------------ Week 4
    @app.route("/api/roads")
    def roads():
        return jsonify(effective_rows(get_db()))

    @app.route("/api/roads/traffic", methods=["POST"])
    def set_traffic():
        """JSON: {"source":4,"destination":5,"traffic_level":"HEAVY","road_condition":"GOOD"}"""
        data = request.get_json(silent=True) or {}
        try:
            db = get_db()
            a, b = int(data["source"]), int(data["destination"])
            update_road_conditions(db, a, b, data.get("traffic_level"), data.get("road_condition"))
            log_road_change(db, a, b)
            notify(db, "Road %d-%d set to traffic %s, condition %s" % (
                a, b, data.get("traffic_level") or "unchanged", data.get("road_condition") or "unchanged"))
        except (KeyError, TypeError):
            return jsonify({"error": "source and destination are required"}), 400
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"message": "Road updated", **after_change(get_db())})

    @app.route("/api/incidents/dispatch", methods=["POST"])
    def dispatch():
        """JSON: {"latitude":15.4881,"longitude":78.4931,"emergency_type":"accident","severity":4}"""
        data = request.get_json(silent=True) or {}
        try:
            result = dispatch_incident(get_db(), float(data["latitude"]), float(data["longitude"]),
                                       data.get("emergency_type", "general"),
                                       int(data.get("severity", 3)))
        except (KeyError, TypeError):
            return jsonify({"error": "latitude and longitude are required"}), 400
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except (NoAmbulanceAvailable, NoHospitalAvailable) as e:
            ids = [r["incident_id"] for r in queued_incidents(get_db())]
            place = ids.index(e.incident_id) + 1 if e.incident_id in ids else None
            return jsonify({"error": "%s. The incident is waiting in the queue (position %s) and will be "
                                     "dispatched automatically." % (e, place),
                            "queued": True, "incident_id": e.incident_id, "queue_position": place}), 409
        db = get_db()
        amb = db.execute("SELECT ambulance_id FROM ambulances WHERE vehicle_number=?",
                         (result["ambulance"],)).fetchone()
        notify(db, "%s dispatched to a %s emergency, ETA %s min, hospital %s" % (
            result["ambulance"], data.get("emergency_type", "general"), result["eta_to_scene_min"],
            result["hospital"]), "ambulance:%s" % amb["ambulance_id"])
        return jsonify(result), 201

    @app.route("/api/dispatches")
    def dispatches():
        rows = get_db().execute(
            """SELECT d.dispatch_id, a.vehicle_number, h.name AS hospital,
                      i.emergency_type, i.status AS incident_status,
                      a.status AS ambulance_status, d.response_time AS eta_min
               FROM dispatches d
               JOIN ambulances a ON a.ambulance_id = d.ambulance_id
               JOIN hospitals h ON h.hospital_id = d.hospital_id
               JOIN incidents i ON i.incident_id = d.incident_id
               ORDER BY d.dispatch_id DESC""").fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/dispatches/<int:dispatch_id>/advance", methods=["POST"])
    def advance(dispatch_id):
        db = get_db()
        try:
            out = advance_dispatch(db, dispatch_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        label = db.execute("SELECT a.vehicle_number, a.ambulance_id FROM dispatches d JOIN ambulances a "
                           "ON a.ambulance_id=d.ambulance_id WHERE d.dispatch_id=?", (dispatch_id,)).fetchone()
        notify(db, "%s is now %s (incident %s)" % (label["vehicle_number"], out["ambulance_status"],
                                                    out["incident_status"]), "ambulance:%s" % label["ambulance_id"])
        if out["ambulance_status"] == "AVAILABLE":
            record_completed_call(db, dispatch_id)        # feedback into the historical data
            out.update(after_change(db, reroute=False))   # the freed ambulance serves the waiting queue
        return jsonify(out)

    # ------------------------------------------------------------------ Week 5
    def demand_context():
        """Clean history + hotspots + recommendations from the request's query string."""
        db = get_db()
        method = request.args.get("method", "dbscan").lower()
        if method not in ("kmeans", "dbscan"):
            raise ValueError("method must be kmeans or dbscan")
        k = request.args.get("k", type=int)
        eps = request.args.get("eps_km", default=0.3, type=float)
        min_samples = request.args.get("min_samples", default=10, type=int)
        calls, report = clean_calls(calls_from_db(db))
        if calls.empty:
            raise LookupError("No historical calls found. Run python load_calls.py")
        spots = find_hotspots(calls, method, k, eps, min_samples)
        ambulance_list = [Ambulance.from_row(r) for r in db.execute("SELECT * FROM ambulances")]
        advice = recommend_positions(spots, load_junctions(db), ambulance_list, calls)
        return method, calls, report, spots, advice

    @app.route("/api/hotspots")
    def hotspots():
        """/api/hotspots?method=dbscan  or  /api/hotspots?method=kmeans&k=3"""
        try:
            method, calls, report, spots, _ = demand_context()
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except LookupError as e:
            return jsonify({"error": str(e)}), 404
        save_hotspots(get_db(), method, spots)
        return jsonify({"method": method, "cleaning": report, "hotspots": spots,
                        "calls_by_hour": demand_by_hour(calls)})

    @app.route("/api/prepositioning")
    def prepositioning():
        try:
            method, _, _, spots, advice = demand_context()
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except LookupError as e:
            return jsonify({"error": str(e)}), 404
        return jsonify({"method": method, "hotspots": spots, **advice})

    @app.route("/hotspot-map")
    def hotspot_map():
        try:
            _, calls, _, spots, advice = demand_context()
        except ValueError as e:
            return str(e), 400
        except LookupError as e:
            return str(e), 404
        db = get_db()
        amb = [dict(r) for r in db.execute("SELECT * FROM ambulances")]
        hosp = [dict(r) for r in db.execute("SELECT * FROM hospitals")]
        summary = ""
        if "improvement_pct" in advice:
            summary = ("Average distance to nearest ambulance:<br>%.2f km now, %.2f km if repositioned (%.1f%% better)"
                       % (advice["avg_distance_km_before"], advice["avg_distance_km_after"],
                          advice["improvement_pct"]))
        return build_map_html(calls, spots, advice["standby_points"], amb, hosp, summary)

    return app
