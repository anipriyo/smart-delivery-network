# Smart Delivery Network on Kalyani

**Algorithms II · Group project.** Akash Chakraborty (CSE/23011) · Anipriyo Mandal (CSE/23017) · Arpan Mandal (CSE/23027)

![Network map: Voronoi service zones, convex hull, KD-tree search area, closest stops and the Hooghly with its bridge and ferries, on the OpenStreetMap basemap of the Kalyani region](report/screenshots/network_map.png)

A geometric decision-support dashboard for deliveries around **Kalyani, West
Bengal**. The study area covers about 400 km² and reaches Naihati, Chakdaha,
Haringhata and, across the Hooghly, Mogra and Bansberia.

Random real places from **OpenStreetMap** become warehouses and customers.
Five Algorithms II techniques then plan the network:

- Voronoi decides who serves whom.
- A KD-tree finds what is where.
- Closest pair finds what is near.
- The convex hull shows how far the network reaches.
- Greedy set cover picks the sites worth keeping.

A **river check** then shows where straight-line planning breaks in the real
world. Customers whose nearest warehouse is across the Hooghly can only be
reached over **Ishwar Gupta Setu** or, on two wheels, by **ferry**.

This is not a vehicle-routing system: it does not model traffic, fuel or
driver scheduling.

<table>
  <tr>
    <td width="33%"><img src="report/screenshots/river_crossing.png" alt="River crossing page"></td>
    <td width="33%"><img src="report/screenshots/coverage_planner.png" alt="Coverage planner page"></td>
    <td width="33%"><img src="report/screenshots/walkthrough_kdtree_search.png" alt="Walkthrough page, KD-tree search"></td>
  </tr>
  <tr>
    <td align="center"><b>River crossing</b>: real trips over the bridge or ferry vs. straight lines</td>
    <td align="center"><b>Coverage planner</b>: greedy set cover, round by round</td>
    <td align="center"><b>Walkthrough</b>: every step of each algorithm (here the KD-tree search)</td>
  </tr>
</table>

The full write-up is in [`report/Smart_Delivery_Network_Report.pdf`](report/Smart_Delivery_Network_Report.pdf).

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
| Network map | Voronoi service zones, convex hull (network reach), KD-tree search area, closest stops (region-wide and per zone), the Hooghly with its bridge and ferries. Click any dot to inspect it. |
| River crossing | Customers whose straight-line warehouse is on the other bank; the real trip via bridge (van) or bridge + ferry (two-wheeler); the extra distance; and the hub that is really nearest. |
| Coverage planner | Greedy set cover: which warehouses to keep for a given radius, round by round. |
| Walkthrough | Step through every decision of each algorithm on the current map. |
| Data | The full point set with zones, banks and distances; CSV download. |
| How it works | The algorithms, the OSM pipeline, scope and limits. |

## Structure

- `src/convex_hull.py`: Andrew's monotone chain (a Graham-scan variant)
- `src/closest_pair.py`: divide and conquer
- `src/kdtree.py`: 2D KD-tree with rectangle range search
- `src/voronoi.py`: nearest-warehouse assignment and service zones clipped to the study area
- `src/set_cover.py`: greedy set cover (optional extension), ln n approximation
- `src/river.py`: river banks, trips via bridges/ferries, the river check
- `src/traces.py`: instrumented copies of the algorithms for the Walkthrough page
- `src/geo.py`: study area, places, river, crossings, and the lat/lon → flat km projection
- `src/data.py`: random sampling of real places, CSV import/export
- `ui/`: Streamlit pages, deck.gl map layers and styling; the theme is in `.streamlit/config.toml`
- `scripts/fetch_osm.py`: downloads the OSM extract into `data/<YYYY-MM>/`
- `tests/`: every algorithm checked against a brute-force reference, plus geography, data and river tests
- `report/`: written report and the scripts that produce its numbers and screenshots

## Data

`data/2026-10/` holds the extract the app uses (fetched 22 Oct 2026): 571 named
places, the Hooghly's main channel, and 3 crossings (Ishwar Gupta Setu,
Naihati ferry, Halisahar ferry). See `data/README.md` for every file. To
refresh it (needs internet):

```
python scripts/fetch_osm.py
```

OpenStreetMap maps few ferry ghats here. Add ones you know to
`data/manual/ferries.csv` (`name,lat_a,lon_a,lat_b,lon_b,note`).

Map data © OpenStreetMap contributors (ODbL). Basemap © CARTO.

## CSV upload format

Any city works: the flat km grid is centred on the uploaded points. Upload up to
8 warehouses. Uploaded networks have no river, so the River crossing page is
skipped.

```
type,name,lat,lon
warehouse,Market No. 1,22.97600,88.44356
customer,Cafe Adda,22.97369,88.43705
```
