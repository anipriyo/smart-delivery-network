"""Sidebar controls and the shared computation every page reads.

The algorithms run once per rerun on the current network; each page then
only draws what it needs from the resulting ``Ctx``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np
import streamlit as st
from shapely.geometry import Polygon

from src.closest_pair import closest_pair
from src.convex_hull import convex_hull
from src.data import Network, network_from_csv, network_to_csv, sample_network
from src.geo import Region, latest_data_dir, load_region
from src.kdtree import KDTree
from src.models import Point
from src.roads import VEHICLES, RoadGraph
from src.voronoi import assign_customers, service_regions

from . import style
from .style import ALGO, LOGO, MAX_WAREHOUSES, esc, fmt_km


@st.cache_resource(show_spinner=False)
def region() -> Region:
    return load_region()


@st.cache_resource(show_spinner="Loading the Kalyani road network…")
def road_graph() -> RoadGraph | None:
    path = latest_data_dir() / "roads.npz"
    if not path.exists():
        return None
    r = region()
    return RoadGraph(path, r.projection, r.river.crossings)


@st.cache_resource(show_spinner=False)
def kalyani_network(n_warehouses: int, n_customers: int, seed: int) -> Network:
    return sample_network(region(), n_warehouses, n_customers, seed)


@dataclass
class Ctx:
    net: Network
    source: str
    wh_index: dict[int, int]  # warehouse id -> position (colour slot)
    assignment: dict[int, int]  # customer id -> warehouse id
    regions: dict[int, Polygon]
    hull: list[Point]
    hull_poly: Polygon | None
    pair: tuple[Point, Point, float] | None
    zone_pairs: dict[int, tuple[Point, Point, float]]
    tree: KDTree | None
    dist_to_hub: dict[int, float]  # customer id -> km (by road when roads are available)
    by_zone: dict[int, list[Point]] = field(default_factory=dict)
    road: RoadGraph | None = None
    vehicle: str = "bike"
    assignment_straight: dict[int, int] = field(default_factory=dict)
    wh_nodes: np.ndarray | None = None  # road node of each warehouse (same order as net.warehouses)
    wh_gaps: np.ndarray | None = None  # km from the warehouse to that node
    cust_nodes: np.ndarray | None = None
    cust_gaps: np.ndarray | None = None
    hub_km: np.ndarray | None = None  # (warehouses x road nodes) road km for the current vehicle
    cust_road_km: np.ndarray | None = None  # (warehouses x customers) door-to-door road km

    @property
    def by_road(self) -> bool:
        return self.road is not None

    @property
    def wh_by_id(self) -> dict[int, Point]:
        return {w.id: w for w in self.net.warehouses}

    @property
    def cust_by_id(self) -> dict[int, Point]:
        return {c.id: c for c in self.net.customers}

    def zone_colour(self, warehouse_id: int) -> str:
        return style.zone_hex(self.wh_index[warehouse_id])

    def colour_of(self) -> dict[int, str]:
        return {w.id: self.zone_colour(w.id) for w in self.net.warehouses}


def compute(net: Network, source: str, vehicle: str = "bike") -> Ctx:
    hubs, custs = net.warehouses, net.customers
    straight = assign_customers(custs, hubs) if hubs else {}
    wh_by_id = {w.id: w for w in hubs}
    g = road_graph() if net.river is not None else None
    assignment, dist = dict(straight), {}
    extra: dict = {}
    if g is not None and hubs and custs:
        wn, wg = g.snap([w.x for w in hubs], [w.y for w in hubs])
        cn, cg = g.snap([c.x for c in custs], [c.y for c in custs])
        hub_km = g.from_sources(wn, vehicle, "km")
        road = hub_km[:, cn] + cg[None, :] + wg[:, None]
        for i, c in enumerate(custs):
            if np.isfinite(road[:, i]).any():
                j = int(np.argmin(road[:, i]))
                assignment[c.id], dist[c.id] = hubs[j].id, float(road[j, i])
            else:  # unreachable by road: fall back to the straight line
                w = wh_by_id[straight[c.id]]
                dist[c.id] = math.hypot(c.x - w.x, c.y - w.y)
        extra = dict(road=g, wh_nodes=wn, wh_gaps=wg, cust_nodes=cn, cust_gaps=cg, hub_km=hub_km,
                     cust_road_km=road)
    else:
        dist = {c.id: math.hypot(c.x - wh_by_id[a].x, c.y - wh_by_id[a].y) for c, a in
                ((c, assignment[c.id]) for c in custs)} if hubs else {}
    by_zone: dict[int, list[Point]] = {w.id: [] for w in hubs}
    for c in custs:
        by_zone[assignment[c.id]].append(c)
    zone_pairs = {wid: closest_pair(pts) for wid, pts in by_zone.items() if len(pts) >= 2}
    hull = convex_hull(custs) if len(custs) >= 3 else []
    return Ctx(
        net=net, source=source,
        wh_index={w.id: i for i, w in enumerate(hubs)},
        assignment=assignment,
        regions=service_regions(hubs, net.region),
        hull=hull,
        hull_poly=Polygon([p.coords() for p in hull]) if len(hull) >= 3 else None,
        pair=closest_pair(custs) if len(custs) >= 2 else None,
        zone_pairs=zone_pairs,
        tree=KDTree(custs) if custs else None,
        dist_to_hub=dist,
        by_zone=by_zone,
        vehicle=vehicle,
        assignment_straight=straight,
        **extra,
    )


def _reshuffle() -> None:
    st.session_state["seed"] = random.randint(1, 9999)


def sidebar() -> Ctx:
    sb = st.sidebar
    with sb:
        style.block(
            f'<div class="sdn-brand"><div class="logo">{LOGO}</div>'
            f'<div><b>{esc(style.PROJECT)}</b><span>Kalyani region · Algorithms II</span></div></div>'
        )

        source = st.segmented_control(
            "Data", ["Kalyani region", "Upload CSV"], default="Kalyani region", required=True,
            key="source", width="stretch",
        )

        net: Network | None = None
        if source == "Kalyani region":
            c = region()
            west = sum(1 for p in c.places if p["bank"] == 0)
            style.block(
                f'<div class="sdn-city"><div class="r1"><span>Kalyani region</span>'
                f'<span>{c.area_km2:.0f} km²</span></div>'
                f'<div class="r2">Kalyani, Naihati, Chakdaha, Haringhata and Mogra, both banks of the Hooghly · '
                f'{len(c.places):,} OpenStreetMap places ({west} west of the river) · extract {esc(c.source)}</div></div>'
            )
            n_w = st.slider("Warehouses", 2, MAX_WAREHOUSES, 5, key="n_w",
                            help="Random real places become dispatch hubs, spread several km apart.")
            max_c = min(1000, (len(c.places) - MAX_WAREHOUSES) // 10 * 10)
            n_c = st.slider("Customers", 10, max_c, min(150, max_c), step=10, key="n_c",
                            help="Random real places (homes, shops, schools, offices...) become delivery stops.")
            if "seed" not in st.session_state:
                st.session_state["seed"] = 42
            seed = st.number_input("Random seed", min_value=0, max_value=99999, step=1, key="seed",
                                   help="Same seed, same network: handy for a repeatable demo.")
            st.button("Shuffle network", icon=":material/casino:", on_click=_reshuffle, width="stretch",
                      help="Pick a new random seed")
            net = kalyani_network(int(n_w), int(n_c), int(seed))
            vehicle = st.segmented_control(
                "Delivery by", list(VEHICLES), format_func=VEHICLES.get, default="bike", required=True,
                key="vehicle", width="stretch",
                help="Road distances and routes use this vehicle. Two-wheelers may also take the Hooghly ferries.")
        else:
            up = st.file_uploader("CSV with type, lat, lon, name", type="csv",
                                  help="type is warehouse or customer; up to 8 warehouses.")
            st.caption("Tip: download the current network from the **Data** page to get a ready-made file.")
            if up is not None:
                try:
                    net = network_from_csv(up)
                    if len(net.warehouses) > MAX_WAREHOUSES:
                        st.error(f"Use at most {MAX_WAREHOUSES} warehouses so each zone keeps a distinct colour.")
                        net = None
                except Exception as exc:  # bad file: tell the user, keep the app alive
                    st.error(str(exc))

        st.divider()
        style.block(
            f'<div class="sdn-foot"><b>{esc(style.COURSE)}</b><br>'
            + " · ".join(esc(n) for n, _ in style.TEAM) + '<br><br>'
            'Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
            'contributors (ODbL) · basemap © <a href="https://carto.com/attributions">CARTO</a>.<br>'
            'Distances to warehouses follow the OpenStreetMap roads (Dijkstra), with the Hooghly crossed only '
            'by Ishwar Gupta Setu or, on a two-wheeler, a ferry.</div>'
        )

    if net is None:
        st.info("Upload a CSV in the sidebar to see your own network, or switch back to **Kalyani region**.",
                icon=":material/upload_file:")
        st.stop()
    return compute(net, source, st.session_state.get("vehicle", "bike") if net.river is not None else "bike")


def csv_bytes(ctx: Ctx) -> str:
    return network_to_csv(ctx.net)


def place_tip(ctx: Ctx, p: Point) -> tuple[str, str, str]:
    """Tooltip lines (title, detail, extra) for a point. Plain text."""
    bank = ""
    if ctx.net.river is not None:
        bank = " · " + ("west bank" if ctx.net.river.bank(p.x, p.y) == 0 else "east bank")
    cat = p.category or p.kind
    if p.kind == "warehouse":
        n = len(ctx.by_zone.get(p.id, []))
        return (p.name or p.label, f"{p.label} · warehouse · {cat}{bank}", f"Serves {n} customer{'s' if n != 1 else ''}")
    hub = ctx.wh_by_id[ctx.assignment[p.id]]
    return (p.name or p.label, f"{p.label} · {cat}{bank}",
            f"Zone {hub.label} · {fmt_km(ctx.dist_to_hub[p.id])} to the hub "
            f"{'by road' if ctx.by_road else '(straight line)'}")


__all__ = ["Ctx", "sidebar", "compute", "csv_bytes", "place_tip", "ALGO"]
