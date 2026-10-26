# data/

OpenStreetMap extracts, one folder per month (`YYYY-MM`), plus hand-kept
additions in `manual/`. Treat each month folder as read-only; to refresh, run
the fetch script, which writes the current month. The app loads the newest
complete folder.

## 2026-10 (fetched 22 Oct 2026, roads and buildings added 26 Oct 2026)

The **Kalyani region**: the convex hull of five town centres (Kalyani, Naihati,
Chakdaha, Mogra, Haringhata) padded by 2.5 km. That is 401 km² on both banks
of the Hooghly.

| File | What it is |
|---|---|
| `raw/overpass_region_places.json` | Overpass response: every named feature (plus warehouses / industrial land) inside the study area |
| `raw/overpass_river.json` | Overpass response: the ways of the OSM relation "Hooghly" near the area |
| `raw/overpass_crossings.json` | Overpass response: road bridges, ferry routes and ferry terminals near the area |
| `raw/overpass_roads.json.gz` | Overpass response (gzipped): every drivable road way (motorway to service roads) inside the area, with its nodes |
| `raw/overpass_buildings.json.gz` | Overpass response (gzipped): every building inside the area, as its centre point with tags |
| `raw/overpass_boundary.json` | Overpass response: the *Kalyani City* outline, OSM way 1094723487 |
| `region.geojson` | Study-area polygon + the five anchor towns (with the OSM node each coordinate came from) |
| `region_places.csv` | 9,422 usable places (52 warehouse candidates): 571 named places plus 8,851 buildings that become homes and other customers. Columns: osm_type, osm_id, name, category, kind, lat, lon, warehouse_candidate, street, source. Unnamed buildings are named from their address, else the nearest named road within 300 m, else the town. |
| `roads.npz` | The road graph: 121,678 nodes (lat, lon) and 129,034 edges (u, v, length in m, road class, name, bridge flag). Ferries are added at load time from `crossings.csv`, for two-wheelers only. |
| `towns.csv` | 10 city/town nodes inside the area (Bansberia, Chakdaha, Gayespur, Halisahar, Haringhata, Hugli-Chuchura, Kalyani, Kanchrapara, Madanpur, Naihati) |
| `river.geojson` | The Hooghly's main channel as one line (side channels around islands dropped) |
| `crossings.csv` | 3 crossings: **Ishwar Gupta Setu** (road bridge), **Naihati Ferry Ghat** (two OSM ferry terminals paired across the river), **Halisahar ferry ghat** (one OSM terminal; far landing estimated by mirroring across the channel) |
| `kalyani_boundary.geojson` | The Kalyani City outline, drawn on the map for context |
| `kalyani_places.csv`, `raw/overpass_places.json` | Legacy: the first extract (Kalyani City only, 242 places). No longer used by the app; kept because raw data is never edited. |

Left out on purpose: the rail-only Jubilee and Sampreeti bridges (Naihati–Bandel),
because delivery vehicles cannot use them, and ferry terminals outside the area
(Jagaddal, Telinipara).

## manual/

`manual/ferries.csv` holds ferry crossings the team knows about that OpenStreetMap
does not map. Columns: `name,lat_a,lon_a,lat_b,lon_b,note`, giving one landing on
each bank. The app adds them to the crossings at start-up, marked "added by hand".
It is empty for now.

## How it is produced

From the project root:

```
python scripts/fetch_osm.py                 # downloads any missing raw files, then rebuilds every output
python scripts/fetch_osm.py --refresh       # downloads every raw file again
```

Data © OpenStreetMap contributors, available under the Open Database License (ODbL).
