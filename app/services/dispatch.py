"""Week 4: dynamic routing and the complete dispatch workflow."""
import json
import sqlite3

from app.models import Ambulance, Hospital, Incident, Location, Road
from .road_graph import RoadGraph, NoRouteError
from .traffic import effective_rows

SPEED_KMPH = 40.0   # average ambulance speed on a cost-1.0 road

# Which hospital specialty each emergency type needs
SPECIALTY_FOR = {
    "accident": "trauma",
    "cardiac": "cardiac",
    "child": "pediatric",
    "pediatric": "pediatric",
}

# Hospital capability tiers (lower = more capable / critical care)
HOSPITAL_TIER = {
    "icu": 1,
    "trauma": 1,
    "cardiac": 1,
    "pediatric": 2,
    "general": 3,
    "minor": 4,
}

# Minimum hospital tier required for each severity level
# Severity 5 (fatal) needs Tier-1 (ICU/trauma/cardiac)
# Severity 1 (minor) can go to any facility
SEVERITY_MIN_TIER = {5: 1, 4: 1, 3: 2, 2: 3, 1: 4}

# When the ambulance reaches a stage, the incident reaches this stage
INCIDENT_STATUS_FOR = {
    Ambulance.AT_SCENE: Incident.ARRIVED,
    Ambulance.TO_HOSPITAL: Incident.TRANSPORTED,
    Ambulance.AVAILABLE: Incident.COMPLETED,
}


class NoAmbulanceAvailable(Exception):
    pass


class NoHospitalAvailable(Exception):
    pass


def to_minutes(cost):
    """Convert a route cost (weighted km) to minutes of travel."""
    return round(cost / SPEED_KMPH * 60, 1)


def load_junctions(conn):
    rows = conn.execute("SELECT * FROM junctions").fetchall()
    return {r["junction_id"]: Location(r["latitude"], r["longitude"]) for r in rows}


def nearest_junction(location, junctions):
    return min(junctions, key=lambda j: location.distance_km(junctions[j]))


class DispatchService:
    """Pure decision logic: no database access, easy to test."""

    def __init__(self, graph, junctions):
        self.graph = graph
        self.junctions = junctions

    def junction_of(self, location):
        return nearest_junction(location, self.junctions)

    def select_ambulance(self, incident_location, ambulances):
        """Nearest available ambulance by travel cost (not straight-line distance)."""
        target = self.junction_of(incident_location)
        options = []
        for amb in ambulances:
            if not amb.is_available():
                continue
            try:
                path, cost, _ = self.graph.shortest_route(self.junction_of(amb.location), target)
            except NoRouteError:
                continue          # this ambulance cannot reach the incident
            options.append((cost, amb, path))
        if not options:
            raise NoAmbulanceAvailable("No available ambulance can reach the incident")
        options.sort(key=lambda o: o[0])
        return options[0], options

    def select_hospital(self, incident_location, hospitals, emergency_type, severity=3):
        """Select nearest hospital that meets severity requirements and specialty match.

        Algorithm (proximity-first, severity-aware):
          1. Sort all reachable hospitals by travel cost (nearest first).
          2. Compute each hospital's best capability tier from its specialties.
          3. Filter to hospitals whose tier meets the minimum for the given severity.
          4. Among qualifying hospitals, prefer those matching the required specialty.
          5. From that pool, pick the one with the shortest travel time.
          6. If no hospital passes the tier filter, fall back to the nearest reachable one.
        """
        start = self.junction_of(incident_location)
        needed = SPECIALTY_FOR.get((emergency_type or "").lower())
        severity = max(1, min(5, int(severity or 3)))
        min_tier = SEVERITY_MIN_TIER.get(severity, 3)

        reachable = []
        for h in hospitals:
            if not h.get_availability():
                continue
            try:
                path, cost, _ = self.graph.shortest_route(start, self.junction_of(h.location))
            except NoRouteError:
                continue
            # Best (lowest) tier this hospital can provide
            specs = [s.strip().lower() for s in (h.specialties or [])]
            best_tier = min((HOSPITAL_TIER.get(s, 4) for s in specs), default=4)
            reachable.append((cost, best_tier, h, path))

        if not reachable:
            raise NoHospitalAvailable("No hospital with a free bed can be reached")

        # Step 1: sort by travel cost so nearest options come first
        reachable.sort(key=lambda r: r[0])

        # Step 2: filter by severity tier requirement
        qualifying = [r for r in reachable if r[1] <= min_tier]

        # Step 3: among qualifying, prefer specialty match for the emergency type
        if needed and qualifying:
            specialty_match = [r for r in qualifying if r[2].has_specialty(needed)]
            pool = specialty_match if specialty_match else qualifying
        else:
            pool = qualifying

        # Fallback: if no hospital meets tier requirement, use the nearest reachable one
        if not pool:
            pool = reachable

        # Step 4: pick the nearest (lowest cost) hospital from the final pool
        cost, _tier, hospital, path = min(pool, key=lambda r: r[0])
        specialty_ok = bool(needed and hospital.has_specialty(needed)) or needed is None
        return cost, hospital, path, specialty_ok

    def plan(self, incident_location, emergency_type, ambulances, hospitals, severity=3):
        (a_cost, ambulance, to_scene), options = self.select_ambulance(incident_location, ambulances)
        h_cost, hospital, to_hospital, specialty_ok = self.select_hospital(
            incident_location, hospitals, emergency_type, severity=severity)
        return {
            "ambulance": ambulance,
            "route_to_scene": to_scene,
            "eta_to_scene_min": to_minutes(a_cost),
            "hospital": hospital,
            "route_to_hospital": to_hospital,
            "eta_to_hospital_min": to_minutes(h_cost),
            "specialty_match": specialty_ok,
            "ambulance_options": [
                {"vehicle_number": o[1].vehicle_number, "eta_min": to_minutes(o[0])}
                for o in options],
        }


