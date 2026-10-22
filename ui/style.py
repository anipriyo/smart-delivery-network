"""Colours, CSS and small HTML building blocks for the dashboard.

Custom HTML only uses ``currentColor`` mixes for ink, borders and surfaces,
so it follows whichever Streamlit theme (light or dark) is active. Accent
colours are the five algorithm colours from the project overview document.
"""

from __future__ import annotations

import html

import streamlit as st

# One colour per algorithm, taken from the overview PDF.
ALGO = {
    "voronoi": "#FF6B6B",
    "hull": "#F2A51A",
    "kdtree": "#3DAE5C",
    "cover": "#4C9AFF",
    "pair": "#8B5CF6",
}

# Service-zone colours, one per warehouse in fixed order (validated for colour
# blindness on both basemaps; see AGENTS.md). Never cycled: max 8 warehouses.
ZONES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
ZONES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MAX_WAREHOUSES = len(ZONES_DARK)


def is_dark() -> bool:
    try:
        return st.context.theme.type != "light"
    except Exception:
        return True


def zone_hex(index: int) -> str:
    return (ZONES_DARK if is_dark() else ZONES_LIGHT)[index]


def rgb(hex_color: str, alpha: int = 255) -> list[int]:
    h = hex_color.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)] + [alpha]


def esc(text: object) -> str:
    return html.escape(str(text))


