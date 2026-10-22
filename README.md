# Smart Delivery & Logistics Network — Kalyani

Algorithms II mini project: a geometric decision-support dashboard for a delivery
network in **Kalyani, West Bengal**. Random real places from **OpenStreetMap**
(banks, clinics, colleges, markets, the FCI warehouses...) become warehouses and
customers, and five Algorithms II techniques answer the planning questions on
the real street map. Not a vehicle-routing system: no traffic, fuel or driver
scheduling.

## Run

```
pip install -r requirements.txt
streamlit run app.py
```

On the project Mac the shared venv already has everything:

```
~/.venvs/analysis/bin/streamlit run app.py
```

The OpenStreetMap extract is saved in `data/`, so the algorithms work offline;
only the background street-map tiles need internet.

## Test

```
pytest tests/ -v
```

## Pages

| Page | What it shows |
|---|---|
| Network map | Voronoi service zones, convex hull (network reach), KD-tree search area, closest stops (city-wide and per zone). Click any dot to inspect it. |
| Coverage planner | Greedy set cover: which warehouses to keep for a given radius, round by round. |
| Walkthrough | Step through every decision of each algorithm on the current map. |
| Data | The full point set with zones and distances; CSV download. |
| How it works | The algorithms, the OSM pipeline, scope and limits. |

## Structure

- `src/convex_hull.py` — Andrew's monotone chain (Graham-scan variant), O(n log n)
- `src/closest_pair.py` — divide and conquer, O(n log n)
- `src/kdtree.py` — 2D KD-tree with rectangle range search
- `src/voronoi.py` — nearest-warehouse assignment and service zones clipped to the city
- `src/set_cover.py` — greedy set cover (optional extension), ln n approximation
- `src/traces.py` — instrumented copies of the algorithms for the Walkthrough page
- `src/geo.py` — Kalyani outline + places, lat/lon → flat km projection
- `src/data.py` — random sampling of real places, CSV import/export
- `ui/` — Streamlit pages, deck.gl map layers, styling; theme in `.streamlit/config.toml`
- `scripts/fetch_osm_kalyani.py` — downloads the OSM extract into `data/<YYYY-MM>/`
- `tests/` — each algorithm against a brute-force reference, plus geography and data checks

## Data

`data/2026-10/` holds the extract used by the app (fetched 22 Oct 2026):

- `raw/` — untouched Overpass API responses
- `kalyani_boundary.geojson` — the *Kalyani City* outline (OSM way 1094723487), 40.3 km²
- `kalyani_places.csv` — 242 named places inside it

To refresh it (needs internet; writes a new month folder, which the app then uses):

```
python scripts/fetch_osm_kalyani.py
```

Map data © OpenStreetMap contributors (ODbL). Basemap © CARTO.

## CSV upload format

Any city works: the flat km grid is centred on the uploaded points. Up to 8 warehouses.

```
type,name,lat,lon
warehouse,Market No. 1,22.97600,88.44356
customer,Cafe Adda,22.97369,88.43705
```