# ----------------------------------------------------------------- database

def _service(conn):
    conn.row_factory = sqlite3.Row
    graph = RoadGraph.from_rows(effective_rows(conn))      # includes rush-hour traffic when switched on
    return DispatchService(graph, load_junctions(conn))


def update_road_conditions(conn, source, destination, traffic_level=None, road_condition=None):
    """Simulated live traffic: change a road in the database."""
    if traffic_level and traffic_level not in Road.TRAFFIC_FACTOR:
        raise ValueError("traffic_level must be one of " + ", ".join(Road.TRAFFIC_FACTOR))
    if road_condition and road_condition not in Road.CONDITION_FACTOR:
        raise ValueError("road_condition must be one of " + ", ".join(Road.CONDITION_FACTOR))
    changed = 0
    for a, b in ((source, destination), (destination, source)):
        if traffic_level:
            changed += conn.execute(
                "UPDATE road_edges SET traffic_level=? WHERE source=? AND destination=?",
                (traffic_level, a, b)).rowcount
        if road_condition:
            changed += conn.execute(
                "UPDATE road_edges SET road_condition=? WHERE source=? AND destination=?",
                (road_condition, a, b)).rowcount
    conn.commit()
    if not changed:
        raise ValueError("No such road")
    return changed


def dispatch_incident(conn, latitude, longitude, emergency_type, severity):
    """Report an emergency, pick ambulance and hospital, store the dispatch.

    The call is stored first. If nobody can respond right now it stays REPORTED
    (= waiting in the queue) and the error carries the incident id."""
    conn.row_factory = sqlite3.Row
    location = Location(latitude, longitude)
    incident = Incident(None, location, emergency_type, severity)   # validates severity

    cur = conn.execute(
        "INSERT INTO incidents (latitude, longitude, emergency_type, severity) VALUES (?,?,?,?)",
        (location.latitude, location.longitude, emergency_type, incident.severity))
    incident.incident_id = cur.lastrowid
    conn.commit()                       # the call is recorded even if nobody can respond
    return _assign(conn, incident)


