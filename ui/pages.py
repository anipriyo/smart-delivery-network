"""The dashboard's pages. Each reads the shared ``Ctx`` from session state."""

from __future__ import annotations

import math

import altair as alt
import pandas as pd
import streamlit as st

from shapely.geometry import Polygon

from src.models import Point
from src.river import TWO_WHEELER, VAN, river_check
from src.set_cover import greedy_set_cover
from src.traces import (
    closest_pair_trace,
    convex_hull_trace,
    kdtree_build_trace,
    kdtree_query_trace,
    voronoi_assignment_trace,
)

from . import layers as L
from . import style
from .state import Ctx, csv_bytes, place_tip, region
from .style import ALGO, BRIDGE, CRITICAL, FERRY, INK, RIVER, esc, fmt_km, rgb

NEUTRAL = "#94A3B8"
MODES = {"van": ("Delivery van", "road bridges only", VAN), "bike": ("Two-wheeler", "bridges + ferries", TWO_WHEELER)}


def ctx() -> Ctx:
    return st.session_state["ctx"]


# ====================================================================== helpers

def _hero_for(c: Ctx, page: str, title: str, sub: str, team: bool = False) -> None:
    """Page header: project + course, page title, summary chips."""
    net = c.net
    chips = []
    if net.river is not None:
        chips.append((f"OpenStreetMap · {net.region.area:.0f} km² · both banks of the Hooghly", RIVER))
    chips.append((f"{len(net.warehouses)} warehouses · {len(net.customers)} customers", style.BRAND))
    if c.source.startswith("Kalyani"):
        chips.append((f"Seed {st.session_state.get('seed', 42)}", NEUTRAL))
    style.header(page, title, sub, chips, team=team)


def _kalyani_centre(c: Ctx) -> tuple[float, float]:
    net = c.net
    if net.inner_outline_lonlat:
        ring = [net.projection.to_xy(lat, lon) for lon, lat in net.inner_outline_lonlat]
        cen = Polygon(ring).centroid
        return (cen.x, cen.y)
    cen = net.region.centroid
    return (cen.x, cen.y)


def _search_options(c: Ctx) -> dict[str, tuple[float, float]]:
    opts = {"Kalyani centre": _kalyani_centre(c)}
    for w in c.net.warehouses:
        opts[f"{w.label} · {w.name}"] = (w.x, w.y)
    for p in sorted(c.net.customers, key=lambda p: p.id):
        opts[f"{p.label} · {p.name}"] = (p.x, p.y)
    return opts


def _option_for(p: Point) -> str:
    return f"{p.label} · {p.name}"


def search_box(c: Ctx) -> tuple[float, float, float, float]:
    """Current KD-tree search rectangle (x0, x1, y0, y1) in km."""
    opts = _search_options(c)
    key = st.session_state.get("search_centre", "Kalyani centre")
    cx, cy = opts.get(key, opts["Kalyani centre"])
    w = st.session_state.get("search_w", 3.0)
    h = st.session_state.get("search_h", 2.4)
    return (cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2)


def _selected(c: Ctx, state_key: str) -> Point | None:
    """The place clicked on a map last run, if it still exists in this network."""
    state = st.session_state.get(state_key)
    try:
        objects = state["selection"]["objects"]
    except (TypeError, KeyError):
        return None
    for layer_id in ("hubs", "customers"):
        for obj in objects.get(layer_id, []):
            pool = c.wh_by_id if obj.get("kind") == "warehouse" else c.cust_by_id
            p = pool.get(obj.get("pid"))
            if p is not None:
                lon, lat = obj["pos"]
                if abs(lat - p.lat) < 1e-9 and abs(lon - p.lon) < 1e-9:
                    return p
    return None


def _set_centre(label: str) -> None:
    st.session_state["search_centre"] = label


def _rows(items: list[tuple[str, str, str, str]]) -> str:
    """items: (colour, title, subtitle, right); ``right`` may hold trusted markup."""
    return "".join(
        f'<div class="sdn-row" style="--c:{col}"><span class="pin"></span><div class="col">'
        f'<span class="t">{esc(t)}</span><span class="s">{esc(s)}</span></div><span class="r">{r}</span></div>'
        for col, t, s, r in items
    )


# ====================================================================== network

