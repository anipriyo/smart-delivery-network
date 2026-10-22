# data/

OpenStreetMap extracts of Kalyani, one folder per month (`YYYY-MM`). Treat each
folder as read-only; to refresh, run the fetch script and it writes a new month.
The app loads the newest complete folder.

## 2026-10 (fetched 22 Oct 2026, OSM timestamp 2026-10-22T07:49Z)

| File | What it is |
|---|---|
| `raw/overpass_boundary.json` | Overpass response: the *Kalyani City* outline, OSM way 1094723487 |
| `raw/overpass_places.json` | Overpass response: every named feature (plus warehouses / industrial land) inside that outline, 443 elements |
| `kalyani_boundary.geojson` | The outline as a GeoJSON Polygon (40.3 km²) |
| `kalyani_places.csv` | 243 usable places: osm_type, osm_id, name, category, kind, lat, lon, warehouse_candidate, street. The app keeps the 242 whose centre lies inside the outline. |

## How it is produced

From the project root:

```
python scripts/fetch_osm_kalyani.py                 # fetch + build, writes data/<this month>/
python scripts/fetch_osm_kalyani.py --month 2026-10 --reuse-raw   # rebuild CSV/GeoJSON from raw/ only
```

The script skips roads, rivers, rail lines, parks, parking and plain residential
land, and drops duplicates where one place is mapped as both a node and a building.

Data © OpenStreetMap contributors, available under the Open Database License (ODbL).
