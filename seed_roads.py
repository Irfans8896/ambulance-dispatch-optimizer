"""Loads a small hand-made city map (junctions + roads) into dispatch.db.

Week 3: roads.  Week 4: junction coordinates, so that ambulances, hospitals
and incidents can be matched to the nearest junction.
Run:  python seed_roads.py
"""
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

# (junction_id, latitude, longitude)
JUNCTIONS = [
    (1, 15.4636, 78.4686),
    (2, 15.4686, 78.4736),   # next to City General hospital
    (3, 15.4755, 78.4792),   # next to ambulance AP21-1001
    (4, 15.4836, 78.4886),   # next to ambulance AP21-1002
    (5, 15.4886, 78.4936),
    (6, 15.4936, 78.4986),   # next to District Hospital
]

# (source, destination, distance_km, traffic_level, road_condition)
ROADS = [
    (1, 2, 2.0, "LOW", "GOOD"),
    (1, 3, 4.0, "LOW", "GOOD"),
    (2, 3, 1.0, "LOW", "GOOD"),
    (2, 4, 5.0, "LOW", "GOOD"),
    (3, 4, 3.0, "LOW", "GOOD"),
    (3, 5, 6.0, "LOW", "GOOD"),
    (4, 5, 2.0, "LOW", "GOOD"),
    (4, 6, 4.0, "LOW", "GOOD"),
    (5, 6, 1.0, "LOW", "GOOD"),
]


def seed(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS junctions (
        junction_id INTEGER PRIMARY KEY,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL)""")
    conn.execute("DELETE FROM junctions")
    conn.execute("DELETE FROM road_edges")
    conn.executemany("INSERT INTO junctions VALUES (?,?,?)", JUNCTIONS)
    conn.executemany(
        "INSERT INTO road_edges (source, destination, distance, traffic_level, road_condition) "
        "VALUES (?,?,?,?,?)", ROADS)
    conn.commit()


if __name__ == "__main__":
    conn = sqlite3.connect(os.path.join(BASE, "dispatch.db"))
    seed(conn)
    print("Inserted", len(JUNCTIONS), "junctions and", len(ROADS), "roads")
    conn.close()
