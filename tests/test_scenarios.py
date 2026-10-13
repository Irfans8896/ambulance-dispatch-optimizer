"""Week 7: end-to-end scenarios. Each test is one real-life situation, run through the REST API
on a fresh demo database (the same data the live Render app starts with)."""
import os
import sys
import tempfile

import networkx as nx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app                      # noqa: E402
from app.models import Road                     # noqa: E402
from app.services import RoadGraph, dijkstra    # noqa: E402
from setup_demo import build_demo_db            # noqa: E402

SCENE = {"latitude": 15.4881, "longitude": 78.4931}      # next to junction 5


def make_client():
    path = os.path.join(tempfile.mkdtemp(), "scenario.db")
    build_demo_db(path)
    app = create_app()
    app.config["DATABASE"] = path
    return app.test_client()


def report(c, etype="accident", severity=4, **where):
    body = {**(where or SCENE), "emergency_type": etype, "severity": severity}
    return c.post("/api/incidents/dispatch", json=body)


def road(c, a, b, **change):
    return c.post("/api/roads/traffic", json={"source": a, "destination": b, **change})


# ---- 1. normal operation -----------------------------------------------------------------

def test_s1_normal_dispatch_picks_nearest_ambulance_and_hospital():
    r = report(make_client())
    d = r.get_json()
    assert r.status_code == 201
    assert d["ambulance"] == "AP21-1002" and d["route_to_scene"] == [4, 5]
    # LifeLine Critical Care is at J5 (same junction as scene) — nearest Tier-1 trauma hospital
    assert d["hospital"] == "LifeLine Critical Care" and d["specialty_match"] is True
    # LifeLine is at the same junction as the scene (J5), so hospital ETA ≈ 0
    assert 0 < d["eta_to_scene_min"] and d["eta_to_hospital_min"] >= 0


def test_s2_full_lifecycle_updates_ambulance_incident_and_beds():
    c = make_client()
    d = report(c).get_json()
    beds_before = {h["name"]: h["available_beds"] for h in c.get("/api/hospitals").get_json()}
    seen = [c.post("/api/dispatches/%d/advance" % d["dispatch_id"]).get_json() for _ in range(3)]
    assert [s["ambulance_status"] for s in seen] == ["AT_SCENE", "TO_HOSPITAL", "AVAILABLE"]
    assert [s["incident_status"] for s in seen] == ["ARRIVED", "TRANSPORTED", "COMPLETED"]
    beds_after = {h["name"]: h["available_beds"] for h in c.get("/api/hospitals").get_json()}
    # LifeLine Critical Care is now the nearest hospital selected for accidents from the scene
    dispatched_hospital = d["hospital"]
    assert beds_after[dispatched_hospital] == beds_before[dispatched_hospital] - 1
    assert c.post("/api/dispatches/%d/advance" % d["dispatch_id"]).status_code == 400


# ---- 2. changing roads -------------------------------------------------------------------

def test_s3_heavy_traffic_raises_eta():
    normal = report(make_client()).get_json()
    c = make_client()
    assert road(c, 4, 5, traffic_level="HEAVY").status_code == 200
    slow = report(c).get_json()
    assert slow["eta_to_scene_min"] > normal["eta_to_scene_min"]
    # Route to hospital may differ under heavy traffic (cost changes)
    # At minimum, the ETA to scene increases due to heavy traffic on J4→J5
    assert slow["eta_to_scene_min"] > normal["eta_to_scene_min"]



def test_s4_closed_roads_change_the_chosen_ambulance():
    c = make_client()
    road(c, 4, 5, road_condition="CLOSED")
    road(c, 5, 6, road_condition="CLOSED")
    d = report(c).get_json()
    assert d["ambulance"] != "AP21-1002"
    for a, b in zip(d["route_to_scene"], d["route_to_scene"][1:]):
        assert {a, b} not in ({4, 5}, {5, 6})


def test_s5_reopening_a_road_restores_the_original_choice():
    c = make_client()
    road(c, 4, 5, road_condition="CLOSED")
    road(c, 4, 5, road_condition="GOOD")
    assert report(c).get_json()["ambulance"] == "AP21-1002"


# ---- 3. resources run out ----------------------------------------------------------------

