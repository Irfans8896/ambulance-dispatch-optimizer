"""Settings and automatic rush-hour traffic (optional, switched on by the administrator)."""
import sqlite3
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
RUSH_HOURS = [(8, 10), (17, 20)]          # 08:00-09:59 and 17:00-19:59 local time
STEP_UP = {"LOW": "MEDIUM", "MEDIUM": "HEAVY", "HEAVY": "HEAVY"}


def current_hour():
    return datetime.now(IST).hour


def is_rush_hour(hour=None):
    h = current_hour() if hour is None else hour
    return any(a <= h < b for a, b in RUSH_HOURS)


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
    conn.commit()


def auto_traffic_on(conn):
    return get_setting(conn, "auto_traffic", "0") == "1"


def effective_rows(conn):
    """Road rows as dicts. With automatic traffic on, every road is one level busier in rush hour.
    `base_traffic_level` is what the administrator set."""
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM road_edges")]
    bump = auto_traffic_on(conn) and is_rush_hour()
    for r in rows:
        r["base_traffic_level"] = r["traffic_level"]
        if bump:
            r["traffic_level"] = STEP_UP.get(r["traffic_level"], r["traffic_level"])
    return rows