def _assign(conn, incident):
    location = incident.location
    ambulances = [Ambulance.from_row(r) for r in conn.execute("SELECT * FROM ambulances")]
    hospitals = [Hospital.from_row(r) for r in conn.execute("SELECT * FROM hospitals")]
    try:
        plan = _service(conn).plan(location, incident.emergency_type, ambulances, hospitals, severity=incident.severity)
    except (NoAmbulanceAvailable, NoHospitalAvailable) as e:
        e.incident_id = incident.incident_id
        raise

    amb, hosp = plan["ambulance"], plan["hospital"]
    amb.update_status(Ambulance.DISPATCHED)
    incident.update_status(Incident.ASSIGNED)
    conn.execute("UPDATE ambulances SET status=? WHERE ambulance_id=?",
                 (amb.status, amb.ambulance_id))
    conn.execute("UPDATE incidents SET status=? WHERE incident_id=?",
                 (incident.status, incident.incident_id))
    route = json.dumps({"to_scene": plan["route_to_scene"],
                        "to_hospital": plan["route_to_hospital"],
                        "eta_scene_min": plan["eta_to_scene_min"],
                        "eta_hospital_min": plan["eta_to_hospital_min"]})
    cur = conn.execute(
        "INSERT INTO dispatches (ambulance_id, incident_id, hospital_id, route, response_time) "
        "VALUES (?,?,?,?,?)",
        (amb.ambulance_id, incident.incident_id, hosp.hospital_id, route,
         plan["eta_to_scene_min"]))
    conn.commit()

    return {
        "dispatch_id": cur.lastrowid,
        "incident_id": incident.incident_id,
        "ambulance": amb.vehicle_number,
        "hospital": hosp.name,
        "route_to_scene": plan["route_to_scene"],
        "route_to_hospital": plan["route_to_hospital"],
        "eta_to_scene_min": plan["eta_to_scene_min"],
        "eta_to_hospital_min": plan["eta_to_hospital_min"],
        "specialty_match": plan["specialty_match"],
        "ambulance_options": plan["ambulance_options"],
    }


# ----------------------------------------------------------------- waiting queue

def queued_incidents(conn):
    """Incidents still waiting for an ambulance: most severe first, then first come first served."""
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT * FROM incidents i WHERE i.status='REPORTED' AND NOT EXISTS "
        "(SELECT 1 FROM dispatches d WHERE d.incident_id = i.incident_id) "
        "ORDER BY i.severity DESC, i.call_time ASC, i.incident_id ASC").fetchall()


def process_queue(conn):
    """Try to dispatch every waiting incident (called whenever something changes). Returns the dispatches made."""
    made = []
    for row in queued_incidents(conn):
        incident = Incident(row["incident_id"], Location(row["latitude"], row["longitude"]),
                            row["emergency_type"], row["severity"])
        try:
            made.append(_assign(conn, incident))
        except (NoAmbulanceAvailable, NoHospitalAvailable):
            continue                    # this one still cannot be served; a less severe one maybe can
    return made


def advance_dispatch(conn, dispatch_id):
    """Move a dispatch to its next stage (driver/dispatcher button)."""
    conn.row_factory = sqlite3.Row
    d = conn.execute("SELECT * FROM dispatches WHERE dispatch_id=?", (dispatch_id,)).fetchone()
    if d is None:
        raise ValueError("No such dispatch")
    amb = Ambulance.from_row(conn.execute(
        "SELECT * FROM ambulances WHERE ambulance_id=?", (d["ambulance_id"],)).fetchone())
    if amb.status == Ambulance.AVAILABLE:
        raise ValueError("This dispatch is already completed")

    new_status = Ambulance.TRANSITIONS[amb.status][0]
    amb.update_status(new_status)                       # validated by the model
    conn.execute("UPDATE ambulances SET status=? WHERE ambulance_id=?",
                 (new_status, amb.ambulance_id))
    conn.execute("UPDATE incidents SET status=? WHERE incident_id=?",
                 (INCIDENT_STATUS_FOR[new_status], d["incident_id"]))

    conn.execute("UPDATE dispatches SET progress=0 WHERE dispatch_id=?", (dispatch_id,))   # new leg starts
    if new_status == Ambulance.AVAILABLE:               # patient handed over
        h = conn.execute("SELECT * FROM hospitals WHERE hospital_id=?",
                         (d["hospital_id"],)).fetchone()
        conn.execute("UPDATE hospitals SET available_beds = available_beds - 1 "
                     "WHERE hospital_id=? AND available_beds > 0", (d["hospital_id"],))
        conn.execute("UPDATE ambulances SET latitude=?, longitude=? WHERE ambulance_id=?",
                     (h["latitude"], h["longitude"], amb.ambulance_id))
    conn.commit()
    return {"dispatch_id": dispatch_id, "ambulance_status": new_status,
            "incident_status": INCIDENT_STATUS_FOR[new_status]}


