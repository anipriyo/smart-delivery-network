"""Instrumented variants of each algorithm that record a step-by-step trace.

Kept separate from the tested core implementations (convex_hull.py,
closest_pair.py, kdtree.py) so the teaching output can never affect
correctness -- these mirror the same logic but log every decision instead
of only returning the final answer.
"""

import math

from .kdtree import KDTree
from .models import Point


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
                prev_id = hull[-1].id if hull else "-"
                steps.append({
                    "chain": chain, "action": "pop", "point": popped.id,
                    "detail": f"P{prev_id} -> P{popped.id} -> P{p.id} is not a left turn, drop P{popped.id}",
                    "snapshot": [q.id for q in hull], "current": p.id,
                })
            hull.append(p)
            steps.append({
                "chain": chain, "action": "push", "point": p.id,
                "detail": f"add P{p.id} to the {chain} chain",
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
            "detail": f"{len(pts)} points ({', '.join('P' + str(p.id) for p in pts)}) -> "
                      f"brute force best P{best[0].id}-P{best[1].id} = {best[2]:.2f}",
            "active_ids": [p.id for p in pts], "best": (best[0].id, best[1].id, best[2]),
        })
        return best

    def solve(pts: list[Point], depth: int = 0):
        n = len(pts)
        if n <= 3:
            return brute(pts, depth)

        mid = n // 2
        mid_x = pts[mid].x
        left, right = pts[:mid], pts[mid:]
        steps.append({
            "depth": depth, "event": "divide",
            "detail": f"split {n} points at x = {mid_x:.1f}: left = "
                      f"{{{', '.join('P' + str(p.id) for p in left)}}}, "
                      f"right = {{{', '.join('P' + str(p.id) for p in right)}}}",
            "active_ids": [p.id for p in pts], "split_x": mid_x,
            "left_ids": [p.id for p in left], "right_ids": [p.id for p in right],
        })

        best_left = solve(left, depth + 1)
        best_right = solve(right, depth + 1)
        best = best_left if best_left[2] <= best_right[2] else best_right
        steps.append({
            "depth": depth, "event": "combine",
            "detail": f"left best = {best_left[2]:.2f}, right best = {best_right[2]:.2f}, "
                      f"delta = {best[2]:.2f}",
            "active_ids": [p.id for p in pts], "split_x": mid_x,
            "best": (best[0].id, best[1].id, best[2]),
        })

        strip = [p for p in pts if abs(p.x - mid_x) < best[2]]
        strip.sort(key=lambda p: p.y)
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
            "detail": f"{len(strip)} point(s) within {best[2]:.2f} of the split line checked, "
                      + ("found a closer cross-boundary pair" if improved else "no improvement, delta stands")
                      + f" -> best P{best[0].id}-P{best[1].id} = {best[2]:.2f}",
            "active_ids": [p.id for p in pts], "split_x": mid_x,
            "strip_ids": [p.id for p in strip], "best": (best[0].id, best[1].id, best[2]),
        })
        return best

    by_x = sorted(points, key=lambda p: p.x)
    result = solve(by_x)
    return result, steps


def kdtree_build_trace(points: list[Point], bounds: tuple[float, float, float, float] = (0.0, 100.0, 0.0, 100.0)) -> list[dict]:
    steps: list[dict] = []

    def build(pts: list[Point], depth: int, box: tuple[float, float, float, float]) -> None:
        if not pts:
            return
        x_min, x_max, y_min, y_max = box
        axis = depth % 2
        pts.sort(key=lambda p: p.x if axis == 0 else p.y)
        mid = len(pts) // 2
        median = pts[mid]
        if axis == 0:
            seg = ((median.x, y_min), (median.x, y_max))
            left_box, right_box = (x_min, median.x, y_min, y_max), (median.x, x_max, y_min, y_max)
        else:
            seg = ((x_min, median.y), (x_max, median.y))
            left_box, right_box = (x_min, x_max, y_min, median.y), (x_min, x_max, median.y, y_max)
        steps.append({
            "depth": depth, "axis": "x" if axis == 0 else "y",
            "median_point": median.id, "n_points": len(pts), "seg": seg,
            "detail": f"depth {depth}, split on {'x' if axis == 0 else 'y'}: "
                      f"median of {len(pts)} point(s) is P{median.id} ({median.x:.1f}, {median.y:.1f})",
        })
        build(pts[:mid], depth + 1, left_box)
        build(pts[mid + 1:], depth + 1, right_box)

    build(list(points), 0, bounds)
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
            "detail": f"visit P{node.point.id} ({node.point.x:.1f}, {node.point.y:.1f}) -> "
                      + ("inside box, report it" if hit else "outside box, keep searching"),
        })

        if node.axis == 0:
            lo, hi, val = x_min, x_max, node.point.x
        else:
            lo, hi, val = y_min, y_max, node.point.y

        go_left = lo <= val
        go_right = hi >= val
        if not go_left:
            steps.append({"depth": depth + 1, "pruned": True, "detail": f"prune left subtree of P{node.point.id}: entirely outside the query box"})
        if not go_right:
            steps.append({"depth": depth + 1, "pruned": True, "detail": f"prune right subtree of P{node.point.id}: entirely outside the query box"})

        if go_left:
            search(node.left, depth + 1)
        if go_right:
            search(node.right, depth + 1)

    search(tree.root, 0)
    return found, steps


def voronoi_assignment_trace(customer: Point, warehouses: list[Point]) -> list[dict]:
    rows = [
        {"warehouse": w.id, "distance": math.hypot(w.x - customer.x, w.y - customer.y)}
        for w in warehouses
    ]
    rows.sort(key=lambda r: r["distance"])
    return rows
