"""Week 5 demo: cleaning, hotspots, pre-positioning. Writes hotspot_map.html.
Uses a temporary in-memory database; your dispatch.db is untouched."""
import os
import sqlite3

import seed_roads
from app.models import Ambulance
from app.services import (clean_calls, find_hotspots, suggest_k, recommend_positions,
                          build_map_html)
from app.services.dispatch import load_junctions
from app.services.sample_data import make_sample_calls

BASE = os.path.dirname(os.path.abspath(__file__))

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.executescript(open(os.path.join(BASE, "schema.sql")).read())
conn.executemany("INSERT INTO ambulances (vehicle_number, latitude, longitude) VALUES (?,?,?)",
                 [("AP21-1001", 15.4755, 78.4792), ("AP21-1002", 15.4836, 78.4886)])
conn.executemany(
    "INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) VALUES (?,?,?,?,?)",
    [("City General", 15.4686, 78.4736, 12, "trauma,cardiac"),
     ("District Hospital", 15.4936, 78.4986, 5, "general,pediatric")])
seed_roads.seed(conn)

print("=== 1. Data cleaning ===")
raw = make_sample_calls()
calls, report = clean_calls(raw)
for key, value in report.items():
    print(f"  {key:32s} {value}")

print("\n=== 2. K-Means hotspots (k=3) ===")
km = find_hotspots(calls, "kmeans", k=3)
for h in km:
    print(f"  #{h['hotspot_id']}  {h['calls']:4d} calls ({h['share_pct']}%)  "
          f"type={h['top_type']:9s} peak={h['peak_hour']}:00  at ({h['latitude']:.4f}, {h['longitude']:.4f})")
best_k, scores = suggest_k(calls)
print("  silhouette scores:", scores)

print("\n=== 3. DBSCAN hotspots (finds the number of clusters itself) ===")
db = find_hotspots(calls, "dbscan")
for h in db:
    print(f"  #{h['hotspot_id']}  {h['calls']:4d} calls ({h['share_pct']}%)  "
          f"type={h['top_type']:9s} peak={h['peak_hour']}:00")
print(f"  calls treated as noise: {len(calls) - sum(h['calls'] for h in db)}")

print("\n=== 4. Ambulance pre-positioning (using DBSCAN hotspots) ===")
ambulances = [Ambulance.from_row(r) for r in conn.execute("SELECT * FROM ambulances")]
advice = recommend_positions(db, load_junctions(conn), ambulances, calls)
for s in advice["standby_points"]:
    print(f"  Hotspot {s['hotspot_id']}: station {s['ambulances_recommended']} ambulance(s) at junction {s['junction_id']}")
for m in advice["moves"]:
    note = "stay" if m["already_in_place"] else f"move {m['from_junction']} -> {m['to_junction']} ({m['distance_km']} km)"
    print(f"  {m['vehicle_number']}: {note}")
print(f"  Average distance from a call to the nearest ambulance: "
      f"{advice['avg_distance_km_before']} km now -> {advice['avg_distance_km_after']} km "
      f"({advice['improvement_pct']}% better)")

html = build_map_html(calls, db, advice["standby_points"],
                      [dict(r) for r in conn.execute("SELECT * FROM ambulances")],
                      [dict(r) for r in conn.execute("SELECT * FROM hospitals")])
path = os.path.join(BASE, "hotspot_map.html")
open(path, "w", encoding="utf-8").write(html)
print("\nMap written to", path, "(open it in your browser)")
