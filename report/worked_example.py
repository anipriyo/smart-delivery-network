"""Print the numbers used in report.md (§2 data facts, §6 worked example, §7 river check, §8 routing).

Run from the project root:
    ~/.venvs/analysis/bin/python report/worked_example.py

Uses the same code and defaults as the dashboard: the newest OSM extract in
data/ (the Kalyani region), seed 42, 5 warehouses, 150 customers, a
two-wheeler, the KD-tree search area centred on Kalyani City (3.0 km x 2.4 km),
a 4.0 km coverage distance along the roads, and the Route planner's opening
example (Medicines, 5 random stops, best warehouse, returning to it). Keep these
in step with ui/state.py and ui/pages.py.
"""

import math
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

from src.closest_pair import closest_pair  # noqa: E402
from src.convex_hull import convex_hull  # noqa: E402
from src.data import PRODUCTS, product_stock, sample_network  # noqa: E402
from src.geo import latest_data_dir, load_region  # noqa: E402
from src.kdtree import KDTree  # noqa: E402
from src.roads import RoadGraph, best_order, held_karp, nearest_neighbour_2opt, plan_route  # noqa: E402
from src.set_cover import greedy_cover, greedy_set_cover  # noqa: E402
from src.traces import (  # noqa: E402
    closest_pair_trace,
    convex_hull_trace,
    kdtree_build_trace,
    kdtree_query_trace,
    voronoi_assignment_trace,
)
from src.voronoi import assign_customers, service_regions  # noqa: E402

SEED, N_WAREHOUSES, N_CUSTOMERS, VEHICLE = 42, 5, 150, "bike"
SEARCH_W, SEARCH_H = 3.0, 2.4  # km, the dashboard's default search area (around Kalyani City)
RADIUS = 4.0  # km along the roads, the Coverage planner's default distance


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
t = time.perf_counter()
g = RoadGraph(latest_data_dir() / "roads.npz", region.projection, rv.crossings)
t_graph = time.perf_counter() - t
net = sample_network(region, N_WAREHOUSES, N_CUSTOMERS, SEED)
hubs, custs = net.warehouses, net.customers
wh = {w.id: w for w in hubs}
idx = {w.id: i for i, w in enumerate(hubs)}

# ------------------------------------------------------------------ region (§2)
x0, y0, x1, y1 = region.boundary_xy.bounds
west = sum(1 for p in region.places if p["bank"] == 0)
named = [p for p in region.places if p.get("source", "named place") == "named place"]
print(f"Region: {region.name}, extract {region.source}, {region.area_km2:.1f} km², "
      f"{x1 - x0:.1f} x {y1 - y0:.1f} km bounding box")
print(f"  projection anchored at lat0={region.projection.lat0:.4f}, lon0={region.projection.lon0:.4f}")
print(f"  {len(region.places)} places ({len(named)} named, {len(region.places) - len(named)} buildings), "
      f"{sum(p['warehouse_candidate'] for p in region.places)} warehouse candidates, "
      f"{west} west bank / {len(region.places) - west} east bank")
print(f"  bank areas: west {rv.banks[0].area:.1f} km², east {rv.banks[1].area:.1f} km²")
print(f"  Hooghly main channel inside the area: {rv.line.intersection(region.boundary_xy).length:.1f} km")
print("  towns: " + ", ".join(f"{t['name']} ({'west' if rv.bank(t['x'], t['y']) == 0 else 'east'})"
                            for t in region.towns))
for x in rv.crossings:
    print(f"  crossing: {x.name} ({x.kind}), {x.length * 1000:.0f} m, {x.source}")
worst = 0.0
pairs = 0
for i, a in enumerate(named):
    for b in named[i + 1:]:
        true = geodesic_km(a["lat"], a["lon"], b["lat"], b["lon"])
        if true >= 0.5:
            pairs += 1
            worst = max(worst, abs(math.hypot(a["x"] - b["x"], a["y"] - b["y"]) - true) / true)
print(f"  projection: worst error {100 * worst:.2f} % over {pairs} named-place pairs >= 0.5 km apart "
      "(vs WGS84 ellipsoid, Vincenty)")
