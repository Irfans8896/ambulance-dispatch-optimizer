import pytest
from app.models import Location, Ambulance, Hospital, Incident, Road, InvalidStatusChange


def test_distance_between_points():
    a = Location(14.68, 77.60)
    b = Location(14.69, 77.61)
    assert 0 < a.distance_km(b) < 3


def test_ambulance_full_cycle():
    amb = Ambulance(1, "AP21-1001", Location(14.68, 77.60))
    assert amb.is_available()
    amb.update_status(Ambulance.DISPATCHED)
    amb.update_status(Ambulance.AT_SCENE)
    amb.update_status(Ambulance.TO_HOSPITAL)
    amb.update_status(Ambulance.AVAILABLE)
    assert amb.is_available()


def test_ambulance_invalid_change():
    amb = Ambulance(1, "AP21-1001", Location(14.68, 77.60))
    with pytest.raises(InvalidStatusChange):
        amb.update_status(Ambulance.AT_SCENE)   # skipped DISPATCHED


def test_hospital_beds():
    h = Hospital(1, "City General", Location(14.67, 77.59), 1, ["trauma"])
    assert h.get_availability()
    h.admit_patient()
    assert not h.get_availability()
    with pytest.raises(ValueError):
        h.admit_patient()


def test_incident_flow_and_severity():
    inc = Incident(1, Location(14.7, 77.6), "accident", 4)
    inc.update_status(Incident.ASSIGNED)
    inc.update_status(Incident.ARRIVED)
    inc.update_status(Incident.TRANSPORTED)
    inc.update_status(Incident.COMPLETED)
    assert inc.status == Incident.COMPLETED
    with pytest.raises(ValueError):
        Incident(2, Location(14.7, 77.6), "fire", 9)


def test_road_weight_and_closure():
    r = Road(1, 2, 2.0, "HEAVY", "GOOD")
    assert r.travel_weight() == 5.0
    assert Road(1, 2, 2.0, "LOW", "CLOSED").is_closed()
