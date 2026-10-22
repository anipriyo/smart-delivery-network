"""Print the numbers used in report.md (§2 data facts, §6 worked example, §7 river check).

Run from the project root:
    ~/.venvs/analysis/bin/python report/worked_example.py

Uses the same code and defaults as the dashboard: the newest OSM extract in
data/ (the Kalyani region), seed 42, 5 warehouses, 80 customers, the KD-tree
search area centred on Kalyani City (3.0 km x 2.4 km) and a 4.0 km coverage
radius. Keep these in step with ui/state.py and ui/pages.py.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import Polygon  # noqa: E402

from src.closest_pair import closest_pair  # noqa: E402
from src.convex_hull import convex_hull  # noqa: E402
from src.data import sample_network  # noqa: E402
from src.geo import load_region  # noqa: E402
from src.kdtree import KDTree  # noqa: E402
from src.river import TWO_WHEELER, VAN, river_check  # noqa: E402
from src.set_cover import greedy_set_cover  # noqa: E402
from src.traces import (  # noqa: E402
    closest_pair_trace,
    convex_hull_trace,
    kdtree_build_trace,
    kdtree_query_trace,
    voronoi_assignment_trace,
)
from src.voronoi import assign_customers, service_regions  # noqa: E402

SEED, N_WAREHOUSES, N_CUSTOMERS = 42, 5, 80
SEARCH_W, SEARCH_H = 3.0, 2.4  # km, the dashboard's default search area (around Kalyani City)
RADIUS = 4.0  # km, the Coverage planner's default radius


def m(km: float) -> str:
    return f"{km * 1000:.0f} m" if km < 1 else f"{km:.2f} km"


def geodesic_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Vincenty's inverse formula on the WGS84 ellipsoid (reference distance)."""
    a, f = 6378.137, 1 / 298.257223563
    b = (1 - f) * a
    u1, u2 = math.atan((1 - f) * math.tan(math.radians(lat1))), math.atan((1 - f) * math.tan(math.radians(lat2)))
    big_l = lam = math.radians(lon2 - lon1)
    for _ in range(200):
        sin_s = math.hypot(math.cos(u2) * math.sin(lam),
                           math.cos(u1) * math.sin(u2) - math.sin(u1) * math.cos(u2) * math.cos(lam))
        if sin_s == 0:
            return 0.0
        cos_s = math.sin(u1) * math.sin(u2) + math.cos(u1) * math.cos(u2) * math.cos(lam)
        sigma = math.atan2(sin_s, cos_s)
        sin_a = math.cos(u1) * math.cos(u2) * math.sin(lam) / sin_s
        cos2_a = 1 - sin_a ** 2
        cos_2sm = cos_s - 2 * math.sin(u1) * math.sin(u2) / cos2_a
        c = f / 16 * cos2_a * (4 + f * (4 - 3 * cos2_a))
        prev, lam = lam, big_l + (1 - c) * f * sin_a * (
            sigma + c * sin_s * (cos_2sm + c * cos_s * (-1 + 2 * cos_2sm ** 2)))
        if abs(lam - prev) < 1e-13:
            break
    usq = cos2_a * (a * a - b * b) / (b * b)
    big_a = 1 + usq / 16384 * (4096 + usq * (-768 + usq * (320 - 175 * usq)))
    big_b = usq / 1024 * (256 + usq * (-128 + usq * (74 - 47 * usq)))
    d_sigma = big_b * sin_s * (cos_2sm + big_b / 4 * (cos_s * (-1 + 2 * cos_2sm ** 2)
                               - big_b / 6 * cos_2sm * (-3 + 4 * sin_s ** 2) * (-3 + 4 * cos_2sm ** 2)))
    return b * big_a * (sigma - d_sigma)


region = load_region()
rv = region.river
net = sample_network(region, N_WAREHOUSES, N_CUSTOMERS, SEED)
hubs, custs = net.warehouses, net.customers
wh = {w.id: w for w in hubs}

# ------------------------------------------------------------------ region (§2)
x0, y0, x1, y1 = region.boundary_xy.bounds
west = sum(1 for p in region.places if p["bank"] == 0)
print(f"Region: {region.name}, extract {region.source}, {region.area_km2:.1f} km², "
      f"{x1 - x0:.1f} x {y1 - y0:.1f} km bounding box")
print(f"  projection anchored at lat0={region.projection.lat0:.4f}, lon0={region.projection.lon0:.4f}")
print(f"  {len(region.places)} places, {sum(p['warehouse_candidate'] for p in region.places)} warehouse candidates, "
      f"{west} west bank / {len(region.places) - west} east bank")
