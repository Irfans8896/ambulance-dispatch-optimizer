from .location import Location


class InvalidStatusChange(Exception):
    pass


class Ambulance:
    AVAILABLE = "AVAILABLE"
    DISPATCHED = "DISPATCHED"
    AT_SCENE = "AT_SCENE"
    TO_HOSPITAL = "TO_HOSPITAL"

    # Allowed status changes
    TRANSITIONS = {
        AVAILABLE: [DISPATCHED],
        DISPATCHED: [AT_SCENE],
        AT_SCENE: [TO_HOSPITAL],
        TO_HOSPITAL: [AVAILABLE],
    }

    def __init__(self, ambulance_id, vehicle_number, location, status=AVAILABLE):
        self.ambulance_id = ambulance_id
        self.vehicle_number = vehicle_number
        self.location = location
        self._status = status

    @property
    def status(self):
        return self._status

    def update_status(self, new_status):
        if new_status not in self.TRANSITIONS.get(self._status, []):
            raise InvalidStatusChange(f"Cannot change {self._status} -> {new_status}")
        self._status = new_status

    def is_available(self):
        return self._status == self.AVAILABLE

    def move_to(self, location):
        self.location = location

    @classmethod
    def from_row(cls, row):
        return cls(row["ambulance_id"], row["vehicle_number"],
                   Location(row["latitude"], row["longitude"]), row["status"])

    def to_dict(self):
        return {"ambulance_id": self.ambulance_id, "vehicle_number": self.vehicle_number,
                "latitude": self.location.latitude, "longitude": self.location.longitude,
                "status": self._status}

    def __repr__(self):
        return f"Ambulance({self.vehicle_number}, {self._status})"
