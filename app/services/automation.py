"""What happens after something changes: re-check trips in progress, then serve the waiting queue."""
from .dispatch import process_queue
from .ops import notify
from .reroute import reroute_active_trips


def after_change(conn, reroute=True, queue=True):
    out = {"rerouted": [], "dispatched_from_queue": []}
    if reroute:
        out["rerouted"] = reroute_active_trips(conn)
    if queue:
        for d in process_queue(conn):
            row = conn.execute("SELECT ambulance_id FROM ambulances WHERE vehicle_number=?",
                               (d["ambulance"],)).fetchone()
            notify(conn, "Waiting incident #%s dispatched: %s, ETA %s min, hospital %s" % (
                d["incident_id"], d["ambulance"], d["eta_to_scene_min"], d["hospital"]),
                "ambulance:%s" % row["ambulance_id"])
            out["dispatched_from_queue"].append(
                {"dispatch_id": d["dispatch_id"], "incident_id": d["incident_id"], "ambulance": d["ambulance"]})
    return out