print(f"  bank areas: west {rv.banks[0].area:.1f} km², east {rv.banks[1].area:.1f} km²")
print("  towns: " + ", ".join(f"{t['name']} ({'west' if rv.bank(t['x'], t['y']) == 0 else 'east'})"
                            for t in region.towns))
for x in rv.crossings:
    print(f"  crossing: {x.name} ({x.kind}), {x.length * 1000:.0f} m, {x.source}")
worst = worst_h = 0.0
pairs = 0
for i, a in enumerate(region.places):
    for b in region.places[i + 1:]:
        true = geodesic_km(a["lat"], a["lon"], b["lat"], b["lon"])
        if true >= 0.5:
            pairs += 1
            worst = max(worst, abs(math.hypot(a["x"] - b["x"], a["y"] - b["y"]) - true) / true)
print(f"  projection: worst error {100 * worst:.2f} % over {pairs} place pairs >= 0.5 km apart "
      "(vs WGS84 ellipsoid, Vincenty)")
gap = 0.55 * math.sqrt(region.area_km2 / N_WAREHOUSES)
print(f"\nNetwork: seed {SEED}, {len(hubs)} warehouses, {len(custs)} customers; target warehouse gap {gap:.2f} km")

print("Warehouses")
for w in hubs:
    bank = "west" if rv.bank(w.x, w.y) == 0 else "east"
    print(f"  {w.label}  {w.name} ({w.category}, {bank} bank)  x={w.x:.2f} y={w.y:.2f} km  {w.lat:.5f}, {w.lon:.5f}")
gaps = [math.dist(a.coords(), b.coords()) for i, a in enumerate(hubs) for b in hubs[i + 1:]]
print(f"  closest two warehouses {min(gaps):.2f} km apart")
print(f"  customers on the west bank: {sum(1 for c in custs if rv.bank(c.x, c.y) == 0)}")

# ------------------------------------------------------------------ Voronoi
assignment = assign_customers(custs, hubs)
regions = service_regions(hubs, net.region)
print("\nVoronoi zones (customers, zone area, mean and farthest distance to hub)")
for w in hubs:
    pts = [c for c in custs if assignment[c.id] == w.id]
    ds = [math.hypot(c.x - w.x, c.y - w.y) for c in pts]
    mean = m(sum(ds) / len(ds)) if ds else "-"
    far = m(max(ds)) if ds else "-"
    print(f"  {w.label}: {len(pts):2d} customers, {regions[w.id].area:6.2f} km², mean {mean}, farthest {far}")
print(f"  zone areas sum to {sum(r.area for r in regions.values()):.2f} km² (area {net.region.area:.2f} km²)")
all_d = [math.hypot(c.x - wh[assignment[c.id]].x, c.y - wh[assignment[c.id]].y) for c in custs]
print(f"  average distance to assigned hub: {m(sum(all_d) / len(all_d))}")
c1 = custs[0]
rows = voronoi_assignment_trace(c1, hubs)
print(f"  trace for {c1.label} ({c1.name}): "
      + ", ".join(f"W{r['warehouse']} {m(r['distance'])}" for r in rows)
      + f" -> zone W{rows[-1]['best_so_far']}")

# ------------------------------------------------------------------ Convex hull
hull = convex_hull(custs)
area = Polygon([p.coords() for p in hull]).area
_, hull_steps = convex_hull_trace(custs)
pops = sum(1 for s in hull_steps if s["action"] == "pop")
print(f"\nConvex hull: {len(hull)} boundary stops, {area:.2f} km² "
      f"({100 * area / net.region.area:.0f} % of the study area)")
print("  " + " -> ".join(f"{p.label} {p.name}" for p in hull))
print(f"  walkthrough: {len(hull_steps)} steps ({len(hull_steps) - pops} pushes, {pops} pops)")

# ------------------------------------------------------------------ Closest pair
p, q, d = closest_pair(custs)
_, pair_steps = closest_pair_trace(custs)
ev = {e: sum(1 for s in pair_steps if s["event"] == e) for e in ("divide", "base case", "combine", "strip check")}
print(f"\nClosest pair (region-wide): {p.label} {p.name} ({p.category}) <-> {q.label} {q.name} ({q.category}), {m(d)}")
print(f"  brute force would compare {len(custs) * (len(custs) - 1) // 2} pairs")
print(f"  walkthrough: {len(pair_steps)} steps {ev}")
print("Closest pair per zone (zones with >= 2 customers)")
zone_pairs = []
for w in hubs:
    pts = [c for c in custs if assignment[c.id] == w.id]
    if len(pts) >= 2:
        zone_pairs.append((w, *closest_pair(pts)))