def network() -> None:
    c = ctx()
    net = c.net
    colour_of = c.colour_of()
    box = search_box(c)
    hits = c.tree.range_query(*box) if c.tree else []
    hit_ids = {p.id for p in hits}

    where = "Kalyani" if net.river is not None else "your city"
    _hero_for(
        c, "",
        f'Smart Delivery Network <span class="accent">on {where}</span>',
        "Kalyani and its neighbours (Naihati, Halisahar, Kanchrapara, Chakdaha, Haringhata, and Mogra and "
        "Bansberia across the Hooghly). Random real places from OpenStreetMap become warehouses and "
        "customers, and five Algorithms II techniques plan the network: <b>who serves whom</b> (Voronoi), "
        "<b>what is where</b> (KD-tree), <b>what is close</b> (closest pair), <b>how far it reaches</b> "
        "(convex hull) and <b>which sites to keep</b> (greedy set cover).",
        team=True,
    )

    # ------------------------------------------------------------------ KPIs
    sizes = {wid: len(pts) for wid, pts in c.by_zone.items()}
    busiest = max(sizes, key=sizes.get) if sizes else None
    avg = sum(c.dist_to_hub.values()) / len(c.dist_to_hub) if c.dist_to_hub else 0
    reach = c.hull_poly.area if c.hull_poly is not None else 0
    cards = [
        {"label": "Service zones", "value": len(net.warehouses), "accent": ALGO["voronoi"],
         "sub": f"busiest: {c.wh_by_id[busiest].label} ({sizes[busiest]})" if busiest else ""},
        {"label": "Delivery stops", "value": len(net.customers), "accent": style.BRAND,
         "sub": f"avg {fmt_km(avg)} to hub"},
        {"label": "Network reach", "value": f"{reach:.1f}", "unit": "km²", "accent": ALGO["hull"],
         "sub": f"{len(c.hull)} boundary stops"},
        {"label": "Closest stops", "value": fmt_km(c.pair[2]) if c.pair else "–", "accent": ALGO["pair"],
         "sub": f"{c.pair[0].label} ↔ {c.pair[1].label}" if c.pair else ""},
        {"label": "In search area", "value": len(hits), "accent": ALGO["kdtree"],
         "sub": f"of {len(net.customers)} customers"},
    ]
    if net.river is not None:
        cross = river_check(net.customers, net.warehouses, c.assignment, net.river, VAN)
        cards.append({"label": "Cross-river", "value": len(cross), "accent": RIVER,
                      "sub": "customers whose hub is across the Hooghly"})
    else:
        cards.append({"label": "Area", "value": f"{net.region.area:.1f}", "unit": "km²", "accent": NEUTRAL,
                      "sub": "around the points"})
    style.kpis(cards)

    options = {
        "zones": ":material/hexagon: Service zones",
        "hull": ":material/pentagon: Network reach",
        "search": ":material/crop_free: Search area",
        "pairs": ":material/join_inner: Closest stops",
        "river": ":material/water: River crossings",
        "labels": ":material/label: Labels",
    }
    on = st.pills("Map layers", list(options), format_func=options.get, selection_mode="multi",
                  default=["zones", "hull", "search", "pairs", "river"], key="layers", label_visibility="collapsed")
    on = set(on or [])

    sel = _selected(c, "netmap")
    map_col, side = st.columns([2.2, 1], gap="medium")

    # ------------------------------------------------------------------ side panel
    with side:
        if sel is not None:
            _place_card(c, sel)
        else:
            style.block('<div class="sdn-note sdn-muted" style="margin:2px 0 6px">'
                        '<b>Tip:</b> click any dot on the map to inspect that place.</div>')

        t_search, t_zones, t_pairs = st.tabs(["Search area", "Zones", "Closest stops"])
        with t_search:
            style.heading("KD-tree range search", ALGO["kdtree"], f"{len(hits)} found")
            opts = _search_options(c)
            if st.session_state.get("search_centre") not in opts:
                st.session_state["search_centre"] = "Kalyani centre"
            st.selectbox("Centre the area on", list(opts), key="search_centre")
            a, b = st.columns(2)
            a.slider("Width (km)", 0.5, 10.0, 3.0, 0.5, key="search_w")
            b.slider("Height (km)", 0.5, 10.0, 2.4, 0.2, key="search_h")
            centre = ((box[0] + box[1]) / 2, (box[2] + box[3]) / 2)
            ordered = sorted(hits, key=lambda p: math.hypot(p.x - centre[0], p.y - centre[1]))
            if ordered:
                style.block('<div class="sdn-list">' + _rows([
                    (colour_of[c.assignment[p.id]], p.name or p.label, f"{p.label} · {p.category}",
                     esc(c.wh_by_id[c.assignment[p.id]].label)) for p in ordered]) + "</div>")
            else:
                style.block('<div class="sdn-note sdn-muted">No customers inside this area. Try a bigger box.</div>')

        with t_zones:
            style.heading("Voronoi service zones", ALGO["voronoi"], "nearest hub wins")
            top = max(sizes.values()) if sizes else 1
            rows = []
            for w in net.warehouses:
                pts = c.by_zone[w.id]
                far = max((c.dist_to_hub[p.id] for p in pts), default=0)
                mean = sum(c.dist_to_hub[p.id] for p in pts) / len(pts) if pts else 0
                rows.append(
                    f'<div class="sdn-zone" style="--c:{colour_of[w.id]}"><span class="sdn-tag">{w.label}</span>'
                    f'<span class="nm">{esc(w.name)}</span><span class="ct">{len(pts)}</span>'
                    f'<span class="bar"><span style="width:{100 * len(pts) / max(top, 1):.0f}%"></span></span>'
                    f'<span class="ds">avg {fmt_km(mean)} · farthest {fmt_km(far)}</span></div>'
                )
            style.block("".join(rows))

        with t_pairs:
            style.heading("Closest pair (divide & conquer)", ALGO["pair"])
            if c.pair:
                p, q, d = c.pair
                style.block(
                    f'<div class="sdn-pair"><div class="end"><b>{p.label}</b><span>{esc(p.name)}</span></div>'
                    f'<div class="mid">{fmt_km(d)}</div><div class="end"><b>{q.label}</b><span>{esc(q.name)}</span></div></div>'
                    '<div class="sdn-note sdn-muted" style="margin-top:6px">The two stops in the whole region that are '
                    'nearest each other: candidates for one shared delivery.</div>'
                )
            style.heading("Within each zone", ALGO["pair"], "proximity only, not routing")
            zp = sorted(c.zone_pairs.items(), key=lambda kv: kv[1][2])
            style.block('<div class="sdn-list">' + _rows([
                (colour_of[wid], f"{a.label} ↔ {b.label}", f"{a.name} · {b.name}", esc(fmt_km(d)))
                for wid, (a, b, d) in zp]) + "</div>")

    # ------------------------------------------------------------------ map
    with map_col:
        tips = {p.id: place_tip(c, p) for p in net.customers}
        hub_tips = {w.id: place_tip(c, w) for w in net.warehouses}
        zone_tips = {w.id: (f"Zone {w.label}", w.name, f"{len(c.by_zone[w.id])} customers") for w in net.warehouses}
        fill = {p.id: rgb(colour_of[c.assignment[p.id]]) for p in net.customers}
        lyr = [L.city_mask(net)]
        if "zones" in on:
            lyr.append(L.zones(net, c.regions, colour_of, zone_tips))
        lyr += L.city_outline(net)
        if "river" in on:
            lyr += L.river(net)
        if "hull" in on:
            lyr += L.hull(net, c.hull)
        if "search" in on:
            lyr.append(L.box(net, *box))
        if "pairs" in on:
            lyr.append(L.pairs(net, list(c.zone_pairs.values()), ALGO["pair"], "zone-pairs", width=2))
            if c.pair:
                lyr.append(L.pairs(net, [c.pair], ALGO["pair"], "pair", width=4))
        lyr.append(L.customers(net, net.customers, fill, tips))
        if "search" in on and hits:
            lyr.append(L.rings_at(net, hits, ALGO["kdtree"], "hits", px=7, width=2))
        if "pairs" in on and c.pair:
            lyr.append(L.rings_at(net, [c.pair[0], c.pair[1]], ALGO["pair"], "pair-rings", px=10, width=2.6))
        if sel is not None:
            lyr.append(L.rings_at(net, [sel], INK, "selected", px=13, width=3))
        if "labels" in on:
            lyr.append(L.text_at(net, net.customers, "cust-labels"))
        if "river" in on:
            lyr += L.crossings(net)
        lyr += L.warehouses(net, net.warehouses, colour_of, hub_tips)

        st.pydeck_chart(L.deck(net, lyr), height=660, on_select="rerun", selection_mode="single-object",
                        key="netmap")
        legend = [("Warehouse zone", colour_of[net.warehouses[0].id], "box")] if net.warehouses else []
        legend += [("Network reach (convex hull)", ALGO["hull"], "line"),
                   ("Search area (KD-tree)", ALGO["kdtree"], "box"),
                   ("Closest stops", ALGO["pair"], "line")]
        if net.river is not None:
            legend += [("Road bridge", BRIDGE, "thick"), ("Ferry", FERRY, "dash"),
                       ("Study area", "#475569", "dash"), ("Kalyani City", style.BRAND, "dash")]
        style.legend(legend)


