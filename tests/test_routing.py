import networkx as nx
import pytest

from app.models import Road
from app.services import RoadGraph, NoRouteError, dijkstra

ROADS = [
    (1, 2, 2.0), (1, 3, 4.0), (2, 3, 1.0), (2, 4, 5.0), (3, 4, 3.0),
    (3, 5, 6.0), (4, 5, 2.0), (4, 6, 4.0), (5, 6, 1.0),
]


def make_city():
    city = RoadGraph()
    for a, b, km in ROADS:
        city.add_road(Road(a, b, km))
    return city


def test_shortest_path_known_answer():
    path, cost, km = make_city().shortest_route(1, 6)
    assert path == [1, 2, 3, 4, 5, 6]
    assert cost == 9.0
    assert km == 9.0


def test_same_junction_is_zero():
    path, cost, km = make_city().shortest_route(3, 3)
    assert path == [3] and cost == 0


def test_matches_networkx_reference():
    city = make_city()
    for target in range(2, 7):
        _, cost = dijkstra(city.graph, 1, target)
        assert cost == nx.dijkstra_path_length(city.graph, 1, target, weight="weight")


def test_heavy_traffic_changes_route():
    city = make_city()
    city.update_road(3, 4, traffic_level="HEAVY")
    path, cost, km = city.shortest_route(1, 6)
    assert path == [1, 2, 3, 5, 6]
    assert cost == 10.0


def test_closed_road_is_avoided():
    city = make_city()
    city.update_road(4, 5, road_condition="CLOSED")
    path, _, _ = city.shortest_route(1, 6)
    assert (4, 5) not in list(zip(path, path[1:]))
    assert (5, 4) not in list(zip(path, path[1:]))


def test_no_route_raises():
    city = make_city()
    city.update_road(4, 6, road_condition="CLOSED")
    city.update_road(5, 6, road_condition="CLOSED")
    with pytest.raises(NoRouteError):
        city.shortest_route(1, 6)


def test_unknown_junction_raises():
    with pytest.raises(NoRouteError):
        make_city().shortest_route(1, 99)
