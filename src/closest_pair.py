"""Closest pair of points via divide and conquer. O(n log n)."""

import math

from .models import Point


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


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

    def solve(pts: list[Point]) -> tuple[Point, Point, float]:
        n = len(pts)
        if n <= 3:
            return brute_force(pts)

        mid = n // 2
        mid_x = pts[mid].x
        left, right = pts[:mid], pts[mid:]

        best_left = solve(left)
        best_right = solve(right)
        best = best_left if best_left[2] <= best_right[2] else best_right

        strip = [p for p in pts if abs(p.x - mid_x) < best[2]]
        strip.sort(key=lambda p: p.y)
        for i in range(len(strip)):
            for j in range(i + 1, len(strip)):
                if strip[j].y - strip[i].y >= best[2]:
                    break
                d = _dist(strip[i], strip[j])
                if d < best[2]:
                    best = (strip[i], strip[j], d)
        return best

    return solve(by_x)
