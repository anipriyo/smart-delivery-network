"""Fetch Kalyani (West Bengal) from OpenStreetMap and save it for the dashboard.

Run once (needs internet):
    python scripts/fetch_osm_kalyani.py            # writes data/<YYYY-MM>/
    python scripts/fetch_osm_kalyani.py --month 2026-10

Outputs, all under data/<YYYY-MM>/:
    raw/overpass_boundary.json   untouched Overpass response for the city outline
    raw/overpass_places.json     untouched Overpass response for named places
    kalyani_boundary.geojson     the city outline as a GeoJSON Polygon
    kalyani_places.csv           one row per usable place (name, category, lat, lon, ...)

The city outline is the OSM way 1094723487 "Kalyani City" (landuse=residential,
wikidata Q2734589). The larger relation 10370850 is the Kalyani sub-district,
which includes rural land, so it is not used.

Data (c) OpenStreetMap contributors, available under the ODbL.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

CITY_WAY_ID = 1094723487
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "SmartDeliveryNetwork-student-project/1.0 (Algorithms II coursework, Kalyani)"

BOUNDARY_QUERY = f"[out:json][timeout:90];way({CITY_WAY_ID});out geom;"

# Every named feature inside the city, plus unnamed warehouses / industrial land.
PLACES_QUERY = f"""
[out:json][timeout:180];
way({CITY_WAY_ID});
map_to_area->.city;
(
  nwr["name"](area.city);
  nwr["industrial"="warehouse"](area.city);
  nwr["building"="warehouse"](area.city);
  nwr["landuse"="industrial"](area.city);
);
out center tags;
"""

# Tags that make a feature a plausible delivery stop, in priority order.
CATEGORY_KEYS = [
    "amenity", "shop", "office", "healthcare", "craft", "tourism",
    "leisure", "railway", "industrial", "building", "landuse",
]
# Features that are not delivery stops at all.
EXCLUDE_KEYS = {"highway", "waterway", "natural", "boundary", "power", "route", "place", "barrier"}
EXCLUDE_VALUES = {
    ("railway", "rail"), ("railway", "platform"), ("railway", "level_crossing"),
    ("landuse", "residential"), ("landuse", "farmland"), ("landuse", "grass"),
    ("landuse", "meadow"), ("landuse", "forest"), ("landuse", "orchard"),
    ("leisure", "park"), ("leisure", "garden"), ("leisure", "pitch"), ("leisure", "playground"),
    ("amenity", "parking"), ("amenity", "bench"), ("amenity", "waste_basket"),
}
# Features that make sense as a warehouse / dispatch hub.
WAREHOUSE_TAGS = {
    ("industrial", "warehouse"), ("building", "warehouse"), ("landuse", "industrial"),
    ("building", "industrial"), ("landuse", "commercial"), ("building", "commercial"),
    ("shop", "wholesale"), ("amenity", "post_office"), ("office", "logistics"),
    ("amenity", "marketplace"), ("shop", "supermarket"), ("landuse", "retail"),
}


def overpass(query: str) -> dict:
    """POST a query, trying each mirror with exponential backoff."""
    body = urllib.parse.urlencode({"data": query}).encode()
    last_error: Exception | None = None
    for attempt in range(4):
        for url in ENDPOINTS:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=200) as resp:
                    text = resp.read().decode("utf-8")
                data = json.loads(text)
                print(f"  ok from {url}", file=sys.stderr)
                return data
            except Exception as exc:  # busy server, timeout or HTML error page
                last_error = exc
                print(f"  {url} failed: {str(exc)[:80]}", file=sys.stderr)
        wait = 10 * 2**attempt
        print(f"  all mirrors busy, retrying in {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"Overpass unavailable: {last_error}")


def classify(tags: dict) -> tuple[str, str] | None:
    """Return (category, value) for a usable place, or None to skip it."""
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


def build_places(raw: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, float, float]] = set()
    for el in raw["elements"]:
        tags = el.get("tags", {})
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        cat = classify(tags)
        if cat is None:
            continue
        name = tags.get("name") or tags.get("name:en") or ""
        is_warehouse = any((k, tags.get(k)) in WAREHOUSE_TAGS for k in tags)
        if not name:
            if not is_warehouse:
                continue
            name = "Unnamed warehouse" if "warehouse" in tags.values() else "Industrial site"
        key = (name.lower(), round(lat, 4), round(lon, 4))
        if key in seen:  # same place mapped as both node and building
            continue
        seen.add(key)
        rows.append({
            "osm_type": el["type"],
            "osm_id": el["id"],
            "name": name.strip(),
            "category": cat[0],
            "kind": cat[1].replace("_", " "),
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "warehouse_candidate": int(is_warehouse),
            "street": tags.get("addr:street", ""),
        })
    rows.sort(key=lambda r: (r["osm_type"], r["osm_id"]))
    return rows


def boundary_geojson(raw: dict) -> dict:
    way = next(e for e in raw["elements"] if e["type"] == "way" and e["id"] == CITY_WAY_ID)
    ring = [[p["lon"], p["lat"]] for p in way["geometry"]]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {
        "type": "Feature",
        "properties": {
            "name": way["tags"].get("name", "Kalyani City"),
            "osm": f"way/{CITY_WAY_ID}",
            "wikidata": way["tags"].get("wikidata", ""),
            "attribution": "(c) OpenStreetMap contributors, ODbL",
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", default=dt.date.today().strftime("%Y-%m"), help="output folder name, YYYY-MM")
    ap.add_argument("--reuse-raw", action="store_true", help="rebuild CSV/GeoJSON from saved raw files only")
    args = ap.parse_args()

    out = Path(__file__).resolve().parent.parent / "data" / args.month
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    b_path, p_path = raw_dir / "overpass_boundary.json", raw_dir / "overpass_places.json"

    if args.reuse_raw:
        b_raw, p_raw = json.loads(b_path.read_text()), json.loads(p_path.read_text())
    else:
        print("Fetching city boundary...", file=sys.stderr)
        b_raw = overpass(BOUNDARY_QUERY)
        b_path.write_text(json.dumps(b_raw))
        print("Fetching named places...", file=sys.stderr)
        p_raw = overpass(PLACES_QUERY)
        p_path.write_text(json.dumps(p_raw))

    (out / "kalyani_boundary.geojson").write_text(json.dumps(boundary_geojson(b_raw), indent=1))
    rows = build_places(p_raw)
    with open(out / "kalyani_places.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    n_wh = sum(r["warehouse_candidate"] for r in rows)
    print(f"Saved {len(rows)} places ({n_wh} warehouse candidates) to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
