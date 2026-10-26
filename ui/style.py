"""Colours, CSS and small HTML building blocks for the dashboard.

One professional light theme (see .streamlit/config.toml): slate neutrals,
an indigo brand colour, white cards with hairline borders and soft shadows,
and one muted accent per algorithm.
"""

from __future__ import annotations

import html

import streamlit as st

PROJECT = "Smart Delivery Network"
COURSE = "Algorithms II · Group project"
TEAM = [
    ("Akash Chakraborty", "CSE/23011"),
    ("Anipriyo Mandal", "CSE/23017"),
    ("Arpan Mandal", "CSE/23027"),
]

BRAND = "#4F46E5"
INK = "#0F172A"
INK_2 = "#475569"
MUTED = "#94A3B8"

# One accent per algorithm (Tailwind 600 steps: same weight, distinct hues).
ALGO = {
    "voronoi": "#E11D48",
    "hull": "#D97706",
    "kdtree": "#059669",
    "pair": "#7C3AED",
    "cover": "#0891B2",
}
RIVER = "#2563EB"
BRIDGE = "#1E293B"
FERRY = "#0284C7"
CRITICAL = "#DC2626"

# Service-zone colours, one per warehouse in fixed order, validated for colour
# blindness on the light basemap (see AGENTS.md). Never cycled: max 8 warehouses.
ZONES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MAX_WAREHOUSES = len(ZONES)


def zone_hex(index: int) -> str:
    return ZONES[index]


def rgb(hex_color: str, alpha: int = 255) -> list[int]:
    h = hex_color.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)] + [alpha]


def esc(text: object) -> str:
    return html.escape(str(text))


