"""Convex hull via Graham scan. O(n log n)."""

from .models import Point


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)


def convex_hull(points: list[Point]) -> list[Point]:
    """Return hull vertices in counter-clockwise order, starting from the
    lowest (then leftmost) point. Collinear boundary points are dropped.
    """
    pts = sorted(set(points), key=lambda p: (p.x, p.y))
    if len(pts) < 3:
        return pts

    def build(seq: list[Point]) -> list[Point]:
        hull: list[Point] = []
        for p in seq:
            while len(hull) >= 2 and _cross(hull[-2], hull[-1], p) <= 0:
                hull.pop()
            hull.append(p)
        return hull

    lower = build(pts)
    upper = build(list(reversed(pts)))
    return lower[:-1] + upper[:-1]
