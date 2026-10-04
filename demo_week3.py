from app.models import Road
from app.services import RoadGraph, NoRouteError

# City map: junctions 1 to 6, roads (distance in km)
#   1-2: 2   1-3: 4   2-3: 1   2-4: 5   3-4: 3
#   3-5: 6   4-5: 2   4-6: 4   5-6: 1
ROADS = [
    (1, 2, 2.0), (1, 3, 4.0), (2, 3, 1.0), (2, 4, 5.0), (3, 4, 3.0),
    (3, 5, 6.0), (4, 5, 2.0), (4, 6, 4.0), (5, 6, 1.0),
]

city = RoadGraph()
for a, b, km in ROADS:
    city.add_road(Road(a, b, km))

path, cost, km = city.shortest_route(1, 6)
print("Route 1 -> 6:", " -> ".join(map(str, path)))
print("Total distance: %.1f km, travel cost: %.1f" % (km, cost))

print("\n--- Heavy traffic on road 3-4 ---")
city.update_road(3, 4, traffic_level="HEAVY")
path, cost, km = city.shortest_route(1, 6)
print("Route 1 -> 6:", " -> ".join(map(str, path)))
print("Total distance: %.1f km, travel cost: %.1f" % (km, cost))

print("\n--- Road 4-5 closed ---")
city.update_road(4, 5, road_condition="CLOSED")
path, cost, km = city.shortest_route(1, 6)
print("Route 1 -> 6:", " -> ".join(map(str, path)))
print("Total distance: %.1f km, travel cost: %.1f" % (km, cost))

print("\n--- Every road into junction 6 closed ---")
city.update_road(4, 6, road_condition="CLOSED")
city.update_road(5, 6, road_condition="CLOSED")
try:
    city.shortest_route(1, 6)
except NoRouteError as e:
    print("No route:", e)
