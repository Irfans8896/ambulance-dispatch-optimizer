"""Week 6: dashboard page and the data endpoints behind it."""
import csv
import io
import json

from flask import Blueprint, Response, jsonify, render_template

from .auth import current_user
from .db import get_db
from .services.dispatch import queued_incidents
from .services.traffic import effective_rows, auto_traffic_on, is_rush_hour

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    user = current_user()
    if user and user["role"] == "driver":
        return render_template("driver.html", user=user)
    return render_template("dashboard.html")


@bp.route("/driver")
def driver_view():
    user = current_user()
    from flask import session, request
    amb_id = request.args.get("ambulance_id", type=int)
    db = get_db()
    if not user or (amb_id and user.get("role") == "driver" and user.get("ambulance_id") != amb_id):
        target_amb = amb_id or 1
        row = db.execute("SELECT * FROM users WHERE role='driver' AND ambulance_id=?", (target_amb,)).fetchone()
        if row:
            session["user"] = {"username": row["username"], "role": row["role"], "ambulance_id": row["ambulance_id"]}
            user = session["user"]
        else:
            user = {"username": f"driver{target_amb}", "role": "driver", "ambulance_id": target_amb}
    return render_template("driver.html", user=user)


@bp.route("/api/state")
def state():
    """Everything the live dashboard needs, in one request."""
    db = get_db()
    rows = lambda sql: [dict(r) for r in db.execute(sql)]
    dispatches = rows(
        """SELECT d.dispatch_id, a.vehicle_number, h.name AS hospital,
                  i.emergency_type, i.severity, i.status AS incident_status,
                  i.latitude AS incident_lat, i.longitude AS incident_lon,
                  a.status AS ambulance_status, d.response_time AS eta_min, d.route,
                  d.progress, d.reroutes
           FROM dispatches d
           JOIN ambulances a ON a.ambulance_id = d.ambulance_id
           JOIN hospitals h ON h.hospital_id = d.hospital_id
           JOIN incidents i ON i.incident_id = d.incident_id
           ORDER BY d.dispatch_id DESC""")
    for d in dispatches:
        d["route"] = json.loads(d["route"]) if d["route"] else {}
    roads = effective_rows(db)
    for r in roads:                                   # traffic_level = what the admin set, effective_traffic = in use now
        r["effective_traffic"], r["traffic_level"] = r["traffic_level"], r.pop("base_traffic_level")
    return jsonify({
        "ambulances": rows("SELECT * FROM ambulances"),
        "hospitals": rows("SELECT * FROM hospitals"),
        "roads": roads,
        "queue": [dict(q) for q in queued_incidents(db)],
        "settings": {"auto_traffic": auto_traffic_on(db), "rush_hour_now": is_rush_hour()},
        "junctions": {r["junction_id"]: [r["latitude"], r["longitude"]]
                      for r in rows("SELECT * FROM junctions")},
        "dispatches": dispatches,
    })


@bp.route("/api/summary")
def summary():
    db = get_db()
    one = lambda sql: db.execute(sql).fetchone()[0]
    avg_eta = one("SELECT AVG(response_time) FROM dispatches")
    return jsonify({
        "ambulances_available": one("SELECT COUNT(*) FROM ambulances WHERE status='AVAILABLE'"),
        "ambulances_total": one("SELECT COUNT(*) FROM ambulances"),
        "total_dispatches": one("SELECT COUNT(*) FROM dispatches"),
        "queued": len(queued_incidents(db)),
        "completed": one("SELECT COUNT(*) FROM incidents WHERE status='COMPLETED'"),
        "active": one("SELECT COUNT(*) FROM incidents WHERE status NOT IN ('REPORTED','COMPLETED')"),
        "avg_eta_min": round(avg_eta, 1) if avg_eta is not None else None,
        "beds_free": one("SELECT COALESCE(SUM(available_beds), 0) FROM hospitals"),
    })


@bp.route("/api/reports/dispatches.csv")
def dispatch_report():
    """Downloadable report of every dispatch."""
    rows = get_db().execute(
        """SELECT d.dispatch_id, i.call_time, i.emergency_type, i.severity,
                  a.vehicle_number, h.name AS hospital, d.response_time AS eta_minutes,
                  i.status AS incident_status
           FROM dispatches d
           JOIN ambulances a ON a.ambulance_id = d.ambulance_id
           JOIN hospitals h ON h.hospital_id = d.hospital_id
           JOIN incidents i ON i.incident_id = d.incident_id
           ORDER BY d.dispatch_id""").fetchall()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["dispatch_id", "call_time", "emergency_type", "severity", "ambulance",
                     "hospital", "eta_minutes", "status"])
    writer.writerows([tuple(r) for r in rows])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=dispatch_report.csv"})
