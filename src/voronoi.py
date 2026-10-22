"""Voronoi service regions over warehouse sites.

Cell geometry comes from scipy.spatial.Voronoi, which wraps Qhull
(O(m log m) for m sites in the plane). Four far-away helper sites are added so
every real warehouse gets a closed cell, and each cell is then clipped to the
city outline with shapely so the zones match the map.

Assigning each customer to its nearest warehouse -- the decision the dashboard
actually needs -- is done directly by nearest-site search, O(m) per customer
and exact by definition of a Voronoi cell, so it never depends on the polygon
geometry.
"""

import math

import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import MultiPoint, Polygon

from .models import Point


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def nearest_warehouse(customer: Point, warehouses: list[Point]) -> Point:
    return min(warehouses, key=lambda w: _dist(w, customer))


def assign_customers(customers: list[Point], warehouses: list[Point]) -> dict[int, int]:
    """Return {customer_id: warehouse_id}."""
    return {c.id: nearest_warehouse(c, warehouses).id for c in customers}


def service_regions(warehouses: list[Point], clip: Polygon) -> dict[int, Polygon]:
    """Return {warehouse_id: service-zone polygon (km)}, clipped to ``clip``."""
    if not warehouses:
        return {}
    if len(warehouses) == 1:
        return {warehouses[0].id: clip}

    x0, y0, x1, y1 = clip.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    span = 10 * max(x1 - x0, y1 - y0, 1.0)
    helpers = [(cx - span, cy - span), (cx + span, cy - span), (cx + span, cy + span), (cx - span, cy + span)]
    vor = Voronoi(np.array([w.coords() for w in warehouses] + helpers))

    regions: dict[int, Polygon] = {}
    for i, w in enumerate(warehouses):
        vertex_ids = vor.regions[vor.point_region[i]]
        if not vertex_ids or -1 in vertex_ids:
            continue
        # Voronoi cells are convex, so the hull of the cell's vertices is the cell.
        cell = MultiPoint([tuple(vor.vertices[v]) for v in vertex_ids]).convex_hull
        clipped = cell.intersection(clip)
        if not clipped.is_empty:
            regions[w.id] = clipped
    return regions
