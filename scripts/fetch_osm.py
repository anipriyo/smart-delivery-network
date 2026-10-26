"""Fetch the Kalyani region from OpenStreetMap and save it for the dashboard.

Run from the project root (needs internet; Overpass is often busy, so this
retries on several mirrors and can take a few minutes):

    python scripts/fetch_osm.py                  # writes data/<YYYY-MM>/, downloading only missing raw files
    python scripts/fetch_osm.py --refresh        # download every raw file again

Study area: the convex hull of five town centres (Kalyani, Naihati, Chakdaha,
Mogra, Haringhata) padded by 2.5 km, about 400 km^2 on both banks of the
Hooghly. Outputs under data/<YYYY-MM>/:

    raw/overpass_*.json        untouched Overpass responses
    region.geojson             study-area polygon + the five anchor towns
    region_places.csv          named places and buildings inside the area (warehouse/customer pool)
    roads.npz                  drivable road network as a graph (nodes, edges, lengths, classes, names)
    towns.csv                  city/town nodes inside the area (map labels)
    river.geojson              Hooghly main channel as one line
    crossings.csv              road bridges and ferries across the Hooghly
    kalyani_boundary.geojson   the Kalyani City outline (context on the map)

Rail-only bridges (Jubilee / Sampreeti at Naihati-Bandel) are left out:
delivery vehicles cannot use them. Ferries come from OSM ferry routes, and
from OSM ferry terminals paired with the nearest terminal on the other bank;
a terminal with no partner gets its far landing estimated by mirroring it
across the river (marked "landing estimated"). Ghats the team knows locally
can be added by hand in data/manual/ferries.csv.

Data (c) OpenStreetMap contributors, available under the ODbL.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import LineString, MultiPoint, Point, Polygon, mapping

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.geo import LocalProjection  # noqa: E402
from src.river import extend, main_channel, side_of  # noqa: E402

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "SmartDeliveryNetwork-student-project/1.0 (Algorithms II coursework, Kalyani)"

KALYANI_CITY_WAY = 1094723487
HOOGHLY_RELATION_NAME = "Hooghly"
# Anchor towns: (name, lat, lon, OSM source of the coordinate)
TOWNS = [
    ("Kalyani", 22.9750, 88.4346, "way 1094723487 (Kalyani City) centroid"),
    ("Naihati", 22.8866078, 88.4241960, "node 570090082"),
    ("Chakdaha", 23.0774983, 88.5320399, "node 570083118"),
    ("Mogra", 22.9882573, 88.3732690, "node 570098553"),
    ("Haringhata", 22.9607700, 88.5674629, "node 5300270745"),
]
PAD_KM = 2.5

# Same place filters as the original Kalyani extract.
CATEGORY_KEYS = ["amenity", "shop", "office", "healthcare", "craft", "tourism",
                 "leisure", "railway", "industrial", "building", "landuse"]
EXCLUDE_KEYS = {"highway", "waterway", "natural", "boundary", "power", "route", "place", "barrier"}
EXCLUDE_VALUES = {
    ("railway", "rail"), ("railway", "platform"), ("railway", "level_crossing"), ("railway", "crossing"),
    ("railway", "switch"), ("railway", "signal"), ("railway", "buffer_stop"),
    ("landuse", "residential"), ("landuse", "farmland"), ("landuse", "grass"), ("landuse", "meadow"),
    ("landuse", "forest"), ("landuse", "orchard"), ("landuse", "farmyard"), ("landuse", "aquaculture"),
    ("leisure", "park"), ("leisure", "garden"), ("leisure", "pitch"), ("leisure", "playground"),
    ("amenity", "parking"), ("amenity", "bench"), ("amenity", "waste_basket"), ("amenity", "toilets"),
}
WAREHOUSE_TAGS = {
    ("industrial", "warehouse"), ("building", "warehouse"), ("landuse", "industrial"),
    ("building", "industrial"), ("landuse", "commercial"), ("building", "commercial"),
    ("shop", "wholesale"), ("amenity", "post_office"), ("office", "logistics"),
    ("amenity", "marketplace"), ("shop", "supermarket"), ("landuse", "retail"),
}
ROAD_BRIDGE = "motorway|trunk|primary|secondary|tertiary"
DRIVABLE = ("motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|"
            "tertiary|tertiary_link|unclassified|residential|living_street|service|road")
# Building types that are not delivery points.
NOT_DELIVERABLE = {"roof", "shed", "garage", "garages", "construction", "ruins", "toilets", "transformer_tower",
                   "bunker", "service", "carport", "cowshed", "hut", "container", "tank", "water_tower"}


# ------------------------------------------------------------------ network

def overpass(query: str) -> dict:
    body = urllib.parse.urlencode({"data": query}).encode()
    last: Exception | None = None
    for attempt in range(5):
        for url in ENDPOINTS:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                print(f"  ok from {url}", file=sys.stderr)
                return data
            except Exception as exc:  # busy server, timeout, HTML error page
                last = exc
                print(f"  {url} failed: {str(exc)[:70]}", file=sys.stderr)
        wait = 10 * 2**attempt
        print(f"  all mirrors busy, retrying in {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"Overpass unavailable: {last}")


# ------------------------------------------------------------------ geometry

def study_area() -> tuple[Polygon, LocalProjection]:
    """Padded convex hull of the anchor towns, as a lon/lat polygon."""
    proj = LocalProjection(lat0=min(t[1] for t in TOWNS) - 0.05, lon0=min(t[2] for t in TOWNS) - 0.05)
    pts = MultiPoint([proj.to_xy(lat, lon) for _, lat, lon, _ in TOWNS])
    area_xy = pts.convex_hull.buffer(PAD_KM, quad_segs=12)
    ring = [proj.to_latlon(x, y) for x, y in area_xy.exterior.coords]
    return Polygon([(lon, lat) for lat, lon in ring]), proj


def poly_filter(area: Polygon) -> str:
    simple = area.simplify(0.0015)
    return " ".join(f"{lat:.5f} {lon:.5f}" for lon, lat in list(simple.exterior.coords)[:-1])


def bbox(area: Polygon, pad: float = 0.03) -> str:
    x0, y0, x1, y1 = area.bounds
    return f"{y0 - pad:.4f},{x0 - pad:.4f},{y1 + pad:.4f},{x1 + pad:.4f}"


def queries(area: Polygon) -> dict[str, str]:
    poly, bb = poly_filter(area), bbox(area)
    return {
        "boundary": f"[out:json][timeout:90];way({KALYANI_CITY_WAY});out geom;",
        "places": f"""[out:json][timeout:240];
