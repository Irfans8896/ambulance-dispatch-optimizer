import os
import sqlite3
import tempfile

import pytest

import seed_roads
from app.models import Ambulance, Location
from app.services import (clean_calls, find_hotspots, suggest_k, demand_by_hour, allocate_slots,
                          recommend_positions, build_map_html)
from app.services.demand import haversine_km
from app.services.sample_data import make_sample_calls, CENTRES

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JUNCTIONS = {j: Location(lat, lon) for j, lat, lon in seed_roads.JUNCTIONS}


def clean():
    return clean_calls(make_sample_calls())


def near_a_true_centre(spot, km=0.5):
    return any(haversine_km(spot["latitude"], spot["longitude"], c[0], c[1]) < km for c in CENTRES)


def test_cleaning_removes_bad_rows():
    df, report = clean()
    assert report["removed_missing_coordinates"] > 0
    assert report["removed_invalid_coordinates"] > 0
    assert report["removed_duplicates"] > 0
    assert report["removed_outside_service_area"] > 0
    assert df["latitude"].notna().all() and not df.duplicated().any()
    assert (df["emergency_type"] == df["emergency_type"].str.strip().str.lower()).all()


def test_cleaning_report_adds_up():
    _, r = clean()
    removed = (r["removed_missing_coordinates"] + r["removed_invalid_coordinates"]
               + r["removed_duplicates"] + r["removed_outside_service_area"])
    assert r["raw_rows"] - removed == r["clean_rows"]


def test_kmeans_finds_the_three_centres():
    df, _ = clean()
    spots = find_hotspots(df, "kmeans", k=3)
    assert len(spots) == 3
    assert all(near_a_true_centre(s) for s in spots)


def test_dbscan_finds_hotspots_and_ignores_noise():
    df, _ = clean()
    spots = find_hotspots(df, "dbscan")
    assert len(spots) == 3
    assert all(near_a_true_centre(s) for s in spots)
    assert sum(s["calls"] for s in spots) < len(df)          # scattered calls are noise


def test_hotspots_are_ranked_by_demand():
    df, _ = clean()
    spots = find_hotspots(df, "dbscan")
    counts = [s["calls"] for s in spots]
    assert counts == sorted(counts, reverse=True)
    assert [s["hotspot_id"] for s in spots] == [1, 2, 3]
    assert sum(s["share_pct"] for s in spots) <= 100


def test_suggest_k_gives_scores():
    df, _ = clean()
    k, scores = suggest_k(df)
    assert 2 <= k <= 6 and len(scores) == 5


def test_empty_data_gives_no_hotspots():
    df, _ = clean()
    assert find_hotspots(df.iloc[0:0], "dbscan") == []
    assert find_hotspots(df.iloc[0:0], "kmeans") == []


def test_demand_by_hour():
    df, _ = clean()
    hours = demand_by_hour(df)
    assert len(hours) == 24 and sum(hours) == df["hour"].notna().sum()


def test_allocation_of_ambulances():
    assert allocate_slots([40, 35, 25], 0) == [0, 0, 0]
    assert allocate_slots([40, 35, 25], 2) == [1, 1, 0]       # busiest two get one each
    five = allocate_slots([40, 35, 25], 5)
    assert sum(five) == 5 and min(five) >= 1
    assert allocate_slots([], 3) == []


def test_recommendation_moves_only_free_ambulances():
    df, _ = clean()
    spots = find_hotspots(df, "dbscan")
    ambulances = [Ambulance(1, "A1", Location(15.4755, 78.4792)),
                  Ambulance(2, "A2", Location(15.4836, 78.4886)),
                  Ambulance(3, "A3", Location(15.4936, 78.4986), status=Ambulance.DISPATCHED)]
    advice = recommend_positions(spots, JUNCTIONS, ambulances, df)
    assert {m["vehicle_number"] for m in advice["moves"]} == {"A1", "A2"}
    assert sum(s["ambulances_recommended"] for s in advice["standby_points"]) == 2


def test_prepositioning_improves_coverage():
    df, _ = clean()
    spots = find_hotspots(df, "dbscan")
    ambulances = [Ambulance(1, "A1", Location(15.4755, 78.4792)),
                  Ambulance(2, "A2", Location(15.4836, 78.4886))]
    advice = recommend_positions(spots, JUNCTIONS, ambulances, df)
    assert advice["avg_distance_km_after"] < advice["avg_distance_km_before"]
    assert advice["improvement_pct"] > 0


def test_map_page_contains_data():
    df, _ = clean()
    spots = find_hotspots(df, "dbscan")
    html = build_map_html(df, spots, [], [], [])
    assert "leaflet" in html.lower() and '"hotspot_id": 1' in html


def make_api_db():
    path = os.path.join(tempfile.mkdtemp(), "test.db")
    conn = sqlite3.connect(path)
    conn.executescript(open(os.path.join(BASE, "schema.sql")).read())
    conn.executemany("INSERT INTO ambulances (vehicle_number, latitude, longitude) VALUES (?,?,?)",
                     [("AP21-1001", 15.4755, 78.4792), ("AP21-1002", 15.4836, 78.4886)])
    conn.executemany(
        "INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) VALUES (?,?,?,?,?)",
        [("City General", 15.4686, 78.4736, 12, "trauma,cardiac")])
    seed_roads.seed(conn)
    import load_calls
    load_calls.load(conn, make_sample_calls())
    conn.close()
    return path


def test_api_endpoints():
    from app import create_app
    app = create_app()
    app.config["DATABASE"] = make_api_db()
    client = app.test_client()

    r = client.get("/api/hotspots").get_json()
    assert len(r["hotspots"]) == 3 and len(r["calls_by_hour"]) == 24
    assert len(client.get("/api/hotspots?method=kmeans&k=3").get_json()["hotspots"]) == 3
    assert client.get("/api/hotspots?method=bogus").status_code == 400

    p = client.get("/api/prepositioning").get_json()
    assert p["improvement_pct"] > 0 and len(p["moves"]) == 2

    page = client.get("/hotspot-map")
    assert page.status_code == 200 and b"leaflet" in page.data.lower()


def test_api_without_history_returns_404():
    from app import create_app
    app = create_app()
    path = make_api_db()
    conn = sqlite3.connect(path)
    conn.execute("DELETE FROM historical_calls")
    conn.commit()
    conn.close()
    app.config["DATABASE"] = path
    assert app.test_client().get("/api/hotspots").status_code == 404
