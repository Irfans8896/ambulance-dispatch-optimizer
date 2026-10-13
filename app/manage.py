"""Week 7: registration, hospital status, notifications, traffic history and the driver endpoint."""
from flask import Blueprint, jsonify, request

from .auth import current_user
from .db import get_db
from .services.analytics import build as build_analytics, simulate
from .services.automation import after_change
from .services.dispatch import queued_incidents
from .services.traffic import set_setting, auto_traffic_on, is_rush_hour
from .services.ops import (Conflict, register_ambulance, register_hospital, update_hospital,
                           notifications_for)

bp = Blueprint("manage", __name__)

NEXT_STEP = {"DISPATCHED": "I have arrived at the scene",
             "AT_SCENE": "Patient loaded, leaving for hospital",
             "TO_HOSPITAL": "Patient handed over at hospital"}


@bp.route("/health")
def health():
    return jsonify({"status": "ok"})


def _json_or_400():
    return request.get_json(silent=True) or {}


@bp.route("/api/ambulances", methods=["POST"])
def add_ambulance():
    from .services.ops import notify
    db = get_db()
    try:
        out = register_ambulance(db, _json_or_400())
    except Conflict as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    notify(db, "New ambulance %s registered" % out["vehicle_number"])
    return jsonify({**out, **after_change(db, reroute=False)}), 201     # it may be able to serve the queue


@bp.route("/api/hospitals", methods=["POST"])
def add_hospital():
    from .services.ops import notify
    db = get_db()
    try:
        out = register_hospital(db, _json_or_400())
    except Conflict as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    notify(db, "New hospital registered: %s" % out["name"])
    return jsonify(out), 201


@bp.route("/api/hospitals/<int:hospital_id>", methods=["POST"])
def change_hospital(hospital_id):
    from .services.ops import notify
    db = get_db()
    try:
        name, status, beds = update_hospital(db, hospital_id, _json_or_400())
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    notify(db, "%s is now %s (%d beds)" % (name, "ACCEPTING PATIENTS" if status == "ACTIVE" else "ON DIVERSION", beds))
    return jsonify({"message": "Hospital updated", "status": status, "available_beds": beds, **after_change(db)})


@bp.route("/api/hospitals/<int:hospital_id>/add-beds", methods=["POST"])
def add_beds(hospital_id):
    from .services.ops import notify
    db = get_db()
    delta = int((_json_or_400()).get("delta", 5))
    row = db.execute("SELECT * FROM hospitals WHERE hospital_id=?", (hospital_id,)).fetchone()
    if not row:
        return jsonify({"error": "Hospital not found"}), 404
    new_beds = max(0, row["available_beds"] + delta)
    db.execute("UPDATE hospitals SET available_beds=? WHERE hospital_id=?", (new_beds, hospital_id))
    db.commit()
    notify(db, f"Hospital Capacity Scaled: {row['name']} received +{delta} beds (now {new_beds} available)")
    return jsonify({"hospital_id": hospital_id, "name": row["name"], "available_beds": new_beds, **after_change(db)})


@bp.route("/api/hospitals/surge", methods=["POST"])
def hospital_surge():
    from .services.ops import notify
    db = get_db()
    delta = int((_json_or_400()).get("delta", 10))
    db.execute("UPDATE hospitals SET available_beds = available_beds + ? WHERE status='ACTIVE'", (delta,))
    db.commit()
    notify(db, f"Emergency Surge Capacity Activated: +{delta} ICU beds allocated across all active facilities")
    return jsonify({"message": f"Added {delta} beds to all active hospitals", **after_change(db)})


