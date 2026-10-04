"""Week 7 completion: registration, notifications, traffic history, hotspot storage, feedback loop."""
import re
import sqlite3

from app.models import Hospital, Location
from .dispatch import load_junctions

SERVICE_RADIUS_KM = 10.0     # new units must be near the road network


class Conflict(ValueError):
    """The record already exists."""


def _number(data, key, lo, hi):
    try:
        value = float(data[key])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"{key} is required and must be a number")
    if not lo <= value <= hi:
        raise ValueError(f"{key} must be between {lo} and {hi}")
    return value


def _inside_service_area(conn, lat, lon):
    here = Location(lat, lon)
    nearest = min(here.distance_km(j) for j in load_junctions(conn).values())
    if nearest > SERVICE_RADIUS_KM:
        raise ValueError("Location is outside the service area (more than %d km from any junction)"
                         % SERVICE_RADIUS_KM)


def register_ambulance(conn, data):
    number = str(data.get("vehicle_number", "")).strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9 -]{2,19}", number):
        raise ValueError("vehicle_number must be 3-20 letters, digits, spaces or dashes")
    lat, lon = _number(data, "latitude", -90, 90), _number(data, "longitude", -180, 180)
    _inside_service_area(conn, lat, lon)
    try:
        cur = conn.execute("INSERT INTO ambulances (vehicle_number, latitude, longitude) VALUES (?,?,?)",
                           (number, lat, lon))
    except sqlite3.IntegrityError:
        raise Conflict("That vehicle number is already registered")
    conn.commit()
    return {"ambulance_id": cur.lastrowid, "vehicle_number": number, "status": "AVAILABLE"}


def register_hospital(conn, data):
    name = " ".join(str(data.get("name", "")).split())
    if not 2 <= len(name) <= 80:
        raise ValueError("name must be 2-80 characters")
    lat, lon = _number(data, "latitude", -90, 90), _number(data, "longitude", -180, 180)
    beds = int(_number(data, "available_beds", 0, 5000))
    specialties = data.get("specialties", "")
    if isinstance(specialties, (list, tuple)):
        specialties = ",".join(str(s) for s in specialties)
    specialties = ",".join(s.strip().lower() for s in str(specialties).split(",") if s.strip())
    _inside_service_area(conn, lat, lon)
    if conn.execute("SELECT 1 FROM hospitals WHERE lower(name)=lower(?)", (name,)).fetchone():
        raise Conflict("A hospital with that name already exists")
    cur = conn.execute("INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) "
                       "VALUES (?,?,?,?,?)", (name, lat, lon, beds, specialties))
    conn.commit()
    return {"hospital_id": cur.lastrowid, "name": name, "available_beds": beds, "specialties": specialties}


def update_hospital(conn, hospital_id, data):
    status, beds = data.get("status"), data.get("available_beds")
    if status is None and beds is None:
        raise ValueError("Give status and/or available_beds")
    if status is not None and status not in Hospital.STATUSES:
        raise ValueError("status must be one of " + ", ".join(Hospital.STATUSES))
    if beds is not None:
        beds = int(_number(data, "available_beds", 0, 5000))
    row = conn.execute("SELECT * FROM hospitals WHERE hospital_id=?", (hospital_id,)).fetchone()
    if row is None:
        raise LookupError("No such hospital")
    conn.execute("UPDATE hospitals SET status=?, available_beds=? WHERE hospital_id=?",
                 (status or row["status"], row["available_beds"] if beds is None else beds, hospital_id))
    conn.commit()
    return row["name"], status or row["status"], row["available_beds"] if beds is None else beds


# ------------------------------------------------------------------ notifications
def notify(conn, message, audience="all"):
    conn.execute("INSERT INTO notifications (audience, message) VALUES (?,?)", (audience, message))
    conn.commit()


def notifications_for(conn, role, ambulance_id, limit=15):
    if role == "driver":
        rows = conn.execute(
            "SELECT * FROM notifications WHERE audience IN ('all', ?) ORDER BY notification_id DESC LIMIT ?",
            ("ambulance:%s" % ambulance_id, limit))
    else:
        rows = conn.execute("SELECT * FROM notifications ORDER BY notification_id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ stored history
def log_road_change(conn, source, destination):
    """Traffic snapshot: the state of a road right after an admin changed it."""
    conn.execute(
        "INSERT INTO traffic_snapshots (source, destination, traffic_level, road_condition) "
        "SELECT source, destination, traffic_level, road_condition FROM road_edges "
        "WHERE (source=? AND destination=?) OR (source=? AND destination=?) LIMIT 1",
        (source, destination, destination, source))
    conn.commit()


def save_hotspots(conn, method, spots):
    conn.execute("DELETE FROM predicted_hotspots WHERE method=?", (method,))
    conn.executemany(
        "INSERT INTO predicted_hotspots (method, hotspot_id, latitude, longitude, calls, top_type, peak_hour) "
        "VALUES (?,?,?,?,?,?,?)",
        [(method, h["hotspot_id"], h["latitude"], h["longitude"], h["calls"], h["top_type"], h["peak_hour"])
         for h in spots])
    conn.commit()


def record_completed_call(conn, dispatch_id):
    """Feedback loop: a completed dispatch becomes a historical call, so future hotspots learn from it."""
    row = conn.execute(
        "SELECT i.latitude, i.longitude, i.emergency_type, i.call_time FROM dispatches d "
        "JOIN incidents i ON i.incident_id = d.incident_id WHERE d.dispatch_id=?", (dispatch_id,)).fetchone()
    if row is None:
        return
    when = row["call_time"] or ""
    conn.execute("INSERT INTO historical_calls (latitude, longitude, date, time, emergency_type) VALUES (?,?,?,?,?)",
                 (row["latitude"], row["longitude"], when[:10], when[11:16], (row["emergency_type"] or "general").lower()))
    conn.commit()
