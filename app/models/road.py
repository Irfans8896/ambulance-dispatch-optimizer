class Road:
    TRAFFIC_FACTOR = {"LOW": 1.0, "MEDIUM": 1.5, "HEAVY": 2.5}
    CONDITION_FACTOR = {"GOOD": 1.0, "POOR": 1.4, "CLOSED": float("inf")}
    WEATHER_FACTOR = {"CLEAR": 1.0, "RAIN": 1.25, "MONSOON": 1.6, "FLOOD": 2.2}

    def __init__(self, source, destination, distance, traffic_level="LOW", road_condition="GOOD", weather="CLEAR"):
        self.source = source
        self.destination = destination
        self.distance = float(distance)
        self.traffic_level = traffic_level
        self.road_condition = road_condition
        self.weather = weather if weather in self.WEATHER_FACTOR else "CLEAR"

    def travel_weight(self):
        """Cost used by Dijkstra in Week 3 and 4 (distance x traffic x condition x weather)."""
        return (self.distance
                * self.TRAFFIC_FACTOR[self.traffic_level]
                * self.CONDITION_FACTOR[self.road_condition]
                * self.WEATHER_FACTOR.get(self.weather, 1.0))

    def is_closed(self):
        return self.road_condition == "CLOSED"

    def __repr__(self):
        return f"Road({self.source}->{self.destination}, {self.distance} km, weather={self.weather})"
