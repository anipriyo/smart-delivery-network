import inspect
import itertools
import math
import random

import src.closest_pair
import src.kdtree
from src.closest_pair import closest_pair, merge_by_y
from src.convex_hull import convex_hull
from src.kdtree import KDTree
from src.models import Point
from src.set_cover import greedy_cover, greedy_set_cover
from src.traces import (
    closest_pair_trace,
    convex_hull_trace,
    kdtree_build_trace,
    kdtree_query_trace,
    voronoi_assignment_trace,
)
from src.voronoi import nearest_warehouse


def _rand_points(n, seed):
    rng = random.Random(seed)
    return [Point(i, rng.uniform(0, 100), rng.uniform(0, 100), "customer") for i in range(n)]


def _dup_points(n, seed, size=6):
    """Points on a small integer grid: many shared x and y values, and exact repeats."""
    rng = random.Random(seed)
    return [Point(i, float(rng.randrange(size)), float(rng.randrange(size)), "customer") for i in range(n)]


def _lattice(size):
    """Every grid point once, in shuffled order: all x and y values are shared, none repeats."""
    pts = [Point(i * size + j, float(i), float(j), "customer") for i in range(size) for j in range(size)]
    random.Random(size).shuffle(pts)
    return pts


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


def test_closest_pair_matches_brute_force_many_sizes():
    for n in (2, 3, 4, 5, 6, 7, 8, 13, 64, 200):
        for seed in range(3):
            points = _rand_points(n, seed)
            p, q, d = closest_pair(points)
            assert math.isclose(d, brute_closest_pair(points), rel_tol=1e-9)
            assert math.isclose(d, math.hypot(p.x - q.x, p.y - q.y))


def test_closest_pair_with_duplicate_coordinates():
    for n in (2, 5, 9, 40, 150):
        for seed in range(5):
            points = _dup_points(n, seed)
            p, q, d = closest_pair(points)
            assert p.id != q.id
            assert math.isclose(d, brute_closest_pair(points), abs_tol=1e-12)
            assert math.isclose(d, math.hypot(p.x - q.x, p.y - q.y))
    # No exact repeats, but every x and y is shared: delta stays 1 and the strips are full.
    for size in (2, 3, 5, 8):
        points = _lattice(size)
        assert math.isclose(closest_pair(points)[2], 1.0)
        # Move one point close to a neighbour across a column so the strip must find it.
        nudged = [Point(p.id, p.x - 0.7 if (p.x, p.y) == (1.0, 1.0) else p.x, p.y, "customer") for p in points]
        assert math.isclose(closest_pair(nudged)[2], brute_closest_pair(nudged))
    vertical = [Point(i, 3.0, float(y), "customer") for i, y in enumerate([9, 1, 4, 7, 2, 8, 5.5, 0])]
    assert math.isclose(closest_pair(vertical)[2], 1.0)
    horizontal = [Point(i, float(x), 3.0, "customer") for i, x in enumerate([9, 1, 3, 7, 4.5, 11, 5, 0])]
    assert math.isclose(closest_pair(horizontal)[2], 0.5)


def test_merge_by_y_is_sorted_and_stable():
    left = [Point(0, 0, 1, "c"), Point(1, 0, 3, "c"), Point(2, 0, 3, "c")]
    right = [Point(3, 1, 0, "c"), Point(4, 1, 3, "c"), Point(5, 1, 7, "c")]
    merged = merge_by_y(left, right)
    assert [p.id for p in merged] == [3, 0, 1, 2, 4, 5]


def test_closest_pair_sorts_only_once(monkeypatch):
    # O(n log n) needs the strip to come from the merged y-order, not a sort per level.
    # Only the first sort (by x) may see more than the 3 points of a base case, and
    # no in-place list.sort (which the spy cannot see) may be used at all.
    assert ".sort(" not in inspect.getsource(src.closest_pair)
    sizes = []

    def spy(items, **kw):
        out = sorted(items, **kw)
        sizes.append(len(out))
        return out

    monkeypatch.setattr(src.closest_pair, "sorted", spy, raising=False)
    closest_pair(_rand_points(500, seed=3))
    assert sizes[0] == 500
    assert max(sizes[1:]) <= 3


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