cls_km: dict[str, float] = {}
for c, k in zip(g.edge_cls.tolist(), g.km.tolist()):
    name = g.classes[c].replace("_link", "")
    cls_km[name] = cls_km.get(name, 0.0) + k
print(f"\nRoad graph: {g.n} nodes, {len(g.u)} edges, {g.km.sum():.0f} km of road, "
      f"largest connected part {len(g.main_nodes)} nodes ({100 * len(g.main_nodes) / g.n:.1f} %), "
      f"loaded in {t_graph:.2f} s")
print("  km by class: " + ", ".join(f"{k} {v:.0f}" for k, v in sorted(cls_km.items(), key=lambda t: -t[1])))
print(f"  bridges: {int(np.count_nonzero(np.load(latest_data_dir() / 'roads.npz')['bridge']))} bridge edges; "
      f"ferry edges (two-wheeler only): {[name for _, _, name in g.ferries]}")

gap = 0.55 * math.sqrt(region.area_km2 / N_WAREHOUSES)
print(f"\nNetwork: seed {SEED}, {len(hubs)} warehouses, {len(custs)} customers, vehicle {VEHICLE}; "
      f"target warehouse gap {gap:.2f} km")
kinds: dict[str, int] = {}
for c in custs:
    kinds[c.category] = kinds.get(c.category, 0) + 1