def update_dispatch_severity(conn, dispatch_id, new_severity):
    """Driver or dispatcher updates the triage severity for an active incident."""
    conn.row_factory = sqlite3.Row
    d = conn.execute(
        """SELECT d.dispatch_id, d.incident_id, d.hospital_id, d.ambulance_id,
                  i.severity AS old_severity, i.emergency_type, a.status AS ambulance_status,
                  a.vehicle_number
           FROM dispatches d
           JOIN incidents i ON i.incident_id = d.incident_id
           JOIN ambulances a ON a.ambulance_id = d.ambulance_id
           WHERE d.dispatch_id = ?""", (dispatch_id,)).fetchone()
    if d is None:
        raise ValueError("No such dispatch")
    if d["ambulance_status"] == Ambulance.AVAILABLE:
        raise ValueError("This dispatch is already completed")
    try:
        val = int(new_severity)
    except (TypeError, ValueError):
        raise ValueError("Severity must be an integer between 1 and 5")
    if not 1 <= val <= 5:
        raise ValueError("Severity must be between 1 and 5")

    conn.execute("UPDATE incidents SET severity=? WHERE incident_id=?", (val, d["incident_id"]))
    conn.commit()
    return {
        "dispatch_id": dispatch_id,
        "incident_id": d["incident_id"],
        "vehicle_number": d["vehicle_number"],
        "ambulance_id": d["ambulance_id"],
        "old_severity": d["old_severity"],
        "new_severity": val,
    }


def get_hospital_options_for_dispatch(conn, dispatch_id):
    """List all available hospitals with estimated ETA and compatibility for this dispatch."""
    conn.row_factory = sqlite3.Row
    d = conn.execute(
        """SELECT d.*, i.latitude AS ilat, i.longitude AS ilon, i.emergency_type, i.severity,
                  a.status AS amb_status, a.latitude AS alat, a.longitude AS alon
           FROM dispatches d
           JOIN incidents i ON i.incident_id = d.incident_id
           JOIN ambulances a ON a.ambulance_id = d.ambulance_id
           WHERE d.dispatch_id = ?""", (dispatch_id,)).fetchone()
    if d is None:
        raise ValueError("No such dispatch")

    svc = _service(conn)
    graph = svc.graph
    needed = SPECIALTY_FOR.get((d["emergency_type"] or "").lower())
    severity = max(1, min(5, int(d["severity"] or 3)))
    min_tier = SEVERITY_MIN_TIER.get(severity, 3)

    route = json.loads(d["route"]) if d["route"] else {}
    if d["amb_status"] == Ambulance.TO_HOSPITAL and "to_hospital" in route:
        from .reroute import _passed_index
        path = route["to_hospital"]
        idx = _passed_index(graph.roads, path, d["progress"] or 0)
        start_junction = path[idx] if idx < len(path) else path[-1]
    else:
        start_junction = svc.junction_of(Location(d["ilat"], d["ilon"]))

    hospitals = [Hospital.from_row(r) for r in conn.execute("SELECT * FROM hospitals").fetchall()]
    options = []
    for h in hospitals:
        specs = [s.strip().lower() for s in (h.specialties or [])]
        best_tier = min((HOSPITAL_TIER.get(s, 4) for s in specs), default=4)
        target_junc = svc.junction_of(h.location)
        try:
            path, cost, _ = graph.shortest_route(start_junction, target_junc)
            reachable = True
            eta_min = to_minutes(cost)
        except NoRouteError:
            path, cost, reachable, eta_min = [], float("inf"), False, None

        options.append({
            "hospital_id": h.hospital_id,
            "name": h.name,
            "available_beds": h.available_beds,
            "status": h.status,
            "specialties": h.specialties,
            "tier": best_tier,
            "tier_qualified": best_tier <= min_tier,
            "specialty_match": bool(needed and h.has_specialty(needed)) or (needed is None),
            "reachable": reachable,
            "eta_min": eta_min,
            "route": path,
            "is_current": (h.hospital_id == d["hospital_id"]),
            "is_available": h.get_availability(),
        })

    # Sort options: current first, then available, then reachable, then qualified, then ETA
    options.sort(key=lambda x: (
        not x["is_current"],
        not x["is_available"],
        not x["reachable"],
        not x["tier_qualified"],
        x["eta_min"] if x["eta_min"] is not None else 9999
    ))
    return options