def _place_card(c: Ctx, p: Point) -> None:
    colour_of = c.colour_of()
    with st.container(border=True):
        if p.kind == "warehouse":
            pts = c.by_zone[p.id]
            style.block(
                f'<div class="sdn-h" style="--accent:{colour_of[p.id]}"><span class="dot"></span>{esc(p.name)}'
                f'<span class="meta">{p.label} · warehouse</span></div>'
                f'<div class="sdn-big"><b>{len(pts)}</b><span>customers in this zone</span></div>'
                f'<div class="sdn-note sdn-muted">{esc(p.category)} · {p.lat:.5f}, {p.lon:.5f}</div>'
            )
        else:
            hub = c.wh_by_id[c.assignment[p.id]]
            ranking = sorted(c.net.warehouses, key=lambda w: math.hypot(w.x - p.x, w.y - p.y))[:3]
            rows = _rows([(colour_of[w.id], f"{w.label} · {w.name}",
                           "assigned: nearest hub" if w.id == hub.id else "farther away",
                           fmt_km(math.hypot(w.x - p.x, w.y - p.y))) for w in ranking])
            style.block(
                f'<div class="sdn-h" style="--accent:{colour_of[hub.id]}"><span class="dot"></span>{esc(p.name)}'
                f'<span class="meta">{p.label}</span></div>'
                f'<div class="sdn-note sdn-muted" style="margin:-4px 0 8px">{esc(p.category)} · zone {hub.label}</div>'
                f'<div class="sdn-list">{rows}</div>'
            )
        st.button("Centre search area here", icon=":material/crop_free:", key="centre_here",
                  on_click=_set_centre, args=(_option_for(p),), width="stretch")


# ====================================================================== river

