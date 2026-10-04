"""Week 4 demo: runs on a temporary in-memory database (your dispatch.db is untouched)."""
import os
import sqlite3

import seed_roads
from app.services import dispatch_incident, advance_dispatch, update_road_conditions

BASE = os.path.dirname(os.path.abspath(__file__))


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


def show(result):
    print("  Ambulance :", result["ambulance"], "| ETA to scene:", result["eta_to_scene_min"], "min")
    print("  Route     :", " -> ".join(map(str, result["route_to_scene"])))
    print("  Hospital  :", result["hospital"], "| ETA to hospital:", result["eta_to_hospital_min"], "min")
    print("  Route     :", " -> ".join(map(str, result["route_to_hospital"])))
    print("  Options   :", result["ambulance_options"])


INCIDENT = (15.4881, 78.4931)     # next to junction 5

conn = make_db()
print("=== Scenario 1: accident, normal traffic ===")
r1 = dispatch_incident(conn, *INCIDENT, "accident", 4)
show(r1)

print("\n=== Scenario 2: same accident, but roads 4-5 and 5-6 are closed ===")
conn = make_db()
update_road_conditions(conn, 4, 5, road_condition="CLOSED")
update_road_conditions(conn, 5, 6, road_condition="CLOSED")
r2 = dispatch_incident(conn, *INCIDENT, "accident", 4)
show(r2)

print("\n=== Scenario 3: child emergency (needs pediatric specialty) ===")
conn = make_db()
r3 = dispatch_incident(conn, *INCIDENT, "child", 3)
show(r3)
print("  Specialty match:", r3["specialty_match"])

print("\n=== Scenario 4: full status lifecycle of dispatch", r1["dispatch_id"], "===")
conn = make_db()
d = dispatch_incident(conn, *INCIDENT, "accident", 4)
for _ in range(3):
    print(" ", advance_dispatch(conn, d["dispatch_id"]))
beds = conn.execute("SELECT available_beds FROM hospitals WHERE name='City General'").fetchone()[0]
print("  City General beds after admission:", beds)

print("\n=== Scenario 5: no ambulance available ===")
conn = make_db()
conn.execute("UPDATE ambulances SET status='DISPATCHED'")
try:
    dispatch_incident(conn, *INCIDENT, "accident", 4)
except Exception as e:
    print(" ", type(e).__name__ + ":", e)
