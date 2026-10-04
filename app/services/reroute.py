"""Live re-routing: when roads or hospitals change, every ambulance already on its way is checked again."""
import json
import sqlite3

from app.models import Hospital, Location
from .dispatch import (_service, to_minutes, NoHospitalAvailable)
from .ops import notify
from .road_graph import NoRouteError

MIN_GAIN_COST = 0.2      # weighted km (= 0.3 min): smaller improvements are not worth changing course
MIN_GAIN_SHARE = 0.05    # and the new route must be at least 5% better


def _passed_index(roads, path, progress):
    """Index of the last junction the ambulance has already passed, from its progress (0..1) along the path."""
    try:
        seg = [roads[tuple(sorted((a, b)))].distance for a, b in zip(path, path[1:])]
    except KeyError:
        return 0
    total, goal, run, idx = sum(seg), (progress or 0) * sum(seg), 0.0, 0
    for i, s in enumerate(seg):
        if run + s <= goal + 1e-9:
            run, idx = run + s, i + 1
        else:
            break
    return min(idx, max(len(path) - 1, 0))


def _cost(graph, path):
    """Cost of a path under today's conditions; None if a road on it is closed."""
    total = 0.0
    for a, b in zip(path, path[1:]):
        if not graph.graph.has_edge(a, b):
            return None
        total += graph.graph[a][b]["weight"]
    return total


def _better(graph, remaining, target):
    """(new_path, new_cost, reason) if a clearly better route exists, else (None, old_cost, None)."""
    if len(remaining) < 2 or remaining[0] == target:
        return None, 0.0, None
    try:
        new_path, new_cost, _ = graph.shortest_route(remaining[0], target)
    except NoRouteError:
        return None, None, "blocked"
    old_cost = _cost(graph, remaining)
    if old_cost is None:
        return new_path, new_cost, "a road on the route is closed"
    if new_path != remaining and new_cost < old_cost - max(MIN_GAIN_SHARE * old_cost, MIN_GAIN_COST):
        return new_path, new_cost, "a faster route is available"
    return None, old_cost, None


def reroute_active_trips(conn):
    """Check every trip in progress. Returns a list describing the trips that changed."""
    conn.row_factory = sqlite3.Row
    svc = _service(conn)
    graph, junctions = svc.graph, svc.junctions
    hospitals = [Hospital.from_row(r) for r in conn.execute("SELECT * FROM hospitals")]
    by_id = {h.hospital_id: h for h in hospitals}
    trips = conn.execute(
        """SELECT d.*, a.status AS amb_status, a.vehicle_number, i.latitude AS ilat, i.longitude AS ilon,
                  i.emergency_type FROM dispatches d
           JOIN ambulances a ON a.ambulance_id = d.ambulance_id
           JOIN incidents i ON i.incident_id = d.incident_id
           WHERE a.status != 'AVAILABLE'
             AND d.dispatch_id = (SELECT MAX(dispatch_id) FROM dispatches WHERE ambulance_id = a.ambulance_id)"""
    ).fetchall()

    changes = []
    for t in trips:
        route = json.loads(t["route"])
        stage = t["amb_status"]
        scene = svc.junction_of(Location(t["ilat"], t["ilon"]))
        hosp = by_id.get(t["hospital_id"])
        reasons, new_hospital, notes = [], None, []
        progress = t["progress"] or 0
        new_rt = t["response_time"]

        # ---- leg 1: ambulance -> scene (only while heading to the scene)
        if stage == "DISPATCHED":
            path = route["to_scene"]
            i = _passed_index(graph.roads, path, progress)
            remaining = path[i:]
            new_path, new_cost, why = _better(graph, remaining, scene)
            if why == "blocked":
                notes.append("no open route to the scene, keeping the old route")
            elif new_path:
                route["to_scene"] = new_path
                route["eta_scene_min"] = to_minutes(new_cost)
                new_rt = round(progress * t["response_time"] + to_minutes(new_cost), 1)
                progress = 0
                reasons.append(why + " on the way to the scene")

        # ---- leg 2: scene -> hospital (or the rest of it when already on the way)
        if stage == "TO_HOSPITAL":
            path = route["to_hospital"]
            i = _passed_index(graph.roads, path, progress)
            remaining, start_node = path[i:], path[i]
        else:
            remaining, start_node = route["to_hospital"], scene
        hospital_ok = hosp is not None and hosp.get_availability()
        if not hospital_ok:                                  # hospital went on diversion / has no bed
            try:
                _, new_hosp, new_path, _ = svc.select_hospital(
                    junctions[start_node], hospitals, t["emergency_type"])
                new_hospital = new_hosp
                _, cost, _ = graph.shortest_route(start_node, svc.junction_of(new_hosp.location))
                route["to_hospital"], route["eta_hospital_min"] = new_path, to_minutes(cost)
                reasons.append("%s is not accepting patients, going to %s" % (hosp.name if hosp else "hospital", new_hosp.name))
                if stage == "TO_HOSPITAL":
                    progress = 0
            except (NoHospitalAvailable, NoRouteError):
                notes.append("no other hospital can take the patient")
        else:
            target = svc.junction_of(hosp.location)
            new_path, new_cost, why = _better(graph, remaining, target)
            if why == "blocked":
                notes.append("no open route to the hospital, keeping the old route")
            elif new_path:
                route["to_hospital"], route["eta_hospital_min"] = new_path, to_minutes(new_cost)
                if stage == "TO_HOSPITAL":
                    progress = 0
                reasons.append(why + " on the way to the hospital")

        if reasons:
            conn.execute("UPDATE dispatches SET route=?, response_time=?, progress=?, reroutes=reroutes+1, "
                         "hospital_id=? WHERE dispatch_id=?",
                         (json.dumps(route), new_rt, progress,
                          new_hospital.hospital_id if new_hospital else t["hospital_id"], t["dispatch_id"]))
            conn.commit()
            eta = route["eta_scene_min"] if stage == "DISPATCHED" else route["eta_hospital_min"]
            msg = "%s rerouted (%s). New ETA %s min." % (t["vehicle_number"], "; ".join(reasons), eta)
            notify(conn, msg, "ambulance:%s" % t["ambulance_id"])
            changes.append({"dispatch_id": t["dispatch_id"], "vehicle_number": t["vehicle_number"],
                            "reason": "; ".join(reasons), "new_eta_min": eta,
                            "new_hospital": new_hospital.name if new_hospital else None})
        for n in notes:
            notify(conn, "%s: %s" % (t["vehicle_number"], n), "ambulance:%s" % t["ambulance_id"])
    return changes
