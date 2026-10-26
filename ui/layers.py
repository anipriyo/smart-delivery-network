"""deck.gl (pydeck) layers that draw the algorithms' output on the region map.

All geometry arrives in km on the flat plane and is converted back to
(lon, lat) here, so the map shows exactly what the algorithms computed.
The basemap is CARTO's light "Positron" style, built from OpenStreetMap data.
"""

from __future__ import annotations

import math

import pydeck as pdk
from shapely.geometry import MultiPolygon, Polygon

from src.data import Network
from src.models import Point

from .style import ALGO, BRIDGE, FERRY, INK, RIVER, rgb

DASH = [{"@@type": "PathStyleExtension", "dash": True}]
# pydeck turns plain strings into JS expressions; constant string props need this.
PX = pdk.types.String("pixels")
BASEMAP = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
LABEL_INK = rgb(INK)
LABEL_HALO = [255, 255, 255, 235]
FONT = pdk.types.String("Inter, system-ui, sans-serif")


def ll(net: Network, x: float, y: float) -> list[float]:
    lat, lon = net.projection.to_latlon(x, y)
    return [lon, lat]


def rings(net: Network, geom) -> list[list[list[float]]]:
    """Outer rings of a (Multi)Polygon in lon/lat, one per part."""
    parts = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    out = []
    for part in parts:
        if isinstance(part, Polygon) and not part.is_empty:
            out.append([ll(net, x, y) for x, y in part.exterior.coords])
    return out


def view_state(net: Network, width_px: int = 760, height_px: int = 640,
               bounds: tuple[float, float, float, float] | None = None, pad: float = 0.06) -> pdk.ViewState:
    """Centre and zoom so ``bounds`` (x0, x1, y0, y1 in km; default: the whole
    region) fits a map of roughly ``width_px`` x ``height_px``."""
    x0, x1, y0, y1 = bounds or net.bounds_xy
    w, h = (x1 - x0) * (1 + 2 * pad), (y1 - y0) * (1 + 2 * pad)
    lat_c, lon_c = net.projection.to_latlon((x0 + x1) / 2, (y0 + y1) / 2)
    m_per_px_z0 = 78271.52 * math.cos(math.radians(lat_c))  # deck.gl / MapLibre use 512 px tiles
    zoom_w = math.log2(m_per_px_z0 * width_px / max(w * 1000, 1))
    zoom_h = math.log2(m_per_px_z0 * height_px / max(h * 1000, 1))
    return pdk.ViewState(latitude=lat_c, longitude=lon_c, zoom=min(zoom_w, zoom_h, 16), pitch=0, bearing=0)


def points_view(net: Network, pts: list[Point], width_px: int = 640, height_px: int = 600) -> pdk.ViewState:
    """View that frames a set of points (used by the walkthrough)."""
    if len(pts) < 2:
        return view_state(net, width_px, height_px)
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    return view_state(net, width_px, height_px, (min(xs), max(xs), min(ys), max(ys)), pad=0.12)


def _tip(tip: tuple | None) -> dict:
    """Tooltip fields for one map object. ``tip`` is (title, line, line); values are shown as plain text."""
    t = tuple(tip or ())
    t = t + ("",) * (3 - len(t))
    return {"tt": t[0], "ta": t[1], "tb": t[2]}


def tooltip() -> dict:
    return {
        "html": "<div style='font-weight:700;font-size:13px;margin-bottom:1px'>{tt}</div>"
                "<div style='color:#64748B'>{ta}</div><div>{tb}</div>",
        "style": {
            "backgroundColor": "rgba(255,255,255,0.98)",
            "color": "#0F172A",
            "fontFamily": "Inter, system-ui, sans-serif",
            "fontSize": "12.5px",
            "lineHeight": "1.45",
            "padding": "9px 11px",
            "borderRadius": "10px",
            "border": "1px solid #E2E8F0",
            "boxShadow": "0 8px 24px -8px rgba(15,23,42,0.22)",
            "maxWidth": "260px",
        },
    }


def deck(net: Network, layers: list, view: pdk.ViewState | None = None) -> pdk.Deck:
    return pdk.Deck(
        layers=[layer for layer in layers if layer is not None],
        initial_view_state=view or view_state(net),
        map_style=BASEMAP,
        tooltip=tooltip(),
    )