CSS = """
<style>
/* ---------- chrome ---------- */
[data-testid="stToolbar"] [data-testid="stAppDeployButton"], footer, [data-testid="stDecoration"] { display: none !important; }
.block-container { padding-top: 4.2rem !important; padding-bottom: 2.5rem !important; max-width: 1480px; }
[data-testid="stSidebarHeader"] { padding-bottom: 0 !important; }
section[data-testid="stSidebar"] .block-container { padding-top: 0.6rem !important; }
[data-testid="stSidebarUserContent"] { padding-top: 0.25rem; }
h1, h2, h3 { letter-spacing: -0.02em; }

/* ---------- shared tokens (theme-agnostic) ---------- */
.sdn { --ink-2: color-mix(in srgb, currentColor 68%, transparent);
       --ink-3: color-mix(in srgb, currentColor 48%, transparent);
       --line:  color-mix(in srgb, currentColor 11%, transparent);
       --wash:  color-mix(in srgb, currentColor 4%, transparent);
       --wash-2:color-mix(in srgb, currentColor 7%, transparent);
       font-feature-settings: "cv11", "ss01"; }

/* ---------- hero ---------- */
.sdn-hero { position: relative; overflow: hidden; border-radius: 18px; padding: 22px 26px 20px;
            border: 1px solid var(--line); background:
              radial-gradient(1200px 300px at 0% 0%, color-mix(in srgb, #4C9AFF 16%, transparent), transparent 60%),
              radial-gradient(900px 260px at 100% 0%, color-mix(in srgb, #8B5CF6 14%, transparent), transparent 60%),
              var(--wash); }
.sdn-hero::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 4px;
            background: linear-gradient(90deg, #FF6B6B 0 20%, #F2A51A 20% 40%, #3DAE5C 40% 60%, #4C9AFF 60% 80%, #8B5CF6 80% 100%); }
.sdn-eyebrow { font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-2); }
.sdn-title { font-size: clamp(26px, 3.2vw, 38px); font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; margin: 6px 0 6px; }
.sdn-title .grad { background: linear-gradient(90deg, #4C9AFF, #8B5CF6 55%, #FF6B6B); -webkit-background-clip: text; background-clip: text; color: transparent; }
.sdn-sub { font-size: 15px; color: var(--ink-2); max-width: 760px; line-height: 1.5; }
.sdn-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.sdn-chip { display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; font-weight: 600; padding: 5px 11px;
            border-radius: 999px; border: 1px solid var(--line); background: var(--wash-2); white-space: nowrap; }
.sdn-chip i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

/* ---------- KPI cards ---------- */
.sdn-kpis { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin: 14px 0 6px; }
@media (max-width: 1100px) { .sdn-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px)  { .sdn-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.sdn-kpi { position: relative; border-radius: 14px; padding: 13px 14px 12px 16px; border: 1px solid var(--line);
           background: var(--wash); overflow: hidden; min-width: 0; }
.sdn-kpi::before { content: ""; position: absolute; left: 0; top: 12px; bottom: 12px; width: 3px; border-radius: 0 3px 3px 0; background: var(--accent); }
.sdn-kpi .lbl { font-size: 12px; font-weight: 600; color: var(--ink-2); display: flex; align-items: center; gap: 6px; }
.sdn-kpi .val { font-size: 25px; font-weight: 800; letter-spacing: -0.03em; margin-top: 4px; line-height: 1.15; white-space: nowrap; }
.sdn-kpi .val small { font-size: 14px; font-weight: 600; color: var(--ink-2); margin-left: 3px; letter-spacing: 0; }
.sdn-kpi .sub { font-size: 12px; color: var(--ink-3); margin-top: 3px; line-height: 1.35; overflow: hidden;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }

/* ---------- panels ---------- */
.sdn-h { display: flex; align-items: center; gap: 9px; font-size: 15px; font-weight: 700; margin: 2px 0 8px; }
.sdn-h .dot { width: 10px; height: 10px; border-radius: 3px; background: var(--accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 18%, transparent); }
.sdn-h .meta { margin-left: auto; font-size: 12px; font-weight: 600; color: var(--ink-3); }
.sdn-note { font-size: 13px; color: var(--ink-2); line-height: 1.5; }
.sdn-note li { font-size: 13.5px; margin-bottom: 2px; }
.sdn-note code { font-size: 12px; padding: 1px 5px; border-radius: 5px; background: var(--wash-2); }
.sdn-muted { color: var(--ink-3); }

/* ---------- zone bars ---------- */
.sdn-zone { display: grid; grid-template-columns: 34px 1fr auto; align-items: center; gap: 4px 10px; padding: 7px 0; border-bottom: 1px solid var(--line); }
.sdn-zone:last-child { border-bottom: 0; }
.sdn-tag { font-size: 11.5px; font-weight: 800; text-align: center; padding: 3px 0; border-radius: 6px; color: #fff; background: var(--c); }
.sdn-zone .nm { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sdn-zone .ct { font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums; }
.sdn-zone .bar { grid-column: 2 / 4; height: 6px; border-radius: 99px; background: var(--wash-2); overflow: hidden; }
.sdn-zone .bar > span { display: block; height: 100%; border-radius: 99px; background: var(--c); }
.sdn-zone .ds { grid-column: 2 / 4; font-size: 11.5px; color: var(--ink-3); }

/* ---------- lists ---------- */
.sdn-list { display: flex; flex-direction: column; gap: 6px; max-height: 320px; overflow: auto; padding-right: 2px; }
.sdn-row { display: flex; align-items: center; gap: 10px; padding: 7px 10px; border-radius: 10px; background: var(--wash); border: 1px solid var(--line); }
.sdn-row .pin { width: 9px; height: 9px; border-radius: 50%; flex: none; background: var(--c); box-shadow: 0 0 0 3px color-mix(in srgb, var(--c) 22%, transparent); }
.sdn-row .t { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.sdn-row .s { font-size: 11.5px; color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sdn-row .r { margin-left: auto; font-size: 12px; font-weight: 700; color: var(--ink-2); white-space: nowrap; font-variant-numeric: tabular-nums; }
.sdn-row .col { display: flex; flex-direction: column; min-width: 0; }

/* ---------- big stat ---------- */
.sdn-big { display: flex; align-items: baseline; gap: 8px; }
.sdn-big b { font-size: 34px; font-weight: 800; letter-spacing: -0.03em; }
.sdn-big span { font-size: 13px; color: var(--ink-2); font-weight: 600; }

/* ---------- pair card ---------- */
.sdn-pair { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: center; margin: 4px 0 2px; }
.sdn-pair .end { padding: 9px 11px; border-radius: 10px; border: 1px solid var(--line); background: var(--wash); min-width: 0; }
.sdn-pair .end b { display: block; font-size: 12px; color: var(--ink-3); }
.sdn-pair .end span { display: block; font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sdn-pair .mid { font-size: 13px; font-weight: 800; color: #8B5CF6; white-space: nowrap; }

/* ---------- algorithm cards (About) ---------- */
.sdn-algos { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.sdn-algo { border-radius: 16px; padding: 16px 18px; border: 1px solid var(--line); background: var(--wash); position: relative; overflow: hidden; }
.sdn-algo::after { content: ""; position: absolute; right: -40px; top: -40px; width: 120px; height: 120px; border-radius: 50%;
                   background: radial-gradient(circle, color-mix(in srgb, var(--accent) 35%, transparent), transparent 70%); }
.sdn-algo .k { font-size: 11.5px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); }
.sdn-algo h4 { font-size: 18px; font-weight: 800; margin: 4px 0 6px; padding: 0; }
.sdn-algo p { font-size: 13.5px; color: var(--ink-2); line-height: 1.5; margin: 0 0 8px; }
.sdn-algo .cx { display: inline-block; font-family: "JetBrains Mono", monospace; font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: var(--wash-2); }

/* ---------- step card (Walkthrough) ---------- */
.sdn-step { border-radius: 14px; padding: 14px 16px; border: 1px solid var(--line); background: var(--wash); }
.sdn-step .n { font-size: 12px; font-weight: 700; color: var(--ink-3); letter-spacing: .04em; }
.sdn-step .ev { display: inline-block; font-size: 11.5px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; padding: 3px 9px;
                border-radius: 999px; color: #fff; background: var(--accent); margin: 6px 0 8px; }
.sdn-step .d { font-size: 15px; line-height: 1.5; font-weight: 500; }
.sdn-chain { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
.sdn-chain span { font-size: 11.5px; font-weight: 700; padding: 2px 7px; border-radius: 6px; background: var(--wash-2); border: 1px solid var(--line); }
.sdn-chain span.on { background: var(--accent); color: #fff; border-color: transparent; }

/* ---------- timeline (Set cover) ---------- */
.sdn-tl { display: flex; flex-direction: column; gap: 0; }
.sdn-tl .it { display: grid; grid-template-columns: 28px 1fr; gap: 12px; position: relative; padding-bottom: 14px; }
.sdn-tl .it::before { content: ""; position: absolute; left: 13px; top: 28px; bottom: 0; width: 2px; background: var(--line); }
.sdn-tl .it:last-child::before { display: none; }
.sdn-tl .no { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-size: 12px; font-weight: 800; color: #fff; background: var(--c); }
.sdn-tl .tx { font-size: 13.5px; line-height: 1.45; padding-top: 4px; }
.sdn-tl .tx b { font-weight: 700; }
.sdn-tl .pr { height: 5px; border-radius: 99px; background: var(--wash-2); margin-top: 6px; overflow: hidden; }
.sdn-tl .pr > span { display: block; height: 100%; background: #4C9AFF; border-radius: 99px; }

/* ---------- sidebar brand ---------- */
.sdn-brand { display: flex; align-items: center; gap: 11px; margin: 0 0 4px; }
.sdn-brand .logo { width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; flex: none;
                   background: conic-gradient(from 200deg, #FF6B6B, #F2A51A, #3DAE5C, #4C9AFF, #8B5CF6, #FF6B6B); }
.sdn-brand .logo svg { width: 22px; height: 22px; }
.sdn-brand b { display: block; font-size: 15px; font-weight: 800; letter-spacing: -0.01em; line-height: 1.2; }
.sdn-brand span { display: block; font-size: 12px; color: var(--ink-3); }
.sdn-city { border-radius: 12px; padding: 10px 12px; border: 1px solid var(--line); background: var(--wash); margin: 6px 0 2px; }
.sdn-city .r1 { display: flex; justify-content: space-between; font-size: 13px; font-weight: 700; }
.sdn-city .r2 { font-size: 11.5px; color: var(--ink-3); margin-top: 2px; }
.sdn-foot { font-size: 11.5px; color: var(--ink-3); line-height: 1.5; }
.sdn-foot a { color: inherit; }
.sdn-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 12px; color: var(--ink-2); margin-top: 6px; }
.sdn-legend span { display: inline-flex; align-items: center; gap: 6px; }
.sdn-legend i { width: 14px; height: 4px; border-radius: 2px; background: var(--c); display: inline-block; }
.sdn-legend i.dot { width: 9px; height: 9px; border-radius: 50%; }
.sdn-legend i.box { width: 11px; height: 11px; border-radius: 3px; background: color-mix(in srgb, var(--c) 30%, transparent); border: 2px solid var(--c); }

/* deck.gl map frame */
[data-testid="stDeckGlJsonChart"] { border-radius: 16px; overflow: hidden; border: 1px solid color-mix(in srgb, currentColor 12%, transparent); }
</style>
"""