def _tree_nodes(node):
    if node is None:
        return []
    return [node] + _tree_nodes(node.left) + _tree_nodes(node.right)


def _height(node):
    return 0 if node is None else 1 + max(_height(node.left), _height(node.right))


def test_kdtree_range_query_with_duplicate_coordinates():
    rng = random.Random(4)
    for n, seed in [(1, 0), (2, 1), (30, 2), (120, 3), (300, 4)]:
        points = _dup_points(n, seed)
        tree = KDTree(points)
        edges = [-1.0, 0.0, 0.5, 1.0, 2.0, 2.5, 3.0, 5.0, 6.0]
        boxes = [(0, 5, 0, 5), (2, 2, 0, 5), (0, 5, 3, 3), (2, 2, 3, 3), (1, 1, 1, 1)]
        boxes += [tuple(sorted(rng.sample(edges, 2)) + sorted(rng.sample(edges, 2))) for _ in range(40)]
        for box in boxes:
            found = sorted(p.id for p in tree.range_query(*box))
            assert found == sorted(p.id for p in brute_range_query(points, *box)), box


def test_kdtree_split_invariant_and_balance_with_ties():
    # range_query searches left when lo <= val and right when hi >= val, so every
    # left point must be <= the node's coordinate and every right point >= it.
    for points in (_dup_points(200, 9), _dup_points(64, 10, size=2), _lattice(7), _rand_points(100, 2)):
        tree = KDTree(points)
        nodes = _tree_nodes(tree.root)
        assert sorted(nd.point.id for nd in nodes) == sorted(p.id for p in points)
        for nd in nodes:
            val = nd.point.x if nd.axis == 0 else nd.point.y
            for sub in _tree_nodes(nd.left):
                assert (sub.point.x if nd.axis == 0 else sub.point.y) <= val
            for sub in _tree_nodes(nd.right):
                assert (sub.point.x if nd.axis == 0 else sub.point.y) >= val
        assert _height(tree.root) == math.floor(math.log2(len(points))) + 1


def test_kdtree_build_sorts_only_once(monkeypatch):
    # O(n log n) needs one presort per axis, then linear splits at every node.
    assert ".sort(" not in inspect.getsource(src.kdtree)
    calls = []

    def spy(items, **kw):
        calls.append(1)
        return sorted(items, **kw)

    monkeypatch.setattr(src.kdtree, "sorted", spy, raising=False)
    KDTree(_rand_points(500, seed=5))
    assert len(calls) == 2


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


def test_traces_agree_with_core_on_duplicates():
    for points in (_dup_points(60, 12), _lattice(5), _rand_points(45, 13)):
        (p, q, d), steps = closest_pair_trace(points)
        assert math.isclose(d, closest_pair(points)[2], abs_tol=1e-12)
        assert steps and all({"depth", "event", "detail", "active_ids"} <= s.keys() for s in steps)
        # The build trace splits at the same medians, in the same order, as the tree.
        build_steps = kdtree_build_trace(points, (0, 10, 0, 10))
        assert [s["median_point"] for s in build_steps] == [nd.point.id for nd in _tree_nodes(KDTree(points).root)]
        assert build_steps[0]["n_points"] == len(points)


def test_voronoi_trace_ends_at_nearest_warehouse():
    hubs = [Point(i + 1, x, y, "warehouse") for i, (x, y) in enumerate([(0, 0), (10, 0), (5, 9)])]
    c = Point(1, 6, 1, "customer")
    rows = voronoi_assignment_trace(c, hubs)
    assert rows[-1]["best_so_far"] == nearest_warehouse(c, hubs).id == 2