@bp.route("/api/ambulances/surge", methods=["POST"])
def ambulance_surge():
    from .services.ops import notify
    db = get_db()
    count = int((_json_or_400()).get("count", 2))
    
    # Get highest vehicle number or junctions to station them
    junction_rows = db.execute("SELECT junction_id, latitude, longitude FROM junctions ORDER BY junction_id").fetchall()
    if not junction_rows:
        return jsonify({"error": "No junctions found"}), 400
        
    existing = [r[0] for r in db.execute("SELECT vehicle_number FROM ambulances").fetchall()]
    added = []
    
    for i in range(1, count + 1):
        # Pick sequential vehicle numbers
        num = 1001
        while f"AP21-{num}" in existing or f"AP21-R{i}" in existing:
            num += 1
        v_num = f"AP21-{num}"
        existing.append(v_num)
        
        # Station at distributed junctions
        target_j = junction_rows[(len(existing) - 1) % len(junction_rows)]
        db.execute("INSERT INTO ambulances (vehicle_number, latitude, longitude, status) VALUES (?,?,?, 'AVAILABLE')",
                   (v_num, target_j["latitude"], target_j["longitude"]))
        added.append(v_num)
        
    db.commit()
    notify(db, f"Fleet Capacity Scaled: {len(added)} Reserve Ambulances deployed ({', '.join(added)})")
    return jsonify({"message": f"Deployed {len(added)} ambulances", "ambulances": added, **after_change(db, reroute=False)})


@bp.route("/api/notifications")
def notifications():
    user = current_user() or {}
    return jsonify(notifications_for(get_db(), user.get("role"), user.get("ambulance_id")))


@bp.route("/api/traffic-history")
def traffic_history():
    rows = get_db().execute("SELECT * FROM traffic_snapshots ORDER BY snapshot_id DESC LIMIT 50").fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/driver/status")
def driver_status():
    user = current_user()
    if not user or user["role"] != "driver" or not user.get("ambulance_id"):
        return jsonify({"error": "Drivers only"}), 400
    db = get_db()
    amb = db.execute("SELECT * FROM ambulances WHERE ambulance_id=?", (user["ambulance_id"],)).fetchone()
    trip = None
    if amb["status"] != "AVAILABLE":
        d = db.execute(
            """SELECT d.dispatch_id, d.response_time AS eta_min, i.emergency_type, i.severity,
                      i.status AS incident_status, i.latitude AS scene_lat, i.longitude AS scene_lon,
                      h.hospital_id, h.name AS hospital, h.latitude AS hospital_lat, h.longitude AS hospital_lon,
                      h.available_beds, h.specialties
               FROM dispatches d JOIN incidents i ON i.incident_id=d.incident_id
               JOIN hospitals h ON h.hospital_id=d.hospital_id
               WHERE d.ambulance_id=? ORDER BY d.dispatch_id DESC LIMIT 1""", (amb["ambulance_id"],)).fetchone()
        if d:
            trip = dict(d)
            to_scene = amb["status"] == "DISPATCHED"
            trip["go_to"] = "scene" if to_scene else "hospital"
            trip["go_to_lat"] = trip["scene_lat"] if to_scene else trip["hospital_lat"]
            trip["go_to_lon"] = trip["scene_lon"] if to_scene else trip["hospital_lon"]
    return jsonify({"username": user["username"], "ambulance": dict(amb), "trip": trip,
                    "next_step": NEXT_STEP.get(amb["status"])})


@bp.route("/api/dispatches/<int:dispatch_id>/severity", methods=["POST"])
def set_severity(dispatch_id):
    """Driver or dispatcher updates the emergency triage severity level (1-5)."""
    from .services.dispatch import update_dispatch_severity
    from .services.ops import notify
    data = _json_or_400()
    try:
        severity = data.get("severity")
        if severity is None:
            return jsonify({"error": "severity is required"}), 400
        db = get_db()
        out = update_dispatch_severity(db, dispatch_id, severity)
        notify(db, "%s: Triage severity updated to Level %d" % (out["vehicle_number"], out["new_severity"]),
               "ambulance:%s" % out["ambulance_id"])
        notify(db, "Ambulance %s: Patient triage severity updated to Level %d" % (
            out["vehicle_number"], out["new_severity"]))
        return jsonify({"ok": True, **out})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/dispatches/<int:dispatch_id>/hospital-options")
