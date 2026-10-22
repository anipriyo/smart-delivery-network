"""Sidebar controls and the shared computation every page reads.

The algorithms run once per rerun on the current network; each page then
only draws what it needs from the resulting ``Ctx``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import streamlit as st
from shapely.geometry import Polygon

from src.closest_pair import closest_pair
from src.convex_hull import convex_hull
from src.data import Network, network_from_csv, network_to_csv, sample_network
from src.geo import City, load_city
from src.kdtree import KDTree
from src.models import Point
from src.voronoi import assign_customers, service_regions

from . import style
from .style import ALGO, LOGO_SVG, MAX_WAREHOUSES, esc, fmt_km


@st.cache_resource(show_spinner=False)
def city() -> City:
    return load_city()


@st.cache_data(show_spinner=False)
def kalyani_network(n_warehouses: int, n_customers: int, seed: int) -> Network:
    return sample_network(city(), n_warehouses, n_customers, seed)


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
    dist_to_hub: dict[int, float]  # customer id -> km
    by_zone: dict[int, list[Point]] = field(default_factory=dict)

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


def compute(net: Network, source: str) -> Ctx:
    hubs, custs = net.warehouses, net.customers
    assignment = assign_customers(custs, hubs) if hubs else {}
    wh_by_id = {w.id: w for w in hubs}
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
    )


def _reshuffle() -> None:
    st.session_state["seed"] = random.randint(1, 9999)


def sidebar() -> Ctx:
    sb = st.sidebar
    with sb:
        style.block(
            f'<div class="sdn-brand"><div class="logo">{LOGO_SVG}</div>'
            '<div><b>Smart Delivery Network</b><span>Algorithms II · Kalyani</span></div></div>'
        )

        source = st.segmented_control(
            "Data", ["Kalyani (OSM)", "Upload CSV"], default="Kalyani (OSM)", required=True,
            key="source", width="stretch",
        )

        net: Network | None = None
        if source == "Kalyani (OSM)":
            c = city()
            style.block(
                f'<div class="sdn-city"><div class="r1"><span>{esc(c.name)}</span>'
                f'<span>{c.area_km2:.1f} km²</span></div>'
                f'<div class="r2">Nadia, West Bengal · {len(c.places):,} named places from OpenStreetMap '
                f'(extract {esc(c.source)})</div></div>'
            )
            n_w = st.slider("Warehouses", 2, MAX_WAREHOUSES, 5, key="n_w",
                            help="Random real places become dispatch hubs, kept at least ~1 km apart.")
            max_c = min(300, (len(c.places) - MAX_WAREHOUSES) // 5 * 5)
            n_c = st.slider("Customers", 10, max_c, min(60, max_c), step=5, key="n_c",
                            help="Random real places (shops, schools, offices, homes...) become delivery stops.")
            if "seed" not in st.session_state:
                st.session_state["seed"] = 42
            seed = st.number_input("Random seed", min_value=0, max_value=99999, step=1, key="seed",
                                   help="Same seed, same network: handy for a repeatable demo.")
            st.button("Shuffle network", icon=":material/casino:", on_click=_reshuffle, width="stretch",
                      help="Pick a new random seed")
            net = kalyani_network(int(n_w), int(n_c), int(seed))
        else:
            up = st.file_uploader("CSV with type, lat, lon, name", type="csv",
                                  help="type is warehouse or customer; up to 8 warehouses.")
            st.caption("Tip: download the current Kalyani network from the **Data** page to get a ready-made file.")
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
            '<div class="sdn-foot">Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
            'contributors (ODbL) · basemap © <a href="https://carto.com/attributions">CARTO</a>.<br>'
            'Distances are straight-line (Euclidean) on a flat km grid, not road distance.</div>'
        )

    if net is None:
        st.info("Upload a CSV in the sidebar to see your own network, or switch back to **Kalyani (OSM)**.",
                icon=":material/upload_file:")
        st.stop()
    return compute(net, source)


def csv_bytes(ctx: Ctx) -> str:
    return network_to_csv(ctx.net)


def place_tip(ctx: Ctx, p: Point) -> str:
    """Tooltip HTML for a point."""
    name = esc(p.name or p.label)
    cat = esc(p.category or p.kind)
    if p.kind == "warehouse":
        n = len(ctx.by_zone.get(p.id, []))
        return (f"<b>{name}</b><br><span style='opacity:.7'>{p.label} · warehouse · {cat}</span>"
                f"<br>Serves <b>{n}</b> customer{'s' if n != 1 else ''}")
    hub = ctx.wh_by_id[ctx.assignment[p.id]]
    return (f"<b>{name}</b><br><span style='opacity:.7'>{p.label} · {cat}</span>"
            f"<br>Zone <b>{hub.label}</b> · {fmt_km(ctx.dist_to_hub[p.id])} from hub")


__all__ = ["Ctx", "sidebar", "compute", "csv_bytes", "place_tip", "ALGO"]
