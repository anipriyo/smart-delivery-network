"""Point sets for the dashboard: random real places of the Kalyani region
from OpenStreetMap, or a user CSV of latitude/longitude points.
"""

from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass, field

import pandas as pd
from shapely.geometry import MultiPoint, Polygon

from .geo import LocalProjection, Region
from .models import Point
from .river import River


@dataclass
class Network:
    """Everything the algorithms and the map need about one point set."""

    title: str
    warehouses: list[Point]
    customers: list[Point]
    projection: LocalProjection
    region: Polygon  # area in km that service zones are clipped to
    boundary_lonlat: list[tuple[float, float]] | None  # study-area outline to draw, if any
    river: River | None = None
    towns: list[dict] = field(default_factory=list)
    inner_outline_lonlat: list[tuple[float, float]] | None = None  # Kalyani City, for context

    @property
    def bounds_xy(self) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = self.region.bounds
        return (x0, x1, y0, y1)


def _to_point(row: dict, pid: int, kind: str) -> Point:
    return Point(
        id=pid, x=row["x"], y=row["y"], kind=kind, name=row["name"],
        lat=row["lat"], lon=row["lon"], category=row.get("kind", ""),
    )


def sample_network(
    city: Region,
    n_warehouses: int = 5,
    n_customers: int = 60,
    seed: int = 42,
) -> Network:
    """Pick random real places of the region as warehouses and customers.

    Warehouses come first from places OSM tags as warehouses, industrial,
    commercial or postal sites, then from any place, and must sit at least a
    minimum gap apart so the service zones are not degenerate. Customers are a
    uniform random sample of the remaining places. The same seed always gives
    the same network.
    """
    rng = random.Random(seed)
    places = list(city.places)
    tagged = [p for p in places if p["warehouse_candidate"]]
    others = [p for p in places if not p["warehouse_candidate"]]
    rng.shuffle(tagged)
    rng.shuffle(others)
    pool = tagged + others

    gap = 0.55 * math.sqrt(city.area_km2 / max(n_warehouses, 1))
    hubs: list[dict] = []
    while len(hubs) < n_warehouses and gap > 0.05:
        for p in pool:
            if len(hubs) == n_warehouses:
                break
            if p in hubs:
                continue
            if all(math.hypot(p["x"] - h["x"], p["y"] - h["y"]) >= gap for h in hubs):
                hubs.append(p)
        gap *= 0.8  # relax the spacing if the region ran out of far-apart places

    hub_ids = {h["osm_id"] for h in hubs}
    rest = [p for p in places if p["osm_id"] not in hub_ids]
    rng.shuffle(rest)
    chosen: list[dict] = []
    taken: set[tuple[float, float]] = set()
    for p in rest:
        key = (round(p["x"], 3), round(p["y"], 3))  # ~1 m grid: skip duplicates
        if key in taken:
            continue
        taken.add(key)
        chosen.append(p)
        if len(chosen) == n_customers:
            break

    warehouses = [_to_point(h, i + 1, "warehouse") for i, h in enumerate(hubs)]
    customers = [_to_point(c, i + 1, "customer") for i, c in enumerate(chosen)]
    return Network(
        title=city.name,
        warehouses=warehouses,
        customers=customers,
        projection=city.projection,
        region=city.boundary_xy,
        boundary_lonlat=city.boundary_lonlat,
        river=city.river,
        towns=city.towns,
        inner_outline_lonlat=city.kalyani_lonlat,
    )


def network_from_csv(file) -> Network:
    """Build a network from a CSV with columns type, lat, lon and optional name.

    ``type`` is ``warehouse`` or ``customer``. The flat km plane is centred on
    the uploaded points, so any city works.
    """
    df = pd.read_csv(file)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = {"type", "lat", "lon"} - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing column(s): {', '.join(sorted(missing))}")
    if "name" not in df.columns:
        df["name"] = ""
    df = df.dropna(subset=["lat", "lon"])
    df["type"] = df["type"].astype(str).str.strip().str.lower()
    proj = LocalProjection(lat0=float(df["lat"].min()), lon0=float(df["lon"].min()))

    warehouses: list[Point] = []
    customers: list[Point] = []
    for _, r in df.iterrows():
        x, y = proj.to_xy(float(r["lat"]), float(r["lon"]))
        is_wh = r["type"] == "warehouse"
        bucket = warehouses if is_wh else customers
        bucket.append(Point(
            id=len(bucket) + 1, x=x, y=y, kind="warehouse" if is_wh else "customer",
            name=str(r["name"]) if pd.notna(r["name"]) else "",
            lat=float(r["lat"]), lon=float(r["lon"]),
        ))
    if not warehouses or len(customers) < 2:
        raise ValueError("CSV needs at least 1 warehouse and 2 customers")

    hull = MultiPoint([p.coords() for p in warehouses + customers]).convex_hull
    region = hull.buffer(0.15 * math.sqrt(max(hull.area, 1.0)) + 0.3)
    return Network(
        title="Uploaded network", warehouses=warehouses, customers=customers,
        projection=proj, region=region, boundary_lonlat=None,
    )


def network_to_csv(net: Network) -> str:
    buf = io.StringIO()
    rows = [
        {"type": p.kind, "label": p.label, "name": p.name, "lat": p.lat, "lon": p.lon, "category": p.category}
        for p in net.warehouses + net.customers
    ]
    pd.DataFrame(rows).to_csv(buf, index=False)
    return buf.getvalue()