CSS = """
<style>
/* ---------- chrome ---------- */
[data-testid="stToolbar"] [data-testid="stAppDeployButton"], footer, [data-testid="stDecoration"] { display: none !important; }
.block-container { padding-top: 4.4rem !important; padding-bottom: 3rem !important; max-width: 1440px; }
[data-testid="stSidebarHeader"] { padding-bottom: 0 !important; }
section[data-testid="stSidebar"] .block-container { padding-top: 0.6rem !important; }
header[data-testid="stHeader"] { background: rgba(255, 255, 255, 0.9); backdrop-filter: saturate(180%) blur(10px);
                                 border-bottom: 1px solid #E2E8F0; }
div[data-testid="stTabs"] button[role="tab"] p { font-weight: 600; }
h1, h2, h3 { letter-spacing: -0.02em; }

/* ---------- tokens ---------- */
.sdn { --ink: #0F172A; --ink-2: #475569; --ink-3: #64748B; --line: #E2E8F0; --line-2: #EEF2F6;
       --card: #FFFFFF; --wash: #F8FAFC; --wash-2: #F1F5F9; --brand: #4F46E5; --brand-ink: #3730A3;
       --shadow: 0 1px 2px rgba(15, 23, 42, .05), 0 1px 1px rgba(15, 23, 42, .03);
       color: var(--ink); font-feature-settings: "cv11", "ss01", "tnum" 0; }

/* ---------- page header ---------- */
.sdn-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: stretch;
            background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 22px 24px;
            box-shadow: var(--shadow); border-top: 3px solid var(--brand); }
.sdn-head > div { min-width: 0; }
@media (max-width: 900px) { .sdn-head { grid-template-columns: minmax(0, 1fr); padding: 18px 18px; } }
@media (max-width: 640px) { .sdn-chip { white-space: normal; max-width: 100%; } .sdn-title { font-size: 24px; } }
.sdn-eyebrow { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; font-size: 11.5px; font-weight: 700; letter-spacing: .1em;
               text-transform: uppercase; color: var(--brand-ink); }
.sdn-eyebrow .sep { color: #CBD5E1; }
.sdn-eyebrow .pg { color: var(--ink-3); }
.sdn-title { font-size: clamp(24px, 2.6vw, 32px); font-weight: 800; letter-spacing: -0.03em; line-height: 1.15; margin: 8px 0 8px; color: var(--ink); }
.sdn-title .accent { color: var(--brand); }
.sdn-sub { font-size: 14.5px; color: var(--ink-2); max-width: 860px; line-height: 1.6; }
.sdn-sub b { color: var(--ink); font-weight: 650; }
.sdn-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.sdn-chip { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 600; padding: 4px 10px;
            border-radius: 7px; border: 1px solid var(--line); background: var(--wash); color: var(--ink-2); white-space: nowrap; }
.sdn-chip i { width: 7px; height: 7px; border-radius: 2px; display: inline-block; }
.sdn-team { border-left: 1px solid var(--line); padding-left: 22px; min-width: 230px; display: flex; flex-direction: column; justify-content: center; gap: 10px; }
@media (max-width: 900px) { .sdn-team { border-left: 0; padding-left: 0; border-top: 1px solid var(--line); padding-top: 14px; } }
.sdn-team .lbl { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-3); }
.sdn-member { display: flex; align-items: center; gap: 10px; }
.sdn-member .av { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; font-size: 11.5px; font-weight: 800;
                  color: var(--brand-ink); background: #EEF2FF; border: 1px solid #E0E7FF; flex: none; }
.sdn-member b { display: block; font-size: 13px; font-weight: 650; line-height: 1.2; }
.sdn-member span { display: block; font-size: 11.5px; color: var(--ink-3); font-variant-numeric: tabular-nums; }

/* ---------- KPI cards ---------- */
.sdn-kpis { display: grid; grid-template-columns: repeat(var(--n, 6), minmax(0, 1fr)); gap: 12px; margin: 14px 0 6px; }
@media (max-width: 1100px) { .sdn-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px)  { .sdn-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.sdn-kpi { border-radius: 14px; padding: 13px 15px 12px; border: 1px solid var(--line); background: var(--card); box-shadow: var(--shadow); min-width: 0; }
.sdn-kpi .lbl { font-size: 11.5px; font-weight: 650; color: var(--ink-3); display: flex; align-items: center; gap: 7px;
                text-transform: uppercase; letter-spacing: .05em; }
.sdn-kpi .lbl i { width: 8px; height: 8px; border-radius: 2px; background: var(--accent); flex: none; }
.sdn-kpi .val { font-size: 24px; font-weight: 750; letter-spacing: -0.03em; margin-top: 6px; line-height: 1.15; white-space: nowrap; color: var(--ink);
                font-variant-numeric: tabular-nums; }
.sdn-kpi .val small { font-size: 13px; font-weight: 600; color: var(--ink-3); margin-left: 3px; letter-spacing: 0; }
.sdn-kpi .sub { font-size: 12px; color: var(--ink-3); margin-top: 3px; line-height: 1.35; overflow: hidden;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }

/* ---------- panels ---------- */
.sdn-h { display: flex; align-items: center; gap: 9px; font-size: 14.5px; font-weight: 700; margin: 2px 0 8px; color: var(--ink); }
.sdn-h .dot { width: 8px; height: 8px; border-radius: 2px; background: var(--accent); }
.sdn-h .meta { margin-left: auto; font-size: 12px; font-weight: 600; color: var(--ink-3); }
.sdn-note { font-size: 13px; color: var(--ink-2); line-height: 1.6; }
.sdn-note li { font-size: 13.5px; margin-bottom: 3px; }
.sdn-note b { color: var(--ink); }
.sdn-note code { font-size: 12px; padding: 1px 5px; border-radius: 5px; background: var(--wash-2); color: var(--ink); }
.sdn-muted { color: var(--ink-3); }
.sdn-callout { border: 1px solid #C7D2FE; background: #EEF2FF; border-radius: 12px; padding: 12px 14px; font-size: 13.5px; line-height: 1.55; color: #1E1B4B; }
.sdn-callout b { color: #1E1B4B; }
.sdn-callout.warn { border-color: #FED7AA; background: #FFF7ED; color: #7C2D12; }
.sdn-callout.warn b { color: #7C2D12; }

/* ---------- zone bars ---------- */
.sdn-zone { display: grid; grid-template-columns: 34px 1fr auto; align-items: center; gap: 4px 10px; padding: 8px 0; border-bottom: 1px solid var(--line-2); }
.sdn-zone:last-child { border-bottom: 0; }
.sdn-tag { font-size: 11.5px; font-weight: 800; text-align: center; padding: 3px 0; border-radius: 6px; color: #fff; background: var(--c); }
.sdn-zone .nm { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sdn-zone .ct { font-size: 13px; font-weight: 750; font-variant-numeric: tabular-nums; }
.sdn-zone .bar { grid-column: 2 / 4; height: 5px; border-radius: 99px; background: var(--wash-2); overflow: hidden; }
.sdn-zone .bar > span { display: block; height: 100%; border-radius: 99px; background: var(--c); }
.sdn-zone .ds { grid-column: 2 / 4; font-size: 11.5px; color: var(--ink-3); }

/* ---------- lists ---------- */
.sdn-list { display: flex; flex-direction: column; gap: 6px; max-height: 340px; overflow: auto; padding: 1px; }
.sdn-row { display: flex; align-items: center; gap: 10px; padding: 8px 11px; border-radius: 10px; background: var(--card); border: 1px solid var(--line); }
.sdn-row .pin { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--c); }
.sdn-row .t { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; color: var(--ink); }
.sdn-row .s { font-size: 11.5px; color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sdn-row .r { margin-left: auto; font-size: 12px; font-weight: 700; color: var(--ink-2); white-space: nowrap; font-variant-numeric: tabular-nums; text-align: right; }
.sdn-row .r small { display: block; font-size: 11px; font-weight: 600; color: var(--ink-3); }
.sdn-row .col { display: flex; flex-direction: column; min-width: 0; }

/* ---------- big stat ---------- */
.sdn-big { display: flex; align-items: baseline; gap: 8px; }
.sdn-big b { font-size: 30px; font-weight: 800; letter-spacing: -0.03em; }
.sdn-big span { font-size: 13px; color: var(--ink-2); font-weight: 600; }

/* ---------- pair card ---------- */
.sdn-pair { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: center; margin: 4px 0 2px; }
.sdn-pair .end { padding: 9px 11px; border-radius: 10px; border: 1px solid var(--line); background: var(--wash); min-width: 0; }
.sdn-pair .end b { display: block; font-size: 12px; color: var(--ink-3); }
.sdn-pair .end span { display: block; font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sdn-pair .mid { font-size: 13px; font-weight: 800; color: #7C3AED; white-space: nowrap; }

/* ---------- algorithm cards (How it works) ---------- */
.sdn-algos { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px; }
.sdn-algo { border-radius: 14px; padding: 16px 16px 14px; border: 1px solid var(--line); background: var(--card); box-shadow: var(--shadow); }
.sdn-algo .k { display: inline-flex; align-items: center; gap: 7px; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-3); }
.sdn-algo .k i { width: 8px; height: 8px; border-radius: 2px; background: var(--accent); }
.sdn-algo h4 { font-size: 16.5px; font-weight: 750; margin: 6px 0 6px; padding: 0; color: var(--ink); }
.sdn-algo p { font-size: 13.5px; color: var(--ink-2); line-height: 1.55; margin: 0 0 10px; }
.sdn-algo .cx { display: inline-block; font-family: "JetBrains Mono", monospace; font-size: 11.5px; font-weight: 600; padding: 3px 8px;
                border-radius: 6px; color: var(--ink-2); background: var(--wash-2); border: 1px solid var(--line); }

/* ---------- step card (Walkthrough) ---------- */
.sdn-step { border-radius: 14px; padding: 14px 16px; border: 1px solid var(--line); background: var(--card); box-shadow: var(--shadow); }
.sdn-step .n { font-size: 11.5px; font-weight: 700; color: var(--ink-3); letter-spacing: .06em; }
.sdn-step .ev { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; padding: 3px 8px;
                border-radius: 6px; color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, white);
                border: 1px solid color-mix(in srgb, var(--accent) 22%, white); margin: 6px 0 8px; }
.sdn-step .d { font-size: 14.5px; line-height: 1.55; font-weight: 500; color: var(--ink); }
.sdn-chain { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
.sdn-chain span { font-size: 11.5px; font-weight: 700; padding: 2px 7px; border-radius: 6px; background: var(--wash); border: 1px solid var(--line); color: var(--ink-2); }
.sdn-chain span.on { background: var(--accent); color: #fff; border-color: transparent; }

/* ---------- pseudocode + plain words ---------- */
.sdn-code, .sdn-words { border-radius: 14px; border: 1px solid var(--line); background: var(--card); box-shadow: var(--shadow);
                        padding: 12px 14px; margin-top: 10px; }
.sdn-code .cap, .sdn-words .cap { font-size: 11.5px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
                                  color: var(--accent); margin-bottom: 8px; display: flex; flex-wrap: wrap; gap: 4px 10px;
                                  justify-content: space-between; align-items: baseline; }
.sdn-code .cap span { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 11px; font-weight: 600;
                      letter-spacing: 0; text-transform: none; color: var(--ink-3); }
.sdn-code .ln { display: flex; gap: 10px; padding: 2px 6px; border-radius: 6px; border-left: 3px solid transparent;
                font-family: "JetBrains Mono", ui-monospace, Menlo, monospace; font-size: 12px; line-height: 1.55; color: var(--ink); }
.sdn-code .ln b { flex: none; width: 16px; text-align: right; font-weight: 500; color: var(--ink-3); }
.sdn-code .ln span { overflow-wrap: anywhere; }
.sdn-code .ln em { font-style: normal; color: var(--ink-3); }
.sdn-code .ln.on { background: color-mix(in srgb, var(--accent) 12%, white); border-left-color: var(--accent); font-weight: 600; }
.sdn-words ol { margin: 0 0 0 18px; padding: 0; }
.sdn-words li { font-size: 13.5px; line-height: 1.6; color: var(--ink-2); margin-bottom: 4px; }

/* ---------- timeline (Coverage) ---------- */
.sdn-tl { display: flex; flex-direction: column; gap: 0; }
.sdn-tl .it { display: grid; grid-template-columns: 26px 1fr; gap: 12px; position: relative; padding-bottom: 14px; }
.sdn-tl .it::before { content: ""; position: absolute; left: 12px; top: 26px; bottom: 0; width: 2px; background: var(--line); }
.sdn-tl .it:last-child::before { display: none; }
.sdn-tl .no { width: 26px; height: 26px; border-radius: 7px; display: grid; place-items: center; font-size: 12px; font-weight: 800; color: #fff; background: var(--c); }
.sdn-tl .tx { font-size: 13.5px; line-height: 1.45; padding-top: 3px; }
.sdn-tl .tx b { font-weight: 700; }
.sdn-tl .pr { height: 5px; border-radius: 99px; background: var(--wash-2); margin-top: 6px; overflow: hidden; }
.sdn-tl .pr > span { display: block; height: 100%; background: #0891B2; border-radius: 99px; }

/* ---------- sidebar ---------- */
.sdn-brand { display: flex; align-items: center; gap: 11px; margin: 0 0 4px; }
.sdn-brand .logo { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; flex: none; background: #4F46E5;
                   color: #fff; font-size: 14px; font-weight: 800; letter-spacing: -0.02em; }
.sdn-brand b { display: block; font-size: 15px; font-weight: 800; letter-spacing: -0.01em; line-height: 1.2; }
.sdn-brand span { display: block; font-size: 12px; color: var(--ink-3); }
.sdn-city { border-radius: 12px; padding: 10px 12px; border: 1px solid var(--line); background: var(--wash); margin: 6px 0 2px; }
.sdn-city .r1 { display: flex; justify-content: space-between; font-size: 13px; font-weight: 700; }
.sdn-city .r2 { font-size: 11.5px; color: var(--ink-3); margin-top: 3px; line-height: 1.45; }
.sdn-foot { font-size: 11.5px; color: var(--ink-3); line-height: 1.55; }
.sdn-foot a { color: inherit; }
.sdn-foot b { color: var(--ink-2); }
.sdn-legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; color: var(--ink-2); margin-top: 8px; }
.sdn-legend span { display: inline-flex; align-items: center; gap: 6px; }
.sdn-legend i { width: 16px; height: 3px; border-radius: 2px; background: var(--c); display: inline-block; }
.sdn-legend i.dash { background: repeating-linear-gradient(90deg, var(--c) 0 5px, transparent 5px 8px); }
.sdn-legend i.thick { height: 5px; }
.sdn-legend i.dot { width: 9px; height: 9px; border-radius: 50%; }
.sdn-legend i.ring { width: 9px; height: 9px; border-radius: 50%; background: transparent; border: 2px solid var(--c); }
.sdn-legend i.box { width: 11px; height: 11px; border-radius: 3px; background: color-mix(in srgb, var(--c) 22%, white); border: 1.5px solid var(--c); }

/* deck.gl map frame */
[data-testid="stDeckGlJsonChart"] { border-radius: 14px; overflow: hidden; border: 1px solid #E2E8F0;
                                    box-shadow: 0 1px 2px rgba(15, 23, 42, .05); }
</style>
"""

