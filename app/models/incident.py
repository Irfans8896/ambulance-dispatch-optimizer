from .ambulance import InvalidStatusChange


class Incident:
    REPORTED = "REPORTED"
    ASSIGNED = "ASSIGNED"
    ARRIVED = "ARRIVED"
    TRANSPORTED = "TRANSPORTED"
    COMPLETED = "COMPLETED"

    TRANSITIONS = {
        REPORTED: [ASSIGNED],
        ASSIGNED: [ARRIVED],
        ARRIVED: [TRANSPORTED],
        TRANSPORTED: [COMPLETED],
        COMPLETED: [],
    }

    def __init__(self, incident_id, location, emergency_type, severity, status=REPORTED):
        if not 1 <= int(severity) <= 5:
            raise ValueError("Severity must be between 1 and 5")
        self.incident_id = incident_id
        self.location = location
        self.emergency_type = emergency_type
        self.severity = int(severity)
        self._status = status

    @property
    def status(self):
        return self._status

    def update_status(self, new_status):
        if new_status not in self.TRANSITIONS.get(self._status, []):
            raise InvalidStatusChange(f"Cannot change {self._status} -> {new_status}")
        self._status = new_status

    def __repr__(self):
        return f"Incident({self.incident_id}, {self.emergency_type}, {self._status})"
