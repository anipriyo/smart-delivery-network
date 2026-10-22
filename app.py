"""Smart Delivery & Logistics Network -- interactive dashboard.

Run with: streamlit run app.py
"""

import io

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.spatial import voronoi_plot_2d

from src.closest_pair import closest_pair
from src.convex_hull import convex_hull
from src.data import demo_set, generate_random
from src.kdtree import KDTree
from src.models import Point
from src.set_cover import greedy_set_cover
from src.traces import (
    closest_pair_trace,
    convex_hull_trace,
    kdtree_build_trace,
    kdtree_query_trace,
    voronoi_assignment_trace,
)
from src.voronoi import assign_customers, build_voronoi

st.set_page_config(
    page_title="Smart Delivery & Logistics Network",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={},
)

st.markdown(
    """
    <style>
    #MainMenu, header[data-testid="stHeader"], footer, [data-testid="stToolbar"],
    [data-testid="stDecoration"], [data-testid="stStatusWidget"],
    [data-testid="stElementToolbar"] { display: none !important; }

    .block-container { padding: 0.5rem 1.2rem 0.25rem 1.2rem !important; }
    section[data-testid="stSidebar"] { width: 280px !important; }
    section[data-testid="stSidebar"] > div { padding-top: 0.5rem; height: 100vh; overflow-y: auto; }
    section[data-testid="stSidebar"] .block-container { padding: 0.25rem 1rem !important; }
    section[data-testid="stSidebar"] h1 { font-size: 1.1rem !important; margin: 0 0 0.3rem 0 !important; line-height: 1.3 !important; }
    section[data-testid="stSidebar"] .stCaption { margin: 0 0 0.2rem 0 !important; font-size: 0.75rem !important; }
    section[data-testid="stSidebar"] hr { margin: 0.4rem 0 !important; }

    /* compact every widget's vertical rhythm, in the sidebar and main body */
    div[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
    div[data-testid="stElementContainer"] { margin-bottom: 0 !important; }
    div[data-testid="stWidgetLabel"] { margin-bottom: 0 !important; padding-bottom: 0 !important; }
    div[data-testid="stWidgetLabel"] p { font-size: 0.82rem !important; margin-bottom: 0 !important; }
    div[data-testid="stSlider"] { padding-bottom: 0 !important; }
    div[data-testid="stSlider"] > div { padding: 0 !important; }
    div[data-testid="stNumberInput"] input { padding: 0.2rem 0.5rem !important; }
    label[data-testid="stCheckbox"], label[data-testid="stWidgetLabel"] { min-height: 0 !important; }
    div[data-testid="stCheckbox"] { padding: 0 !important; }
    div[data-testid="stRadio"] > div { gap: 0.1rem !important; }
    div[data-testid="stMarkdownContainer"] p { margin-bottom: 0.1rem !important; font-size: 0.85rem !important; }

    h1 { font-size: 1.3rem !important; margin-bottom: 0 !important; }
    h2 { font-size: 1.1rem !important; margin: 0.2rem 0 0.3rem 0 !important; }
    h3 { font-size: 1rem !important; margin: 0.2rem 0 0.3rem 0 !important; }
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 { padding: 0 !important; }
    .stCaption, [data-testid="stCaptionContainer"] { margin-bottom: 0.2rem !important; font-size: 0.78rem !important; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    div[data-testid="stMetric"] { padding: 0.1rem 0; }
    div[data-testid="stMetricLabel"] { font-size: 0.78rem; }
    .stTabs { margin-top: 0 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; margin-bottom: 0.3rem; }
    .stTabs [data-baseweb="tab"] { padding: 2px 12px; height: auto; }
    .stTabs [data-baseweb="tab-panel"] { padding-top: 0.3rem !important; }

    div[data-testid="stImage"] img { max-height: calc(100vh - 170px); width: auto !important; margin: 0 auto; display: block; }
    div[data-testid="stDataFrame"], div[data-testid="stVegaLiteChart"] { margin-top: 0.35rem; }
    div[data-testid="stAlert"] { margin-top: 0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

REGION_COLORS = ["#F87171", "#60A5FA", "#34D399", "#FBBF24", "#A78BFA", "#F472B6", "#38BDF8", "#FB923C"]


# ---------------------------------------------------------------- data load

def load_points_from_csv(file) -> tuple[list[Point], list[Point]]:
    df = pd.read_csv(file)
    required = {"id", "x", "y", "type"}
    if not required.issubset(df.columns):
        raise ValueError(f"CSV must have columns {required}, got {set(df.columns)}")
    warehouses, customers = [], []
    for _, row in df.iterrows():
        p = Point(id=int(row["id"]), x=float(row["x"]), y=float(row["y"]), kind=str(row["type"]))
        (warehouses if p.kind == "warehouse" else customers).append(p)
    return warehouses, customers


st.sidebar.title("Smart Delivery Network")
st.sidebar.caption("Computational geometry for delivery analysis")

source = st.sidebar.radio("Data source", ["Random (seeded)", "Fixed demo set", "Upload CSV"])

if source == "Random (seeded)":
    w_col, c_col = st.sidebar.columns(2)
    n_w = w_col.slider("Warehouses", 2, 10, 5)
    n_c = c_col.slider("Customers", 10, 150, 40)
    seed = st.sidebar.number_input("Random seed", value=42, step=1)
    warehouses, customers = generate_random(n_w, n_c, seed=int(seed))
elif source == "Fixed demo set":
    warehouses, customers = demo_set()
else:
    uploaded = st.sidebar.file_uploader("CSV with columns id,x,y,type", type="csv")
    if uploaded is None:
        st.info("Upload a CSV with columns: id, x, y, type (type = warehouse/customer).")
        st.stop()
    warehouses, customers = load_points_from_csv(uploaded)

all_points = warehouses + customers

st.sidebar.markdown("---")
h_col, v_col, cp_col = st.sidebar.columns(3)
show_hull = h_col.checkbox("Hull", value=True)
show_voronoi = v_col.checkbox("Voronoi", value=True)
show_closest = cp_col.checkbox("Closest", value=True)
st.sidebar.caption("Range query (KD-tree)")
x_range = st.sidebar.slider("X range", 0.0, 100.0, (30.0, 60.0))
y_range = st.sidebar.slider("Y range", 0.0, 100.0, (40.0, 70.0))
run_set_cover = st.sidebar.checkbox("Run greedy set cover (optional)", value=False)
cover_radius = st.sidebar.slider("Set cover radius", 5.0, 60.0, 25.0) if run_set_cover else None

tab_map, tab_data, tab_cover, tab_walk, tab_about = st.tabs(
    ["Map", "Data", "Set cover", "Walkthrough", "Algorithms"]
)

# ---------------------------------------------------------------- compute

hull = convex_hull(customers) if (show_hull and len(customers) >= 3) else []
assignment = assign_customers(customers, warehouses) if warehouses else {}
vor = build_voronoi(warehouses) if show_voronoi else None
cp = closest_pair(customers) if (show_closest and len(customers) >= 2) else None

tree = KDTree(customers) if customers else None
box_hits = tree.range_query(x_range[0], x_range[1], y_range[0], y_range[1]) if tree else []

wh_by_id = {w.id: w for w in warehouses}

# ---------------------------------------------------------------- map tab

with tab_map:
    map_col, info_col = st.columns([3, 1], gap="medium")

    fig, ax = plt.subplots(figsize=(5.0, 5.0))

    if vor is not None:
        voronoi_plot_2d(
            vor, ax=ax, show_vertices=False, show_points=False,
            line_colors="#94A3B8", line_width=1.0, line_alpha=0.8,
        )
        for region_idx in vor.point_region:
            region = vor.regions[region_idx]
            if -1 in region or not region:
                continue
            poly = [vor.vertices[i] for i in region]
            ax.add_patch(mpatches.Polygon(poly, closed=True, facecolor="#CBD5E1", alpha=0.25, edgecolor="none"))

    if customers:
        wh_id_to_color = {w.id: REGION_COLORS[i % len(REGION_COLORS)] for i, w in enumerate(warehouses)}
        cust_colors = [wh_id_to_color.get(assignment.get(c.id), "#94A3B8") for c in customers]
        ax.scatter([c.x for c in customers], [c.y for c in customers], c=cust_colors, s=35, zorder=3, label="Customers")

    for i, w in enumerate(warehouses):
        ax.scatter(w.x, w.y, marker="*", s=400, c=REGION_COLORS[i % len(REGION_COLORS)],
                   edgecolors="black", linewidths=1, zorder=5)
        ax.annotate(f"W{w.id}", (w.x, w.y), textcoords="offset points", xytext=(10, 10), fontweight="bold")

    if hull:
        hull_pts = hull + [hull[0]]
        ax.plot([p.x for p in hull_pts], [p.y for p in hull_pts], "k--", linewidth=2, zorder=4, label="Convex hull")

    rect = mpatches.Rectangle(
        (x_range[0], y_range[0]), x_range[1] - x_range[0], y_range[1] - y_range[0],
        fill=False, edgecolor="#DC2626", linewidth=2, zorder=4,
    )
    ax.add_patch(rect)
    if box_hits:
        ax.scatter([p.x for p in box_hits], [p.y for p in box_hits], s=90, facecolors="none",
                   edgecolors="#DC2626", linewidths=2, zorder=6)

    if cp:
        p, q, d = cp
        ax.plot([p.x, q.x], [p.y, q.y], color="black", linewidth=1.5, zorder=6)
        mx, my = (p.x + q.x) / 2, (p.y + q.y) / 2
        ax.add_patch(mpatches.Circle((mx, my), radius=max(d / 2 + 1.5, 2.5), fill=False, edgecolor="black", linewidth=1.5, zorder=6))

    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.set_aspect("equal")
    ax.set_title("Delivery network", fontsize=10)
    ax.tick_params(labelsize=8)
    fig.tight_layout(pad=0.3)

    with map_col:
        st.pyplot(fig, width="stretch")

    with info_col:
        m1, m2 = st.columns(2)
        m1.metric("Warehouses", len(warehouses))
        m2.metric("Customers", len(customers))
        m3, m4 = st.columns(2)
        m3.metric("Hull pts", len(hull))
        m4.metric("In box", len(box_hits))

        if cp:
            st.success(f"Closest pair: #{cp[0].id} & #{cp[1].id}, d={cp[2]:.2f}", icon="📍")

        if box_hits:
            st.caption("**In range box:** " + ", ".join(str(p.id) for p in box_hits))
        else:
            st.caption("No customers in the current range box.")

        st.markdown("---")
        st.caption(
            "⭐ warehouse · ● customer · dashed = convex hull · shaded cells = Voronoi "
            "regions · red box = KD-tree range query · black circle = closest pair"
        )

# ---------------------------------------------------------------- data tab

with tab_data:
    table_col, chart_col = st.columns([3, 2], gap="medium")

    with table_col:
        st.markdown("**Point set**")
        df = pd.DataFrame(
            [{"id": p.id, "x": p.x, "y": p.y, "type": p.kind,
              "served_by": str(assignment[p.id]) if p.kind == "customer" and p.id in assignment else ""}
             for p in all_points]
        )
        table_height = min(38 * (len(df) + 1) + 3, 700)
        st.dataframe(df, width="stretch", height=table_height)
        csv_buf = io.StringIO()
        df[["id", "x", "y", "type"]].to_csv(csv_buf, index=False)
        st.download_button("Download as CSV", csv_buf.getvalue(), file_name="delivery_points.csv")

    with chart_col:
        st.markdown("**Customers per warehouse**")
        if assignment:
            counts = pd.Series(list(assignment.values())).value_counts().rename_axis("warehouse_id").reset_index(name="customers")
            st.bar_chart(counts.set_index("warehouse_id"), height=table_height)
        else:
            st.info("No customers assigned yet.")

# ---------------------------------------------------------------- set cover tab

with tab_cover:
    st.markdown(
        "**Greedy set cover: which warehouses to keep**<br>"
        "<span style='font-size:0.85rem; display:block; margin-top:0.3rem'>Treats every warehouse as a <i>candidate</i> site covering customers "
        "within the chosen radius, then greedily picks the site covering the most still-uncovered customers "
        "until everyone is covered.</span>",
        unsafe_allow_html=True,
    )
    if not run_set_cover:
        st.info("Enable 'Run greedy set cover' in the sidebar to compute this.")
    elif not warehouses:
        st.warning("No warehouse candidates available.")
    else:
        chosen, rounds = greedy_set_cover(warehouses, customers, cover_radius)
        for i, r in enumerate(rounds, start=1):
            st.write(
                f"**Round {i}:** pick warehouse **W{r['site'].id}** -> "
                f"covers {len(r['new_covered'])} new customer(s) "
                f"(total covered: {r['total_covered']}/{len(customers)})"
            )
        if chosen:
            st.success(
                f"Result: {len(chosen)} of {len(warehouses)} warehouses "
                f"({', '.join('W' + str(w.id) for w in chosen)}) cover "
                f"{rounds[-1]['total_covered']}/{len(customers)} customers at radius {cover_radius:.0f}."
            )
        else:
            st.warning("No candidate covers any customer at this radius. Try increasing it.")

# ---------------------------------------------------------------- walkthrough tab

cust_by_id = {c.id: c for c in customers}


def _wk_base_ax(ax, dim=False):
    """Draw every customer as a light backdrop so the highlighted subset stands out."""
    if customers:
        ax.scatter([c.x for c in customers], [c.y for c in customers],
                   s=22, c="#E2E8F0" if dim else "#CBD5E1", zorder=1, linewidths=0)
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.set_aspect("equal")
    ax.tick_params(labelsize=7)


def _wk_fig():
    return plt.subplots(figsize=(4.3, 4.3))


with tab_walk:
    st.caption("Pick an algorithm, then step through it one decision at a time on the data currently loaded.")
    wk_hull, wk_closest, wk_kdtree, wk_voronoi = st.tabs(
        ["Convex hull", "Closest pair", "KD-tree", "Voronoi"]
    )

    # -------------------------------------------------------- convex hull
    with wk_hull:
        if len(customers) < 3:
            st.warning("Need at least 3 customers to build a hull.")
        else:
            hull_result, hull_steps = convex_hull_trace(customers)
            n = len(hull_steps)
            txt_col, viz_col = st.columns([1, 1], gap="medium")

            with txt_col:
                st.markdown("**Graham scan** sorts points, then builds two chains (lower, upper), "
                            "popping the last point whenever it would make a non-left turn.")
                step_i = st.slider("Step", 1, n, n, key="hull_step")
                s = hull_steps[step_i - 1]
                icon = "➕ push" if s["action"] == "push" else "➖ pop"
                st.markdown(f"**Step {step_i}/{n} · {s['chain']} chain · {icon}**")
                st.info(s["detail"])
                if step_i == n:
                    st.success("Final hull (in order): " + " -> ".join(f"P{p.id}" for p in hull_result))

            with viz_col:
                fig, ax = _wk_fig()
                _wk_base_ax(ax)
                chain_pts = [cust_by_id[i] for i in s["snapshot"] if i in cust_by_id]
                if len(chain_pts) >= 2:
                    color = "#2563EB" if s["chain"] == "lower" else "#D97706"
                    ax.plot([p.x for p in chain_pts], [p.y for p in chain_pts], "-o",
                            color=color, linewidth=2, markersize=5, zorder=3)
                cur = cust_by_id.get(s["current"])
                if cur:
                    ax.scatter([cur.x], [cur.y], s=160, facecolors="none",
                               edgecolors="#DC2626", linewidths=2.5, zorder=4)
                    ax.annotate(f"P{cur.id}", (cur.x, cur.y), textcoords="offset points",
                               xytext=(6, 6), fontsize=8, fontweight="bold")
                ax.set_title(f"{s['chain']} chain, step {step_i}", fontsize=9)
                fig.tight_layout(pad=0.3)
                st.pyplot(fig, width="stretch")

    # -------------------------------------------------------- closest pair
    with wk_closest:
        if len(customers) < 2:
            st.warning("Need at least 2 customers.")
        else:
            (bp, bq, bd), cp_steps = closest_pair_trace(customers)
            n = len(cp_steps)
            txt_col, viz_col = st.columns([1, 1], gap="medium")

            with txt_col:
                st.markdown("**Divide and conquer**: split by x, solve both halves, then check only "
                            "the thin strip around the dividing line for a closer cross-boundary pair.")
                step_i = st.slider("Step", 1, n, n, key="cp_step")
                s = cp_steps[step_i - 1]
                label = {"divide": "🔀 divide", "base case": "⏹️ base case",
                         "combine": "🔗 combine", "strip check": "📏 strip check"}[s["event"]]
                st.markdown(f"**Step {step_i}/{n} · depth {s['depth']} · {label}**")
                st.info(s["detail"])
                if step_i == n:
                    st.success(f"Result: P{bp.id} and P{bq.id}, distance = {bd:.2f}")

            with viz_col:
                fig, ax = _wk_fig()
                _wk_base_ax(ax, dim=True)
                active = [cust_by_id[i] for i in s.get("active_ids", []) if i in cust_by_id]
                if active:
                    ax.scatter([p.x for p in active], [p.y for p in active],
                               s=45, c="#64748B", zorder=2)
                if s["event"] == "divide":
                    left = [cust_by_id[i] for i in s["left_ids"] if i in cust_by_id]
                    right = [cust_by_id[i] for i in s["right_ids"] if i in cust_by_id]
                    if left:
                        ax.scatter([p.x for p in left], [p.y for p in left], s=45, c="#2563EB", zorder=3)
                    if right:
                        ax.scatter([p.x for p in right], [p.y for p in right], s=45, c="#D97706", zorder=3)
                if s.get("split_x") is not None:
                    ax.axvline(s["split_x"], color="#111827", linestyle="--", linewidth=1.2, zorder=2)
                if s["event"] == "strip check":
                    strip = [cust_by_id[i] for i in s["strip_ids"] if i in cust_by_id]
                    if strip:
                        ax.scatter([p.x for p in strip], [p.y for p in strip],
                                   s=70, facecolors="none", edgecolors="#059669", linewidths=2, zorder=4)
                if s.get("best") is not None:
                    bi, bj, _ = s["best"]
                    p1, p2 = cust_by_id.get(bi), cust_by_id.get(bj)
                    if p1 and p2:
                        ax.plot([p1.x, p2.x], [p1.y, p2.y], color="#DC2626", linewidth=2, zorder=5)
                        ax.scatter([p1.x, p2.x], [p1.y, p2.y], s=60, c="#DC2626", zorder=5)
                ax.set_title(f"{s['event']}, depth {s['depth']}", fontsize=9)
                fig.tight_layout(pad=0.3)
                st.pyplot(fig, width="stretch")

    # -------------------------------------------------------- kd-tree
    with wk_kdtree:
        if not customers:
            st.warning("No customers to build a tree from.")
        else:
            sub_build, sub_query = st.tabs(["Build", "Range query"])

            with sub_build:
                build_steps = kdtree_build_trace(customers)
                n = len(build_steps)
                txt_col, viz_col = st.columns([1, 1], gap="medium")

                with txt_col:
                    st.markdown("**Build**: split the points by x at even depths and by y at odd "
                               "depths, always on the median, so lookups can skip whole subtrees.")
                    step_i = st.slider("Step", 1, n, n, key="kd_build_step")
                    s = build_steps[step_i - 1]
                    st.markdown(f"**Step {step_i}/{n} · depth {s['depth']} · split on {s['axis']}**")
                    st.info(s["detail"])

                with viz_col:
                    fig, ax = _wk_fig()
                    _wk_base_ax(ax)
                    for prev in build_steps[:step_i]:
                        (x0, y0), (x1, y1) = prev["seg"]
                        fade = prev is build_steps[step_i - 1]
                        ax.plot([x0, x1], [y0, y1],
                               color="#DC2626" if fade else "#94A3B8",
                               linewidth=2 if fade else 1, zorder=2)
                    med = cust_by_id.get(s["median_point"])
                    if med:
                        ax.scatter([med.x], [med.y], s=140, facecolors="none",
                                  edgecolors="#DC2626", linewidths=2.5, zorder=4)
                        ax.annotate(f"P{med.id}", (med.x, med.y), textcoords="offset points",
                                   xytext=(6, 6), fontsize=8, fontweight="bold")
                    ax.set_title(f"depth {s['depth']}, split on {s['axis']}", fontsize=9)
                    fig.tight_layout(pad=0.3)
                    st.pyplot(fig, width="stretch")

            with sub_query:
                _, query_steps = kdtree_query_trace(tree, x_range[0], x_range[1], y_range[0], y_range[1])
                n = len(query_steps)
                txt_col, viz_col = st.columns([1, 1], gap="medium")

                with txt_col:
                    st.markdown(f"**Range query** for the box x:[{x_range[0]:.0f}, {x_range[1]:.0f}], "
                               f"y:[{y_range[0]:.0f}, {y_range[1]:.0f}]. Whole subtrees are skipped "
                               "whenever the splitting value puts them entirely outside the box.")
                    step_i = st.slider("Step", 1, n, n, key="kd_query_step")
                    s = query_steps[step_i - 1]
                    if s.get("pruned"):
                        st.markdown(f"**Step {step_i}/{n} · ✂️ pruned**")
                    else:
                        icon = "✅ inside box" if s["in_box"] else "👀 outside box"
                        st.markdown(f"**Step {step_i}/{n} · depth {s['depth']} · {icon}**")
                    st.info(s["detail"])

                with viz_col:
                    fig, ax = _wk_fig()
                    _wk_base_ax(ax, dim=True)
                    rect = mpatches.Rectangle(
                        (x_range[0], y_range[0]), x_range[1] - x_range[0], y_range[1] - y_range[0],
                        fill=False, edgecolor="#DC2626", linewidth=1.5, zorder=2,
                    )
                    ax.add_patch(rect)
                    visited = [t for t in query_steps[:step_i] if not t.get("pruned")]
                    for v in visited:
                        p = cust_by_id.get(v["point"])
                        if not p:
                            continue
                        is_current = v is query_steps[step_i - 1]
                        color = "#059669" if v["in_box"] else "#94A3B8"
                        ax.scatter([p.x], [p.y], s=100 if is_current else 55,
                                  facecolors="none" if is_current else color,
                                  edgecolors=color, linewidths=2 if is_current else 0, zorder=3)
                    ax.set_title("range query", fontsize=9)
                    fig.tight_layout(pad=0.3)
                    st.pyplot(fig, width="stretch")

    # -------------------------------------------------------- voronoi
    with wk_voronoi:
        if not customers or not warehouses:
            st.warning("Need at least one warehouse and one customer.")
        else:
            cust_ids = [c.id for c in customers]
            picked_id = st.selectbox("Pick a customer to trace", cust_ids, index=0)
            picked = next(c for c in customers if c.id == picked_id)
            rows = voronoi_assignment_trace(picked, warehouses)
            n = len(rows)
            txt_col, viz_col = st.columns([1, 1], gap="medium")

            with txt_col:
                st.markdown("**Voronoi assignment**: a customer belongs to whichever warehouse it is "
                           "closest to -- exactly the cell of the Voronoi diagram it falls inside.")
                step_i = st.slider("Warehouses compared so far", 1, n, n, key="vor_step")
                shown = rows[:step_i]
                df = pd.DataFrame(shown).rename(columns={"warehouse": "warehouse id", "distance": "distance"})
                df["distance"] = df["distance"].round(2)
                st.dataframe(df, width="stretch", height=min(38 * (step_i + 1), 220))
                if step_i == n:
                    nearest = rows[0]
                    st.success(f"Customer P{picked_id} is closest to warehouse W{nearest['warehouse']} "
                              f"(distance {nearest['distance']:.2f}) -> assigned to W{nearest['warehouse']}.")

            with viz_col:
                fig, ax = _wk_fig()
                _wk_base_ax(ax, dim=True)
                ax.scatter([picked.x], [picked.y], s=130, c="#DC2626", zorder=5, marker="o",
                          edgecolors="black", linewidths=1)
                ax.annotate(f"P{picked.id}", (picked.x, picked.y), textcoords="offset points",
                           xytext=(6, 6), fontsize=8, fontweight="bold")
                wh_by_id_local = {w.id: w for w in warehouses}
                for i, row in enumerate(rows[:step_i]):
                    w = wh_by_id_local.get(row["warehouse"])
                    if not w:
                        continue
                    is_nearest = i == 0
                    ax.plot([picked.x, w.x], [picked.y, w.y],
                           color="#059669" if is_nearest else "#94A3B8",
                           linewidth=2 if is_nearest else 1, linestyle="-" if is_nearest else "--", zorder=2)
                    ax.scatter([w.x], [w.y], marker="*", s=260,
                              c="#059669" if is_nearest else "#CBD5E1", edgecolors="black", linewidths=1, zorder=4)
                    ax.annotate(f"W{w.id}", (w.x, w.y), textcoords="offset points", xytext=(6, 6), fontsize=8)
                ax.set_title(f"comparing {step_i}/{n} warehouse(s)", fontsize=9)
                fig.tight_layout(pad=0.3)
                st.pyplot(fig, width="stretch")

# ---------------------------------------------------------------- about tab

with tab_about:
    st.subheader("Which algorithm answers which question")
    st.table(pd.DataFrame([
        ["Voronoi diagram", "Which warehouse serves this area?", "O(m log m)"],
        ["KD-tree range search", "Which customers lie inside this box?", "build O(n log n), query O(√n + k)"],
        ["Closest pair (divide & conquer)", "Which two stops are nearest each other?", "O(n log n)"],
        ["Convex hull (Graham scan)", "How far does the network reach?", "O(n log n)"],
        ["Greedy set cover", "Which few warehouses cover the most demand?", "ln n approximation"],
    ], columns=["Algorithm", "Question", "Cost"]))
    st.caption(
        "This is a geometric decision-support tool, not a full vehicle-routing system: "
        "no traffic, fuel, or driver scheduling. Distances are Euclidean on a flat plane."
    )
