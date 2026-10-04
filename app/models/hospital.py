from .location import Location


class Hospital:
    STATUSES = ("ACTIVE", "DIVERSION")      # DIVERSION = not accepting new patients

    def __init__(self, hospital_id, name, location, available_beds, specialties=None, status="ACTIVE"):
        self.hospital_id = hospital_id
        self.name = name
        self.location = location
        self.available_beds = int(available_beds)
        self.specialties = specialties or []
        self.status = status

    def get_availability(self):
        return self.available_beds > 0 and self.status == "ACTIVE"

    def has_specialty(self, specialty):
        return specialty in self.specialties

    def admit_patient(self):
        if self.available_beds <= 0:
            raise ValueError("No beds available")
        self.available_beds -= 1

    def discharge_patient(self):
        self.available_beds += 1

    @classmethod
    def from_row(cls, row):
        specs = [s.strip() for s in (row["specialties"] or "").split(",") if s.strip()]
        return cls(row["hospital_id"], row["name"],
                   Location(row["latitude"], row["longitude"]),
                   row["available_beds"], specs,
                   row["status"] if "status" in row.keys() else "ACTIVE")

    def __repr__(self):
        return f"Hospital({self.name}, beds={self.available_beds})"