# ------------------------------------------------------------------ study area

def city_mask(net: Network) -> pdk.Layer | None:
    """Fade everything outside the study area."""
    if not net.boundary_lonlat:
        return None
    lons = [p[0] for p in net.boundary_lonlat]
    lats = [p[1] for p in net.boundary_lonlat]
    pad = 0.6
    outer = [[min(lons) - pad, min(lats) - pad], [max(lons) + pad, min(lats) - pad],
             [max(lons) + pad, max(lats) + pad], [min(lons) - pad, max(lats) + pad]]
    hole = [list(p) for p in net.boundary_lonlat]
    return pdk.Layer(
        "PolygonLayer", id="mask", data=[{"polygon": [outer, hole]}], get_polygon="polygon",
        get_fill_color=[248, 250, 252, 165], stroked=False, pickable=False,
    )


def city_outline(net: Network) -> list[pdk.Layer]:
    """Study-area outline, plus the Kalyani City outline for context."""
    out = []
    if net.boundary_lonlat:
        out.append(pdk.Layer(
            "PathLayer", id="outline", data=[{"path": [list(p) for p in net.boundary_lonlat]}], get_path="path",
            get_color=[71, 85, 105, 200], width_units=PX, get_width=1.6,
            get_dash_array=[5, 4], dash_justified=True, extensions=DASH, pickable=False,
        ))
    if net.inner_outline_lonlat:
        out.append(pdk.Layer(
            "PathLayer", id="kalyani-outline", data=[{"path": [list(p) for p in net.inner_outline_lonlat]}],
            get_path="path", get_color=rgb("#4F46E5", 120), width_units=PX, get_width=1.2,
            get_dash_array=[2, 3], dash_justified=True, extensions=DASH, pickable=False,
        ))
    return out


# ------------------------------------------------------------------ river

def river(net: Network) -> list[pdk.Layer]:
    """The Hooghly's main channel as a soft blue band with a label."""
    if net.river is None:
        return []
    line = net.river.line
    path = [ll(net, x, y) for x, y in line.coords]
    s = line.project(net.region.centroid)  # label the stretch nearest the middle of the map
    mid, ahead = line.interpolate(s), line.interpolate(min(line.length, s + 0.3))
    angle = math.degrees(math.atan2(ahead.y - mid.y, ahead.x - mid.x))
    angle = angle - 180 if angle > 90 else angle + 180 if angle <= -90 else angle  # keep text upright
    return [
        pdk.Layer("PathLayer", id="river", data=[{"path": path}], get_path="path", get_color=rgb(RIVER, 70),
                  width_units=PX, get_width=7, joint_rounded=True, cap_rounded=True, pickable=False),
        pdk.Layer("TextLayer", id="river-label", data=[{"pos": ll(net, mid.x, mid.y), "text": "Hooghly"}],
                  get_position="pos", get_text="text", get_size=12, get_color=rgb(RIVER), font_weight=700,
                  font_family=FONT, get_angle=angle, outline_width=4, outline_color=LABEL_HALO,
                  font_settings={"sdf": True}, get_pixel_offset=[0, -12], pickable=False),
    ]