def river() -> None:
    c = ctx()
    net = c.net
    colour_of = c.colour_of()
    _hero_for(
        c, "River crossing", 'Across the <span class="accent">Hooghly</span>',
        "The five algorithms measure distance in straight lines. The Hooghly splits this region, so a customer "
        "whose nearest warehouse <b>as the crow flies</b> is on the other bank can only be reached over a "
        "<b>road bridge</b> or, on two wheels, by <b>ferry</b>. This page measures how far off the straight-line "
        "plan is.",
    )
    if net.river is None:
        st.info("The river check needs the Kalyani region data. Uploaded CSV networks have no river.",
                icon=":material/water:")
        return
    rv = net.river
    mode = st.segmented_control(
        "Delivery by", list(MODES), format_func=lambda k: f"{MODES[k][0]} · {MODES[k][1]}", default="van",
        required=True, key="river_mode", label_visibility="collapsed",
    )
    vehicle, rule, kinds = MODES[mode]
    rows = river_check(net.customers, net.warehouses, c.assignment, rv, kinds)
    west = [p for p in net.customers if rv.bank(p.x, p.y) == 0]
    west_hubs = [w for w in net.warehouses if rv.bank(w.x, w.y) == 0]
    reachable = [r for r in rows if math.isfinite(r["real"])]
    switch = [r for r in reachable if r["best_hub"].id != r["hub"].id]
    n = len(reachable)
    avg_s = sum(r["straight"] for r in reachable) / n if n else 0
    avg_r = sum(r["real"] for r in reachable) / n if n else 0
    used: dict[str, int] = {}
    for r in reachable:
        used[r["crossing"].name] = used.get(r["crossing"].name, 0) + 1
    top = max(used, key=used.get) if used else "–"

    style.kpis([
        {"label": "West-bank customers", "value": len(west), "unit": f"of {len(net.customers)}", "accent": RIVER,
         "sub": f"{len(west_hubs)} warehouse{'s' if len(west_hubs) != 1 else ''} on the west bank"},
        {"label": "Hub across the river", "value": len(rows), "accent": CRITICAL,
         "sub": "straight-line (Voronoi) choice"},
        {"label": "Straight line", "value": fmt_km(avg_s) if n else "–", "accent": NEUTRAL, "sub": "average, what Voronoi assumes"},
        {"label": "Real trip", "value": fmt_km(avg_r) if n else "–", "accent": BRIDGE if mode == "van" else FERRY,
         "sub": f"average, mostly via {top}" if n else "no crossing needed"},
        {"label": "Extra distance", "value": f"+{fmt_km(avg_r - avg_s)}" if n else "–", "accent": ALGO["hull"],
         "sub": f"+{100 * (avg_r - avg_s) / avg_s:.0f}% per trip" if n and avg_s else ""},
        {"label": "Better hub exists", "value": len(switch), "unit": f"of {len(rows)}" if rows else "", "accent": ALGO["kdtree"],
         "sub": "closer once the river counts"},
    ])

    map_col, side = st.columns([2.2, 1], gap="medium")
    with side:
        names = [x.name for x in rv.crossings if x.kind in kinds]
        if rows:
            style.block(
                f'<div class="sdn-callout warn"><b>{len(rows)} customer{"s" if len(rows) != 1 else ""}</b> '
                f'{"are" if len(rows) != 1 else "is"} assigned to a warehouse on the other bank. By '
                f'{esc(vehicle.lower())} ({esc(rule)}: {esc(", ".join(names))}) the trip averages '
                f'<b>{fmt_km(avg_r)}</b> instead of {fmt_km(avg_s)}. For <b>{len(switch)}</b> of them another warehouse '
                'is actually nearer once the river is taken into account.</div>'
            )
        else:
            style.block('<div class="sdn-callout">Every customer\'s straight-line warehouse is on its own bank in '
                        'this network, so the river costs nothing here. Try more customers or another seed.</div>')
        st.space("small")
        style.heading("Customers affected", CRITICAL, f"{len(rows)}")
        items = []
        for r in sorted(rows, key=lambda r: -(r["real"] - r["straight"])):
            cu, hub, best = r["customer"], r["hub"], r["best_hub"]
            via = r["crossing"].name if r["crossing"] else "no crossing"
            change = f"→ better {best.label}" if best.id != hub.id else "keeps hub"
            right = (f'{fmt_km(r["real"])}<small>vs {fmt_km(r["straight"])}</small>' if math.isfinite(r["real"])
                     else "no route<small>by this mode</small>")
            items.append((colour_of[hub.id], f"{cu.label} · {cu.name}", f"{hub.label} via {via} · {change}", right))
        if items:
            style.block('<div class="sdn-list">' + _rows(items) + "</div>")
        st.space("small")
        style.heading("Crossings in the area", RIVER, f"{len(rv.crossings)}")
        style.block('<div class="sdn-list">' + _rows([
            (BRIDGE if x.kind == "bridge" else FERRY, x.name,
             ("Road bridge" if x.kind == "bridge" else "Ferry") + " · " + x.source,
             esc(f"{x.length * 1000:.0f} m") + ("" if x.kind in kinds else "<small>not for vans</small>"))
            for x in rv.crossings]) + "</div>")

    with map_col:
        affected = {r["customer"].id for r in rows}
        fill = {p.id: rgb(colour_of[c.assignment[p.id]], 255 if p.id in affected else 110) for p in net.customers}
        straight, real = [], []
        for r in reachable:
            cu, hub, x = r["customer"], r["hub"], r["crossing"]
            straight.append({"path": [cu.coords(), hub.coords()], "colour": "#64748B", "alpha": 170})
            near, far = (x.a, x.b) if rv.bank(cu.x, cu.y) == 0 else (x.b, x.a)
            real.append({"path": [cu.coords(), near, far, hub.coords()],
                         "colour": BRIDGE if x.kind == "bridge" else FERRY, "alpha": 200,
                         "tip": (f"{cu.name} → {hub.label}", f"straight line {fmt_km(r['straight'])}",
                                 f"real trip {fmt_km(r['real'])} via {x.name}")})
        lyr = [L.city_mask(net), L.zones(net, c.regions, colour_of, {}, alpha=20), *L.city_outline(net),
               *L.river(net), L.route_paths(net, straight, "straight", width=1.6, dashed=True),
               L.route_paths(net, real, "real", width=2.6),
               L.customers(net, net.customers, fill, {p.id: place_tip(c, p) for p in net.customers}),
               L.rings_at(net, [r["customer"] for r in rows], CRITICAL, "affected", px=8, width=2.2) if rows else None,
               *L.crossings(net, kinds)]
        lyr += L.warehouses(net, net.warehouses, colour_of, {w.id: place_tip(c, w) for w in net.warehouses})
        st.pydeck_chart(L.deck(net, lyr), height=660, key=f"rivermap_{mode}")
        style.legend([("Hub across the river", CRITICAL, "ring"), ("Straight line (what Voronoi assumes)", "#64748B", "dash"),
                      ("Real trip via bridge", BRIDGE, "line"), ("Real trip via ferry", FERRY, "line"),
                      ("Road bridge", BRIDGE, "thick"), ("Ferry", FERRY, "dash")])


# ====================================================================== coverage

