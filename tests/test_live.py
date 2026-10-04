"""Live re-routing, waiting queue with priority, rush-hour traffic, analytics."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_complete import SCENE, make_app, login, rows       # noqa: E402
from app.services import traffic                              # noqa: E402
from app.services.reroute import _passed_index                # noqa: E402
from app.services.road_graph import RoadGraph                 # noqa: E402
from app.models import Road                                  # noqa: E402

J6 = {"latitude": 15.4936, "longitude": 78.4986, "emergency_type": "general", "severity": 3}   # junction 6


def road(c, a, b, **kw):
    return c.post("/api/roads/traffic", json={"source": a, "destination": b, **kw}).get_json()


def trip(c, i=0):
    return c.get("/api/state").get_json()["dispatches"][i]


# ---------------------------------------------------------------- live re-routing
def test_closing_the_road_ahead_reroutes_the_ambulance_on_its_way():
    c = make_app().test_client()
    d = c.post("/api/incidents/dispatch", json=SCENE).get_json()
    assert d["route_to_scene"] == [4, 5]
    out = road(c, 4, 5, road_condition="CLOSED")
    assert len(out["rerouted"]) == 1 and out["rerouted"][0]["vehicle_number"] == "AP21-1002"
    t = trip(c)
    assert t["route"]["to_scene"] == [4, 6, 5] and t["reroutes"] == 1
    assert t["eta_min"] > d["eta_to_scene_min"]
    assert any("AP21-1002 rerouted" in n["message"] for n in c.get("/api/notifications").get_json())


def test_unrelated_road_changes_do_not_reroute():
    c = make_app().test_client()
    c.post("/api/incidents/dispatch", json=SCENE)
    assert road(c, 1, 2, road_condition="CLOSED")["rerouted"] == []
    assert trip(c)["reroutes"] == 0 and trip(c)["route"]["to_scene"] == [4, 5]


def test_reroute_starts_from_the_junction_the_ambulance_has_reached():
    c = make_app().test_client()
    d = c.post("/api/incidents/dispatch", json=J6).get_json()
    assert d["route_to_scene"] == [4, 5, 6]
    before = trip(c)["eta_min"]
    assert c.post("/api/dispatches/%d/progress" % d["dispatch_id"], json={"fraction": 0.7}).status_code == 200
    out = road(c, 5, 6, road_condition="CLOSED")                 # the road right ahead of the ambulance
    t = trip(c)
    assert out["rerouted"] and t["route"]["to_scene"] == [5, 4, 6]            # continues from junction 5
    assert abs(t["eta_min"] - (0.7 * before + t["route"]["eta_scene_min"])) < 0.11   # time already driven counts
    assert t["progress"] == 0


def test_passed_junction_is_found_from_progress():
    city = RoadGraph()
    for a, b, km in [(1, 2, 2.0), (2, 4, 5.0), (4, 6, 4.0)]:
        city.add_road(Road(a, b, km))
    path = [1, 2, 4, 6]
    assert [_passed_index(city.roads, path, p) for p in (0, 0.1, 0.2, 0.7, 0.99, 1.0)] == [0, 0, 1, 2, 2, 3]


def test_hospital_diversion_sends_trips_to_another_hospital():
    c = make_app().test_client()
    d = c.post("/api/incidents/dispatch", json={**SCENE, "emergency_type": "cardiac"}).get_json()
    assert d["hospital"] == "City General"
    hid = [h for h in c.get("/api/hospitals").get_json() if h["name"] == "City General"][0]["hospital_id"]
    out = c.post("/api/hospitals/%d" % hid, json={"status": "DIVERSION"}).get_json()
    assert out["rerouted"] and out["rerouted"][0]["new_hospital"] == "District Hospital"
    assert trip(c)["hospital"] == "District Hospital"


def test_trip_already_at_the_hospital_leg_is_rerouted_too():
    c = make_app().test_client()
    d = c.post("/api/incidents/dispatch", json=SCENE).get_json()
    for _ in range(2):
        c.post("/api/dispatches/%d/advance" % d["dispatch_id"])          # now TO_HOSPITAL
    assert d["route_to_hospital"] == [5, 4, 3, 2]
    road(c, 3, 4, road_condition="CLOSED")
    new = trip(c)["route"]["to_hospital"]
    assert new[0] == 5 and new[-1] == 2 and {3, 4} != set(new[1:-1]) and (3, 4) not in zip(new, new[1:]) \
        and (4, 3) not in zip(new, new[1:])                                   # avoids the closed road 3-4
    assert trip(c)["reroutes"] == 1


def test_recheck_endpoint_and_progress_validation():
    c = make_app().test_client()
    out = c.post("/api/dispatches/recheck").get_json()
    assert out == {"rerouted": [], "dispatched_from_queue": []}
    d = c.post("/api/incidents/dispatch", json=SCENE).get_json()
    url = "/api/dispatches/%d/progress" % d["dispatch_id"]
    assert c.post(url, json={"fraction": 1.5}).status_code == 400
    assert c.post(url, json={"fraction": "x"}).status_code == 400
    assert c.post("/api/dispatches/99/progress", json={"fraction": 0.5}).status_code == 404
    assert c.post(url, json={"fraction": 0.4}).status_code == 200
    assert rows(c.application, "SELECT progress FROM dispatches")[0][0] == 0.4
    c.post("/api/dispatches/%d/advance" % d["dispatch_id"])
    assert rows(c.application, "SELECT progress FROM dispatches")[0][0] == 0        # each leg starts at 0


def test_driver_can_report_progress_only_for_own_trip():
    app = make_app(auth=True)
    d = login(app, "dispatcher").post("/api/incidents/dispatch", json=SCENE).get_json()
    url = "/api/dispatches/%d/progress" % d["dispatch_id"]
    assert login(app, "driver1").post(url, json={"fraction": 0.3}).status_code == 403
    assert login(app, "driver2").post(url, json={"fraction": 0.3}).status_code == 200


# ---------------------------------------------------------------- waiting queue
def fill_fleet(c):
    return [c.post("/api/incidents/dispatch", json=SCENE).get_json() for _ in range(3)]


def test_busy_fleet_queues_the_call_and_serves_it_when_an_ambulance_is_free():
    c = make_app().test_client()
    first = fill_fleet(c)
    r = c.post("/api/incidents/dispatch", json=SCENE)
    q = r.get_json()
    assert r.status_code == 409 and q["queued"] is True and q["queue_position"] == 1
    assert len(c.get("/api/queue").get_json()) == 1 and c.get("/api/summary").get_json()["queued"] == 1
    for _ in range(2):
        c.post("/api/dispatches/%d/advance" % first[0]["dispatch_id"])
    out = c.post("/api/dispatches/%d/advance" % first[0]["dispatch_id"]).get_json()   # ambulance free again
    assert [x["incident_id"] for x in out["dispatched_from_queue"]] == [q["incident_id"]]
    assert c.get("/api/queue").get_json() == [] and c.get("/api/summary").get_json()["total_dispatches"] == 4
    assert any("Waiting incident" in n["message"] for n in c.get("/api/notifications").get_json())


def test_most_severe_waiting_call_is_served_first():
    c = make_app().test_client()
    first = fill_fleet(c)
    mild = c.post("/api/incidents/dispatch", json={**SCENE, "severity": 2}).get_json()
    grave = c.post("/api/incidents/dispatch", json={**SCENE, "severity": 5}).get_json()
    assert mild["queue_position"] == 1 and grave["queue_position"] == 1       # the grave one jumps ahead
    for _ in range(3):
        out = c.post("/api/dispatches/%d/advance" % first[0]["dispatch_id"]).get_json()
    assert [x["incident_id"] for x in out["dispatched_from_queue"]] == [grave["incident_id"]]
    assert [q["incident_id"] for q in c.get("/api/queue").get_json()] == [mild["incident_id"]]


def test_call_from_an_unreachable_place_is_served_when_the_road_reopens():
    c = make_app().test_client()
    for a, b in ((4, 5), (5, 6), (3, 5)):
        road(c, a, b, road_condition="CLOSED")
    assert c.post("/api/incidents/dispatch", json=SCENE).status_code == 409
    out = road(c, 4, 5, road_condition="GOOD")
    assert len(out["dispatched_from_queue"]) == 1 and c.get("/api/queue").get_json() == []


def test_registering_an_ambulance_serves_the_queue():
    c = make_app().test_client()
    fill_fleet(c)
    assert c.post("/api/incidents/dispatch", json=SCENE).status_code == 409
    out = c.post("/api/ambulances", json={"vehicle_number": "AP21-3001", "latitude": 15.4886, "longitude": 78.4936}).get_json()
    assert out["dispatched_from_queue"][0]["ambulance"] == "AP21-3001"


# ---------------------------------------------------------------- rush-hour traffic
def with_hour(hour, fn):
    old = traffic.current_hour
    traffic.current_hour = lambda: hour
    try:
        return fn()
    finally:
        traffic.current_hour = old


def test_rush_hour_hours():
    assert [traffic.is_rush_hour(h) for h in (7, 8, 9, 10, 16, 17, 19, 20)] == [False, True, True, False, False, True, True, False]


def test_automatic_traffic_slows_roads_only_in_rush_hour_and_only_when_on():
    c = make_app().test_client()
    base = c.post("/api/incidents/dispatch", json=SCENE).get_json()["eta_to_scene_min"]

    def levels():
        return {r["effective_traffic"] for r in c.get("/api/state").get_json()["roads"]}

    def run():
        assert levels() == {"LOW"}                                           # switched off: nothing changes
        assert c.post("/api/settings/auto-traffic", json={"enabled": True}).get_json()["auto_traffic"] is True
        assert levels() == {"MEDIUM"}
        assert all(r["traffic_level"] == "LOW" for r in c.get("/api/state").get_json()["roads"])   # admin setting kept
        assert {r["traffic_level"] for r in c.get("/api/roads").get_json()} == {"MEDIUM"}
        d = c.post("/api/incidents/dispatch", json={**SCENE, "severity": 5}).get_json()
        assert d["eta_to_scene_min"] > base
    with_hour(9, run)
    assert with_hour(12, lambda: {r["effective_traffic"] for r in c.get("/api/state").get_json()["roads"]}) == {"LOW"}
    assert c.post("/api/settings/auto-traffic", json={"enabled": "yes"}).status_code == 400
    c.post("/api/settings/auto-traffic", json={"enabled": False})
    assert with_hour(9, lambda: {r["effective_traffic"] for r in c.get("/api/state").get_json()["roads"]}) == {"LOW"}


def test_only_admin_changes_traffic_mode():
    app = make_app(auth=True)
    assert login(app, "dispatcher").post("/api/settings/auto-traffic", json={"enabled": True}).status_code == 403
    assert login(app, "admin").post("/api/settings/auto-traffic", json={"enabled": True}).status_code == 200


# ---------------------------------------------------------------- analytics
def test_analytics_empty_then_filled_by_demo_data():
    app = make_app()
    c = app.test_client()
    a = c.get("/api/analytics").get_json()
    assert a["totals"]["dispatches"] == 0 and a["totals"]["avg_eta_min"] is None and len(a["by_hour"]) == 24
    beds = rows(app, "SELECT hospital_id, available_beds FROM hospitals ORDER BY hospital_id")
    out = c.post("/api/demo/simulate", json={"count": 8}).get_json()
    assert out["created"] + out["skipped"] == 8 and out["created"] > 0
    a = c.get("/api/analytics").get_json()
    assert a["totals"]["dispatches"] == out["created"] and a["totals"]["completed"] == out["created"]
    assert sum(a["by_type"].values()) == out["created"] and sum(a["by_severity"].values()) == out["created"]
    assert sum(p["trips"] for p in a["per_ambulance"]) == out["created"]
    assert 0 <= a["totals"]["within_target_pct"] <= 100 and sum(a["by_hour"]) == out["created"]
    assert rows(app, "SELECT hospital_id, available_beds FROM hospitals ORDER BY hospital_id") == beds   # beds restored
    assert c.get("/analytics").status_code == 200


def test_analytics_permissions_and_limits():
    app = make_app(auth=True)
    assert login(app, "driver1").get("/api/analytics").status_code == 403
    assert login(app, "dispatcher").get("/api/analytics").status_code == 200
    assert login(app, "dispatcher").post("/api/demo/simulate", json={"count": 3}).status_code == 403
    admin = login(app, "admin")
    assert admin.post("/api/demo/simulate", json={"count": 0}).status_code == 400
    assert admin.post("/api/demo/simulate", json={"count": 99}).status_code == 400
    assert admin.post("/api/demo/simulate", json={"count": "x"}).status_code == 400


def test_dashboard_has_the_new_controls():
    page = make_app().test_client().get("/").data.decode()
    for needle in ['id="queue"', 'id="queueCount"', 'id="autoTraffic"', 'id="recheckBtn"', "/analytics", "travel(id"]:
        assert needle in page, needle