def crossings(net: Network, kinds: tuple[str, ...] = ("bridge", "ferry")) -> list[pdk.Layer]:
    """Road bridges (solid) and ferries (dashed) across the river, with landings."""
    if net.river is None:
        return []
    bridges, ferries, ends, labels = [], [], [], []
    for c in net.river.crossings:
        if c.kind not in kinds:
            continue
        a, b = ll(net, *c.a), ll(net, *c.b)
        tip = _tip((c.name, f"{'Road bridge' if c.kind == 'bridge' else 'Ferry'} · {c.length * 1000:.0f} m", c.source))
        (bridges if c.kind == "bridge" else ferries).append({"s": a, "t": b, **tip})
        colour = BRIDGE if c.kind == "bridge" else FERRY
        estimated = "estimated" in c.source
        ends += [{"pos": a, "line": rgb(colour), "fill": [255, 255, 255, 255], **tip},
                 {"pos": b, "line": rgb(colour), "fill": [255, 255, 255, 120 if estimated else 255], **tip}]
        labels.append({"pos": [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], "text": c.name, "colour": rgb(colour)})
    out = []
    if bridges:
        out += [
            pdk.Layer("LineLayer", id="bridge-casing", data=bridges, get_source_position="s", get_target_position="t",
                      get_color=[255, 255, 255, 255], get_width=9, width_units=PX, pickable=False),
            pdk.Layer("LineLayer", id="bridges", data=bridges, get_source_position="s", get_target_position="t",
                      get_color=rgb(BRIDGE), get_width=5, width_units=PX, pickable=True, auto_highlight=True),
        ]
    if ferries:
        out.append(pdk.Layer(
            "PathLayer", id="ferries", data=[{**f, "path": [f["s"], f["t"]]} for f in ferries],
            get_path="path", get_color=rgb(FERRY), width_units=PX, get_width=3.5, cap_rounded=True,
            get_dash_array=[3, 2], dash_justified=True, extensions=DASH, pickable=True, auto_highlight=True))
    if ends:
        out.append(pdk.Layer(
            "ScatterplotLayer", id="landings", data=ends, get_position="pos", get_fill_color="fill",
            get_line_color="line", stroked=True, line_width_min_pixels=2, get_radius=40,
            radius_min_pixels=4, radius_max_pixels=7, pickable=True))
        out.append(pdk.Layer(
            "TextLayer", id="crossing-labels", data=labels, get_position="pos", get_text="text", get_size=11.5,
            get_color="colour", font_weight=700, font_family=FONT, get_pixel_offset=[0, 16],
            outline_width=4, outline_color=LABEL_HALO, font_settings={"sdf": True}, pickable=False))
    return out


def route_paths(net: Network, routes: list[dict], layer_id: str = "routes", width: float = 3,
                dashed: bool = False) -> pdk.Layer | None:
    """routes: dicts with 'path' (list of (x, y) km), 'colour' (hex), optional 'alpha' and 'tip' tuple."""
    if not routes:
        return None
    data = [{"path": [ll(net, x, y) for x, y in r["path"]], "colour": rgb(r["colour"], r.get("alpha", 230)),
             **_tip(r.get("tip"))} for r in routes]
    extra = {"get_dash_array": [4, 3], "dash_justified": True, "extensions": DASH} if dashed else {}
    return pdk.Layer("PathLayer", id=layer_id, data=data, get_path="path", get_color="colour",
                     width_units=PX, get_width=width, joint_rounded=True, cap_rounded=True,
                     pickable=any(r.get("tip") for r in routes), **extra)


# ------------------------------------------------------------------ zones

def zones(net: Network, regions: dict, colour_of: dict[int, str], tips: dict[int, tuple], alpha: int = 46) -> pdk.Layer:
    data = []
    for wid, geom in regions.items():
        for ring in rings(net, geom):
            data.append({"polygon": ring, "fill": rgb(colour_of[wid], alpha),
                         "line": rgb(colour_of[wid], 210), **_tip(tips.get(wid))})
    return pdk.Layer(
        "PolygonLayer", id="zones", data=data, get_polygon="polygon", get_fill_color="fill",
        get_line_color="line", line_width_units=PX, get_line_width=1.4, stroked=True,
        pickable=True, auto_highlight=True, highlight_color=[255, 255, 255, 28],
    )


# ------------------------------------------------------------------ points

def customers(net: Network, pts: list[Point], fill: dict[int, list[int]], tips: dict[int, tuple],
              layer_id: str = "customers", radius_m: float = 26) -> pdk.Layer:
    ring = [255, 255, 255, 245]
    data = [{"pos": ll(net, p.x, p.y), "fill": fill[p.id], **_tip(tips.get(p.id)), "pid": p.id, "kind": "customer"}
            for p in pts]
    return pdk.Layer(
        "ScatterplotLayer", id=layer_id, data=data, get_position="pos", get_fill_color="fill",
        get_line_color=ring, stroked=True, line_width_min_pixels=1.2, get_radius=radius_m,
        radius_min_pixels=4, radius_max_pixels=11, pickable=True, auto_highlight=True,
        highlight_color=[255, 255, 255, 120],
    )


