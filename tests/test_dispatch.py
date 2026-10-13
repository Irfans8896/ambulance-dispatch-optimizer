import os
import sqlite3

import pytest

import seed_roads
from app.models import Ambulance
from app.services import (dispatch_incident, advance_dispatch, update_road_conditions,
                          NoAmbulanceAvailable)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INCIDENT = (15.4881, 78.4931)     # next to junction 5


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(open(os.path.join(BASE, "schema.sql")).read())
    conn.executemany(
        "INSERT INTO ambulances (vehicle_number, latitude, longitude) VALUES (?,?,?)",
        [("AP21-1001", 15.4755, 78.4792), ("AP21-1002", 15.4836, 78.4886)])
    conn.executemany(
        "INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) "
        "VALUES (?,?,?,?,?)",
        [("City General", 15.4686, 78.4736, 12, "trauma,cardiac"),
         ("District Hospital", 15.4936, 78.4986, 5, "general,pediatric")])
    seed_roads.seed(conn)
    return conn


def test_nearest_ambulance_is_chosen():
    r = dispatch_incident(make_db(), *INCIDENT, "accident", 4)
    assert r["ambulance"] == "AP21-1002"
    assert r["route_to_scene"] == [4, 5]


def test_closed_road_changes_the_ambulance():
    conn = make_db()
    update_road_conditions(conn, 4, 5, road_condition="CLOSED")
    update_road_conditions(conn, 5, 6, road_condition="CLOSED")
    r = dispatch_incident(conn, *INCIDENT, "accident", 4)
    assert r["ambulance"] == "AP21-1001"


def test_heavy_traffic_slows_the_eta():
    normal = dispatch_incident(make_db(), *INCIDENT, "accident", 4)
    conn = make_db()
    update_road_conditions(conn, 4, 5, traffic_level="HEAVY")
    slow = dispatch_incident(conn, *INCIDENT, "accident", 4)
    assert slow["eta_to_scene_min"] > normal["eta_to_scene_min"]


def test_hospital_matches_specialty():
    assert dispatch_incident(make_db(), *INCIDENT, "accident", 4)["hospital"] == "City General"
    assert dispatch_incident(make_db(), *INCIDENT, "child", 3)["hospital"] == "District Hospital"


def test_full_hospital_is_skipped():
    conn = make_db()
    conn.execute("UPDATE hospitals SET available_beds=0 WHERE name='City General'")
    r = dispatch_incident(conn, *INCIDENT, "accident", 4)
    assert r["hospital"] == "District Hospital"
    assert r["specialty_match"] is False


def test_no_available_ambulance():
    conn = make_db()
    conn.execute("UPDATE ambulances SET status='DISPATCHED'")
    with pytest.raises(NoAmbulanceAvailable):
        dispatch_incident(conn, *INCIDENT, "accident", 4)
    # the call is still recorded
    assert conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 1


def test_dispatch_is_stored():
    conn = make_db()
    r = dispatch_incident(conn, *INCIDENT, "accident", 4)
    row = conn.execute("SELECT * FROM dispatches WHERE dispatch_id=?", (r["dispatch_id"],)).fetchone()
    assert row["response_time"] > 0
    amb = conn.execute("SELECT status FROM ambulances WHERE vehicle_number='AP21-1002'").fetchone()
    assert amb["status"] == Ambulance.DISPATCHED


def test_full_lifecycle():
    conn = make_db()
    r = dispatch_incident(conn, *INCIDENT, "accident", 4)
    for _ in range(3):
        advance_dispatch(conn, r["dispatch_id"])
    amb = conn.execute("SELECT * FROM ambulances WHERE vehicle_number='AP21-1002'").fetchone()
    inc = conn.execute("SELECT status FROM incidents").fetchone()
    hosp = conn.execute("SELECT * FROM hospitals WHERE name='City General'").fetchone()
    assert amb["status"] == "AVAILABLE"
    assert (amb["latitude"], amb["longitude"]) == (hosp["latitude"], hosp["longitude"])
    assert inc["status"] == "COMPLETED"
    assert hosp["available_beds"] == 11
    with pytest.raises(ValueError):
        advance_dispatch(conn, r["dispatch_id"])      # already completed


def test_invalid_input_is_rejected():
    conn = make_db()
    with pytest.raises(ValueError):
        update_road_conditions(conn, 4, 5, traffic_level="JAMMED")
    with pytest.raises(ValueError):
        dispatch_incident(conn, *INCIDENT, "accident", 9)      # severity out of range
    assert conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0


def test_severity_and_shortest_location_hospital_selection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(open(os.path.join(BASE, "schema.sql")).read())
    conn.executemany(
        "INSERT INTO ambulances (vehicle_number, latitude, longitude) VALUES (?,?,?)",
        [("AP21-1001", 15.4755, 78.4792), ("AP21-1002", 15.4836, 78.4886)])
    conn.executemany(
        "INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) VALUES (?,?,?,?,?)",
        [
            ("City General", 15.4686, 78.4736, 12, "trauma,cardiac"),
            ("Apollo Emergency", 15.4836, 78.4886, 10, "trauma,cardiac"),
            ("District Hospital", 15.4936, 78.4986, 5, "general,pediatric"),
            ("Community Health Center", 15.4636, 78.4686, 6, "general,minor"),
        ]
    )
    seed_roads.seed(conn)

    # Severe accident (Severity 5) near Junction 5:
    # Both City General (Junction 2) and Apollo Emergency (Junction 4) have trauma capabilities.
    # Apollo Emergency (J4) is closer to J5 (2.0km) than City General (J2, 6.0km), so it is selected.
    r_severe = dispatch_incident(conn, *INCIDENT, "accident", 5)
    assert r_severe["hospital"] == "Apollo Emergency"

    # Pediatric incident: District Hospital at Junction 6 (1.0km from J5) is selected.
    r_child = dispatch_incident(conn, *INCIDENT, "child", 3)
    assert r_child["hospital"] == "District Hospital"
