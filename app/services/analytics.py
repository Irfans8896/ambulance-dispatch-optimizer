"""Analytics from the dispatch history, plus a demo-data generator."""
import random
import statistics
from datetime import datetime, timedelta, timezone

from .dispatch import dispatch_incident, advance_dispatch, NoAmbulanceAvailable, NoHospitalAvailable, queued_incidents
from .sample_data import CENTRES

TARGET_MIN = 8.0                       # response-time target shown on the page
IST = timezone(timedelta(hours=5, minutes=30))


def build(conn):
    rows = [dict(r) for r in conn.execute(
        """SELECT d.dispatch_id, d.response_time, d.reroutes, a.vehicle_number, h.name AS hospital,
                  i.emergency_type, i.severity, i.status, i.call_time
           FROM dispatches d JOIN ambulances a ON a.ambulance_id = d.ambulance_id
           JOIN hospitals h ON h.hospital_id = d.hospital_id
           JOIN incidents i ON i.incident_id = d.incident_id ORDER BY d.dispatch_id""")]
    etas = [r["response_time"] for r in rows if r["response_time"] is not None]

    def count(key):
        out = {}
        for r in rows:
            out[str(r[key])] = out.get(str(r[key]), 0) + 1
        return out

    per_amb = {}
    for r in rows:
        a = per_amb.setdefault(r["vehicle_number"], {"vehicle_number": r["vehicle_number"], "trips": 0, "eta_sum": 0.0})
        a["trips"] += 1
        a["eta_sum"] += r["response_time"] or 0
    by_hour = [0] * 24
    for r in conn.execute("SELECT call_time FROM incidents"):
        try:
            utc = datetime.strptime(r["call_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            by_hour[utc.astimezone(IST).hour] += 1
        except (TypeError, ValueError):
            pass
    return {
        "totals": {
            "dispatches": len(rows),
            "completed": sum(1 for r in rows if r["status"] == "COMPLETED"),
            "active": sum(1 for r in rows if r["status"] not in ("COMPLETED",)),
            "queued": len(queued_incidents(conn)),
            "reroutes": sum(r["reroutes"] for r in rows),
            "avg_eta_min": round(statistics.mean(etas), 1) if etas else None,
            "median_eta_min": round(statistics.median(etas), 1) if etas else None,
            "max_eta_min": round(max(etas), 1) if etas else None,
            "within_target_pct": round(100 * sum(1 for e in etas if e <= TARGET_MIN) / len(etas), 1) if etas else None,
            "target_min": TARGET_MIN,
        },
        "by_type": count("emergency_type"),
        "by_severity": {str(s): sum(1 for r in rows if r["severity"] == s) for s in range(1, 6)},
        "by_hospital": count("hospital"),
        "per_ambulance": [{"vehicle_number": a["vehicle_number"], "trips": a["trips"],
                           "avg_eta_min": round(a["eta_sum"] / a["trips"], 1)} for a in per_amb.values()],
        "by_hour": by_hour,
        "eta_series": [{"dispatch_id": r["dispatch_id"], "eta_min": r["response_time"]} for r in rows[-25:]],
    }


def simulate(conn, count=10, seed=None):
    """DEMO DATA: create and complete `count` random emergencies so the analytics have something to show.
    Hospital beds are put back afterwards and the incidents get call times spread over the last 3 days."""
    rng = random.Random(seed)
    beds = conn.execute("SELECT hospital_id, available_beds FROM hospitals").fetchall()
    homes = conn.execute("SELECT ambulance_id, latitude, longitude FROM ambulances").fetchall()
    made = skipped = 0
    for _ in range(count):
        lat0, lon0, _, types, _ = rng.choice(CENTRES)
        etype = rng.choices(list(types), list(types.values()))[0]
        try:
            d = dispatch_incident(conn, rng.gauss(lat0, 0.006), rng.gauss(lon0, 0.006), etype, rng.randint(1, 5))
        except (NoAmbulanceAvailable, NoHospitalAvailable):
            skipped += 1
            continue
        for _ in range(3):
            advance_dispatch(conn, d["dispatch_id"])
        conn.execute("UPDATE incidents SET call_time = datetime('now', ?) WHERE incident_id=?",
                     ("-%d minutes" % rng.randint(0, 3 * 24 * 60), d["incident_id"]))
        made += 1
        for aid, la, lo in homes:                       # ambulances go back to their bases for the next call
            conn.execute("UPDATE ambulances SET latitude=?, longitude=? WHERE ambulance_id=?", (la, lo, aid))
    for hid, b in beds:
        conn.execute("UPDATE hospitals SET available_beds=? WHERE hospital_id=?", (b, hid))
    conn.commit()
    return {"created": made, "skipped": skipped}