def update_dispatch_hospital(conn, dispatch_id, new_hospital_id):
    """Change destination hospital for an active dispatch and recompute the route."""
    conn.row_factory = sqlite3.Row
    d = conn.execute(
        """SELECT d.*, i.latitude AS ilat, i.longitude AS ilon, i.emergency_type, i.severity,
                  a.status AS amb_status, a.vehicle_number, a.ambulance_id,
                  h.name AS old_hospital_name
           FROM dispatches d
           JOIN incidents i ON i.incident_id = d.incident_id
           JOIN ambulances a ON a.ambulance_id = d.ambulance_id
           JOIN hospitals h ON h.hospital_id = d.hospital_id
           WHERE d.dispatch_id = ?""", (dispatch_id,)).fetchone()
    if d is None:
        raise ValueError("No such dispatch")
    if d["amb_status"] == Ambulance.AVAILABLE:
        raise ValueError("This dispatch is already completed")

    target_hosp_row = conn.execute("SELECT * FROM hospitals WHERE hospital_id = ?", (new_hospital_id,)).fetchone()
    if not target_hosp_row:
        raise ValueError("Hospital not found")
    new_hosp = Hospital.from_row(target_hosp_row)
    if not new_hosp.get_availability():
        raise ValueError("Hospital '%s' is not accepting patients (no beds or on diversion)" % new_hosp.name)

    svc = _service(conn)
    graph = svc.graph
    route = json.loads(d["route"]) if d["route"] else {}

    if d["amb_status"] == Ambulance.TO_HOSPITAL and "to_hospital" in route:
        from .reroute import _passed_index
        path = route["to_hospital"]
        idx = _passed_index(graph.roads, path, d["progress"] or 0)
        start_junction = path[idx] if idx < len(path) else path[-1]
    else:
        start_junction = svc.junction_of(Location(d["ilat"], d["ilon"]))

    target_junction = svc.junction_of(new_hosp.location)
    try:
        new_path, cost, _ = graph.shortest_route(start_junction, target_junction)
    except NoRouteError:
        raise ValueError("No open road route from current location to %s" % new_hosp.name)

    route["to_hospital"] = new_path
    route["eta_hospital_min"] = to_minutes(cost)
    new_progress = 0 if d["amb_status"] == Ambulance.TO_HOSPITAL else (d["progress"] or 0)

    conn.execute(
        "UPDATE dispatches SET hospital_id=?, route=?, progress=?, reroutes=reroutes+1 WHERE dispatch_id=?",
        (new_hospital_id, json.dumps(route), new_progress, dispatch_id)
    )
    conn.commit()

    return {
        "dispatch_id": dispatch_id,
        "old_hospital": d["old_hospital_name"],
        "new_hospital": new_hosp.name,
        "hospital_id": new_hospital_id,
        "route_to_hospital": new_path,
        "eta_hospital_min": route["eta_hospital_min"],
        "vehicle_number": d["vehicle_number"],
        "ambulance_id": d["ambulance_id"],
    }