def coverage() -> None:
    c = ctx()
    net = c.net
    colour_of = c.colour_of()
    _hero_for(
        c, "Coverage planner", 'Which warehouses are <span class="accent">worth keeping?</span>',
        "Every warehouse covers the customers within a chosen radius. Finding the fewest warehouses that "
        "cover everyone is NP-hard, so we pick greedily: each round keeps the warehouse that covers the most "
        "customers not yet covered. The result is at most about ln&nbsp;n times the true minimum.",
    )
    radius = st.slider("Coverage radius (km)", 1.0, 10.0, 4.0, 0.5, key="cover_r",
                       help="How far a warehouse can serve from, as the crow flies.")
    chosen, rounds = greedy_set_cover(net.warehouses, net.customers, radius)
    covered_by: dict[int, int] = {}
    for r in rounds:
        for cid in r["new_covered"]:
            covered_by[cid] = r["site"].id
    n = len(net.customers)
    covered = len(covered_by)
    style.kpis([
        {"label": "Warehouses kept", "value": len(chosen), "unit": f"of {len(net.warehouses)}", "accent": ALGO["cover"],
         "sub": ", ".join(w.label for w in chosen) or "none"},
        {"label": "Customers covered", "value": f"{100 * covered / n:.0f}" if n else "0", "unit": "%",
         "accent": ALGO["kdtree"], "sub": f"{covered} of {n}"},
        {"label": "Not covered", "value": n - covered, "accent": CRITICAL,
         "sub": "outside every radius" if n - covered else "everyone is reachable"},
        {"label": "Radius", "value": f"{radius:.1f}", "unit": "km", "accent": NEUTRAL, "sub": "straight-line"},
        {"label": "Greedy rounds", "value": len(rounds), "accent": ALGO["pair"], "sub": "one pick per round"},
        {"label": "Guarantee", "value": f"≤ {sum(1 / k for k in range(1, max(n, 1) + 1)):.1f}×", "accent": ALGO["hull"],
         "sub": "H(n) × optimum"},
    ])

    map_col, side = st.columns([2.2, 1], gap="medium")
    with side:
        style.heading("Round by round", ALGO["cover"], f"{len(rounds)} rounds")
        if not rounds:
            style.block('<div class="sdn-note">No warehouse reaches any customer at this radius. Increase it.</div>')
        items = []
        for i, r in enumerate(rounds, 1):
            w = r["site"]
            items.append(
                f'<div class="it" style="--c:{colour_of[w.id]}"><div class="no">{i}</div><div class="tx">'
                f'Keep <b>{w.label}</b> · {esc(w.name)}<br><span class="sdn-muted">covers '
                f'<b>{len(r["new_covered"])}</b> new customer{"s" if len(r["new_covered"]) != 1 else ""}, '
                f'{r["total_covered"]}/{n} in total</span>'
                f'<div class="pr"><span style="width:{100 * r["total_covered"] / max(n, 1):.0f}%"></span></div></div></div>'
            )
        style.block(f'<div class="sdn-tl">{"".join(items)}</div>')
        dropped = [w for w in net.warehouses if w not in chosen]
        if dropped:
            style.block(
                '<div class="sdn-note" style="margin-top:4px"><b>Could close:</b> '
                + ", ".join(f"{w.label} ({esc(w.name)})" for w in dropped)
                + (". Every customer within its radius is already covered by a kept warehouse.</div>"
                   if len(dropped) == 1 else ". Every customer within their radius is already covered by a kept warehouse.</div>")
            )

    with map_col:
        fill = {p.id: rgb(colour_of[covered_by[p.id]]) if p.id in covered_by else rgb(NEUTRAL, 200)
                for p in net.customers}
        tips = {}
        for p in net.customers:
            t, a, b = place_tip(c, p)
            tips[p.id] = (t, a, b if p.id in covered_by else "Not covered by any kept warehouse")
        uncovered = [p for p in net.customers if p.id not in covered_by]
        chosen_ids = {w.id for w in chosen}
        lyr = [
            L.city_mask(net), *L.city_outline(net), *L.river(net),
            L.circles(net, [(w, colour_of[w.id]) for w in chosen], radius, "cover"),
            L.circles(net, [(w, NEUTRAL) for w in net.warehouses if w.id not in chosen_ids], radius, "cover-off", 0),
            L.customers(net, net.customers, fill, tips),
            L.rings_at(net, uncovered, CRITICAL, "uncovered", px=8, width=2.2) if uncovered else None,
        ]
        lyr += L.warehouses(net, net.warehouses, colour_of, {w.id: place_tip(c, w) for w in net.warehouses},
                            dimmed={w.id for w in net.warehouses if w.id not in chosen_ids})
        st.pydeck_chart(L.deck(net, lyr), height=600, key="covermap")
        style.legend([("Kept warehouse, its radius", ALGO["cover"], "box"),
                      ("Could close (outline only)", NEUTRAL, "line"),
                      ("Customer not covered", CRITICAL, "dot")])


# ====================================================================== walkthrough

ALGOS = {
    "hull": ("Convex hull", ALGO["hull"], "O(n log n)"),
    "pair": ("Closest pair", ALGO["pair"], "O(n log n)"),
    "kdbuild": ("KD-tree build", ALGO["kdtree"], "O(n log n)"),
    "kdquery": ("KD-tree search", ALGO["kdtree"], "O(√n + k)"),
    "voronoi": ("Voronoi assignment", ALGO["voronoi"], "O(m) per customer"),
}


def _step_nav(key: str, n: int) -> int:
    if key not in st.session_state or st.session_state[key] > n:
        st.session_state[key] = n

    def shift(delta: int) -> None:
        st.session_state[key] = min(n, max(1, st.session_state[key] + delta))

    def jump(v: int) -> None:
        st.session_state[key] = v

    b1, b2, b3, b4 = st.columns(4)
    b1.button("", icon=":material/first_page:", key=f"{key}_first", on_click=jump, args=(1,), width="stretch", help="First step")
    b2.button("", icon=":material/chevron_left:", key=f"{key}_prev", on_click=shift, args=(-1,), width="stretch", help="Previous step")
    b3.button("", icon=":material/chevron_right:", key=f"{key}_next", on_click=shift, args=(1,), width="stretch", help="Next step")
    b4.button("", icon=":material/last_page:", key=f"{key}_last", on_click=jump, args=(n,), width="stretch", help="Final result")
    if n > 1:
        st.slider("Step", 1, n, key=key, label_visibility="collapsed")
    return st.session_state[key]


def _step_card(i: int, n: int, event: str, accent: str, detail: str, chain_html: str = "") -> None:
    style.block(
        f'<div class="sdn-step" style="--accent:{accent}"><div class="n">STEP {i} OF {n}</div>'
        f'<span class="ev">{esc(event)}</span><div class="d">{esc(detail)}</div>{chain_html}</div>'
    )


def _chain(labels: list[str], on: set[str] | None = None) -> str:
    on = on or set()
    return '<div class="sdn-chain">' + "".join(
        f'<span class="{"on" if s in on else ""}">{esc(s)}</span>' for s in labels) + "</div>"


def _base_points(c: Ctx, pts: list[Point], colour: list[int], layer_id: str = "base") -> object:
    fill = {p.id: colour for p in pts}
    return L.customers(c.net, pts, fill, {p.id: place_tip(c, p) for p in pts}, layer_id=layer_id, radius_m=22)