def hospital_options(dispatch_id):
    """Get candidate hospitals for this trip with travel ETA and capability tier matching."""
    from .services.dispatch import get_hospital_options_for_dispatch
    try:
        db = get_db()
        options = get_hospital_options_for_dispatch(db, dispatch_id)
        return jsonify(options)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/api/dispatches/<int:dispatch_id>/hospital", methods=["POST"])
def select_or_change_hospital(dispatch_id):
    """Driver or dispatcher selects or changes the destination hospital."""
    from .services.dispatch import update_dispatch_hospital
    from .services.ops import notify
    data = _json_or_400()
    try:
        hospital_id = data.get("hospital_id")
        if hospital_id is None:
            return jsonify({"error": "hospital_id is required"}), 400
        db = get_db()
        out = update_dispatch_hospital(db, dispatch_id, int(hospital_id))
        notify(db, "%s: Destination hospital changed to %s (ETA %s min)" % (
            out["vehicle_number"], out["new_hospital"], out["eta_hospital_min"]),
            "ambulance:%s" % out["ambulance_id"])
        notify(db, "Ambulance %s rerouted destination from %s to %s (ETA %s min)" % (
            out["vehicle_number"], out["old_hospital"], out["new_hospital"], out["eta_hospital_min"]))
        return jsonify({"ok": True, **out})
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400


# ------------------------------------------------------------------ re-routing, queue, settings, analytics
@bp.route("/api/dispatches/<int:dispatch_id>/progress", methods=["POST"])
def report_progress(dispatch_id):
    """The map (or a driver app) reports how far along the current leg the ambulance is, 0 to 1."""
    try:
        fraction = float((_json_or_400()).get("fraction"))
    except (TypeError, ValueError):
        return jsonify({"error": "fraction must be a number between 0 and 1"}), 400
    if not 0 <= fraction <= 1:
        return jsonify({"error": "fraction must be between 0 and 1"}), 400
    db = get_db()
    row = db.execute("SELECT a.status FROM dispatches d JOIN ambulances a ON a.ambulance_id=d.ambulance_id "
                     "WHERE d.dispatch_id=?", (dispatch_id,)).fetchone()
    if row is None:
        return jsonify({"error": "No such dispatch"}), 404
    if row["status"] == "AVAILABLE":
        return jsonify({"error": "This dispatch is already completed"}), 400
    db.execute("UPDATE dispatches SET progress=? WHERE dispatch_id=?", (fraction, dispatch_id))
    db.commit()
    return jsonify({"ok": True})


@bp.route("/api/dispatches/recheck", methods=["POST"])
def recheck():
    """Re-check every trip in progress and the waiting queue now (e.g. after the clock moved into rush hour)."""
    return jsonify(after_change(get_db()))


@bp.route("/api/queue")
def queue():
    return jsonify([dict(r) for r in queued_incidents(get_db())])


@bp.route("/api/settings/auto-traffic", methods=["POST"])
def auto_traffic():
    enabled = _json_or_400().get("enabled")
    if not isinstance(enabled, bool):
        return jsonify({"error": "enabled must be true or false"}), 400
    from .services.ops import notify
    db = get_db()
    set_setting(db, "auto_traffic", "1" if enabled else "0")
    notify(db, "Automatic rush-hour traffic is now %s" % ("ON" if enabled else "OFF"))
    return jsonify({"auto_traffic": enabled, "rush_hour_now": is_rush_hour(), **after_change(db)})


@bp.route("/api/analytics")
def analytics():
    return jsonify(build_analytics(get_db()))


@bp.route("/analytics")
def analytics_page():
    from flask import render_template
    return render_template("analytics.html")


@bp.route("/api/demo/simulate", methods=["POST"])
def demo_simulate():
    """Create and complete a few random emergencies so the analytics page has data (demo only)."""
    try:
        count = int(_json_or_400().get("count", 10))
    except (TypeError, ValueError):
        return jsonify({"error": "count must be a whole number"}), 400
    if not 1 <= count <= 30:
        return jsonify({"error": "count must be between 1 and 30"}), 400
    return jsonify(simulate(get_db(), count))
