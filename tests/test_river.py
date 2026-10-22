"""River logic: joining the channel, which bank, trips via crossings, river check."""

import math

import pytest
from shapely.geometry import LineString, Polygon

from src.data import sample_network
from src.geo import load_region
from src.models import Point
from src.river import TWO_WHEELER, VAN, Crossing, River, main_channel, river_check, side_of
from src.voronoi import assign_customers

# A toy world: a 10 x 10 km square split by a north-south river at x = 5.
SQUARE = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
LINE = LineString([(5, 10), (5, 0)])  # flows south
BRIDGE = Crossing("Bridge", "bridge", (4.8, 2.0), (5.2, 2.0))
FERRY = Crossing("Ferry", "ferry", (5.2, 8.0), (4.8, 8.0))  # given east -> west on purpose


@pytest.fixture()
def toy():
    return River(LINE, SQUARE, [BRIDGE, FERRY])


def test_banks_and_orientation(toy):
    assert toy.bank(2, 5) == 0 and toy.bank(8, 5) == 1  # west = 0
    assert math.isclose(toy.banks[0].area, 50) and math.isclose(toy.banks[1].area, 50)
    ferry = next(c for c in toy.crossings if c.kind == "ferry")
    assert toy.bank(*ferry.a) == 0  # re-oriented so a is on the west bank


def test_route_same_bank_is_straight(toy):
    d, via = toy.route((1, 1), (4, 5))
    assert via is None and math.isclose(d, 5.0)


def test_route_across_uses_best_allowed_crossing(toy):
    p, q = (4, 8), (6, 8)  # either side of the ferry
    d_bike, via_bike = toy.route(p, q, TWO_WHEELER)
    d_van, via_van = toy.route(p, q, VAN)
    assert via_bike.kind == "ferry" and math.isclose(d_bike, 0.8 + 0.4 + 0.8)
    assert via_van.kind == "bridge" and d_van > d_bike >= math.dist(p, q)


def test_no_allowed_crossing_is_infinite():
    river = River(LINE, SQUARE, [FERRY])
    d, via = river.route((1, 5), (9, 5), VAN)
    assert math.isinf(d) and via is None


def test_river_check_flags_only_cross_bank_assignments(toy):
    hubs = [Point(1, 5.5, 5, "warehouse"), Point(2, 1, 9, "warehouse")]
    custs = [Point(1, 4.5, 5, "customer"), Point(2, 7, 5, "customer"), Point(3, 1, 8, "customer")]
    rows = river_check(custs, hubs, assign_customers(custs, hubs), toy, VAN)
    assert [r["customer"].id for r in rows] == [1]  # straight-line nearest is W1, across the river
    assert rows[0]["best_hub"].id == 2 and rows[0]["best_real"] <= rows[0]["real"]


def test_main_channel_is_one_simple_line_past_an_island():
    a = LineString([(0, 10), (0, 5)])
    b = LineString([(0, 5), (0, 0)])
    side = LineString([(0.0, 8), (1, 6.5), (0.0, 6)])  # channel round an island between y=6 and y=8
    far = LineString([(5, 5), (6, 5)])  # unrelated piece that never touches
    chan = main_channel([b, side, far, a], tol=1e-6)
    ends = {tuple(chan.coords[0]), tuple(chan.coords[-1])}
    assert ends == {(0.0, 10.0), (0.0, 0.0)} and chan.is_simple
    assert side_of(chan, -1, 2) != side_of(chan, 1, 2)


def test_real_region_banks_and_crossings():
    region = load_region()
    rv = region.river
    town = {t["name"]: t for t in region.anchors}
    assert rv.bank(town["Mogra"]["x"], town["Mogra"]["y"]) == 0
    for name in ("Kalyani", "Naihati", "Chakdaha", "Haringhata"):
        assert rv.bank(town[name]["x"], town[name]["y"]) == 1, name
    names = {c.name: c for c in rv.crossings}
    assert names["Ishwar Gupta Setu"].kind == "bridge"
    assert all(rv.bank(*c.a) == 0 and rv.bank(*c.b) == 1 for c in rv.crossings)
    net = sample_network(region, 5, 80, seed=42)
    rows = river_check(net.customers, net.warehouses, assign_customers(net.customers, net.warehouses), rv, VAN)
    assert all(r["real"] >= r["straight"] - 1e-9 for r in rows)