LOGO = "SD"  # st.html strips inline SVG, so the logo is the project's initials


def inject() -> None:
    st.html(CSS)


def block(inner: str) -> None:
    """Render custom HTML inside the styled wrapper."""
    st.html(f'<div class="sdn">{inner}</div>')


def team_html() -> str:
    people = "".join(
        f'<div class="sdn-member"><span class="av">{esc("".join(w[0] for w in name.split()[:2]))}</span>'
        f'<span><b>{esc(name)}</b><span>{esc(roll)}</span></span></div>'
        for name, roll in TEAM
    )
    return f'<div class="sdn-team"><span class="lbl">Team</span>{people}</div>'


def header(page: str, title_html: str, sub: str, chips: list[tuple[str, str]], team: bool = False) -> None:
    """Page header. ``title_html`` and ``sub`` may contain trusted markup."""
    crumb = f'<span class="sep">/</span><span class="pg">{esc(page)}</span>' if page else ""
    chip_html = "".join(f'<span class="sdn-chip"><i style="background:{c}"></i>{esc(t)}</span>' for t, c in chips)
    block(
        f'<div class="sdn-head"><div><div class="sdn-eyebrow">{esc(PROJECT)}<span class="sep">·</span>'
        f'{esc(COURSE)}{crumb}</div><div class="sdn-title">{title_html}</div><div class="sdn-sub">{sub}</div>'
        f'<div class="sdn-chips">{chip_html}</div></div>{team_html() if team else ""}</div>'
    )


