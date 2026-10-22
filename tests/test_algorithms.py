import itertools
import math
import random

from src.closest_pair import closest_pair
from src.convex_hull import convex_hull
from src.kdtree import KDTree
from src.models import Point
from src.set_cover import greedy_cover, greedy_set_cover
from src.traces import closest_pair_trace, convex_hull_trace, kdtree_query_trace, voronoi_assignment_trace
from src.voronoi import nearest_warehouse


def _rand_points(n, seed):
    rng = random.Random(seed)
    return [Point(i, rng.uniform(0, 100), rng.uniform(0, 100), "customer") for i in range(n)]


def brute_closest_pair(points):
    best = None
    for a, b in itertools.combinations(points, 2):
        d = math.hypot(a.x - b.x, a.y - b.y)
        if best is None or d < best:
            best = d
    return best


def test_closest_pair_matches_brute_force():
    for seed in range(5):
        points = _rand_points(30, seed)
        _, _, d = closest_pair(points)
        assert math.isclose(d, brute_closest_pair(points), rel_tol=1e-9)


def test_closest_pair_simple():
    pts = [Point(0, 0, 0, "c"), Point(1, 10, 10, "c"), Point(2, 0, 1, "c")]
    p, q, d = closest_pair(pts)
    assert math.isclose(d, 1.0)


def test_convex_hull_square_contains_only_corners():
    pts = [
        Point(0, 0, 0, "c"), Point(1, 10, 0, "c"), Point(2, 10, 10, "c"), Point(3, 0, 10, "c"),
        Point(4, 5, 5, "c"),  # interior point, must not be on hull
    ]
    hull = convex_hull(pts)
    hull_ids = {p.id for p in hull}
    assert hull_ids == {0, 1, 2, 3}


def test_convex_hull_all_collinear():
    pts = [Point(i, float(i), float(i), "c") for i in range(5)]
    hull = convex_hull(pts)
    assert len(hull) <= 2


def brute_range_query(points, x_min, x_max, y_min, y_max):
    return {p for p in points if x_min <= p.x <= x_max and y_min <= p.y <= y_max}


def test_kdtree_range_query_matches_brute_force():
    points = _rand_points(50, seed=7)
    tree = KDTree(points)
    box = (20, 60, 30, 70)
    result = set(tree.range_query(*box))
    assert result == brute_range_query(points, *box)


def test_kdtree_empty_box():
    points = _rand_points(10, seed=1)
    tree = KDTree(points)
    assert tree.range_query(1000, 2000, 1000, 2000) == []


def test_greedy_set_cover_covers_everything_possible():
    customers = [Point(i, float(i) * 10, 0.0, "customer") for i in range(9)]
    candidates = [
        Point(100, 15, 0, "warehouse"),  # covers 1,2,3,4 within radius ~25 -> ids 0..4 roughly
        Point(101, 45, 0, "warehouse"),
        Point(102, 65, 0, "warehouse"),
        Point(103, 5, 0, "warehouse"),
    ]
    chosen, rounds = greedy_set_cover(candidates, customers, radius=20)
    covered = set()
    for r in rounds:
        covered |= r["new_covered"]
    assert covered == {c.id for c in customers}
    assert len(chosen) <= len(candidates)


def test_greedy_cover_matches_overview_worked_example():
    # Overview PDF, page 3: four candidate sites, nine customers.
    sets = {
        "W1": {1, 2, 3, 4},
        "W2": {3, 4, 5, 6, 7},
        "W3": {6, 7, 8},
        "W4": {1, 2, 8, 9},
    }
    picks = greedy_cover(set(range(1, 10)), sets)
    assert [name for name, _ in picks] == ["W2", "W4"]
    assert picks[0][1] == {3, 4, 5, 6, 7}
    assert picks[1][1] == {1, 2, 8, 9}


def test_greedy_cover_stops_when_nothing_new():
    picks = greedy_cover({1, 2, 3}, {"A": {1}, "B": {1}})
    assert picks == [("A", {1})]


def test_traces_agree_with_core_algorithms():
    points = _rand_points(40, seed=11)
    hull, _ = convex_hull_trace(points)
    assert hull == convex_hull(points)
    (p, q, d), _ = closest_pair_trace(points)
    assert math.isclose(d, closest_pair(points)[2])
    tree = KDTree(points)
    found, _ = kdtree_query_trace(tree, 20, 60, 30, 70)
    assert set(found) == set(tree.range_query(20, 60, 30, 70))


def test_voronoi_trace_ends_at_nearest_warehouse():
    hubs = [Point(i + 1, x, y, "warehouse") for i, (x, y) in enumerate([(0, 0), (10, 0), (5, 9)])]
    c = Point(1, 6, 1, "customer")
    rows = voronoi_assignment_trace(c, hubs)
    assert rows[-1]["best_so_far"] == nearest_warehouse(c, hubs).id == 2