for w, a, b, dd in sorted(zone_pairs, key=lambda t: t[3]):
    print(f"  {w.label}: {a.label} {a.name} <-> {b.label} {b.name}, {m(dd)}")

# ------------------------------------------------------------------ KD-tree
tree = KDTree(custs)
ring = [net.projection.to_xy(lat, lon) for lon, lat in net.inner_outline_lonlat]
centre = Polygon(ring).centroid  # Kalyani City, as in ui/pages.py::_kalyani_centre
box = (centre.x - SEARCH_W / 2, centre.x + SEARCH_W / 2, centre.y - SEARCH_H / 2, centre.y + SEARCH_H / 2)
hits = tree.range_query(*box)
found, q_steps = kdtree_query_trace(tree, *box)
visited = [s for s in q_steps if not s.get("pruned")]
pruned = [s for s in q_steps if s.get("pruned")]
brute = [c for c in custs if box[0] <= c.x <= box[1] and box[2] <= c.y <= box[3]]
build_steps = kdtree_build_trace(custs, net.bounds_xy)
print(f"\nKD-tree: {len(build_steps)} build splits, depth {max(s['depth'] for s in build_steps) + 1} levels")
print(f"  search area centred on Kalyani City's centroid ({centre.x:.2f}, {centre.y:.2f}) km, "
      f"{SEARCH_W} x {SEARCH_H} km: x {box[0]:.2f}-{box[1]:.2f}, y {box[2]:.2f}-{box[3]:.2f}")
print(f"  {len(hits)} customers inside (brute force agrees: {sorted(c.id for c in brute) == sorted(c.id for c in hits)})")
print(f"  visited {len(visited)} of {len(custs)} nodes, skipped {len(pruned)} subtrees, {len(q_steps)} walkthrough steps")
for c in sorted(hits, key=lambda c: math.hypot(c.x - centre.x, c.y - centre.y)):
    print(f"    {c.label} {c.name} ({c.category}), zone W{assignment[c.id]}")

# ------------------------------------------------------------------ Greedy set cover
chosen, rounds = greedy_set_cover(hubs, custs, RADIUS)
print(f"\nGreedy set cover at {RADIUS} km: keep {', '.join(w.label for w in chosen)}")
for i, r in enumerate(rounds, 1):
    w = r["site"]
    print(f"  round {i}: {w.label} {w.name}, +{len(r['new_covered'])} new, {r['total_covered']}/{len(custs)} covered")
covered = set().union(*(r["new_covered"] for r in rounds)) if rounds else set()
for c in custs:
    if c.id not in covered:
        near = min(math.hypot(c.x - w.x, c.y - w.y) for w in hubs)
        print(f"  not covered: {c.label} {c.name} ({c.category}), nearest warehouse {near:.2f} km away")
dropped = [w for w in hubs if w not in chosen]
print(f"  could close: {', '.join(f'{w.label} {w.name}' for w in dropped) or 'none'}")
print(f"  H(n) bound: {sum(1 / k for k in range(1, len(custs) + 1)):.2f}x optimum")

# ------------------------------------------------------------------ River check
for label, kinds in (("van (road bridges only)", VAN), ("two-wheeler (bridges + ferries)", TWO_WHEELER)):
    rows = river_check(custs, hubs, assignment, rv, kinds)
    ok = [r for r in rows if math.isfinite(r["real"])]
    print(f"\nRiver check by {label}: {len(rows)} customers have their straight-line hub across the river")
    if ok:
        s = sum(r["straight"] for r in ok) / len(ok)
        real = sum(r["real"] for r in ok) / len(ok)
        print(f"  average straight {s:.2f} km, real {real:.2f} km, extra {real - s:.2f} km (+{100 * (real - s) / s:.0f} %)")
    used: dict[str, int] = {}
    for r in ok:
        used[r["crossing"].name] = used.get(r["crossing"].name, 0) + 1
    print(f"  crossings used: {used}")
    switch = [r for r in ok if r["best_hub"].id != r["hub"].id]
    print(f"  a nearer hub exists for {len(switch)} of {len(rows)}")
    for r in sorted(rows, key=lambda r: -(r["real"] - r["straight"])):
        cu, hub, best = r["customer"], r["hub"], r["best_hub"]
        via = r["crossing"].name if r["crossing"] else "no crossing"
        print(f"    {cu.label} {cu.name}: {hub.label} straight {r['straight']:.2f} km, real {r['real']:.2f} km "
              f"via {via}; best {best.label} {r['best_real']:.2f} km"
              + (f" via {r['best_crossing'].name}" if r["best_crossing"] else " (same bank)"))