def warehouses(net: Network, hubs: list[Point], colour_of: dict[int, str], tips: dict[int, tuple],
               dimmed: set[int] | None = None) -> list[pdk.Layer]:
    dimmed = dimmed or set()
    halo, core, labels = [], [], []
    for w in hubs:
        c = colour_of[w.id] if w.id not in dimmed else "#7C8599"
        pos = ll(net, w.x, w.y)
        halo.append({"pos": pos, "fill": rgb(c, 55)})
        core.append({"pos": pos, "fill": rgb(c), **_tip(tips.get(w.id)), "pid": w.id, "kind": "warehouse"})
        labels.append({"pos": pos, "text": w.label})
    return [
        pdk.Layer("ScatterplotLayer", id="hub-halo", data=halo, get_position="pos", get_fill_color="fill",
                  get_radius=190, radius_min_pixels=13, radius_max_pixels=34, pickable=False),
        pdk.Layer("ScatterplotLayer", id="hubs", data=core, get_position="pos", get_fill_color="fill",
                  get_line_color=[255, 255, 255, 255], stroked=True, line_width_min_pixels=2.2,
                  get_radius=80, radius_min_pixels=8, radius_max_pixels=16, pickable=True, auto_highlight=True),
        pdk.Layer("TextLayer", id="hub-labels", data=labels, get_position="pos", get_text="text",
                  get_size=13, get_color=LABEL_INK, font_weight=800, get_pixel_offset=[0, -24],
                  font_family=FONT, outline_width=5, outline_color=LABEL_HALO,
                  font_settings={"sdf": True}, background=False, pickable=False),
    ]


def rings_at(net: Network, pts: list[Point], colour: str, layer_id: str, px: float = 9, width: float = 2.4) -> pdk.Layer:
    data = [{"pos": ll(net, p.x, p.y)} for p in pts]
    return pdk.Layer(
        "ScatterplotLayer", id=layer_id, data=data, get_position="pos", filled=False, stroked=True,
        get_line_color=rgb(colour), line_width_min_pixels=width, get_radius=10,
        radius_min_pixels=px, radius_max_pixels=px + 6, pickable=False,
    )


def text_at(net: Network, pts: list[Point], layer_id: str, size: int = 11) -> pdk.Layer:
    data = [{"pos": ll(net, p.x, p.y), "text": p.label} for p in pts]
    return pdk.Layer(
        "TextLayer", id=layer_id, data=data, get_position="pos", get_text="text", get_size=size,
        get_color=LABEL_INK, font_weight=700, get_pixel_offset=[0, -15],
        font_family=FONT, outline_width=4, outline_color=LABEL_HALO,
        font_settings={"sdf": True}, pickable=False,
    )


# ------------------------------------------------------------------ overlays

def hull(net: Network, hull_pts: list[Point], colour: str = ALGO["hull"]) -> list[pdk.Layer]:
    if len(hull_pts) < 2:
        return []
    path = [ll(net, p.x, p.y) for p in hull_pts + [hull_pts[0]]]
    data = [{"path": path}]
    return [
        pdk.Layer("PathLayer", id="hull-glow", data=data, get_path="path", get_color=rgb(colour, 60),
                  width_units=PX, get_width=11, joint_rounded=True, cap_rounded=True, pickable=False),
        pdk.Layer("PathLayer", id="hull", data=data, get_path="path", get_color=rgb(colour, 255),
                  width_units=PX, get_width=3, joint_rounded=True, cap_rounded=True, pickable=False),
    ]


def path(net: Network, pts: list[Point], colour: str, layer_id: str, width: float = 3, closed: bool = False,
         dashed: bool = False, alpha: int = 255) -> pdk.Layer | None:
    if len(pts) < 2:
        return None
    coords = [ll(net, p.x, p.y) for p in pts + ([pts[0]] if closed else [])]
    extra = {"get_dash_array": [6, 4], "dash_justified": True, "extensions": DASH} if dashed else {}
    return pdk.Layer("PathLayer", id=layer_id, data=[{"path": coords}], get_path="path", get_color=rgb(colour, alpha),
                     width_units=PX, get_width=width, joint_rounded=True, cap_rounded=True, pickable=False, **extra)


