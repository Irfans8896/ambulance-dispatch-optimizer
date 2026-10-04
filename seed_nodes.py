import os, sqlite3
BASE = os.path.dirname(os.path.abspath(__file__))
c = sqlite3.connect(os.path.join(BASE, "dispatch.db"))

c.execute("""CREATE TABLE IF NOT EXISTS nodes (
  node_id INTEGER PRIMARY KEY, name TEXT,
  latitude REAL NOT NULL, longitude REAL NOT NULL)""")
c.execute("DELETE FROM nodes")
# PLACEHOLDER positions (edit if you have real ones)
c.executemany("INSERT INTO nodes VALUES (?,?,?,?)", [
    (1, "Node 1", 14.6819, 77.5900),
    (2, "Node 2", 14.6900, 77.5980),
    (3, "Node 3", 14.6760, 77.6030),
    (4, "Node 4", 14.6860, 77.6150),
    (5, "Node 5", 14.6700, 77.6200),
    (6, "Node 6", 14.6780, 77.6300),
])

if c.execute("SELECT COUNT(*) FROM ambulances").fetchone()[0] == 0:
    c.executemany(
        "INSERT INTO ambulances (vehicle_number, latitude, longitude, status) VALUES (?,?,?,'AVAILABLE')",
        [("AP-01", 14.6822, 77.5905), ("AP-02", 14.6702, 77.6195), ("AP-03", 14.6782, 77.6298)])
if c.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0] == 0:
    c.executemany(
        "INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) VALUES (?,?,?,?,?)",
        [("City Hospital", 14.6862, 77.6148, 5, "General"),
         ("District Hospital", 14.6782, 77.6298, 3, "Trauma")])
c.commit()
print("nodes:", c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
      "| ambulances:", c.execute("SELECT COUNT(*) FROM ambulances").fetchone()[0],
      "| hospitals:", c.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0])
c.close()