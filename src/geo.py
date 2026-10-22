"""Real-world geography: the Kalyani region (Kalyani and its neighbouring
towns on both banks of the Hooghly), its OpenStreetMap places, the river and
its crossings, and the projection that turns latitude/longitude into a flat
km plane.

Every algorithm in this project works on Euclidean (x, y) coordinates. The
region is about 20 x 25 km, small enough that an equirectangular projection
centred on it is accurate to well under 0.5 %, so 1 unit = 1 km everywhere
and distances can be reported in metres.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapelyPoint
from shapely.prepared import prep

from .river import Crossing, River

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
MANUAL_FERRIES = DATA_ROOT / "manual" / "ferries.csv"
KM_PER_DEG_LAT = 110.574
REQUIRED = ("region.geojson", "region_places.csv", "river.geojson", "crossings.csv", "towns.csv")


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
class Region:
    name: str
    boundary_lonlat: list[tuple[float, float]]  # closed ring of (lon, lat): the study area
    places: list[dict]  # rows of region_places.csv
    towns: list[dict]  # city/town labels
    anchors: list[dict]  # the five towns that define the area
    river_lonlat: list[tuple[float, float]]
    crossing_rows: list[dict]
    kalyani_lonlat: list[tuple[float, float]] | None
    source: str  # data folder the region was loaded from
    projection: LocalProjection = field(init=False)
    boundary_xy: Polygon = field(init=False)
    river: River = field(init=False)

    def __post_init__(self) -> None:
        lons = [p[0] for p in self.boundary_lonlat]
        lats = [p[1] for p in self.boundary_lonlat]
        self.projection = LocalProjection(lat0=min(lats), lon0=min(lons))
        xy = self.projection.to_xy
        self.boundary_xy = Polygon([xy(lat, lon) for lon, lat in self.boundary_lonlat])
        for row in self.places + self.towns + self.anchors:
            row["x"], row["y"] = xy(row["lat"], row["lon"])
        inside = prep(self.boundary_xy)
        self.places = [r for r in self.places if inside.contains(ShapelyPoint(r["x"], r["y"]))]
        crossings = [
            Crossing(r["name"], r["kind"], xy(float(r["lat_a"]), float(r["lon_a"])),
                     xy(float(r["lat_b"]), float(r["lon_b"])), r.get("source", ""))
            for r in self.crossing_rows
        ]
        line = LineString([xy(lat, lon) for lon, lat in self.river_lonlat])
        self.river = River(line, self.boundary_xy, crossings)
        for row in self.places:
            row["bank"] = self.river.bank(row["x"], row["y"])

    @property
    def area_km2(self) -> float:
        return self.boundary_xy.area


def latest_data_dir(root: Path = DATA_ROOT) -> Path:
    """Newest data/YYYY-MM folder that holds a complete OSM extract."""
    candidates = sorted(
        d for d in root.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]") if all((d / f).exists() for f in REQUIRED)
    )
    if not candidates:
        raise FileNotFoundError("No OpenStreetMap extract found. Run: python scripts/fetch_osm.py")
    return candidates[-1]


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_region(data_dir: Path | None = None, manual_ferries: Path | None = MANUAL_FERRIES) -> Region:
    data_dir = data_dir or latest_data_dir()
    fc = json.loads((data_dir / "region.geojson").read_text())
    area = next(f for f in fc["features"] if f["geometry"]["type"] == "Polygon")
    anchors = [{"name": f["properties"]["name"], "lon": f["geometry"]["coordinates"][0],
                "lat": f["geometry"]["coordinates"][1]}
               for f in fc["features"] if f["geometry"]["type"] == "Point"]
    places = _read_csv(data_dir / "region_places.csv")
    for row in places:
        row["lat"], row["lon"] = float(row["lat"]), float(row["lon"])
        row["osm_id"] = int(row["osm_id"])
        row["warehouse_candidate"] = row["warehouse_candidate"] == "1"
    towns = _read_csv(data_dir / "towns.csv")
    for row in towns:
        row["lat"], row["lon"] = float(row["lat"]), float(row["lon"])
    crossings = _read_csv(data_dir / "crossings.csv")
    if manual_ferries and manual_ferries.exists():
        for row in _read_csv(manual_ferries):
            if row.get("name") and row.get("lat_a"):
                crossings.append({**row, "kind": row.get("kind") or "ferry", "source": "added by hand"})
    river = json.loads((data_dir / "river.geojson").read_text())["geometry"]["coordinates"]
    kalyani = None
    if (data_dir / "kalyani_boundary.geojson").exists():
        feat = json.loads((data_dir / "kalyani_boundary.geojson").read_text())
        kalyani = [tuple(p) for p in feat["geometry"]["coordinates"][0]]
    return Region(
        name="Kalyani region", boundary_lonlat=[tuple(p) for p in area["geometry"]["coordinates"][0]],
        places=places, towns=towns, anchors=anchors, river_lonlat=[tuple(p) for p in river],
        crossing_rows=crossings, kalyani_lonlat=kalyani, source=data_dir.name,
    )