(
  nwr["name"](poly:"{poly}");
  nwr["industrial"="warehouse"](poly:"{poly}");
  nwr["building"="warehouse"](poly:"{poly}");
  nwr["landuse"="industrial"](poly:"{poly}");
);
out center tags;""",
        "river": f"""[out:json][timeout:120];
relation["waterway"="river"]["name"="{HOOGHLY_RELATION_NAME}"]({bb})->.r;
way(r.r)({bb});
out geom tags;""",
        "roads": f"""[out:json][timeout:300];
way["highway"~"^({DRIVABLE})$"](poly:"{poly_filter(area.buffer(0.01))}");
out body;
>;
out skel qt;""",
        "buildings": f"""[out:json][timeout:240];
way["building"](poly:"{poly}");
out center tags;""",
        "crossings": f"""[out:json][timeout:120];
(
  way["bridge"]["highway"~"^({ROAD_BRIDGE})$"]({bb});
  way["route"="ferry"]({bb});
);
out geom tags;
node["amenity"="ferry_terminal"]({bb});
out;""",
    }


# ------------------------------------------------------------------ places

def classify(tags: dict) -> tuple[str, str] | None:
    if any(k in tags for k in EXCLUDE_KEYS) and not any(k in tags for k in ("amenity", "shop", "office")):
        return None
    for key in CATEGORY_KEYS:
        if key in tags:
            value = tags[key]
            if (key, value) in EXCLUDE_VALUES:
                return None
            if key == "building" and value in ("yes", "house", "residential", "apartments"):
                return ("building", "residential" if value != "yes" else "building")
            return (key, value)
    return None


def latlon(el: dict) -> tuple[float | None, float | None]:
    return el.get("lat", el.get("center", {}).get("lat")), el.get("lon", el.get("center", {}).get("lon"))


def build_places(raw: dict, area: Polygon) -> tuple[list[dict], list[dict]]:
    places, towns = [], []
    seen: set[tuple[str, float, float]] = set()
    for el in raw["elements"]:
        tags = el.get("tags", {})
        lat, lon = latlon(el)
        if lat is None or not area.contains(Point(lon, lat)):
            continue
        if el["type"] == "node" and tags.get("place") in ("city", "town") and tags.get("name"):
            towns.append({"name": tags.get("name:en") or tags["name"], "kind": tags["place"],
                          "lat": round(lat, 7), "lon": round(lon, 7), "osm_id": el["id"]})
            continue
        cat = classify(tags)
        if cat is None:
            continue
        name = tags.get("name:en") or tags.get("name") or ""
        is_wh = any((k, tags.get(k)) in WAREHOUSE_TAGS for k in tags)
        if not name:
            if not is_wh:
                continue
            name = "Unnamed warehouse" if "warehouse" in tags.values() else "Industrial site"
        key = (name.lower(), round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)
        places.append({
            "osm_type": el["type"], "osm_id": el["id"], "name": name.strip(), "category": cat[0],
            "kind": cat[1].replace("_", " "), "lat": round(lat, 7), "lon": round(lon, 7),
            "warehouse_candidate": int(is_wh), "street": tags.get("addr:street", ""),
        })
    places.sort(key=lambda r: (r["osm_type"], r["osm_id"]))
    towns.sort(key=lambda t: t["name"])
    return places, towns


# ------------------------------------------------------------------ river + crossings

def build_river(raw: dict, area: Polygon) -> LineString:
    """Main channel of the Hooghly, trimmed to a box around the study area."""
    lines = [LineString([(p["lon"], p["lat"]) for p in w["geometry"]])
             for w in raw["elements"] if w["type"] == "way" and len(w.get("geometry", [])) > 1]
    channel = main_channel(lines)
    x0, y0, x1, y1 = area.bounds
    box = Polygon([(x0 - 0.05, y0 - 0.05), (x1 + 0.05, y0 - 0.05), (x1 + 0.05, y1 + 0.05), (x0 - 0.05, y1 + 0.05)])
    keep = channel.intersection(box)
    if keep.geom_type != "LineString":  # the channel left and re-entered the box: keep the longest run
        keep = max(keep.geoms, key=lambda g: g.length)
    return keep


def nearest_town(lat: float, lon: float, towns: list[dict]) -> str:
    return min(towns, key=lambda t: (t["lat"] - lat) ** 2 + (t["lon"] - lon) ** 2)["name"] if towns else ""


def build_crossings(raw: dict, river_ll: LineString, area: Polygon, towns: list[dict]) -> list[dict]:
    """Road bridges and ferries that cross the river inside (or at) the study area."""
    near_area = area.buffer(0.01)
    proj = LocalProjection(lat0=area.bounds[1], lon0=area.bounds[0])
    river_xy = LineString([proj.to_xy(lat, lon) for lon, lat in river_ll.coords])
    long_xy = extend(river_xy, 50)
    rows: list[dict] = []

    def add(name, kind, a_ll, b_ll, source, ref):
        rows.append({"name": name, "kind": kind, "lat_a": round(a_ll[1], 6), "lon_a": round(a_ll[0], 6),
                     "lat_b": round(b_ll[1], 6), "lon_b": round(b_ll[0], 6), "source": source, "osm": ref})

    bridges: dict[str, list[tuple[LineString, int]]] = {}
    for el in raw["elements"]:
        if el["type"] != "way" or len(el.get("geometry", [])) < 2:
            continue
        line = LineString([(p["lon"], p["lat"]) for p in el["geometry"]])
        if not line.intersects(river_ll) or not line.intersects(near_area):
            continue
        tags = el.get("tags", {})
        if tags.get("route") == "ferry":
            c = line.coords
            mid = line.interpolate(0.5, normalized=True)
            label = tags.get("name") or f"{nearest_town(mid.y, mid.x, towns)} ferry"
            add(label, "ferry", c[0], c[-1], "OSM ferry route", f"way/{el['id']}")
        else:
            bridges.setdefault(tags.get("name") or f"bridge way/{el['id']}", []).append((line, el["id"]))
    for name, parts in bridges.items():
        ends = [pt for ln, _ in parts for pt in (ln.coords[0], ln.coords[-1])]
        a, b = max(((p, q) for p in ends for q in ends), key=lambda pq: math.dist(*pq))
        add(name, "bridge", a, b, "OSM road bridge", ";".join(f"way/{i}" for _, i in parts))

    # Ferry terminals: pair across the river, else mirror across the centreline.
    terms = []
    for el in raw["elements"]:
        if el["type"] == "node" and el.get("tags", {}).get("amenity") == "ferry_terminal":
            if not near_area.contains(Point(el["lon"], el["lat"])):
                continue
            x, y = proj.to_xy(el["lat"], el["lon"])
            terms.append({"id": el["id"], "name": el["tags"].get("name:en") or el["tags"].get("name") or "",
                          "lat": el["lat"], "lon": el["lon"], "x": x, "y": y, "side": side_of(long_xy, x, y)})
    used: set[int] = set()
    for t in sorted(terms, key=lambda t: (t["name"] == "", t["id"])):
        if t["id"] in used:
            continue
        others = [o for o in terms if o["side"] != t["side"] and o["id"] not in used]
        partner = min(others, key=lambda o: math.dist((t["x"], t["y"]), (o["x"], o["y"])), default=None)
        town = nearest_town(t["lat"], t["lon"], towns)
        if partner and math.dist((t["x"], t["y"]), (partner["x"], partner["y"])) < 1.8:
            used |= {t["id"], partner["id"]}
            label = t["name"] or partner["name"] or f"{town} ferry ghat"
            add(label, "ferry", (t["lon"], t["lat"]), (partner["lon"], partner["lat"]),
                "OSM ferry terminals (paired)", f"node/{t['id']};node/{partner['id']}")
        else:
            used.add(t["id"])
            s = river_xy.project(Point(t["x"], t["y"]))
            c = river_xy.interpolate(s)
            mx, my = 2 * c.x - t["x"], 2 * c.y - t["y"]  # mirror across the channel
            m_lat, m_lon = proj.to_latlon(mx, my)
            label = t["name"] or f"{town} ferry ghat"
            add(label, "ferry", (t["lon"], t["lat"]), (m_lon, m_lat),
                "OSM ferry terminal (far landing estimated)", f"node/{t['id']}")
    rows = [r for r in rows if area.buffer(0.01).contains(Point(r["lon_a"], r["lat_a"]))
            or area.buffer(0.01).contains(Point(r["lon_b"], r["lat_b"]))]
    rows.sort(key=lambda r: (r["kind"], -r["lat_a"]))
    return rows


# ------------------------------------------------------------------ main

# ------------------------------------------------------------------ roads + buildings

def build_roads(raw: dict, area: Polygon) -> dict:
    """Road graph: every OSM node of a drivable way, edges between consecutive nodes."""
    import numpy as np

    proj = LocalProjection(lat0=area.bounds[1], lon0=area.bounds[0])
    coords = {e["id"]: (e["lat"], e["lon"]) for e in raw["elements"] if e["type"] == "node"}
    index: dict[int, int] = {}
    lat, lon = [], []

    def idx(node_id: int) -> int:
        if node_id not in index:
            index[node_id] = len(lat)
            la, lo = coords[node_id]
            lat.append(la)
            lon.append(lo)
        return index[node_id]

    classes: list[str] = []
    names: list[str] = [""]
    u, v, length, cls, name, bridge = [], [], [], [], [], []
    for w in raw["elements"]:
        if w["type"] != "way":
            continue
        tags = w.get("tags", {})
        h = tags.get("highway", "road")
        if h not in classes:
            classes.append(h)
        nm = tags.get("name:en") or tags.get("name") or tags.get("ref") or ""
        if nm not in names:
            names.append(nm)
        refs = [r for r in w.get("nodes", []) if r in coords]
        for a, b in zip(refs, refs[1:]):
            ia, ib = idx(a), idx(b)
            xa, ya = proj.to_xy(*coords[a])
            xb, yb = proj.to_xy(*coords[b])
            u.append(ia); v.append(ib)
            length.append(math.hypot(xb - xa, yb - ya) * 1000.0)
            cls.append(classes.index(h))
            name.append(names.index(nm))
            bridge.append(1 if tags.get("bridge") not in (None, "no") else 0)
    return {
        "lat": np.array(lat), "lon": np.array(lon),
        "u": np.array(u, dtype=np.int32), "v": np.array(v, dtype=np.int32),
        "length_m": np.array(length, dtype=np.float32), "cls": np.array(cls, dtype=np.int8),
        "name": np.array(name, dtype=np.int32), "bridge": np.array(bridge, dtype=np.int8),
        "classes": np.array(classes), "names": np.array(names),
    }


def build_buildings(raw: dict, area: Polygon, roads: dict, towns: list[dict], known: list[dict]) -> list[dict]:
    """Unnamed buildings as extra customers, named from their address or the nearest named road."""
    import numpy as np
    from scipy.spatial import cKDTree

    proj = LocalProjection(lat0=area.bounds[1], lon0=area.bounds[0])
    named_edges = np.nonzero(roads["name"] > 0)[0]
    mid_x, mid_y = [], []
    for e in named_edges:
        a, b = roads["u"][e], roads["v"][e]
        xa, ya = proj.to_xy(roads["lat"][a], roads["lon"][a])
        xb, yb = proj.to_xy(roads["lat"][b], roads["lon"][b])
        mid_x.append((xa + xb) / 2); mid_y.append((ya + yb) / 2)
    road_tree = cKDTree(np.c_[mid_x, mid_y]) if mid_x else None
    taken = {(round(p["lat"], 4), round(p["lon"], 4)) for p in known}
    known_ids = {(p["osm_type"], p["osm_id"]) for p in known}
    rows = []
    for el in raw["elements"]:
        tags = el.get("tags", {})
        lat, lon = latlon(el)
        if lat is None or ("way", el["id"]) in known_ids or tags.get("name"):
            continue  # named buildings are already in the places query
        btype = tags.get("building", "yes")
        if btype in NOT_DELIVERABLE or not area.contains(Point(lon, lat)):
            continue
        if (round(lat, 4), round(lon, 4)) in taken:
            continue
        taken.add((round(lat, 4), round(lon, 4)))
        x, y = proj.to_xy(lat, lon)
        kind = "home" if btype in ("yes", "house", "residential", "apartments", "detached", "semidetached_house",
                                   "terrace", "bungalow") else btype.replace("_", " ")
        hn, street = tags.get("addr:housenumber"), tags.get("addr:street")
        if street:
            label = f"No. {hn}, {street}" if hn else f"Home on {street}"
        else:
            label = None
            if road_tree is not None:
                d, i = road_tree.query([x, y])
                if d <= 0.3:
                    label = f"{'Home' if kind == 'home' else kind.capitalize()} near " \
                            f"{roads['names'][roads['name'][named_edges[i]]]}"
            if label is None:
                label = f"{'Home' if kind == 'home' else kind.capitalize()} in {nearest_town(lat, lon, towns)}"
        rows.append({
            "osm_type": "way", "osm_id": el["id"], "name": label, "category": "building", "kind": kind,
            "lat": round(lat, 7), "lon": round(lon, 7), "warehouse_candidate": 0, "street": street or "",
        })
    rows.sort(key=lambda r: r["osm_id"])
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", default=dt.date.today().strftime("%Y-%m"), help="output folder name, YYYY-MM")
    ap.add_argument("--refresh", action="store_true", help="download every raw file again")
    args = ap.parse_args()

    out = ROOT / "data" / args.month
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    area, _ = study_area()
    names = {"boundary": "overpass_boundary.json", "places": "overpass_region_places.json",
             "river": "overpass_river.json", "crossings": "overpass_crossings.json",
             "roads": "overpass_roads.json.gz", "buildings": "overpass_buildings.json.gz"}
    raw: dict[str, dict] = {}
    for key, query in queries(area).items():
        path = raw_dir / names[key]
        opener = gzip.open if path.suffix == ".gz" else open
        if path.exists() and not args.refresh:
            with opener(path, "rt", encoding="utf-8") as fh:
                raw[key] = json.load(fh)
            continue
        print(f"Fetching {key}...", file=sys.stderr)
        raw[key] = overpass(query)
        with opener(path, "wt", encoding="utf-8") as fh:
            json.dump(raw[key], fh)

    import numpy as np

    places, towns = build_places(raw["places"], area)
    roads = build_roads(raw["roads"], area)
    np.savez_compressed(out / "roads.npz", **roads)
    buildings = build_buildings(raw["buildings"], area, roads, towns, places)
    for p in places:
        p["source"] = "named place"
    for b in buildings:
        b["source"] = "building"
    places = places + buildings
    river = build_river(raw["river"], area)
    crossings = build_crossings(raw["crossings"], river, area, towns)

    way = next(e for e in raw["boundary"]["elements"] if e["type"] == "way")
    ring = [[p["lon"], p["lat"]] for p in way["geometry"]]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    (out / "kalyani_boundary.geojson").write_text(json.dumps({
        "type": "Feature",
        "properties": {"name": way["tags"].get("name", "Kalyani City"), "osm": f"way/{KALYANI_CITY_WAY}",
                       "wikidata": way["tags"].get("wikidata", ""), "attribution": "(c) OpenStreetMap contributors, ODbL"},
        "geometry": {"type": "Polygon", "coordinates": [ring]}}, indent=1))
    (out / "region.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": "Kalyani region", "pad_km": PAD_KM,
                                           "rule": "convex hull of the anchor towns, padded"},
         "geometry": mapping(area)},
        *[{"type": "Feature", "properties": {"name": n, "role": "anchor town", "source": src},
           "geometry": {"type": "Point", "coordinates": [lon, lat]}} for n, lat, lon, src in TOWNS],
    ]}, indent=1))
    (out / "river.geojson").write_text(json.dumps({
        "type": "Feature", "properties": {"name": "Hooghly (Bhagirathi-Hooghly) main channel"},
        "geometry": mapping(river)}))
    write_csv(out / "region_places.csv", places)
    write_csv(out / "towns.csv", towns)
    write_csv(out / "crossings.csv", crossings)
    n_wh = sum(p["warehouse_candidate"] for p in places)
    print(f"Saved {len(places)} places ({len(buildings)} buildings, {n_wh} warehouse candidates), "
          f"{len(towns)} towns, {len(crossings)} crossings, road graph {len(roads['lat'])} nodes / "
          f"{len(roads['u'])} edges to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
