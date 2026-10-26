"""Instrumented variants of each algorithm that record a step-by-step trace.

Kept separate from the tested core implementations (convex_hull.py,
closest_pair.py, kdtree.py) so the teaching output can never affect
correctness -- these mirror the same logic but log every decision instead
of only returning the final answer. They reuse the core modules' small linear
helpers (the y-merge, the KD-tree presort and median split) so the steps shown
are exactly the ones the core runs. Coordinates are km, so distances are
shown in metres.
"""

import math

from .closest_pair import merge_by_y
from .kdtree import KDTree, presort, split_at_median
from .models import Point


def fmt_dist(km: float) -> str:
    return f"{km * 1000:.0f} m" if km < 1 else f"{km:.2f} km"


def convex_hull_trace(points: list[Point]) -> tuple[list[Point], list[dict]]:
    pts = sorted(set(points), key=lambda p: (p.x, p.y))
    steps: list[dict] = []
    if len(pts) < 3:
        return pts, steps

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)

    def build(seq: list[Point], chain: str) -> list[Point]:
        hull: list[Point] = []
        for p in seq:
            while len(hull) >= 2 and cross(hull[-2], hull[-1], p) <= 0:
                popped = hull.pop()
                prev = hull[-1].label if hull else "-"
                steps.append({
                    "chain": chain, "action": "pop", "point": popped.id,
                    "detail": f"{prev} → {popped.label} → {p.label} is not a left turn, so {popped.label} "
                              f"cannot be on the boundary: drop it",
                    "snapshot": [q.id for q in hull], "current": p.id, "popped": popped.id,
                })
            hull.append(p)
            steps.append({
                "chain": chain, "action": "push", "point": p.id,
                "detail": f"add {p.label} to the {chain} chain",
                "snapshot": [q.id for q in hull], "current": p.id,
            })
        return hull

    lower = build(pts, "lower")
    upper = build(list(reversed(pts)), "upper")
    hull = lower[:-1] + upper[:-1]
    return hull, steps


def closest_pair_trace(points: list[Point]) -> tuple[tuple[Point, Point, float], list[dict]]:
    steps: list[dict] = []

    def dist(a: Point, b: Point) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    def brute(pts: list[Point], depth: int):
        best = (pts[0], pts[1], dist(pts[0], pts[1]))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = dist(pts[i], pts[j])
                if d < best[2]:
                    best = (pts[i], pts[j], d)
        steps.append({
            "depth": depth, "event": "base case",
            "detail": f"{len(pts)} points ({', '.join(p.label for p in pts)}): brute force gives "
                      f"{best[0].label}–{best[1].label} = {fmt_dist(best[2])}",
            "active_ids": [p.id for p in pts], "best": (best[0].id, best[1].id, best[2]),
        })
        return best, sorted(pts, key=lambda p: p.y)

    def solve(pts: list[Point], depth: int = 0):
        """Return (best pair, pts sorted by y), like the core ``solve``."""
        n = len(pts)
        if n <= 3:
            return brute(pts, depth)

        mid = n // 2
        mid_x = pts[mid].x
        left, right = pts[:mid], pts[mid:]
        steps.append({
            "depth": depth, "event": "divide",
            "detail": f"split {n} points at x = {mid_x:.2f} km into {len(left)} on the left "
                      f"and {len(right)} on the right",
            "active_ids": [p.id for p in pts], "split_x": mid_x,
            "left_ids": [p.id for p in left], "right_ids": [p.id for p in right],
        })

        best_left, left_by_y = solve(left, depth + 1)
        best_right, right_by_y = solve(right, depth + 1)
        best = best_left if best_left[2] <= best_right[2] else best_right
        by_y = merge_by_y(left_by_y, right_by_y)
        steps.append({
            "depth": depth, "event": "combine",
            "detail": f"left best = {fmt_dist(best_left[2])}, right best = {fmt_dist(best_right[2])}, "
                      f"so δ = {fmt_dist(best[2])}; merge both halves' south-to-north orders "
                      f"into one ({n} points, no sorting)",
            "active_ids": [p.id for p in pts], "split_x": mid_x,
            "best": (best[0].id, best[1].id, best[2]),
        })

        strip = [p for p in by_y if abs(p.x - mid_x) < best[2]]
        improved = False
        for i in range(len(strip)):
            for j in range(i + 1, len(strip)):
                if strip[j].y - strip[i].y >= best[2]:
                    break
                d = dist(strip[i], strip[j])
                if d < best[2]:
                    best = (strip[i], strip[j], d)
                    improved = True
        steps.append({
            "depth": depth, "event": "strip check",
            "detail": f"{len(strip)} point(s) lie within δ of the split line; "
                      + ("a closer pair crosses the line" if improved else "none beats δ")
                      + f", best is {best[0].label}–{best[1].label} = {fmt_dist(best[2])}",
            "active_ids": [p.id for p in pts], "split_x": mid_x, "delta": best[2],
            "strip_ids": [p.id for p in strip], "best": (best[0].id, best[1].id, best[2]),
        })
        return best, by_y

    by_x = sorted(points, key=lambda p: p.x)
    result, _ = solve(by_x)
    return result, steps


