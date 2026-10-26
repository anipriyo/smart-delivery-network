"""Real road routing on the OpenStreetMap road network of the Kalyani region.

The road graph (data/<month>/roads.npz) has one node per OSM road node and
one edge per consecutive pair of nodes on a drivable way. Two vehicles are
modelled:

* ``bike`` (two-wheeler): every road plus the Hooghly ferries
* ``van`` (delivery van): every road, no ferries (Ishwar Gupta Setu is a road
  bridge, so vans still cross the river there)

Shortest paths use Dijkstra's algorithm (scipy.sparse.csgraph), either by
length (km) or by travel time (minutes, from a speed per road class). Each
place is snapped to its nearest road node with a KD-tree. The visiting order
of several stops is exact for up to ``EXACT_LIMIT`` stops (Held-Karp dynamic
programming over subsets, O(2^k k^2)); above that it uses nearest neighbour
followed by 2-opt improvement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

from .geo import LocalProjection
from .river import Crossing

VEHICLES = {"bike": "Two-wheeler", "van": "Delivery van"}
# km/h by OSM highway class
SPEED = {
    "bike": {"motorway": 45, "trunk": 40, "primary": 35, "secondary": 30, "tertiary": 28, "unclassified": 25,
             "residential": 22, "living_street": 15, "service": 15, "road": 20},
    "van": {"motorway": 55, "trunk": 45, "primary": 38, "secondary": 32, "tertiary": 28, "unclassified": 24,
            "residential": 18, "living_street": 12, "service": 12, "road": 18},
}
FERRY_WAIT_MIN = 10.0  # average wait at the ghat
FERRY_KMH = 8.0
SERVICE_MIN = 3.0  # time spent at each stop handing over the parcel
WALK_KMH = 5.0  # from the nearest road node to the door
EXACT_LIMIT = 10


def _class_speed(cls_name: str, vehicle: str) -> float:
    base = cls_name.replace("_link", "")
    return SPEED[vehicle].get(base, 18)


@dataclass
class Leg:
    start: int  # stop index in the route (0 = depot)
    end: int
    nodes: list[int]
    km: float
    minutes: float
    roads: list[str]  # named roads used, in order


@dataclass
class Route:
    vehicle: str
    depot: int  # index into the candidate depots
    order: list[int]  # visiting order as indices into the stop list
    legs: list[Leg]
    km: float
    minutes: float
    method: str


class RoadGraph:
    def __init__(self, npz_path: Path, projection: LocalProjection, crossings: list[Crossing] | None = None):
        d = np.load(npz_path, allow_pickle=False)
        self.lat, self.lon = d["lat"], d["lon"]
        self.x, self.y = projection.to_xy(self.lat, self.lon)
        self.x, self.y = np.asarray(self.x), np.asarray(self.y)
        u, v = d["u"].astype(np.int64), d["v"].astype(np.int64)
        km = d["length_m"].astype(np.float64) / 1000.0
        self.classes = [str(c) for c in d["classes"]]
        self.names = [str(n) for n in d["names"]]
        self.edge_cls, self.edge_name = d["cls"], d["name"]
        self.u, self.v, self.km = u, v, km
        n = len(self.lat)
        self.n = n

        # optional ferry edges (two-wheeler only): nearest road nodes at each landing
        tree_all = cKDTree(np.c_[self.x, self.y])
        fu, fv, fkm, fmin, self.ferries = [], [], [], [], []
        for c in crossings or []:
            if c.kind != "ferry":
                continue
            _, a = tree_all.query(c.a)
            _, b = tree_all.query(c.b)
            fu.append(a); fv.append(b); fkm.append(c.length)
            fmin.append(FERRY_WAIT_MIN + c.length / FERRY_KMH * 60)
            self.ferries.append((int(a), int(b), c.name))

        self.graphs: dict[tuple[str, str], object] = {}
        for vehicle in VEHICLES:
            speed = np.array([_class_speed(self.classes[c], vehicle) for c in self.edge_cls])
            minutes = km / speed * 60.0
            eu, ev, ekm, emin = u, v, km, minutes
            if vehicle == "bike" and fu:
                eu = np.r_[u, fu]; ev = np.r_[v, fv]
                ekm = np.r_[km, fkm]; emin = np.r_[minutes, fmin]
            for metric, w in (("km", ekm), ("min", emin)):
                w = np.maximum(w, 1e-6)  # csgraph drops explicit zeros
                g = coo_matrix((np.r_[w, w], (np.r_[eu, ev], np.r_[ev, eu])), shape=(n, n)).tocsr()
                g.sum_duplicates()
                self.graphs[(vehicle, metric)] = g
        # snap only to the largest connected part of the van network (every vehicle can reach it)
        _, labels = connected_components(self.graphs[("van", "km")], directed=False)
        main = np.argmax(np.bincount(labels))
        self.main_nodes = np.nonzero(labels == main)[0]
        self.tree = cKDTree(np.c_[self.x[self.main_nodes], self.y[self.main_nodes]])
        self._km_lookup = self.graphs[("bike", "km")]
        self._edge_name = {}
        for a, b, nm in zip(u.tolist(), v.tolist(), self.edge_name.tolist()):
            self._edge_name[(a, b) if a < b else (b, a)] = nm

    # -------------------------------------------------------------- basics

    def snap(self, xs, ys) -> tuple[np.ndarray, np.ndarray]:
        """Nearest connected road node for each point, and the straight gap (km) to it."""
        dist, i = self.tree.query(np.c_[np.atleast_1d(xs), np.atleast_1d(ys)])
        return self.main_nodes[i], dist

    def from_sources(self, nodes, vehicle: str, metric: str, predecessors: bool = False):
        """Dijkstra from each source node to every node."""
        return dijkstra(self.graphs[(vehicle, metric)], directed=False, indices=np.asarray(nodes),
                        return_predecessors=predecessors)

    def path(self, pred_row: np.ndarray, target: int) -> list[int]:
        out = [int(target)]
        while pred_row[out[-1]] >= 0:
            out.append(int(pred_row[out[-1]]))
        return out[::-1]

    def path_km(self, nodes: list[int]) -> float:
        if len(nodes) < 2:
            return 0.0
        a, b = np.array(nodes[:-1]), np.array(nodes[1:])
        return float(np.asarray(self._km_lookup[a, b]).ravel().sum())

    def path_roads(self, nodes: list[int]) -> list[str]:
        """Names of the roads a path follows, in order, without repeats."""
        out: list[str] = []
        for a, b in zip(nodes, nodes[1:]):
            nm = self._edge_name.get((a, b) if a < b else (b, a), 0)
            name = self.names[nm] if nm else ""
            if name and (not out or out[-1] != name):
                out.append(name)
        return out

    MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary",
             "secondary_link", "tertiary", "tertiary_link", "unclassified"}

    def major_runs(self) -> list[np.ndarray]:
        """Main-road edges grouped into chains (consecutive edges of one way), for drawing."""
        if getattr(self, "_runs", None) is None:
            major = np.array([self.classes[c] in self.MAJOR for c in self.edge_cls])
            idx = np.nonzero(major)[0]
            runs, cur = [], [idx[0]] if len(idx) else []
            for a, b in zip(idx[:-1], idx[1:]):
                if b == a + 1 and self.v[a] == self.u[b] and self.edge_cls[a] == self.edge_cls[b]:
                    cur.append(b)
                else:
                    runs.append(np.array(cur)); cur = [b]
            if cur:
                runs.append(np.array(cur))
            self._runs = runs
        return self._runs

    def coords(self, nodes: list[int]) -> list[list[float]]:
        return [[float(self.lon[i]), float(self.lat[i])] for i in nodes]


# ------------------------------------------------------------------ visiting order

def held_karp(cost: np.ndarray, closed: bool) -> tuple[list[int], float]:
    """Exact order of stops 1..k starting from 0 (dynamic programming over subsets).

    ``cost`` is a (k+1) x (k+1) matrix, node 0 is the depot. With ``closed``
    the tour returns to the depot.
    """
    k = cost.shape[0] - 1
    if k == 0:
        return [], 0.0
    full = (1 << k) - 1
    best: dict[tuple[int, int], tuple[float, int]] = {}
    for j in range(k):
        best[(1 << j, j)] = (cost[0, j + 1], -1)
    for mask in range(1, full + 1):
        for j in range(k):
            if not mask & (1 << j) or (mask, j) not in best:
                continue
            c, _ = best[(mask, j)]
            for nxt in range(k):
                if mask & (1 << nxt):
                    continue
                m2 = mask | (1 << nxt)
                c2 = c + cost[j + 1, nxt + 1]
                if c2 < best.get((m2, nxt), (math.inf, -1))[0]:
                    best[(m2, nxt)] = (c2, j)
    end, total = min(((j, best[(full, j)][0] + (cost[j + 1, 0] if closed else 0.0)) for j in range(k)),
                     key=lambda t: t[1])
    order, mask, j = [], full, end
    while j != -1:
        order.append(j)
        _, prev = best[(mask, j)]
        mask ^= 1 << j
        j = prev
    return order[::-1], total


def tour_cost(order: list[int], cost: np.ndarray, closed: bool) -> float:
    seq = [0] + [o + 1 for o in order] + ([0] if closed else [])
    return float(sum(cost[a, b] for a, b in zip(seq, seq[1:])))


def nearest_neighbour_2opt(cost: np.ndarray, closed: bool) -> tuple[list[int], float]:
    """Greedy nearest-neighbour order, then 2-opt segment reversals until no gain."""
    k = cost.shape[0] - 1
    left, cur, order = set(range(k)), 0, []
    while left:
        nxt = min(left, key=lambda j: cost[cur, j + 1])
        order.append(nxt)
        left.remove(nxt)
        cur = nxt + 1
    best = tour_cost(order, cost, closed)
    improved = True
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                c = tour_cost(cand, cost, closed)
                if c < best - 1e-9:
                    order, best, improved = cand, c, True
    return order, best


def brute_force_order(cost: np.ndarray, closed: bool) -> tuple[list[int], float]:
    k = cost.shape[0] - 1
    best = min((list(p) for p in permutations(range(k))), key=lambda o: tour_cost(o, cost, closed))
    return best, tour_cost(best, cost, closed)


def best_order(cost: np.ndarray, closed: bool) -> tuple[list[int], float, str]:
    k = cost.shape[0] - 1
    if k <= EXACT_LIMIT:
        order, total = held_karp(cost, closed)
        return order, total, "Held-Karp (exact)"
    order, total = nearest_neighbour_2opt(cost, closed)
    return order, total, "nearest neighbour + 2-opt"


def plan_route(g: RoadGraph, depot_nodes, depot_gaps, stop_nodes, stop_gaps, vehicle: str,
               closed: bool = True) -> Route | None:
    """Fastest delivery round from the best depot through every stop.

    Times include riding (Dijkstra on travel time), walking from the road to
    each door and back, and a fixed hand-over time per stop.
    """
    depot_nodes, stop_nodes = list(map(int, depot_nodes)), list(map(int, stop_nodes))
    k = len(stop_nodes)
    if not depot_nodes or k == 0:
        return None
    sources = depot_nodes + stop_nodes
    T, P = g.from_sources(sources, vehicle, "min", predecessors=True)
    walk = [gap / WALK_KMH * 60.0 for gap in stop_gaps]
    best = None
    for di, dn in enumerate(depot_nodes):
        rows = [di] + [len(depot_nodes) + s for s in range(k)]
        nodes = [dn] + stop_nodes
        cost = np.array([[T[rows[a], nodes[b]] for b in range(k + 1)] for a in range(k + 1)])
        cost[:, 1:] += SERVICE_MIN + 2 * np.array(walk)
        np.fill_diagonal(cost, 0.0)
        if not np.isfinite(cost).all():
            continue
        order, total, method = best_order(cost, closed)
        if best is None or total < best[1]:
            best = (di, total, order, method, rows, nodes)
    if best is None:
        return None
    di, total, order, method, rows, nodes = best
    seq = [0] + [o + 1 for o in order] + ([0] if closed else [])
    legs = []
    for a, b in zip(seq, seq[1:]):
        path = g.path(P[rows[a]], nodes[b])
        minutes = float(T[rows[a], nodes[b]]) + (SERVICE_MIN + 2 * walk[b - 1] if b else 0.0)
        legs.append(Leg(start=a, end=b, nodes=path, km=g.path_km(path), minutes=minutes, roads=g.path_roads(path)))
    return Route(vehicle=vehicle, depot=di, order=order, legs=legs, km=sum(l.km for l in legs),
                 minutes=sum(l.minutes for l in legs), method=method)

