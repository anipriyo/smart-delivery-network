"""deck.gl (pydeck) layers that draw the algorithms' output on the city map.

All geometry arrives in km on the flat plane and is converted back to
(lon, lat) here, so the map shows exactly what the algorithms computed.
The basemap is CARTO's OpenStreetMap style, chosen by Streamlit to match the
light or dark theme.
"""

from __future__ import annotations

import math

import pydeck as pdk
from shapely.geometry import MultiPolygon, Polygon

from src.data import Network
from src.models import Point

from .style import ALGO, is_dark, rgb

DASH = [{"@@type": "PathStyleExtension", "dash": True}]
# pydeck turns plain strings into JS expressions; constant string props need this.
PX = pdk.types.String("pixels")
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


def view_state(net: Network, width_px: int = 700, height_px: int = 620,
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


def tooltip() -> dict:
    dark = is_dark()
    return {
        "html": "{tip}",
        "style": {
            "backgroundColor": "rgba(15,20,35,0.94)" if dark else "rgba(255,255,255,0.97)",
            "color": "#E6EAF2" if dark else "#0F172A",
            "fontFamily": "Inter, system-ui, sans-serif",
            "fontSize": "12.5px",
            "lineHeight": "1.45",
            "padding": "9px 11px",
            "borderRadius": "10px",
            "border": "1px solid rgba(127,127,127,0.25)",
            "boxShadow": "0 8px 24px rgba(0,0,0,0.25)",
            "maxWidth": "260px",
        },
    }


def deck(net: Network, layers: list, view: pdk.ViewState | None = None) -> pdk.Deck:
    return pdk.Deck(
        layers=[layer for layer in layers if layer is not None],
        initial_view_state=view or view_state(net),
        map_style=None,  # Streamlit picks CARTO light/dark to match the theme
        tooltip=tooltip(),
    )


# ------------------------------------------------------------------ city

def city_mask(net: Network) -> pdk.Layer | None:
    """Dim everything outside the city outline."""
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
        get_fill_color=[6, 9, 18, 120] if is_dark() else [255, 255, 255, 120], stroked=False, pickable=False,
    )


def city_outline(net: Network) -> pdk.Layer | None:
    if not net.boundary_lonlat:
        return None
    return pdk.Layer(
        "PathLayer", id="outline", data=[{"path": [list(p) for p in net.boundary_lonlat]}], get_path="path",
        get_color=[230, 234, 242, 170] if is_dark() else [30, 41, 59, 150], width_units=PX, get_width=1.6,
        get_dash_array=[5, 4], dash_justified=True, extensions=DASH, pickable=False,
    )


# ------------------------------------------------------------------ zones

def zones(net: Network, regions: dict, colour_of: dict[int, str], tips: dict[int, str], alpha: int = 46) -> pdk.Layer:
    data = []
    for wid, geom in regions.items():
        for ring in rings(net, geom):
            data.append({"polygon": ring, "fill": rgb(colour_of[wid], alpha),
                         "line": rgb(colour_of[wid], 210), "tip": tips.get(wid, "")})
    return pdk.Layer(
        "PolygonLayer", id="zones", data=data, get_polygon="polygon", get_fill_color="fill",
        get_line_color="line", line_width_units=PX, get_line_width=1.4, stroked=True,
        pickable=True, auto_highlight=True, highlight_color=[255, 255, 255, 28],
    )


# ------------------------------------------------------------------ points

def customers(net: Network, pts: list[Point], fill: dict[int, list[int]], tips: dict[int, str],
              layer_id: str = "customers", radius_m: float = 26) -> pdk.Layer:
    ring = [8, 12, 24, 230] if is_dark() else [255, 255, 255, 240]
    data = [{"pos": ll(net, p.x, p.y), "fill": fill[p.id], "tip": tips.get(p.id, ""), "pid": p.id, "kind": "customer"}
            for p in pts]
    return pdk.Layer(
        "ScatterplotLayer", id=layer_id, data=data, get_position="pos", get_fill_color="fill",
        get_line_color=ring, stroked=True, line_width_min_pixels=1.2, get_radius=radius_m,
        radius_min_pixels=4, radius_max_pixels=11, pickable=True, auto_highlight=True,
        highlight_color=[255, 255, 255, 120],
    )


def warehouses(net: Network, hubs: list[Point], colour_of: dict[int, str], tips: dict[int, str],
               dimmed: set[int] | None = None) -> list[pdk.Layer]:
    dimmed = dimmed or set()
    halo, core, labels = [], [], []
    for w in hubs:
        c = colour_of[w.id] if w.id not in dimmed else "#7C8599"
        pos = ll(net, w.x, w.y)
        halo.append({"pos": pos, "fill": rgb(c, 55)})
        core.append({"pos": pos, "fill": rgb(c), "tip": tips.get(w.id, ""), "pid": w.id, "kind": "warehouse"})
        labels.append({"pos": pos, "text": w.label})
    return [
        pdk.Layer("ScatterplotLayer", id="hub-halo", data=halo, get_position="pos", get_fill_color="fill",
                  get_radius=190, radius_min_pixels=13, radius_max_pixels=34, pickable=False),
        pdk.Layer("ScatterplotLayer", id="hubs", data=core, get_position="pos", get_fill_color="fill",
                  get_line_color=[255, 255, 255, 255], stroked=True, line_width_min_pixels=2.2,
                  get_radius=80, radius_min_pixels=8, radius_max_pixels=16, pickable=True, auto_highlight=True),
        pdk.Layer("TextLayer", id="hub-labels", data=labels, get_position="pos", get_text="text",
                  get_size=13, get_color=[255, 255, 255, 255], font_weight=800, get_pixel_offset=[0, -24],
                  font_family=FONT, outline_width=4, outline_color=[10, 14, 26, 230],
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
        get_color=[255, 255, 255, 255], font_weight=700, get_pixel_offset=[0, -15],
        font_family=FONT, outline_width=3, outline_color=[10, 14, 26, 220],
        font_settings={"sdf": True}, pickable=False,
    )


# ------------------------------------------------------------------ overlays

def hull(net: Network, hull_pts: list[Point], colour: str = ALGO["hull"]) -> list[pdk.Layer]:
    if len(hull_pts) < 2:
        return []
    path = [ll(net, p.x, p.y) for p in hull_pts + [hull_pts[0]]]
    data = [{"path": path, "tip": ""}]
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
          width: float = 3, tips: list[str] | None = None) -> pdk.Layer:
    data = [{"s": ll(net, a.x, a.y), "t": ll(net, b.x, b.y), "tip": (tips[i] if tips else "")}
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
