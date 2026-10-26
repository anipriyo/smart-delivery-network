"""Road network and route planning: visiting order, paths on the real OSM graph."""

import math
import random

import numpy as np
import pytest
from shapely.geometry import Point as Point_

from src.data import sample_network
from src.geo import latest_data_dir, load_region
from src.roads import (
    RoadGraph,
    area_grid,
    best_order,
    brute_force_order,
    grid_km,
    held_karp,
    nearest_neighbour_2opt,
    plan_route,
    tour_cost,
    zone_polygons,
)


def _random_cost(k: int, seed: int) -> np.ndarray:
    """Asymmetric travel times between a depot (0) and k stops."""
    rng = np.random.default_rng(seed)
    cost = rng.uniform(1, 30, size=(k + 1, k + 1))
    np.fill_diagonal(cost, 0)
    return cost


@pytest.mark.parametrize("closed", [True, False])
@pytest.mark.parametrize("seed", range(6))
def test_held_karp_matches_brute_force(seed, closed):
    cost = _random_cost(6, seed)
    order, total = held_karp(cost, closed)
    _, best = brute_force_order(cost, closed)
    assert sorted(order) == list(range(6))
    assert math.isclose(total, best) and math.isclose(tour_cost(order, cost, closed), total)


@pytest.mark.parametrize("seed", range(6))
def test_two_opt_is_never_below_the_optimum(seed):
    cost = _random_cost(8, seed)
    order, total = nearest_neighbour_2opt(cost, True)
    assert sorted(order) == list(range(8))
    assert total >= held_karp(cost, True)[1] - 1e-9


def test_best_order_switches_to_the_heuristic_above_ten_stops():
    assert best_order(_random_cost(10, 1), True)[2].startswith("Held-Karp")
    assert "2-opt" in best_order(_random_cost(14, 1), True)[2]


# ---------------------------------------------------------------- real Kalyani road graph

@pytest.fixture(scope="module")
def world():
    path = latest_data_dir() / "roads.npz"
    if not path.exists():
        pytest.skip("no road graph in the data folder")
    region = load_region()
    return region, RoadGraph(path, region.projection, region.river.crossings)


def test_road_distance_is_never_shorter_than_the_straight_line(world):
    region, g = world
    net = sample_network(region, 5, 60, seed=7)
    wn, wg = g.snap([w.x for w in net.warehouses], [w.y for w in net.warehouses])
    cn, cg = g.snap([p.x for p in net.customers], [p.y for p in net.customers])
    km = g.from_sources(wn, "van", "km")[:, cn]
    for i, w in enumerate(net.warehouses):
        for j, p in enumerate(net.customers):
            if np.isfinite(km[i, j]):
                assert km[i, j] + wg[i] + cg[j] >= math.dist(w.coords(), p.coords()) - 1e-6


def test_planned_route_is_a_continuous_path_through_every_stop(world):
    region, g = world
    net = sample_network(region, 5, 60, seed=3)
    stops = random.Random(3).sample(net.customers, 6)
    wn, wg = g.snap([w.x for w in net.warehouses], [w.y for w in net.warehouses])
    sn, sg = g.snap([p.x for p in stops], [p.y for p in stops])
    route = plan_route(g, wn, wg, sn, sg, "bike", closed=True)
    assert route is not None and sorted(route.order) == list(range(6))
    assert len(route.legs) == 7 and route.legs[0].start == 0 and route.legs[-1].end == 0
    for leg in route.legs:
        target = wn[route.depot] if leg.end == 0 else sn[leg.end - 1]
        assert leg.nodes[-1] == target
    for a, b in zip(route.legs, route.legs[1:]):
        assert a.nodes[-1] == b.nodes[0]
    assert math.isclose(route.km, sum(leg.km for leg in route.legs))
    assert route.minutes > 6 * 3  # at least the hand-over time at every stop


def test_vans_cannot_take_the_ferry(world):
    _, g = world
    if not g.ferries:
        pytest.skip("no ferry in this extract")
    a, b, _ = g.ferries[0]
    bike = g.from_sources([a], "bike", "km")[0, b]
    van = g.from_sources([a], "van", "km")[0, b]
    assert bike < 2 and van > bike  # the van has to go round by the bridge


def test_zones_by_road_partition_the_area_and_hold_their_warehouse(world):
    region, g = world
    net = sample_network(region, 5, 60, seed=42)
    wn, wg = g.snap([w.x for w in net.warehouses], [w.y for w in net.warehouses])
    grid = area_grid(g, net.region)
    km = grid_km(g, grid, g.from_sources(wn, "van", "km"), wg)
    zones = zone_polygons(grid, np.argmin(km, axis=0), net.region)
    assert sorted(zones) == list(range(5))
    assert math.isclose(sum(z.area for z in zones.values()), net.region.area, rel_tol=1e-6)
    for i, a in zones.items():
        assert a.contains(Point_(net.warehouses[i].x, net.warehouses[i].y))
        for j, b in zones.items():
            if i < j:
                assert a.intersection(b).area < 1e-6