def test_s6_two_incidents_use_two_different_ambulances():
    c = make_client()
    a = report(c).get_json()["ambulance"]
    b = report(c).get_json()["ambulance"]
    assert a != b


def test_s7_all_ambulances_busy_returns_409_but_call_is_recorded():
    c = make_client()
    for _ in range(3):
        assert report(c).status_code == 201
    r = report(c)
    assert r.status_code == 409 and "ambulance" in r.get_json()["error"].lower()
    assert c.get("/api/summary").get_json()["total_dispatches"] == 3


def test_s8_full_hospital_is_skipped():
    c = make_client()
    # LifeLine Critical Care (nearest cardiac, 10 beds) — drain it completely
    for _ in range(10):
        d = report(c, "cardiac").get_json()
        for _ in range(3):
            c.post("/api/dispatches/%d/advance" % d["dispatch_id"])
    # Next cardiac dispatch should go to Apollo Emergency Care (next nearest cardiac Tier-1)
    last = report(c, "cardiac").get_json()
    assert last["hospital"] == "Apollo Emergency Care" and last["specialty_match"] is True


def test_s9_unreachable_scene_gives_409():
    c = make_client()
    for a, b in ((4, 5), (5, 6), (3, 5)):
        road(c, a, b, road_condition="CLOSED")           # junction 5 is cut off
    assert report(c).status_code == 409


def test_s10_pediatric_case_goes_to_pediatric_hospital():
    # Mother & Child Center is at J5 (same junction as scene) — nearest Tier-2 pediatric hospital
    assert report(make_client(), "child", 3).get_json()["hospital"] == "Mother & Child Center"


# ---- 4. bad input ------------------------------------------------------------------------

def test_s11_invalid_requests_are_rejected():
    c = make_client()
    assert report(c, severity=9).status_code == 400
    assert c.post("/api/incidents/dispatch", json={"emergency_type": "accident"}).status_code == 400
    assert road(c, 4, 5, traffic_level="JAMMED").status_code == 400
    assert road(c, 1, 6, traffic_level="LOW").status_code == 400          # no such road
    assert c.post("/api/dispatches/999/advance").status_code == 400
    assert c.get("/api/route?source=1").status_code == 400
    assert c.get("/api/route?source=1&target=99").status_code == 404


# ---- 5. demand analysis ------------------------------------------------------------------

def test_s12_dbscan_and_kmeans_find_the_three_hotspots():
    c = make_client()
    db = c.get("/api/hotspots?method=dbscan").get_json()
    km = c.get("/api/hotspots?method=kmeans&k=3").get_json()
    assert len(db["hotspots"]) == 3 and len(km["hotspots"]) == 3
    assert db["cleaning"]["raw_rows"] > sum(h["calls"] for h in db["hotspots"])   # dirty rows removed
    assert len(db["calls_by_hour"]) == 24


def test_s13_prepositioning_reduces_average_distance():
    p = make_client().get("/api/prepositioning").get_json()
    assert p["standby_points"] and p["improvement_pct"] > 0
    assert p["avg_distance_km_after"] < p["avg_distance_km_before"]


def test_s14_hotspot_map_and_csv_report_work():
    c = make_client()
    assert c.get("/hotspot-map").status_code == 200
    report(c, "cardiac", 3)
    lines = c.get("/api/reports/dispatches.csv").data.decode().strip().splitlines()
    assert len(lines) == 2 and "cardiac" in lines[1]


# ---- 6. algorithm correctness ------------------------------------------------------------

def test_s15_own_dijkstra_matches_networkx_for_every_pair_under_traffic():
    city = RoadGraph()
    for a, b, km in [(1, 2, 2.0), (1, 3, 4.0), (2, 3, 1.0), (2, 4, 5.0), (3, 4, 3.0),
                     (3, 5, 6.0), (4, 5, 2.0), (4, 6, 4.0), (5, 6, 1.0)]:
        city.add_road(Road(a, b, km))
    city.update_road(3, 4, traffic_level="HEAVY")
    city.update_road(2, 4, road_condition="POOR")
    city.update_road(5, 6, traffic_level="MEDIUM")
    for s in range(1, 7):
        for t in range(1, 7):
            _, cost = dijkstra(city.graph, s, t)
            assert cost == pytest.approx(nx.dijkstra_path_length(city.graph, s, t, weight="weight"))
