import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "dispatch.db")
SCHEMA_PATH = os.path.join(BASE, "schema.sql")

print("Project folder:", BASE)

if not os.path.exists(SCHEMA_PATH):
    raise SystemExit("ERROR: schema.sql not found in " + BASE)

conn = sqlite3.connect(DB_PATH)

with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    schema = f.read()

if not schema.strip():
    raise SystemExit("ERROR: schema.sql is empty. Paste the CREATE TABLE code and save it.")

# Start fresh so re-running never fails with "table already exists"
conn.executescript("""
DROP TABLE IF EXISTS dispatches;
DROP TABLE IF EXISTS historical_calls;
DROP TABLE IF EXISTS road_edges;
DROP TABLE IF EXISTS incidents;
DROP TABLE IF EXISTS hospitals;
DROP TABLE IF EXISTS ambulances;
""")
conn.executescript(schema)

conn.executemany(
    "INSERT INTO ambulances (vehicle_number, latitude, longitude) VALUES (?,?,?)",
    [("AP02-1001", 14.6819, 77.6006), ("AP02-1002", 14.6900, 77.6100)],
)
conn.executemany(
    "INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) VALUES (?,?,?,?,?)",
    [
        ("City General", 15.4686, 78.4736, 16, "trauma,cardiac,icu"),
        ("District Hospital", 15.4936, 78.4986, 12, "general,pediatric,trauma"),
        ("Apollo Emergency Care", 15.4836, 78.4886, 14, "cardiac,trauma,icu"),
        ("Community Health Center", 15.4636, 78.4686, 6, "general,minor"),
        ("Children & Maternity Clinic", 15.4755, 78.4792, 8, "pediatric,general"),
        ("LifeLine Critical Care", 15.4886, 78.4936, 10, "cardiac,icu,trauma"),
        ("Sanjeevani Trauma Care", 15.4710, 78.4760, 9, "trauma,general"),
        ("Mother & Child Center", 15.4900, 78.4960, 7, "pediatric,minor"),
    ],
)
conn.commit()

tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
).fetchall()
print("Database created at:", DB_PATH)
print("Tables:", [t[0] for t in tables])
conn.close()