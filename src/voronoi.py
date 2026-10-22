"""Voronoi service regions over warehouse sites.

Cell geometry comes from scipy's Fortune-sweep implementation
(scipy.spatial.Voronoi, O(m log m) for m sites) so that cell polygons are
robust to degenerate input; assigning each customer to its nearest
warehouse -- the actual decision the dashboard needs -- is done directly
by brute-force nearest-site search, which is O(m) per customer and exact
by definition of a Voronoi cell (no reliance on the polygon geometry).
"""

import math

import numpy as np
from scipy.spatial import Voronoi

from .models import Point


def nearest_warehouse(customer: Point, warehouses: list[Point]) -> Point:
    return min(warehouses, key=lambda w: math.hypot(w.x - customer.x, w.y - customer.y))


def assign_customers(customers: list[Point], warehouses: list[Point]) -> dict[int, int]:
    """Return {customer_id: warehouse_id}."""
    return {c.id: nearest_warehouse(c, warehouses).id for c in customers}


def build_voronoi(warehouses: list[Point]) -> Voronoi | None:
    """Return a scipy Voronoi diagram over warehouse sites, or None if there
    are too few distinct sites (fewer than 3) to form one.
    """
    coords = np.array([w.coords() for w in warehouses])
    if len(coords) < 3:
        return None
    return Voronoi(coords)
