import heapq

import networkx as nx

from app.models import Road


class NoRouteError(Exception):
    """Raised when no route exists between two junctions."""


def dijkstra(graph, source, target, weight="weight"):
    """Dijkstra's shortest-path algorithm (written by hand).

    graph  : a networkx graph whose edges carry a numeric `weight`
    returns: (path as list of nodes, total cost)
    """
    if source not in graph or target not in graph:
        raise NoRouteError(f"Unknown junction: {source} or {target}")

    dist = {source: 0.0}
    previous = {}
    visited = set()
    heap = [(0.0, source)]          # (cost so far, node)

    while heap:
        cost, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == target:
            break
        for neighbour, data in graph[node].items():
            if neighbour in visited:
                continue
            new_cost = cost + data[weight]
            if new_cost < dist.get(neighbour, float("inf")):
                dist[neighbour] = new_cost
                previous[neighbour] = node
                heapq.heappush(heap, (new_cost, neighbour))

    if target not in dist:
        raise NoRouteError(f"No route from {source} to {target}")

    # Rebuild the path by walking backwards from the target
    path = [target]
    while path[-1] != source:
        path.append(previous[path[-1]])
    path.reverse()
    return path, dist[target]


class RoadGraph:
    """City road network: junctions are nodes, roads are weighted edges."""

    def __init__(self):
        self.graph = nx.Graph()      # roads are two-way
        self.roads = {}              # (a, b) -> Road

    def add_road(self, road):
        key = tuple(sorted((road.source, road.destination)))
        self.roads[key] = road
        self._refresh_edge(key)

    def _refresh_edge(self, key):
        road = self.roads[key]
        a, b = key
        if road.is_closed():
            if self.graph.has_edge(a, b):
                self.graph.remove_edge(a, b)
            self.graph.add_node(a)
            self.graph.add_node(b)
        else:
            self.graph.add_edge(a, b, weight=road.travel_weight(),
                                distance=road.distance)

    def update_road(self, source, destination, traffic_level=None, road_condition=None):
        """Used in Week 4 for live traffic. Rebuilds the edge weight."""
        key = tuple(sorted((source, destination)))
        road = self.roads[key]
        if traffic_level:
            road.traffic_level = traffic_level
        if road_condition:
            road.road_condition = road_condition
        self._refresh_edge(key)

    def shortest_route(self, source, target):
        """Return (path, total_weight, total_distance_km)."""
        path, cost = dijkstra(self.graph, source, target)
        distance = sum(self.graph[a][b]["distance"] for a, b in zip(path, path[1:]))
        return path, cost, distance

    @classmethod
    def from_rows(cls, rows):
        """Build from database rows of the road_edges table."""
        g = cls()
        for r in rows:
            g.add_road(Road(r["source"], r["destination"], r["distance"],
                            r["traffic_level"], r["road_condition"]))
        return g
