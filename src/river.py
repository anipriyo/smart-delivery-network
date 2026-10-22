"""The Hooghly river: which bank a point is on, and trip lengths that must
use a real crossing (road bridge or ferry) when the two ends are on opposite
banks.

The five core algorithms all use straight-line distance. This module exists
to measure where that assumption breaks in the real region: a customer on
the west bank whose straight-line nearest warehouse is on the east bank can
only be reached via a bridge or a ferry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.geometry import Point as SPoint
from shapely.ops import linemerge, split, unary_union
from shapely.prepared import prep

from .models import Point

VAN = ("bridge",)
TWO_WHEELER = ("bridge", "ferry")


@dataclass(frozen=True)
class Crossing:
    """A way across the river between two landings (km coordinates)."""

    name: str
    kind: str  # "bridge" or "ferry"
    a: tuple[float, float]
    b: tuple[float, float]
    source: str = ""

    @property
    def length(self) -> float:
        return math.dist(self.a, self.b)


def main_channel(lines: list[LineString], tol: float = 1e-3) -> LineString:
    """Join river segments into one line.

    Starts from the longest merged piece and keeps attaching whichever piece
    touches either end of the chain (gap <= ``tol``, in the lines' units).
    A piece whose far end comes back onto the chain would close a loop
    around an island, so it is skipped: the result follows one channel past
    each island and never crosses itself. Pieces that never touch an end are
    dropped.
    """
    merged = linemerge(unary_union(lines))
    geoms = merged.geoms if isinstance(merged, MultiLineString) else [merged]
    parts = sorted((list(g.coords) for g in geoms), key=lambda c: -LineString(c).length)
    chain = parts.pop(0)
    while parts:
        on_chain = LineString(chain)
        options = []
        for i, c in enumerate(parts):
            for seg in (c, c[::-1]):
                if on_chain.distance(SPoint(seg[-1])) > tol:
                    options.append((math.dist(chain[-1], seg[0]), i, chain + seg[1:]))
                if on_chain.distance(SPoint(seg[0])) > tol:
                    options.append((math.dist(seg[-1], chain[0]), i, seg[:-1] + chain))
        if not options:
            break
        gap, i, joined = min(options, key=lambda t: t[0])
        if gap > tol:
            break
        chain = joined
        parts.pop(i)
    return LineString(chain)


def extend(line: LineString, dist: float) -> LineString:
    """Lengthen both ends of a line along its end segments."""
    c = list(line.coords)

    def push(p, q):  # point dist beyond q, away from p
        dx, dy = q[0] - p[0], q[1] - p[1]
        n = math.hypot(dx, dy) or 1.0
        return (q[0] + dx / n * dist, q[1] + dy / n * dist)

    return LineString([push(c[1], c[0]), *c, push(c[-2], c[-1])])


def side_of(line: LineString, x: float, y: float) -> int:
    """+1 if (x, y) is left of the line's direction at its nearest point, else -1."""
    s = line.project(SPoint(x, y))
    eps = max(line.length / 5000, 1e-6)
    a = line.interpolate(max(0.0, s - eps))
    b = line.interpolate(min(line.length, s + eps))
    cross = (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x)
    return 1 if cross > 0 else -1


class River:
    """Splits a region into a west bank (0) and an east bank (1)."""

    def __init__(self, centerline: LineString, region: Polygon, crossings: list[Crossing], name: str = "Hooghly"):
        self.name = name
        self.line = centerline
        x0, y0, x1, y1 = region.bounds
        self._long = extend(centerline, 2 * max(x1 - x0, y1 - y0))
        pieces = [g for g in split(region, self._long).geoms if g.area > 1e-9]
        by_side: dict[int, list[Polygon]] = {1: [], -1: []}
        for piece in pieces:
            rp = piece.representative_point()
            by_side[side_of(self._long, rp.x, rp.y)].append(piece)
        banks = {s: unary_union(ps) if ps else Polygon() for s, ps in by_side.items()}
        west_side = 1 if (banks[1].centroid.x if not banks[1].is_empty else math.inf) < \
                         (banks[-1].centroid.x if not banks[-1].is_empty else math.inf) else -1
        self._side_to_bank = {west_side: 0, -west_side: 1}
        self.banks = [banks[west_side], banks[-west_side]]
        self._prep = [prep(b) for b in self.banks]
        self.crossings = [self._orient(c) for c in crossings]

    def _orient(self, c: Crossing) -> Crossing:
        """Make ``a`` the west-bank landing."""
        if self.bank(*c.a) == 1 and self.bank(*c.b) == 0:
            return Crossing(c.name, c.kind, c.b, c.a, c.source)
        return c

    def bank(self, x: float, y: float) -> int:
        pt = SPoint(x, y)
        for i, bank in enumerate(self._prep):
            if bank.contains(pt):
                return i
        return self._side_to_bank[side_of(self._long, x, y)]

    def route(self, p: tuple[float, float], q: tuple[float, float],
              kinds: tuple[str, ...] = TWO_WHEELER) -> tuple[float, Crossing | None]:
        """Shortest trip p -> q: straight if same bank, else via the best crossing.

        Returns (km, crossing used). The distance is inf when the banks differ
        and no crossing of the allowed kinds exists.
        """
        bp, bq = self.bank(*p), self.bank(*q)
        if bp == bq:
            return math.dist(p, q), None
        best: tuple[float, Crossing | None] = (math.inf, None)
        for c in self.crossings:
            if c.kind not in kinds:
                continue
            near_p, near_q = (c.a, c.b) if bp == 0 else (c.b, c.a)
            d = math.dist(p, near_p) + c.length + math.dist(near_q, q)
            if d < best[0]:
                best = (d, c)
        return best


def river_check(customers: list[Point], warehouses: list[Point], assignment: dict[int, int],
                river: River, kinds: tuple[str, ...]) -> list[dict]:
    """Customers whose straight-line (Voronoi) hub is on the other bank.

    For each: the straight-line distance, the real trip via the best allowed
    crossing, and the hub that is actually nearest once the river is respected.
    """
    wh = {w.id: w for w in warehouses}
    rows = []
    for c in customers:
        hub = wh[assignment[c.id]]
        if river.bank(c.x, c.y) == river.bank(hub.x, hub.y):
            continue
        straight = math.dist(c.coords(), hub.coords())
        real, crossing = river.route(c.coords(), hub.coords(), kinds)
        options = [(w, *river.route(c.coords(), w.coords(), kinds)) for w in warehouses]
        best_w, best_d, best_cross = min(options, key=lambda t: t[1])
        rows.append({
            "customer": c, "hub": hub, "straight": straight, "real": real, "crossing": crossing,
            "best_hub": best_w, "best_real": best_d, "best_crossing": best_cross,
        })
    return rows
