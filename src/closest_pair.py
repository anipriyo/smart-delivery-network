"""Closest pair of points via divide and conquer. O(n log n).

The points are sorted by x once. Each call returns its best pair together with
its points sorted by y, built by merging the two halves' y-orders in linear
time (as in merge sort). The strip around the dividing line is filtered from
that merged list, so no level sorts anything: T(n) = 2T(n/2) + O(n).
"""

import math

from .models import Point


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def merge_by_y(left: list[Point], right: list[Point]) -> list[Point]:
    """Merge two lists already sorted by y into one, in linear time.

    On equal y the left point comes first, so the merge is stable.
    """
    merged: list[Point] = []
    i = j = 0
    while i < len(left) and j < len(right):
        if right[j].y < left[i].y:
            merged.append(right[j])
            j += 1
        else:
            merged.append(left[i])
            i += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def closest_pair(points: list[Point]) -> tuple[Point, Point, float]:
    """Return (p, q, distance) for the closest pair. Requires len(points) >= 2."""
    if len(points) < 2:
        raise ValueError("need at least 2 points")

    by_x = sorted(points, key=lambda p: p.x)

    def brute_force(pts: list[Point]) -> tuple[Point, Point, float]:
        best = (pts[0], pts[1], _dist(pts[0], pts[1]))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = _dist(pts[i], pts[j])
                if d < best[2]:
                    best = (pts[i], pts[j], d)
        return best

    def solve(pts: list[Point]) -> tuple[tuple[Point, Point, float], list[Point]]:
        """Return (best pair, pts sorted by y). ``pts`` is sorted by x."""
        n = len(pts)
        if n <= 3:
            # At most 3 points, so this sort is constant time.
            return brute_force(pts), sorted(pts, key=lambda p: p.y)

        mid = n // 2
        mid_x = pts[mid].x
        left, right = pts[:mid], pts[mid:]

        best_left, left_by_y = solve(left)
        best_right, right_by_y = solve(right)
        best = best_left if best_left[2] <= best_right[2] else best_right

        by_y = merge_by_y(left_by_y, right_by_y)
        strip = [p for p in by_y if abs(p.x - mid_x) < best[2]]
        for i in range(len(strip)):
            for j in range(i + 1, len(strip)):
                if strip[j].y - strip[i].y >= best[2]:
                    break
                d = _dist(strip[i], strip[j])
                if d < best[2]:
                    best = (strip[i], strip[j], d)
        return best, by_y

    return solve(by_x)[0]
