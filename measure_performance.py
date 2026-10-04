"""Week 7: response-time measurement.

  python3 measure_performance.py

Part A  Software speed: how long the system takes to answer (milliseconds).
Part B  Ambulance response time: ETA to the scene under random traffic and road closures,
        comparing our system with simpler strategies (500 seeded scenarios, repeatable).
Results are printed and saved to reports/performance.json.
"""
import json
import os
import random
import statistics
import tempfile
import time

from app import create_app
from app.models import Ambulance, Location
from app.services import RoadGraph, NoRouteError, dijkstra
from app.services.dispatch import DispatchService, load_junctions, to_minutes, _service
from setup_demo import build_demo_db, AMBULANCES
import seed_roads

BASE = os.path.dirname(os.path.abspath(__file__))
SCENE = {"latitude": 15.4881, "longitude": 78.4931, "emergency_type": "accident", "severity": 4}


def ms_stats(samples):
    s = sorted(samples)
    return {"runs": len(s), "mean_ms": round(statistics.mean(s), 2),
            "median_ms": round(statistics.median(s), 2),
            "p95_ms": round(s[int(0.95 * (len(s) - 1))], 2), "max_ms": round(s[-1], 2)}


def timed(fn, runs):
    out = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1000)
    return out


# --------------------------------------------------------------------------- Part A
def part_a():
    path = os.path.join(tempfile.mkdtemp(), "perf.db")
    build_demo_db(path)
    app = create_app()
    app.config["DATABASE"] = path
    app.config["AUTH_REQUIRED"] = False            # measure the system, not the login
    client = app.test_client()
    results = {}

    for name, url in [("GET /api/state", "/api/state"), ("GET /api/summary", "/api/summary"),
                      ("GET /api/hotspots (DBSCAN)", "/api/hotspots?method=dbscan"),
                      ("GET /api/hotspots (K-Means)", "/api/hotspots?method=kmeans&k=3"),
                      ("GET /api/prepositioning", "/api/prepositioning")]:
        client.get(url)                                         # warm-up
        results[name] = ms_stats(timed(lambda: client.get(url), 30))

    # one dispatch needs a fresh database each time (ambulances become busy)
    times = []
    for _ in range(30):
        build_demo_db(path)
        t = time.perf_counter()
        r = client.post("/api/incidents/dispatch", json=SCENE)
        times.append((time.perf_counter() - t) * 1000)
        assert r.status_code == 201
    results["POST /api/incidents/dispatch"] = ms_stats(times)

    # the decision itself (graph + Dijkstra for every ambulance and hospital), no HTTP, no writes
    import sqlite3
    build_demo_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    amb = [Ambulance.from_row(r) for r in conn.execute("SELECT * FROM ambulances")]
    from app.models import Hospital
    hosp = [Hospital.from_row(r) for r in conn.execute("SELECT * FROM hospitals")]
    here = Location(SCENE["latitude"], SCENE["longitude"])
    results["Dispatch decision only (Dijkstra x ambulances + hospitals)"] = ms_stats(
        timed(lambda: _service(conn).plan(here, "accident", amb, hosp), 300))
    conn.close()
    return results


# --------------------------------------------------------------------------- Part B
def build_scenario(rng):
    rows = []
    for a, b, km, _, _ in seed_roads.ROADS:
        traffic = rng.choices(["LOW", "MEDIUM", "HEAVY"], [0.5, 0.3, 0.2])[0]
        cond = rng.choices(["GOOD", "POOR", "CLOSED"], [0.75, 0.15, 0.10])[0]
        rows.append({"source": a, "destination": b, "distance": km,
                     "traffic_level": traffic, "road_condition": cond})
    j = rng.choice(seed_roads.JUNCTIONS)
    scene = Location(j[1] + rng.uniform(-0.002, 0.002), j[2] + rng.uniform(-0.002, 0.002))
    return rows, scene


def path_cost(graph, path):
    return sum(graph[a][b]["weight"] for a, b in zip(path, path[1:]))