LOGO_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 21s-6-5.3-6-10a6 6 0 1 1 12 0c0 4.7-6 10-6 10z"/><circle cx="12" cy="11" r="2.3"/></svg>'
)


def inject() -> None:
    st.html(CSS)


def block(inner: str) -> None:
    """Render custom HTML inside the theme-aware wrapper."""
    st.html(f'<div class="sdn">{inner}</div>')


def hero(eyebrow: str, title_html: str, sub: str, chips: list[tuple[str, str]]) -> None:
    chip_html = "".join(f'<span class="sdn-chip"><i style="background:{c}"></i>{esc(t)}</span>' for t, c in chips)
    block(
        f'<div class="sdn-hero"><div class="sdn-eyebrow">{esc(eyebrow)}</div>'
        f'<div class="sdn-title">{title_html}</div><div class="sdn-sub">{sub}</div>'
        f'<div class="sdn-chips">{chip_html}</div></div>'
    )


def kpis(cards: list[dict]) -> None:
    """cards: dicts with label, value, unit (optional), sub, accent."""
    out = []
    for c in cards:
        unit = f"<small>{esc(c['unit'])}</small>" if c.get("unit") else ""
        out.append(
            f'<div class="sdn-kpi" style="--accent:{c["accent"]}"><div class="lbl">{esc(c["label"])}</div>'
            f'<div class="val">{esc(c["value"])}{unit}</div><div class="sub">{esc(c.get("sub", ""))}</div></div>'
        )
    block(f'<div class="sdn-kpis">{"".join(out)}</div>')


def heading(text: str, accent: str, meta: str = "") -> None:
    m = f'<span class="meta">{esc(meta)}</span>' if meta else ""
    block(f'<div class="sdn-h" style="--accent:{accent}"><span class="dot"></span>{esc(text)}{m}</div>')


def legend(items: list[tuple[str, str, str]]) -> None:
    """items: (label, colour, shape) with shape in line | dot | box."""
    spans = "".join(
        f'<span><i class="{shape}" style="--c:{c}"></i>{esc(t)}</span>' for t, c, shape in items
    )
    block(f'<div class="sdn-legend">{spans}</div>')


def fmt_km(km: float) -> str:
    return f"{km * 1000:.0f} m" if km < 1 else f"{km:.2f} km"
