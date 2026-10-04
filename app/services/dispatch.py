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

    def select_hospital(self, incident_location, hospitals, emergency_type):
        """Closest hospital with a free bed, preferring the needed specialty."""
        start = self.junction_of(incident_location)
        needed = SPECIALTY_FOR.get((emergency_type or "").lower())
        reachable = []
        for h in hospitals:
            if not h.get_availability():
                continue
            try:
                path, cost, _ = self.graph.shortest_route(start, self.junction_of(h.location))
            except NoRouteError:
                continue
            reachable.append((cost, h, path))
        if not reachable:
            raise NoHospitalAvailable("No hospital with a free bed can be reached")
        matching = [r for r in reachable if needed and r[1].has_specialty(needed)]
        pool = matching if matching else reachable
        cost, hospital, path = min(pool, key=lambda r: r[0])
        return cost, hospital, path, bool(matching) or needed is None

    def plan(self, incident_location, emergency_type, ambulances, hospitals):
        (a_cost, ambulance, to_scene), options = self.select_ambulance(incident_location, ambulances)
        h_cost, hospital, to_hospital, specialty_ok = self.select_hospital(
            incident_location, hospitals, emergency_type)
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
        plan = _service(conn).plan(location, incident.emergency_type, ambulances, hospitals)
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