def part_b(n=500, seed=2026):
    rng = random.Random(seed)
    junctions = {j: Location(la, lo) for j, la, lo in seed_roads.JUNCTIONS}
    fleet = [Ambulance(i + 1, v, Location(la, lo)) for i, (v, la, lo) in enumerate(AMBULANCES)]
    sums = {"naive": 0.0, "smart_choice": 0.0, "system": 0.0}
    used = changed_choice = changed_route = 0

    for _ in range(n):
        rows, scene = build_scenario(rng)
        city = RoadGraph.from_rows(rows)
        svc = DispatchService(city, junctions)
        target = svc.junction_of(scene)

        try:
            (cost_system, best, path_system), _ = svc.select_ambulance(scene, fleet)
        except Exception:
            continue                                  # nobody can reach: skipped for all methods

        # Strategy 1: nearest ambulance in a straight line, route planned on distance only
        static = city.graph.copy()
        for _, _, d in static.edges(data=True):
            d["weight"] = d["distance"]
        by_line = sorted(fleet, key=lambda a: a.location.distance_km(scene))
        naive_cost = None
        for amb in by_line:
            try:
                p, _ = dijkstra(static, svc.junction_of(amb.location), target)
            except NoRouteError:
                continue
            naive_cost = path_cost(city.graph, p)     # but the real trip suffers the real traffic
            naive_amb = amb
            break
        # Strategy 2: nearest by straight line, but routed with live traffic
        smart_cost = None
        for amb in by_line:
            try:
                _, smart_cost, _ = city.shortest_route(svc.junction_of(amb.location), target)
                break
            except NoRouteError:
                continue
        if naive_cost is None or smart_cost is None:
            continue

        used += 1
        sums["naive"] += naive_cost
        sums["smart_choice"] += smart_cost
        sums["system"] += cost_system
        changed_choice += best.vehicle_number != by_line[0].vehicle_number
        changed_route += naive_cost != smart_cost

    avg = {k: round(to_minutes(v / used), 2) for k, v in sums.items()}
    gain = lambda a, b: round(100 * (a - b) / a, 1)
    return {
        "scenarios_used": used, "avg_eta_min": avg,
        "system_vs_naive_pct_faster": gain(avg["naive"], avg["system"]),
        "live_routing_alone_pct_faster": gain(avg["naive"], avg["smart_choice"]),
        "scenarios_where_ambulance_choice_changed": changed_choice,
        "scenarios_where_route_changed": changed_route,
    }


if __name__ == "__main__":
    a = part_a()
    print("\nPART A: software response time (milliseconds)")
    print("%-62s %7s %7s %7s" % ("operation", "mean", "p95", "max"))
    for name, s in a.items():
        print("%-62s %7.2f %7.2f %7.2f" % (name, s["mean_ms"], s["p95_ms"], s["max_ms"]))

    b = part_b()
    print("\nPART B: ambulance ETA to scene over %d random traffic/closure scenarios" % b["scenarios_used"])
    print("  Naive (nearest in a straight line, route ignores traffic): %.2f min" % b["avg_eta_min"]["naive"])
    print("  Nearest in a straight line + live-traffic routing        : %.2f min" % b["avg_eta_min"]["smart_choice"])
    print("  Our system (nearest by travel time + live routing)       : %.2f min" % b["avg_eta_min"]["system"])
    print("  Improvement over naive: %.1f%%" % b["system_vs_naive_pct_faster"])
    print("  Ambulance choice differed in %d scenarios, route differed in %d"
          % (b["scenarios_where_ambulance_choice_changed"], b["scenarios_where_route_changed"]))

    os.makedirs(os.path.join(BASE, "reports"), exist_ok=True)
    with open(os.path.join(BASE, "reports", "performance.json"), "w") as f:
        json.dump({"software_ms": a, "eta_comparison": b}, f, indent=2)
    print("\nSaved reports/performance.json")