def walkthrough() -> None:
    c = ctx()
    net = c.net
    _hero_for(
        c, "Walkthrough", 'Watch each algorithm <span class="accent">think</span>',
        "Pick an algorithm and step through every decision it makes on the customers currently on the map. "
        "Use the arrows, or drag the slider to jump.",
    )
    algo = st.segmented_control("Algorithm", list(ALGOS), format_func=lambda k: ALGOS[k][0], default="hull",
                                required=True, key="wk_algo", label_visibility="collapsed")
    name, accent, cost = ALGOS[algo]
    custs = net.customers
    cust_by_id = c.cust_by_id
    dim = [148, 163, 184, 120]
    seen = rgb("#475569")

    left, right = st.columns([1, 2], gap="medium")
    lyr: list = [L.city_mask(net), *L.city_outline(net), *L.river(net)]

    with left:
        style.heading(name, accent, cost)
        if algo == "hull":
            hull_pts, steps = convex_hull_trace(custs)
            if not steps:
                st.warning("Need at least 3 customers.")
                return
            i = _step_nav("wk_hull", len(steps))
            s = steps[i - 1]
            chain = [cust_by_id[j] for j in s["snapshot"]]
            done_lower = []
            if s["chain"] == "upper":
                last_lower = max(k for k, t in enumerate(steps) if t["chain"] == "lower")
                done_lower = [cust_by_id[j] for j in steps[last_lower]["snapshot"]]
            _step_card(i, len(steps), f'{s["chain"]} chain · {s["action"]}', accent, s["detail"],
                       _chain([p.label for p in chain], {cust_by_id[s["current"]].label}))
            if i == len(steps):
                st.success(f"Hull of {len(hull_pts)} stops: " + " → ".join(p.label for p in hull_pts), icon=":material/check_circle:")
            style.block('<div class="sdn-note sdn-muted" style="margin-top:8px">Points are scanned west to east for the '
                        'lower chain, then east to west for the upper chain. A point is dropped whenever keeping it '
                        'would make a right turn (a dent in the boundary).</div>')
            order = sorted(set(custs), key=lambda p: (p.x, p.y))
            if s["chain"] == "upper":
                order = list(reversed(order))
            pos = next(k for k, p in enumerate(order) if p.id == s["current"])
            scanned = order[: pos + 1]
            lyr.append(_base_points(c, custs, dim))
            lyr.append(_base_points(c, scanned, seen, "scanned"))
            if done_lower:
                lyr.append(L.path(net, done_lower, ALGO["hull"], "lower-done", width=3, alpha=110))
            lyr.append(L.path(net, chain, ALGO["hull"], "chain", width=4))
            lyr.append(L.rings_at(net, [cust_by_id[s["current"]]], INK, "current", px=11, width=3))
            if s["action"] == "pop":
                lyr.append(L.rings_at(net, [cust_by_id[s["popped"]]], CRITICAL, "popped", px=11, width=3))
            lyr.append(L.text_at(net, chain, "chain-labels"))

        elif algo == "pair":
            (bp, bq, bd), steps = closest_pair_trace(custs)
            i = _step_nav("wk_pair", len(steps))
            s = steps[i - 1]
            _step_card(i, len(steps), f'{s["event"]} · depth {s["depth"]}', accent, s["detail"])
            if i == len(steps):
                st.success(f"Closest pair: {bp.label} and {bq.label}, {fmt_km(bd)} apart", icon=":material/check_circle:")
            style.block('<div class="sdn-note sdn-muted" style="margin-top:8px">Split the stops by a north-south line, '
                        'solve each half, then only re-check the thin strip of width 2δ around the line. Inside the '
                        'strip each point needs comparing with just a few neighbours above it.</div>')
            active = [cust_by_id[j] for j in s["active_ids"]]
            lyr.append(_base_points(c, custs, dim))
            if s["event"] == "divide":
                lyr.append(_base_points(c, [cust_by_id[j] for j in s["left_ids"]], rgb(style.BRAND), "left"))
                lyr.append(_base_points(c, [cust_by_id[j] for j in s["right_ids"]], rgb(ALGO["voronoi"]), "right"))
            else:
                lyr.append(_base_points(c, active, seen, "active"))
            x0, x1, y0, y1 = net.bounds_xy
            if s.get("split_x") is not None:
                sx = s["split_x"]
                if s["event"] == "strip check":
                    d = s["delta"]
                    lyr.append(L.box(net, sx - d, sx + d, y0, y1, ALGO["pair"], "strip"))
                    lyr.append(L.rings_at(net, [cust_by_id[j] for j in s["strip_ids"]], ALGO["pair"], "strip-pts", px=8))
                lyr.append(L.segments(net, [((sx, y0), (sx, y1))], [15, 23, 42, 200], "split", 2))
            if s.get("best"):
                a, b, _ = s["best"]
                lyr.append(L.pairs(net, [(cust_by_id[a], cust_by_id[b], 0)], ALGO["pair"], "best", width=4))
                lyr.append(L.rings_at(net, [cust_by_id[a], cust_by_id[b]], ALGO["pair"], "best-rings", px=10))

        elif algo == "kdbuild":
            steps = kdtree_build_trace(custs, net.bounds_xy)
            i = _step_nav("wk_kdb", len(steps))
            s = steps[i - 1]
            _step_card(i, len(steps), f'split on {s["axis"]} · depth {s["depth"]}', accent, s["detail"])
            style.block('<div class="sdn-note sdn-muted" style="margin-top:8px">Each split cuts its cell in half at the '
                        'median stop, alternating north-south and east-west lines. The tree ends up about '
                        f'log₂ n ≈ {math.ceil(math.log2(max(len(custs), 2)))} levels deep.</div>')
            lyr.append(_base_points(c, custs, seen))
            old = [t["seg"] for t in steps[: i - 1]]
            if old:
                lyr.append(L.segments(net, old, [148, 156, 172, 150], "old-splits", 1.5))
            lyr.append(L.segments(net, [s["seg"]], rgb(ALGO["kdtree"]), "split", 3.5))
            lyr.append(L.rings_at(net, [cust_by_id[s["median_point"]]], ALGO["kdtree"], "median", px=11, width=3))

        elif algo == "kdquery":
            box = search_box(c)
            found, steps = kdtree_query_trace(c.tree, *box)
            i = _step_nav("wk_kdq", len(steps))
            s = steps[i - 1]
            visited = [t for t in steps[:i] if not t.get("pruned")]
            pruned = sum(1 for t in steps[:i] if t.get("pruned"))
            event = "skip subtree" if s.get("pruned") else ("inside → report" if s["in_box"] else "visit")
            _step_card(i, len(steps), event, accent, s["detail"])
            ninside = sum(1 for t in visited if t["in_box"])
            style.block(
                f'<div class="sdn-note" style="margin-top:8px">Visited <b>{len(visited)}</b> of {len(custs)} stops, '
                f'skipped <b>{pruned}</b> subtree(s), found <b>{ninside}</b> so far. The search area is the one set '
                'on the Network page.</div>'
            )
            if i == len(steps):
                st.success(f"{len(found)} customers in the area after visiting only {len(visited)} of {len(custs)}.",
                           icon=":material/check_circle:")
            lyr.append(L.box(net, *box))
            lyr.append(_base_points(c, custs, dim))
            lyr.append(_base_points(c, [cust_by_id[t["point"]] for t in visited if not t["in_box"]],
                                    seen, "visited"))
            lyr.append(_base_points(c, [cust_by_id[t["point"]] for t in visited if t["in_box"]], rgb(ALGO["kdtree"]), "found"))
            lyr.append(L.rings_at(net, [cust_by_id[s["point"]]], CRITICAL if s.get("pruned") else INK,
                                  "current", px=12, width=3))

        else:  # voronoi
            labels = {p.id: f"{p.label} · {p.name}" for p in custs}
            sel = _selected(c, "netmap")
            default_id = sel.id if sel is not None and sel.kind == "customer" else custs[0].id
            if st.session_state.get("wk_vor_c") not in labels:
                st.session_state["wk_vor_c"] = default_id
            cid = st.selectbox("Customer", list(labels), format_func=labels.get, key="wk_vor_c")
            p = cust_by_id[cid]
            rows = voronoi_assignment_trace(p, net.warehouses)
            i = _step_nav("wk_vor", len(rows))
            r = rows[i - 1]
            w = c.wh_by_id[r["warehouse"]]
            best = c.wh_by_id[r["best_so_far"]]
            _step_card(i, len(rows), f"compare {w.label}", accent,
                       f"{p.label} is {fmt_km(r['distance'])} from {w.label}. Nearest so far: {best.label} "
                       f"({fmt_km(r['best_distance'])}).")
            if i == len(rows):
                st.success(f"{p.label} belongs to zone {best.label}: it lies inside {best.label}'s Voronoi cell.",
                           icon=":material/check_circle:")
            colour_of = c.colour_of()
            lyr.append(L.zones(net, c.regions, colour_of, {}, alpha=22))
            lyr.append(_base_points(c, custs, dim))
            for k, row in enumerate(rows[:i]):
                hub = c.wh_by_id[row["warehouse"]]
                is_best = row["warehouse"] == r["best_so_far"]
                lyr.append(L.pairs(net, [(p, hub, 0)], colour_of[hub.id] if is_best else "#94A3B8",
                                   f"cmp-{k}", width=4 if is_best else 1.5))
            lyr.append(L.rings_at(net, [p], INK, "picked", px=12, width=3))
            lyr += L.warehouses(net, net.warehouses, colour_of, {h.id: place_tip(c, h) for h in net.warehouses},
                                dimmed={h.id for h in net.warehouses if h.id not in {row["warehouse"] for row in rows[:i]}})

    with right:
        st.pydeck_chart(L.deck(net, lyr, L.points_view(net, custs + net.warehouses)), height=600,
                        key=f"wkmap_{algo}")


