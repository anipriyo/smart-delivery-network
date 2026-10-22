"""2D KD-tree with axis-aligned rectangle range search.

Build: O(n log n). The points are sorted once by x and once by y; every node
then splits both orders at its median in linear time, so no level sorts
anything: T(n) = 2T(n/2) + O(n).
Range query: O(sqrt(n) + k) for k points reported.
"""

from dataclasses import dataclass

from .models import Point

# Both sorted orders hold indices into the point list rather than points, and
# ``rank[axis][i]`` is point i's position in that axis's order.
Ranks = tuple[list[int], list[int]]


@dataclass
class KDNode:
    point: Point
    axis: int  # 0 = split on x, 1 = split on y
    left: "KDNode | None" = None
    right: "KDNode | None" = None


def presort(points: list[Point]) -> tuple[list[int], list[int], Ranks]:
    """Sort the point indices once by x and once by y. O(n log n).

    Ties are broken by the other coordinate and then by input position, so
    each axis order is strict and every point has a unique rank on it.
    """
    n = len(points)
    by_x = sorted(range(n), key=lambda i: (points[i].x, points[i].y, i))
    by_y = sorted(range(n), key=lambda i: (points[i].y, points[i].x, i))
    rank: Ranks = ([0] * n, [0] * n)
    for r, i in enumerate(by_x):
        rank[0][i] = r
    for r, i in enumerate(by_y):
        rank[1][i] = r
    return by_x, by_y, rank


def split_at_median(
    by_x: list[int], by_y: list[int], axis: int, rank: Ranks
) -> tuple[int, tuple[list[int], list[int]], tuple[list[int], list[int]]]:
    """Split both orders of one subtree at the median on ``axis``. O(n).

    Returns (median index, (left by_x, left by_y), (right by_x, right by_y)).
    The order along ``axis`` is simply cut at the middle. The other order is
    filtered in one pass by comparing ranks with the median's, which keeps it
    sorted. Left points rank before the median, so their coordinate on
    ``axis`` is <= the median's, and right points' is >= it, which is what
    ``range_query`` relies on when values tie.
    """
    along = by_x if axis == 0 else by_y
    mid = len(along) // 2
    m = along[mid]
    cut = rank[axis][m]
    if axis == 0:
        left = (by_x[:mid], [i for i in by_y if rank[0][i] < cut])
        right = (by_x[mid + 1 :], [i for i in by_y if rank[0][i] > cut])
    else:
        left = ([i for i in by_x if rank[1][i] < cut], by_y[:mid])
        right = ([i for i in by_x if rank[1][i] > cut], by_y[mid + 1 :])
    return m, left, right


class KDTree:
    def __init__(self, points: list[Point]):
        pts = list(points)
        by_x, by_y, rank = presort(pts)

        def build(by_x: list[int], by_y: list[int], depth: int) -> KDNode | None:
            if not by_x:
                return None
            axis = depth % 2
            m, left, right = split_at_median(by_x, by_y, axis, rank)
            node = KDNode(point=pts[m], axis=axis)
            node.left = build(*left, depth + 1)
            node.right = build(*right, depth + 1)
            return node

        self.root = build(by_x, by_y, 0)

    def range_query(self, x_min: float, x_max: float, y_min: float, y_max: float) -> list[Point]:
        """Return every point whose (x, y) falls inside the given box, inclusive."""
        found: list[Point] = []

        def in_box(p: Point) -> bool:
            return x_min <= p.x <= x_max and y_min <= p.y <= y_max

        def search(node: KDNode | None) -> None:
            if node is None:
                return
            if in_box(node.point):
                found.append(node.point)

            if node.axis == 0:
                lo, hi, val = x_min, x_max, node.point.x
            else:
                lo, hi, val = y_min, y_max, node.point.y

            if lo <= val:
                search(node.left)
            if hi >= val:
                search(node.right)

        search(self.root)
        return found
