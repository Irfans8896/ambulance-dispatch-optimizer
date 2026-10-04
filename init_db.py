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
        ("City General", 14.6750, 77.5950, 12, "trauma,cardiac"),
        ("District Hospital", 14.7000, 77.6200, 5, "general,pediatric"),
    ],
)
conn.commit()

tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
).fetchall()
print("Database created at:", DB_PATH)
print("Tables:", [t[0] for t in tables])
conn.close()