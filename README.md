# Smart Delivery & Logistics Network

Algorithms II mini project: a geometric decision-support dashboard for a delivery
network of warehouses and customers. Not a vehicle-routing system — no traffic,
fuel, or driver scheduling.

## Run

```
pip install -r requirements.txt
streamlit run app.py
```

## Test

```
pytest tests/ -v
```

## Structure

- `src/convex_hull.py` — Graham scan, O(n log n)
- `src/closest_pair.py` — divide and conquer, O(n log n)
- `src/kdtree.py` — 2D KD-tree with rectangle range search
- `src/voronoi.py` — warehouse service regions and nearest-warehouse assignment
- `src/set_cover.py` — greedy set cover (optional extension), ln n approximation
- `src/data.py` — seeded random point generation and a fixed demo set
- `app.py` — Streamlit dashboard tying all of the above together
- `tests/test_algorithms.py` — each algorithm checked against a brute-force reference

## Data format (CSV upload)

```
id,x,y,type
0,20,80,warehouse
5,5,90,customer
```
