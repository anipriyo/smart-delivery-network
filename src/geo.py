"""Real-world geography: the Kalyani city outline, its OpenStreetMap places,
and the projection that turns latitude/longitude into a flat km plane.

Every algorithm in this project works on Euclidean (x, y) coordinates. A city
is small enough (about 7 x 10 km) that an equirectangular projection centred
on it is accurate to well under 0.1 %, so 1 unit = 1 km everywhere on the map
and distances can be reported in metres.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon
from shapely.prepared import prep

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
KM_PER_DEG_LAT = 110.574


@dataclass(frozen=True)
class LocalProjection:
    """Equirectangular projection around a reference corner (lat0, lon0)."""

    lat0: float
    lon0: float

    @property
    def km_per_deg_lon(self) -> float:
        return 111.320 * math.cos(math.radians(self.lat0))

    def to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        return ((lon - self.lon0) * self.km_per_deg_lon, (lat - self.lat0) * KM_PER_DEG_LAT)

    def to_latlon(self, x: float, y: float) -> tuple[float, float]:
        return (self.lat0 + y / KM_PER_DEG_LAT, self.lon0 + x / self.km_per_deg_lon)


@dataclass
class City:
    name: str
    boundary_lonlat: list[tuple[float, float]]  # closed ring of (lon, lat)
    places: list[dict]  # rows of kalyani_places.csv
    source: str  # data folder the city was loaded from
    projection: LocalProjection = field(init=False)
    boundary_xy: Polygon = field(init=False)

    def __post_init__(self) -> None:
        lons = [p[0] for p in self.boundary_lonlat]
        lats = [p[1] for p in self.boundary_lonlat]
        self.projection = LocalProjection(lat0=min(lats), lon0=min(lons))
        self.boundary_xy = Polygon([self.projection.to_xy(lat, lon) for lon, lat in self.boundary_lonlat])
        for row in self.places:
            row["x"], row["y"] = self.projection.to_xy(row["lat"], row["lon"])
        # A building that straddles the outline can have its centre just outside it.
        inside = prep(self.boundary_xy)
        self.places = [r for r in self.places if inside.contains(ShapelyPoint(r["x"], r["y"]))]

    @property
    def bounds_xy(self) -> tuple[float, float, float, float]:
        """(x_min, x_max, y_min, y_max) of the city outline in km."""
        x0, y0, x1, y1 = self.boundary_xy.bounds
        return (x0, x1, y0, y1)

    @property
    def centre_latlon(self) -> tuple[float, float]:
        c = self.boundary_xy.centroid
        return self.projection.to_latlon(c.x, c.y)

    @property
    def area_km2(self) -> float:
        return self.boundary_xy.area


def latest_data_dir(root: Path = DATA_ROOT) -> Path:
    """Newest data/YYYY-MM folder that holds a complete OSM extract."""
    candidates = sorted(
        d for d in root.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]")
        if (d / "kalyani_places.csv").exists() and (d / "kalyani_boundary.geojson").exists()
    )
    if not candidates:
        raise FileNotFoundError(
            "No OpenStreetMap extract found. Run: python scripts/fetch_osm_kalyani.py"
        )
    return candidates[-1]


def load_city(data_dir: Path | None = None) -> City:
    data_dir = data_dir or latest_data_dir()
    feature = json.loads((data_dir / "kalyani_boundary.geojson").read_text())
    ring = [tuple(pt) for pt in feature["geometry"]["coordinates"][0]]
    places: list[dict] = []
    with open(data_dir / "kalyani_places.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["lat"], row["lon"] = float(row["lat"]), float(row["lon"])
            row["osm_id"] = int(row["osm_id"])
            row["warehouse_candidate"] = row["warehouse_candidate"] == "1"
            places.append(row)
    name = feature["properties"].get("name", "Kalyani City")
    return City(name=name, boundary_lonlat=ring, places=places, source=data_dir.name)
