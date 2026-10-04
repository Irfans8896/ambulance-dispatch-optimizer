"""Creates a fresh demo database (schema + roads + ambulances + hospitals + history).

  python3 setup_demo.py          -> rebuilds dispatch.db (local reset)

Render's free tier loses local files on restart, so wsgi.py calls
build_demo_db() on every start: the live app always has sample data.
"""
import os
import sqlite3

from werkzeug.security import generate_password_hash

import load_calls
import seed_roads
from app.services.sample_data import make_sample_calls

BASE = os.path.dirname(os.path.abspath(__file__))

AMBULANCES = [
    ("AP21-1001", 15.4755, 78.4792),
    ("AP21-1002", 15.4836, 78.4886),
    ("AP21-1003", 15.4696, 78.4746),
]
HOSPITALS = [
    ("City General", 15.4686, 78.4736, 12, "trauma,cardiac"),
    ("District Hospital", 15.4936, 78.4986, 5, "general,pediatric"),
]


def seed_users(conn):
    """Demo accounts. Set ADMIN_PASSWORD / DISPATCHER_PASSWORD / DRIVER_PASSWORD in the environment
    (Render > Environment) to use your own passwords on the live site."""
    h = lambda pw: generate_password_hash(pw, method="pbkdf2:sha256:100000")
    admin = os.environ.get("ADMIN_PASSWORD", "admin123")
    dispatcher = os.environ.get("DISPATCHER_PASSWORD", "dispatch123")
    driver = os.environ.get("DRIVER_PASSWORD", "driver123")
    users = [("admin", h(admin), "admin", None), ("dispatcher", h(dispatcher), "dispatcher", None)]
    for i in range(1, len(AMBULANCES) + 1):                       # driver1 drives ambulance 1, ...
        users.append(("driver%d" % i, h(driver), "driver", i))
    conn.executemany("INSERT INTO users (username, password_hash, role, ambulance_id) VALUES (?,?,?,?)", users)
    conn.commit()


def build_demo_db(path):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.executescript(open(os.path.join(BASE, "schema.sql")).read())
    conn.executemany(
        "INSERT INTO ambulances (vehicle_number, latitude, longitude) VALUES (?,?,?)", AMBULANCES)
    conn.executemany(
        "INSERT INTO hospitals (name, latitude, longitude, available_beds, specialties) "
        "VALUES (?,?,?,?,?)", HOSPITALS)
    seed_roads.seed(conn)
    load_calls.load(conn, make_sample_calls())
    seed_users(conn)
    conn.close()
    return path


if __name__ == "__main__":
    from app import create_app
    p = build_demo_db(create_app().config["DATABASE"])
    print("Demo database ready:", p)