def box(net: Network, x0: float, x1: float, y0: float, y1: float, colour: str = ALGO["kdtree"],
        layer_id: str = "box") -> pdk.Layer:
    ring = [ll(net, x0, y0), ll(net, x1, y0), ll(net, x1, y1), ll(net, x0, y1)]
    return pdk.Layer(
        "PolygonLayer", id=layer_id, data=[{"polygon": ring}], get_polygon="polygon",
        get_fill_color=rgb(colour, 34), get_line_color=rgb(colour, 255), line_width_units=PX,
        get_line_width=2.4, stroked=True, pickable=False,
    )


def segments(net: Network, segs: list[tuple[tuple[float, float], tuple[float, float]]], colour: list[int],
             layer_id: str, width: float = 2) -> pdk.Layer:
    data = [{"s": ll(net, *a), "t": ll(net, *b)} for a, b in segs]
    return pdk.Layer("LineLayer", id=layer_id, data=data, get_source_position="s", get_target_position="t",
                     get_color=colour, get_width=width, width_units=PX, pickable=False)


def pairs(net: Network, pair_list: list[tuple[Point, Point, float]], colour: str, layer_id: str,
          width: float = 3, tips: list[tuple] | None = None) -> pdk.Layer:
    data = [{"s": ll(net, a.x, a.y), "t": ll(net, b.x, b.y), **_tip(tips[i] if tips else None)}
            for i, (a, b, _) in enumerate(pair_list)]
    return pdk.Layer("LineLayer", id=layer_id, data=data, get_source_position="s", get_target_position="t",
                     get_color=rgb(colour), get_width=width, width_units=PX, pickable=bool(tips))


def circles(net: Network, centres: list[tuple[Point, str]], radius_km: float, layer_id: str = "cover",
            fill_alpha: int = 34) -> pdk.Layer:
    data = [{"pos": ll(net, p.x, p.y), "fill": rgb(c, fill_alpha), "line": rgb(c, 230)} for p, c in centres]
    return pdk.Layer(
        "ScatterplotLayer", id=layer_id, data=data, get_position="pos", get_fill_color="fill",
        get_line_color="line", stroked=True, line_width_min_pixels=2, get_radius=radius_km * 1000,
        pickable=False,
    )


# ------------------------------------------------------------------ roads

def lonlat_paths(paths: list[dict], layer_id: str, width: float = 4, dashed: bool = False) -> pdk.Layer | None:
    """paths: dicts with 'path' ([[lon, lat], ...]), 'colour' (hex), optional 'alpha' and 'tip' tuple."""
    if not paths:
        return None
    data = [{"path": p["path"], "colour": rgb(p["colour"], p.get("alpha", 235)), **_tip(p.get("tip"))} for p in paths]
    extra = {"get_dash_array": [4, 3], "dash_justified": True, "extensions": DASH} if dashed else {}
    return pdk.Layer("PathLayer", id=layer_id, data=data, get_path="path", get_color="colour", width_units=PX,
                     get_width=width, joint_rounded=True, cap_rounded=True,
                     pickable=any(p.get("tip") for p in paths), **extra)


def numbered_stops(points: list[tuple[list[float], str, str]], layer_id: str = "stops") -> list[pdk.Layer]:
    """points: ([lon, lat], label, hex colour) drawn as filled discs with the label inside."""
    data = [{"pos": pos, "text": label, "fill": rgb(colour)} for pos, label, colour in points]
    return [
        pdk.Layer("ScatterplotLayer", id=f"{layer_id}-disc", data=data, get_position="pos", get_fill_color="fill",
                  get_line_color=[255, 255, 255, 255], stroked=True, line_width_min_pixels=2, get_radius=60,
                  radius_min_pixels=11, radius_max_pixels=15, pickable=False),
        pdk.Layer("TextLayer", id=f"{layer_id}-text", data=data, get_position="pos", get_text="text", get_size=11,
                  get_color=[255, 255, 255, 255], font_weight=800, font_family=FONT, pickable=False,
                  get_text_anchor=pdk.types.String("middle"), get_alignment_baseline=pdk.types.String("center")),
    ]

