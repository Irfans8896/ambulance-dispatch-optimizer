import os
import sqlite3
import tempfile

import seed_roads
import load_calls
from app import create_app
from app.services.sample_data import make_sample_calls

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_client():
    path = os.path.join(tempfile.mkdtemp(), "test.db")
    conn = sqlite3.connect(path)
    conn.executescript(open(os.path.join(BASE, "schema.sql")).read())
    conn.executemany("INSERT INTO ambulances (vehicle_number, latitude, longitude) VALUES (?,?,?)",
                     [("AP21-1001", 15.4755, 78.4792), ("AP21-1002", 15.4836, 78.4886)])
    conn.executemany(
        "INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) VALUES (?,?,?,?,?)",
        [("City General", 15.4686, 78.4736, 12, "trauma,cardiac")])
    seed_roads.seed(conn)
    load_calls.load(conn, make_sample_calls())
    conn.close()
    app = create_app()
    app.config["DATABASE"] = path
    return app.test_client()


def test_dashboard_page_loads():
    page = make_client().get("/")
    assert page.status_code == 200
    assert b"Ambulance Dispatch" in page.data and b"leaflet" in page.data.lower()
    assert b"router.project-osrm.org" in page.data and b"function animate" in page.data


def test_state_has_everything_the_dashboard_needs():
    s = make_client().get("/api/state").get_json()
    assert len(s["ambulances"]) == 2 and len(s["roads"]) == 9 and len(s["junctions"]) == 6
    assert s["dispatches"] == []


def test_summary_and_dispatch_flow():
    c = make_client()
    assert c.get("/api/summary").get_json()["avg_eta_min"] is None
    r = c.post("/api/incidents/dispatch", json={"latitude": 15.4881, "longitude": 78.4931,
                                                "emergency_type": "accident", "severity": 4})
    assert r.status_code == 201
    summary = c.get("/api/summary").get_json()
    assert summary["total_dispatches"] == 1 and summary["active"] == 1
    assert summary["ambulances_available"] == 1 and summary["avg_eta_min"] > 0
    d = c.get("/api/state").get_json()["dispatches"][0]
    assert d["route"]["to_scene"] and d["incident_lat"] == 15.4881
    for _ in range(3):
        c.post("/api/dispatches/%d/advance" % d["dispatch_id"])
    summary = c.get("/api/summary").get_json()
    assert summary["completed"] == 1 and summary["ambulances_available"] == 2


def test_csv_report():
    c = make_client()
    c.post("/api/incidents/dispatch", json={"latitude": 15.4881, "longitude": 78.4931,
                                            "emergency_type": "cardiac", "severity": 3})
    r = c.get("/api/reports/dispatches.csv")
    lines = r.data.decode().strip().splitlines()
    assert r.mimetype == "text/csv" and lines[0].startswith("dispatch_id,call_time")
    assert len(lines) == 2 and "cardiac" in lines[1]