# ====================================================================== data

def data() -> None:
    c = ctx()
    net = c.net
    colour_of = c.colour_of()
    _hero_for(c, "Data", 'The <span class="accent">point set</span> behind the map',
              "Every warehouse and customer, the OpenStreetMap place it stands for, its position on the flat "
              "km grid the algorithms use, and the zone it was assigned to.")
    rows = []
    for p in net.warehouses + net.customers:
        zone = p.label if p.kind == "warehouse" else c.wh_by_id[c.assignment[p.id]].label
        rows.append({
            "Label": p.label, "Name": p.name, "Type": p.kind, "Category": p.category, "Zone": zone,
            "Bank": ("" if net.river is None else ("west" if net.river.bank(p.x, p.y) == 0 else "east")),
            "To hub (m)": None if p.kind == "warehouse" else round(c.dist_to_hub[p.id] * 1000),
            "x (km)": round(p.x, 3), "y (km)": round(p.y, 3), "Latitude": p.lat, "Longitude": p.lon,
        })
    df = pd.DataFrame(rows)
    left, right = st.columns([2, 1], gap="medium")
    with left:
        style.heading("Warehouses and customers", style.BRAND, f"{len(df)} points")
        far = max(c.dist_to_hub.values(), default=1) * 1000
        st.dataframe(
            df, hide_index=True, height=520, width="stretch",
            column_config={
                "To hub (m)": st.column_config.ProgressColumn("To hub", format="%d m", min_value=0, max_value=int(far) or 1),
                "Latitude": st.column_config.NumberColumn(format="%.5f"),
                "Longitude": st.column_config.NumberColumn(format="%.5f"),
            },
        )
        st.download_button("Download this network (CSV)", csv_bytes(c), file_name="kalyani_region_network.csv",
                           mime="text/csv", icon=":material/download:")
    with right:
        style.heading("Customers per zone", ALGO["voronoi"])
        zdf = pd.DataFrame([{"Zone": w.label, "Customers": len(c.by_zone[w.id]), "Hub": w.name}
                            for w in net.warehouses])
        chart = (
            alt.Chart(zdf).mark_bar(cornerRadiusEnd=4, height=18)
            .encode(
                y=alt.Y("Zone:N", sort=None, title=None),
                x=alt.X("Customers:Q", title=None, axis=alt.Axis(tickMinStep=1, grid=True)),
                color=alt.Color("Zone:N", scale=alt.Scale(domain=list(zdf["Zone"]),
                                range=[colour_of[w.id] for w in net.warehouses]), legend=None),
                tooltip=["Zone", "Hub", "Customers"],
            )
            .properties(height=max(140, 34 * len(zdf)))
        )
        text = chart.mark_text(align="left", dx=6, fontWeight=700).encode(text="Customers:Q", color=alt.value("#64748B"))
        st.altair_chart(chart + text, width="stretch")

        style.heading("What kinds of places", ALGO["kdtree"])
        cat = df[df["Type"] == "customer"]["Category"].value_counts().head(8).reset_index()
        cat.columns = ["Category", "Count"]
        bars = (
            alt.Chart(cat).mark_bar(cornerRadiusEnd=4, height=14, color="#64748B")
            .encode(y=alt.Y("Category:N", sort="-x", title=None, axis=alt.Axis(labelLimit=170)), x=alt.X("Count:Q", title=None,
                    axis=alt.Axis(tickMinStep=1)), tooltip=["Category", "Count"])
            .properties(height=max(120, 26 * len(cat)))
        )
        st.altair_chart(bars, width="stretch")
        if net.river is not None:
            src = region().source
            style.block(
                '<div class="sdn-note" style="margin-top:6px"><b>Source.</b> Named OpenStreetMap places inside the '
                'study area (the towns Kalyani, Naihati, Chakdaha, Mogra and Haringhata, padded by 2.5 km), plus the '
                'Hooghly and its road bridges and ferries. Fetched with <code>scripts/fetch_osm.py</code> into '
                f'<code>data/{esc(src)}/</code>. Map data © OpenStreetMap contributors, ODbL.</div>'
            )


