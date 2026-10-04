import math


class Location:
    """A point on the map (latitude, longitude)."""

    def __init__(self, latitude, longitude):
        self.latitude = float(latitude)
        self.longitude = float(longitude)

    def distance_km(self, other):
        """Straight-line (haversine) distance in kilometres."""
        r = 6371.0
        lat1, lat2 = math.radians(self.latitude), math.radians(other.latitude)
        dlat = lat2 - lat1
        dlon = math.radians(other.longitude - self.longitude)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    def __repr__(self):
        return f"Location({self.latitude}, {self.longitude})"
