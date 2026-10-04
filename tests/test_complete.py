"""Week 7 completion: login and roles, registration, hospital status, notifications,
traffic history, stored hotspots, feedback loop, driver view."""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app          # noqa: E402
from setup_demo import build_demo_db  # noqa: E402

SCENE = {"latitude": 15.4881, "longitude": 78.4931, "emergency_type": "accident", "severity": 4}
PASSWORDS = {"admin": "admin123", "dispatcher": "dispatch123", "driver1": "driver123", "driver2": "driver123"}


def make_app(auth=False):
    path = os.path.join(tempfile.mkdtemp(), "complete.db")
    build_demo_db(path)
    app = create_app()
    app.config["DATABASE"] = path
    app.config["AUTH_REQUIRED"] = auth
    return app


def login(app, username):
    c = app.test_client()
    r = c.post("/login", data={"username": username, "password": PASSWORDS[username]})
    assert r.status_code == 302
    return c


def rows(app, sql, *args):
    conn = sqlite3.connect(app.config["DATABASE"])
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------- login and roles
def test_login_is_required_when_enabled():
    c = make_app(auth=True).test_client()
    assert c.get("/api/state").status_code == 401
    r = c.get("/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert c.get("/health").get_json() == {"status": "ok"}          # public (Render health check)
    assert c.get("/login").status_code == 200


def test_wrong_password_and_open_redirect_are_blocked():
    c = make_app(auth=True).test_client()
    assert c.post("/login", data={"username": "admin", "password": "nope"}).status_code == 401
    r = c.post("/login?next=//evil.example", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 302 and r.headers["Location"] == "/"


def test_me_returns_the_role():
    app = make_app(auth=True)
    assert login(app, "dispatcher").get("/api/me").get_json()["role"] == "dispatcher"
    assert login(app, "driver1").get("/api/me").get_json()["ambulance_id"] == 1


def test_role_permissions():
    app = make_app(auth=True)
    admin, disp, driver = login(app, "admin"), login(app, "dispatcher"), login(app, "driver1")
    reg = {"vehicle_number": "AP21-2001", "latitude": 15.4736, "longitude": 78.4786}
    assert disp.post("/api/ambulances", json=reg).status_code == 403
    assert disp.post("/api/roads/traffic", json={"source": 4, "destination": 5, "traffic_level": "HEAVY"}).status_code == 403
    assert driver.post("/api/incidents/dispatch", json=SCENE).status_code == 403
    assert driver.get("/api/hotspots").status_code == 403
    assert disp.post("/api/incidents/dispatch", json=SCENE).status_code == 201
    assert admin.post("/api/ambulances", json=reg).status_code == 201
    assert disp.get("/api/hotspots").status_code == 200


def test_driver_can_only_advance_their_own_trip():
    app = make_app(auth=True)
    d = login(app, "dispatcher").post("/api/incidents/dispatch", json=SCENE).get_json()
    assert d["ambulance"] == "AP21-1002"                              # ambulance 2 -> driver2
    url = "/api/dispatches/%d/advance" % d["dispatch_id"]
    assert login(app, "driver1").post(url).status_code == 403
    r = login(app, "driver2").post(url)
    assert r.status_code == 200 and r.get_json()["ambulance_status"] == "AT_SCENE"


def test_driver_page_and_status():
    app = make_app(auth=True)
    c = login(app, "driver2")
    idle = c.get("/api/driver/status").get_json()
    assert idle["trip"] is None and idle["ambulance"]["vehicle_number"] == "AP21-1002"
    assert b"Driver" in c.get("/").data and b"hospital" in c.get("/").data.lower()
    login(app, "dispatcher").post("/api/incidents/dispatch", json=SCENE)
    s = c.get("/api/driver/status").get_json()
    assert s["trip"]["go_to"] == "scene" and s["next_step"] == "I have arrived at the scene"
    c.post("/api/dispatches/%d/advance" % s["trip"]["dispatch_id"])
    assert c.get("/api/driver/status").get_json()["trip"]["go_to"] == "hospital"
    assert login(app, "admin").get("/api/driver/status").status_code == 400    # drivers only


# ---------------------------------------------------------------- registration
def test_register_ambulance_validation():
    c = make_app().test_client()
    ok = c.post("/api/ambulances", json={"vehicle_number": " ap21-2001 ", "latitude": 15.4736, "longitude": 78.4786})
    assert ok.status_code == 201 and ok.get_json()["vehicle_number"] == "AP21-2001"
    assert c.post("/api/ambulances", json={"vehicle_number": "AP21-2001", "latitude": 15.4736, "longitude": 78.4786}).status_code == 409
    assert c.post("/api/ambulances", json={"vehicle_number": "!", "latitude": 15.4736, "longitude": 78.4786}).status_code == 400
    assert c.post("/api/ambulances", json={"vehicle_number": "AP21-2002", "latitude": 28.6, "longitude": 78.0786}).status_code == 400
    assert c.post("/api/ambulances", json={"vehicle_number": "AP21-2003"}).status_code == 400
    assert any(a["vehicle_number"] == "AP21-2001" for a in c.get("/api/ambulances").get_json())


def test_new_ambulance_can_be_dispatched():
    c = make_app().test_client()
    c.post("/api/ambulances", json={"vehicle_number": "AP21-2001", "latitude": 15.4881, "longitude": 78.4931})
    assert c.post("/api/incidents/dispatch", json=SCENE).get_json()["ambulance"] == "AP21-2001"   # right at the scene


def test_register_hospital_validation():
    c = make_app().test_client()
    ok = c.post("/api/hospitals", json={"name": "Lakeside  Clinic", "latitude": 15.4836, "longitude": 78.4786,
                                        "available_beds": 4, "specialties": "Trauma, Cardiac"})
    assert ok.status_code == 201 and ok.get_json()["specialties"] == "trauma,cardiac"
    assert ok.get_json()["name"] == "Lakeside Clinic"
    assert c.post("/api/hospitals", json={"name": "lakeside clinic", "latitude": 15.4836, "longitude": 78.4786,
                                          "available_beds": 1}).status_code == 409
    assert c.post("/api/hospitals", json={"name": "X", "latitude": 15.4836, "longitude": 78.4786, "available_beds": 1}).status_code == 400
    assert c.post("/api/hospitals", json={"name": "Bad Beds", "latitude": 15.4836, "longitude": 78.4786,
                                          "available_beds": -3}).status_code == 400


def test_hospital_diversion_is_respected_and_reversible():
    c = make_app().test_client()
    hid = [h for h in c.get("/api/hospitals").get_json() if h["name"] == "City General"][0]["hospital_id"]
    assert c.post("/api/hospitals/%d" % hid, json={"status": "DIVERSION"}).status_code == 200
    d = c.post("/api/incidents/dispatch", json=SCENE).get_json()
    assert d["hospital"] == "District Hospital" and d["specialty_match"] is False
    assert c.post("/api/hospitals/%d" % hid, json={"status": "ACTIVE", "available_beds": 30}).status_code == 200
    assert c.post("/api/incidents/dispatch", json=SCENE).get_json()["hospital"] == "City General"
    assert c.post("/api/hospitals/%d" % hid, json={"status": "CLOSED"}).status_code == 400
    assert c.post("/api/hospitals/%d" % hid, json={}).status_code == 400
    assert c.post("/api/hospitals/999", json={"status": "ACTIVE"}).status_code == 404


# ---------------------------------------------------------------- notifications, history, feedback
def test_notifications_are_role_filtered():
    app = make_app(auth=True)
    login(app, "dispatcher").post("/api/incidents/dispatch", json=SCENE)       # ambulance 2
    admin_msgs = [n["message"] for n in login(app, "admin").get("/api/notifications").get_json()]
    d2 = [n["message"] for n in login(app, "driver2").get("/api/notifications").get_json()]
    d1 = [n["message"] for n in login(app, "driver1").get("/api/notifications").get_json()]
    assert any("AP21-1002 dispatched" in m for m in admin_msgs)
    assert any("AP21-1002 dispatched" in m for m in d2)
    assert not any("AP21-1002 dispatched" in m for m in d1)


def test_road_change_is_logged_as_a_traffic_snapshot():
    app = make_app()
    c = app.test_client()
    c.post("/api/roads/traffic", json={"source": 4, "destination": 5, "traffic_level": "HEAVY"})
    c.post("/api/roads/traffic", json={"source": 5, "destination": 4, "road_condition": "CLOSED"})
    hist = c.get("/api/traffic-history").get_json()
    assert len(hist) == 2 and hist[0]["road_condition"] == "CLOSED" and hist[1]["traffic_level"] == "HEAVY"
    assert any("Road 4-5" in n["message"] for n in c.get("/api/notifications").get_json())


def test_predicted_hotspots_are_stored():
    app = make_app()
    c = app.test_client()
    assert c.get("/api/hotspots?method=dbscan").status_code == 200
    assert rows(app, "SELECT COUNT(*) FROM predicted_hotspots WHERE method='dbscan'")[0][0] == 3
    c.get("/api/hotspots?method=dbscan")                                       # re-run replaces, not duplicates
    assert rows(app, "SELECT COUNT(*) FROM predicted_hotspots WHERE method='dbscan'")[0][0] == 3


def test_completed_dispatch_feeds_the_historical_data():
    app = make_app()
    c = app.test_client()
    before = rows(app, "SELECT COUNT(*) FROM historical_calls")[0][0]
    d = c.post("/api/incidents/dispatch", json=SCENE).get_json()
    for _ in range(2):
        c.post("/api/dispatches/%d/advance" % d["dispatch_id"])
    assert rows(app, "SELECT COUNT(*) FROM historical_calls")[0][0] == before      # not finished yet
    c.post("/api/dispatches/%d/advance" % d["dispatch_id"])
    assert rows(app, "SELECT COUNT(*) FROM historical_calls")[0][0] == before + 1
    last = rows(app, "SELECT latitude, longitude, emergency_type FROM historical_calls ORDER BY call_id DESC LIMIT 1")[0]
    assert last == (15.4881, 78.4931, "accident")


# ---------------------------------------------------------------- web page
def test_dashboard_has_every_feature_from_the_brief():
    page = make_app().test_client().get("/").data.decode()
    for needle in ["/hotspot-map", 'id="method"', 'id="standby"', 'id="moves"', 'id="notes"', 'id="addAmb"',
                   'id="addHosp"', 'id="updHosp"', 'id="roadBtn"', 'id="dispatchBtn"', 'id="hourChart"',
                   "/api/reports/dispatches.csv", "Next stage", "/logout"]:
        assert needle in page, needle
