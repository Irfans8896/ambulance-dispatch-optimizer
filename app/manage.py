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
                      h.name AS hospital, h.latitude AS hospital_lat, h.longitude AS hospital_lon
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
