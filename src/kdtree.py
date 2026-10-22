"""2D KD-tree with axis-aligned rectangle range search.

Build: O(n log n). Range query: O(sqrt(n) + k) for k points reported.
"""

from dataclasses import dataclass

from .models import Point


@dataclass
class KDNode:
    point: Point
    axis: int  # 0 = split on x, 1 = split on y
    left: "KDNode | None" = None
    right: "KDNode | None" = None


class KDTree:
    def __init__(self, points: list[Point]):
        self.root = self._build(list(points), depth=0)

    def _build(self, points: list[Point], depth: int) -> KDNode | None:
        if not points:
            return None
        axis = depth % 2
        points.sort(key=lambda p: p.x if axis == 0 else p.y)
        mid = len(points) // 2
        node = KDNode(point=points[mid], axis=axis)
        node.left = self._build(points[:mid], depth + 1)
        node.right = self._build(points[mid + 1 :], depth + 1)
        return node

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