def kpis(cards: list[dict]) -> None:
    """cards: dicts with label, value, unit (optional), sub, accent."""
    out = []
    for c in cards:
        unit = f"<small>{esc(c['unit'])}</small>" if c.get("unit") else ""
        out.append(
            f'<div class="sdn-kpi" style="--accent:{c["accent"]}"><div class="lbl"><i></i>{esc(c["label"])}</div>'
            f'<div class="val">{esc(c["value"])}{unit}</div><div class="sub">{esc(c.get("sub", ""))}</div></div>'
        )
    block(f'<div class="sdn-kpis" style="--n:{len(cards)}">{"".join(out)}</div>')


def heading(text: str, accent: str, meta: str = "") -> None:
    m = f'<span class="meta">{esc(meta)}</span>' if meta else ""
    block(f'<div class="sdn-h" style="--accent:{accent}"><span class="dot"></span>{esc(text)}{m}</div>')


def legend(items: list[tuple[str, str, str]]) -> None:
    """items: (label, colour, shape) with shape in line | dash | thick | dot | ring | box."""
    spans = "".join(
        f'<span><i class="{shape}" style="--c:{c}"></i>{esc(t)}</span>' for t, c, shape in items
    )
    block(f'<div class="sdn-legend">{spans}</div>')


def fmt_km(km: float) -> str:
    return f"{km * 1000:.0f} m" if km < 1 else f"{km:.2f} km"