def kdtree_build_trace(
    points: list[Point], bounds: tuple[float, float, float, float] = (0.0, 100.0, 0.0, 100.0)
) -> list[dict]:
    """``bounds`` is (x_min, x_max, y_min, y_max) of the area being split."""
    steps: list[dict] = []
    pts = list(points)
    by_x, by_y, rank = presort(pts)

    def build(bx: list[int], by: list[int], depth: int, box: tuple[float, float, float, float]) -> None:
        if not bx:
            return
        x_min, x_max, y_min, y_max = box
        axis = depth % 2
        m, left, right = split_at_median(bx, by, axis, rank)
        median = pts[m]
        if axis == 0:
            seg = ((median.x, y_min), (median.x, y_max))
            left_box, right_box = (x_min, median.x, y_min, y_max), (median.x, x_max, y_min, y_max)
        else:
            seg = ((x_min, median.y), (x_max, median.y))
            left_box, right_box = (x_min, x_max, y_min, median.y), (x_min, x_max, median.y, y_max)
        steps.append({
            "depth": depth, "axis": "x" if axis == 0 else "y",
            "median_point": median.id, "n_points": len(bx), "seg": seg,
            "detail": f"depth {depth}: split {len(bx)} point(s) on {'x (west/east)' if axis == 0 else 'y (south/north)'} "
                      f"at the median, {median.label}, read from the presorted order",
        })
        build(*left, depth + 1, left_box)
        build(*right, depth + 1, right_box)

    build(by_x, by_y, 0, bounds)
    return steps


def kdtree_query_trace(
    tree: KDTree, x_min: float, x_max: float, y_min: float, y_max: float
) -> tuple[list[Point], list[dict]]:
    steps: list[dict] = []
    found: list[Point] = []

    def in_box(p: Point) -> bool:
        return x_min <= p.x <= x_max and y_min <= p.y <= y_max

    def search(node, depth: int) -> None:
        if node is None:
            return
        hit = in_box(node.point)
        if hit:
            found.append(node.point)
        steps.append({
            "depth": depth, "point": node.point.id, "in_box": hit,
            "detail": f"visit {node.point.label}: " + ("inside the area, report it" if hit else "outside the area"),
        })

        if node.axis == 0:
            lo, hi, val = x_min, x_max, node.point.x
        else:
            lo, hi, val = y_min, y_max, node.point.y

        go_left = lo <= val
        go_right = hi >= val
        side = ("west", "east") if node.axis == 0 else ("south", "north")
        if not go_left:
            steps.append({"depth": depth + 1, "pruned": True, "point": node.point.id,
                          "detail": f"skip everything {side[0]} of {node.point.label}: the area cannot reach it"})
        if not go_right:
            steps.append({"depth": depth + 1, "pruned": True, "point": node.point.id,
                          "detail": f"skip everything {side[1]} of {node.point.label}: the area cannot reach it"})

        if go_left:
            search(node.left, depth + 1)
        if go_right:
            search(node.right, depth + 1)

    search(tree.root, 0)
    return found, steps


def voronoi_assignment_trace(customer: Point, warehouses: list[Point],
                             distances: list[float] | None = None) -> list[dict]:
    """Compare the customer with each warehouse in turn, keeping the nearest so far.

    ``distances`` (one per warehouse, e.g. by road) replaces the straight line when given.
    """
    rows: list[dict] = []
    best: tuple[int, float] | None = None
    for k, w in enumerate(warehouses):
        d = math.hypot(w.x - customer.x, w.y - customer.y) if distances is None else float(distances[k])
        if best is None or d < best[1]:
            best = (w.id, d)
        rows.append({"warehouse": w.id, "distance": d, "best_so_far": best[0], "best_distance": best[1]})
    return rows