print("  customers by category: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda t: -t[1])))
print("Warehouses")
for w in hubs:
    bank = "west" if rv.bank(w.x, w.y) == 0 else "east"
    print(f"  {w.label}  {w.name} ({w.category}, {bank} bank)  x={w.x:.2f} y={w.y:.2f} km  {w.lat:.5f}, {w.lon:.5f}")
gaps = [math.dist(a.coords(), b.coords()) for i, a in enumerate(hubs) for b in hubs[i + 1:]]
print(f"  closest two warehouses {min(gaps):.2f} km apart")
print(f"  customers on the west bank: {sum(1 for c in custs if rv.bank(c.x, c.y) == 0)}")

# ------------------------------------------------------------------ road distances and assignment
wn, wg = g.snap([w.x for w in hubs], [w.y for w in hubs])
cn, cg = g.snap([c.x for c in custs], [c.y for c in custs])
print(f"\nSnapping: customers are {1000 * np.median(cg):.0f} m (median), {1000 * cg.max():.0f} m (max) from a road node")
straight_assign = assign_customers(custs, hubs)
road_km = {}
for vehicle in ("bike", "van"):
    t = time.perf_counter()
    hub_km = g.from_sources(wn, vehicle, "km")
    t_dij = time.perf_counter() - t
    road_km[vehicle] = hub_km[:, cn] + cg[None, :] + wg[:, None]
    print(f"  Dijkstra from {len(hubs)} warehouses ({vehicle}, km): {1000 * t_dij:.0f} ms")
road = road_km[VEHICLE]
assignment = {c.id: hubs[int(np.argmin(road[:, i]))].id for i, c in enumerate(custs)}
dist = {c.id: float(road[:, i].min()) for i, c in enumerate(custs)}
for vehicle in ("bike", "van"):
    a2 = {c.id: hubs[int(np.argmin(road_km[vehicle][:, i]))].id for i, c in enumerate(custs)}
    moved = [c for c in custs if a2[c.id] != straight_assign[c.id]]
    print(f"  by road ({vehicle}): {len(moved)} of {len(custs)} customers change warehouse vs the straight line")
ratios = [road[idx[straight_assign[c.id]], i] / max(math.dist(c.coords(), wh[straight_assign[c.id]].coords()), 1e-9)
          for i, c in enumerate(custs)]
print(f"  road / straight-line ratio to the straight-line hub: median {statistics.median(ratios):.2f}, "
      f"mean {statistics.mean(ratios):.2f}, max {max(ratios):.2f}")

regions = service_regions(hubs, net.region)
print("\nZones by road (customers, Voronoi cell area, mean and farthest road distance to hub)")
for w in hubs:
    pts = [c for c in custs if assignment[c.id] == w.id]
    ds = [dist[c.id] for c in pts]
    sv = sum(1 for c in custs if straight_assign[c.id] == w.id)
    mean = m(sum(ds) / len(ds)) if ds else "-"
    far = m(max(ds)) if ds else "-"
    print(f"  {w.label}: {len(pts):3d} customers by road ({sv} by straight line), cell {regions[w.id].area:6.2f} km², "
          f"mean {mean}, farthest {far}")
print(f"  cell areas sum to {sum(r.area for r in regions.values()):.2f} km² (area {net.region.area:.2f} km²)")
all_s = [math.dist(c.coords(), wh[straight_assign[c.id]].coords()) for c in custs]
print(f"  average to hub: {m(sum(dist.values()) / len(custs))} by road, {m(sum(all_s) / len(all_s))} straight line")
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
(na, nb), pg = g.snap([p.x, q.x], [p.y, q.y])
pr = g.from_sources([na], VEHICLE, "km")[0, nb] + pg.sum()
print(f"\nClosest pair (region-wide): {p.label} {p.name} ({p.category}) <-> {q.label} {q.name} ({q.category}), "
      f"{m(d)} straight, {m(pr)} by road")
print(f"  brute force would compare {len(custs) * (len(custs) - 1) // 2} pairs")
print(f"  walkthrough: {len(pair_steps)} steps {ev}")
print("Closest pair per zone (zones by road with >= 2 customers)")
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
zones_in = {}
for c in hits:
    zones_in[f"W{assignment[c.id]}"] = zones_in.get(f"W{assignment[c.id]}", 0) + 1
print(f"  zones of the customers inside: {zones_in}")

# ------------------------------------------------------------------ Greedy set cover (by road)
sets = {w.id: {c.id for i, c in enumerate(custs) if road[idx[w.id], i] <= RADIUS} for w in hubs}
picks = greedy_cover({c.id for c in custs}, sets)
total = 0
print(f"\nGreedy set cover at {RADIUS} km along the roads ({VEHICLE}): keep {', '.join(f'W{w}' for w, _ in picks)}")
for i, (wid, new) in enumerate(picks, 1):
    total += len(new)
    print(f"  round {i}: W{wid} {wh[wid].name}, +{len(new)} new, {total}/{len(custs)} covered")
covered = set().union(*(new for _, new in picks)) if picks else set()
print(f"  not covered: {len(custs) - len(covered)}")
dropped = [w for w in hubs if w.id not in {wid for wid, _ in picks}]
print(f"  could close: {', '.join(f'{w.label} {w.name}' for w in dropped) or 'none'}")
chosen_s, rounds_s = greedy_set_cover(hubs, custs, RADIUS)
print(f"  straight-line radius for comparison: keep {', '.join(w.label for w in chosen_s)}, "
      f"{rounds_s[-1]['total_covered'] if rounds_s else 0}/{len(custs)} covered")
print(f"  H(n) bound: {sum(1 / k for k in range(1, len(custs) + 1)):.2f}x optimum")

# ------------------------------------------------------------------ River check by road (as ui/pages.py::_river_rows)
ferry_edges = {frozenset((a, b)): name for a, b, name in g.ferries}
for label, vehicle in (("van (road bridges only)", "van"), ("two-wheeler (bridges + ferries)", "bike")):
    km, pred = g.from_sources(wn, vehicle, "km", predecessors=True)
    rows = []
    for i, c in enumerate(custs):
        h = wh[straight_assign[c.id]]
        if rv.bank(c.x, c.y) == rv.bank(h.x, h.y):
            continue
        every = km[:, cn[i]] + cg[i] + wg
        real = float(every[idx[h.id]])
        path = g.path(pred[idx[h.id]], int(cn[i]))
        via = next((ferry_edges[frozenset((a, b))] for a, b in zip(path, path[1:])
                    if frozenset((a, b)) in ferry_edges), "Ishwar Gupta Setu")
        bi = int(np.argmin(every))
        rows.append(dict(c=c, h=h, straight=math.dist(c.coords(), h.coords()), real=real, via=via,
                         best=hubs[bi], best_real=float(every[bi])))
    print(f"\nRiver check by road, {label}: {len(rows)} customers have their straight-line hub across the river")
    if rows:
        s_ = sum(r["straight"] for r in rows) / len(rows)
        r_ = sum(r["real"] for r in rows) / len(rows)
        print(f"  average straight {s_:.2f} km, real road {r_:.2f} km, extra {r_ - s_:.2f} km (+{100 * (r_ - s_) / s_:.0f} %)")
        used: dict[str, int] = {}
        for r in rows:
            used[r["via"]] = used.get(r["via"], 0) + 1
        print(f"  crossings used: {used}")
        print(f"  a nearer hub by road exists for {sum(1 for r in rows if r['best'].id != r['h'].id)} of {len(rows)}")
        for r in sorted(rows, key=lambda r: -(r["real"] - r["straight"])):
            print(f"    {r['c'].label} {r['c'].name}: {r['h'].label} straight {r['straight']:.2f} km, road {r['real']:.2f} km "
                  f"via {r['via']}; best {r['best'].label} {r['best_real']:.2f} km")

# ------------------------------------------------------------------ Route planner (§8)
stock = product_stock(hubs, SEED)
print("\nRoute planner: stock " + "; ".join(f"{p} at {', '.join(f'W{w}' for w in stock[p])}" for p in PRODUCTS))
product = PRODUCTS[0]
stops = sorted(p.id for p in random.Random(SEED).sample(custs, k=5))
pos = {c.id: i for i, c in enumerate(custs)}
s_idx = [pos[s] for s in stops]
d_idx = [idx[h] for h in stock[product]]
by_id = {c.id: c for c in custs}
for vehicle in ("bike", "van"):
    t = time.perf_counter()
    route = plan_route(g, wn[d_idx], wg[d_idx], cn[s_idx], cg[s_idx], vehicle, closed=True)
    t_route = time.perf_counter() - t
    depot = wh[stock[product][route.depot]]
    seq = [stops[o] for o in route.order]
    pts = [depot] + [by_id[i] for i in seq] + [depot]
    straight = sum(math.dist(a.coords(), b.coords()) for a, b in zip(pts, pts[1:]))
    print(f"  {product}, {len(stops)} stops, {vehicle}: start {depot.label} {depot.name}, {route.method}, "
          f"{route.km:.1f} km ({straight:.1f} km straight), {route.minutes:.0f} min, planned in {1000 * t_route:.0f} ms")
    for n, leg in enumerate(route.legs, 1):
        to = by_id[stops[leg.end - 1]] if leg.end else depot
        print(f"    {n}. to {to.label} {to.name}: {leg.km:.2f} km, {leg.minutes:.1f} min, via {', '.join(leg.roads[:4]) or 'local roads'}")

# 2-opt against the exact Held-Karp order on real travel times (10 random stops, best warehouse)
gaps_pct, same, t_hk, t_2o = [], 0, [], []
for trial in range(20):
    rng = random.Random(1000 + trial)
    pick = rng.sample(range(len(custs)), 10)
    T = g.from_sources([int(wn[0])] + [int(cn[i]) for i in pick], VEHICLE, "min")
    nodes = [int(wn[0])] + [int(cn[i]) for i in pick]
    cost = np.array([[T[a, b] for b in nodes] for a in range(11)])
    np.fill_diagonal(cost, 0)
    if not np.isfinite(cost).all():
        continue
    t = time.perf_counter(); _, opt = held_karp(cost, True); t_hk.append(time.perf_counter() - t)
    t = time.perf_counter(); _, heur = nearest_neighbour_2opt(cost, True); t_2o.append(time.perf_counter() - t)
    gaps_pct.append(100 * (heur - opt) / opt)
    same += heur <= opt + 1e-9
print(f"\n2-opt vs Held-Karp on {len(gaps_pct)} random 10-stop rounds from W{hubs[0].id}: optimal in {same}, "
      f"mean gap {statistics.mean(gaps_pct):.2f} %, worst {max(gaps_pct):.2f} %; "
      f"Held-Karp {1000 * statistics.mean(t_hk):.0f} ms, 2-opt {1000 * statistics.mean(t_2o):.1f} ms on average")
big = random.Random(7).sample(range(len(custs)), 20)
t = time.perf_counter()
r20 = plan_route(g, wn, wg, cn[big], cg[big], VEHICLE, closed=True)
print(f"20-stop round: {r20.method}, {r20.km:.1f} km, {r20.minutes:.0f} min, planned in "
      f"{1000 * (time.perf_counter() - t):.0f} ms")