# ====================================================================== about

def about() -> None:
    c = ctx()
    _hero_for(c, "How it works", 'Five algorithms, <span class="accent">one map</span>',
              "Voronoi decides who serves whom, the KD-tree finds what is where, closest pair finds what is near, "
              "the hull shows how far it all reaches, and set cover picks the sites worth keeping.", team=True)
    cards = [
        ("voronoi", "Voronoi diagram", "Which warehouse serves each area?",
         "Each warehouse owns the part of the region closer to it than to any other. Customers are assigned "
         "to the nearest warehouse, which is the cell they fall in. Cells come from scipy (Qhull) and are "
         "clipped to the study area.", "O(m log m)"),
        ("kdtree", "KD-tree + range search", "Which customers are inside this area?",
         "The tree splits the stops at the median, alternating east-west and north-south. A rectangle query "
         "skips every subtree its box cannot reach instead of testing every stop.", "build O(n log n) · query O(√n + k)"),
        ("pair", "Closest pair", "Which two stops are nearest each other?",
         "Divide and conquer: split by x, solve both halves, then check only the thin strip around the "
         "dividing line. Run per zone to find stops worth grouping into one delivery.", "O(n log n) vs O(n²)"),
        ("hull", "Convex hull", "How far does the network reach?",
         "Andrew's monotone chain, a Graham-scan variant: sort the stops by x, then build the lower and upper "
         "chains, popping any point that makes a right turn. The area it encloses is the network's reach.", "O(n log n)"),
        ("cover", "Greedy set cover", "Which few warehouses cover everyone?",
         "Each warehouse covers the customers within a radius. Repeatedly keep the one that covers the most "
         "customers still uncovered. NP-hard to solve exactly; greedy is within H(n) ≈ ln n of optimal.", "ln n approximation"),
    ]
    cards.append(("river", "River check (real-world issue)", "Where does straight-line planning break?",
                  "The Hooghly splits the region. For every customer whose nearest hub is on the other bank, the "
                  "real trip must use a road bridge or a ferry; we measure the detour and the hub that is really "
                  "nearest.", "O(n · m · c) for c crossings"))
    accent = {**ALGO, "river": RIVER}
    style.block('<div class="sdn-algos">' + "".join(
        f'<div class="sdn-algo" style="--accent:{accent[k]}"><div class="k"><i></i>{esc(q)}</div><h4>{esc(t)}</h4>'
        f'<p>{esc(body)}</p><span class="cx">{esc(cx)}</span></div>' for k, t, q, body, cx in cards) + "</div>")

    st.space("medium")
    a, b = st.columns(2, gap="medium")
    with a:
        style.heading("From OpenStreetMap to the map", style.BRAND)
        style.block(
            '<div class="sdn-note"><ol style="margin:0 0 0 18px;padding:0;line-height:1.75">'
            '<li>Define the study area: the convex hull of Kalyani, Naihati, Chakdaha, Mogra and Haringhata, '
            'padded by 2.5 km (about 400 km², both banks of the Hooghly).</li>'
            '<li>Download every named place inside it, the Hooghly, its road bridges and its ferries from '
            'OpenStreetMap (<code>scripts/fetch_osm.py</code>).</li>'
            '<li>Pick random real places: a few become warehouses (markets, post offices, warehouses and industrial '
            'sites first, kept several km apart); the rest become customers.</li>'
            '<li>Project latitude/longitude onto a flat km grid, so every distance is real metres, run the '
            'algorithms there and draw the results back on the street map.</li></ol></div>'
        )
    with b:
        style.heading("Scope and limits", ALGO["voronoi"])
        style.block(
            '<div class="sdn-note"><b>A decision-support tool, not a routing system:</b> no traffic, fuel, GPS '
            'navigation or driver scheduling. The algorithms use straight lines, not roads; the river check is the one '
            'place where real geography (bridges and ferries) is modelled, and it is still straight-line on each bank. '
            'OpenStreetMap maps only a few ferry ghats here, so one far landing is estimated; known ghats can be '
            'added in <code>data/manual/ferries.csv</code>. The places are random real OSM features standing in for '
            'customers, and OSM coverage is uneven, so some neighbourhoods have few named places.</div>'
        )
    st.space("small")
    style.block(
        '<div class="sdn-foot">Map data © OpenStreetMap contributors (ODbL) · basemap © CARTO · '
        'built with Streamlit, deck.gl, scipy and shapely.</div>'
    )
