"""Each algorithm in plain words and in pseudocode, for the Walkthrough and the planner pages.

Pseudocode lines are plain text; ``▷`` starts a comment. ``LINES`` maps a
Walkthrough step to the line(s) it is executing, so the card can highlight them.
"""

from __future__ import annotations

from . import style
from .style import esc

ALGOS: dict[str, dict] = {
    "hull": {
        "words": [
            "Sort the stops from west to east.",
            "Walk along them and keep a chain of points. Before adding a new point, look at the last two points "
            "of the chain. If the turn to the new point is a right turn (or straight), the last point makes a dent, "
            "so remove it, and repeat.",
            "That gives the lower half of the boundary. Walk back from east to west the same way for the upper half.",
            "Join the two halves. Every point is added once and removed at most once, so after sorting the scan is "
            "linear.",
        ],
        "code": [
            "ConvexHull(P):",
            "  sort P by x (ties by y)",
            "  lower ← empty chain",
            "  for each p in P, west to east:",
            "    while lower has ≥ 2 points and last two + p turn right:",
            "      remove the last point          ▷ it makes a dent",
            "    add p to lower",
            "  upper ← the same scan, east to west",
            "  return lower + upper (shared ends once)",
        ],
        "cost": "Sorting O(n log n) + scan O(n) = O(n log n)",
    },
    "pair": {
        "words": [
            "Sort the stops by x once.",
            "Divide: cut them into a west half and an east half at the middle x.",
            "Conquer: find the closest pair in each half the same way (three or fewer points are compared directly).",
            "Combine: let δ be the smaller of the two answers. A closer pair can only straddle the cut, so look only at "
            "points within δ of the cut line, in order of y.",
            "Each of those needs comparing only with the next few points above it (at most 7), so combining is linear.",
        ],
        "code": [
            "ClosestPair(P):",
            "  sort P by x once;  return Solve(P)",
            "Solve(P):",
            "  if |P| ≤ 3: compare every pair, return the best",
            "  split P at the middle x into L and R   ▷ divide",
            "  bestL ← Solve(L);  bestR ← Solve(R)      ▷ conquer",
            "  δ ← the smaller of bestL, bestR",
            "  merge L and R by y                    ▷ linear, like merge sort",
            "  S ← points closer than δ to the cut, by y",
            "  for each p in S, check the next points while Δy < δ:",
            "    if closer than δ: δ ← that distance, keep the pair",
            "  return the best pair",
        ],
        "cost": "T(n) = 2T(n/2) + O(n) = O(n log n), against O(n²) for checking every pair",
    },
    "kdbuild": {
        "words": [
            "Sort the stops once by x and once by y.",
            "At the root, cut at the median stop by x (a north-south line). Half the stops go left, half go right.",
            "In each half, cut at the median by y (an east-west line), then by x again, alternating.",
            "Each cut splits both sorted lists in one linear pass, so no level sorts again. The tree is about "
            "log₂ n levels deep.",
        ],
        "code": [
            "Build(P, depth):",
            "  if P is empty: return nothing",
            "  axis ← x if depth is even, else y",
            "  m ← the median point of P on axis      ▷ from the presorted lists",
            "  node ← m",
            "  node.left  ← Build(points before m on axis, depth + 1)",
            "  node.right ← Build(points after m on axis, depth + 1)",
            "  return node",
        ],
        "cost": "Presort O(n log n), then T(n) = 2T(n/2) + O(n) = O(n log n)",
    },
    "kdquery": {
        "words": [
            "Start at the root with the search rectangle.",
            "If the node's stop is inside the rectangle, report it.",
            "The node's line splits the plane. Go into a side only if the rectangle reaches across to that side.",
            "A side the rectangle cannot reach is skipped together with every stop below it. That is where the "
            "speed comes from.",
        ],
        "code": [
            "Search(node, box):",
            "  if node is empty: return",
            "  if node.point is inside box: report it",
            "  v ← node.point's coordinate on node.axis",
            "  if box.low ≤ v:  Search(node.left, box)",
            "  if box.high ≥ v: Search(node.right, box)",
            "  ▷ a side the box cannot reach is skipped, whole subtree",
        ],
        "cost": "O(√n + k) for k stops found, against O(n) for testing every stop",
    },
    "voronoi": {
        "words": [
            "A warehouse's Voronoi cell is every spot closer to it than to any other warehouse.",
            "To find a customer's zone, compare its distance to every warehouse and keep the nearest. That warehouse's "
            "cell is the one the customer lies in.",
            "The cells drawn on the map come from scipy (Qhull) and are clipped to the study area.",
            "In the app the same rule runs on road distance (one Dijkstra per warehouse), so the river and the road "
            "layout are respected. The walkthrough shows the straight-line version.",
        ],
        "code": [
            "Assign(customer c, warehouses W):",
            "  best ← none;  bestDist ← ∞",
            "  for each warehouse w in W:",
            "    d ← distance(c, w)        ▷ by road in the app",
            "    if d < bestDist: best ← w;  bestDist ← d",
            "  return best                 ▷ c lies in best's cell",
            "ServiceZones(W):",
            "  cells ← Voronoi diagram of W   ▷ Qhull, O(m log m)",
            "  clip every cell to the study area",
        ],
        "cost": "O(m) per customer for m warehouses; the diagram itself O(m log m)",
    },
    "cover": {
        "words": [
            "Each warehouse covers the customers it can reach within the chosen distance along the roads.",
            "Round by round, keep the warehouse that covers the most customers not yet covered.",
            "Stop when everyone is covered, or when no warehouse adds anybody new (the rest are out of reach).",
            "Finding the true minimum is NP-hard. Greedy is at most about ln n times the minimum.",
        ],
        "code": [
            "GreedyCover(customers U, sites S, distance r):",
            "  for each site s: cover(s) ← customers within r of s",
            "  covered ← ∅;  chosen ← []",
            "  while covered ≠ U:",
            "    s ← the site with the most customers in cover(s) − covered",
            "    if s adds nobody new: stop",
            "    add s to chosen;  covered ← covered ∪ cover(s)",
            "  return chosen",
        ],
        "cost": "O(rounds · m · n); answer within H(n) ≈ ln n of the optimum",
    },
    "route": {
        "words": [
            "Snap every stop and warehouse to its nearest road point (KD-tree on the road nodes).",
            "Run Dijkstra on the OpenStreetMap road graph from each warehouse and each stop to get the travel time "
            "between every pair. Vans use road bridges only; two-wheelers may also take a ferry.",
            "Each stop adds 3 minutes for the hand-over plus the walk from the road to the door.",
            "Choose the visiting order. Up to 10 stops Held-Karp dynamic programming gives the exact best order. "
            "Above that, start with nearest neighbour and improve it with 2-opt (reverse a stretch whenever that "
            "makes the round shorter).",
            "Try every warehouse that stocks the product and keep the fastest. Draw each leg's road path.",
        ],
        "code": [
            "PlanRoute(product, stops):",
            "  snap stops and warehouses to road nodes      ▷ KD-tree",
            "  T ← Dijkstra times from every warehouse and stop",
            "  for each warehouse w that stocks the product:",
            "    cost[a][b] ← T[a][b] + hand-over + walk at b",
            "    if stops ≤ 10: order ← HeldKarp(cost)        ▷ exact",
            "    else: order ← NearestNeighbour(cost), then 2-opt",
            "  keep the warehouse and order with the least time",
            "HeldKarp(cost):",
            "  best[S][j] ← quickest way from w through set S, ending at j",
            "  best[{j}][j] ← cost[w][j]",
            "  best[S][j] ← min over i in S−{j} of best[S−{j}][i] + cost[i][j]",
            "  answer ← min over j of best[all][j] (+ cost[j][w] to return)",
        ],
        "cost": "Dijkstra O(E log V) per source; Held-Karp O(2ᵏ k²) for k stops; 2-opt O(k²) per pass",
    },
}


def lines_for(key: str, step: dict) -> set[int]:
    """Pseudocode lines (0-based) that a Walkthrough step is executing."""
    if key == "hull":
        return {4, 5} if step.get("action") == "pop" else {6} if step.get("chain") == "lower" else {7}
    if key == "pair":
        return {"base case": {3}, "divide": {4, 5}, "combine": {6, 7}, "strip check": {8, 9, 10}}.get(
            step.get("event"), set())
    if key == "kdbuild":
        return {2, 3, 4}
    if key == "kdquery":
        if step.get("pruned"):
            return {6}
        return {2} if step.get("in_box") else {3, 4, 5}
    if key == "voronoi":
        return {3, 4}
    return set()


def code_card(key: str, accent: str, active: set[int] | None = None, title: str = "Pseudocode") -> None:
    a = ALGOS[key]
    active = active or set()
    rows = []
    for i, line in enumerate(a["code"]):
        text, _, note = line.partition("▷")
        indent = len(text) - len(text.lstrip())
        note_html = f'<em>▷ {esc(note.strip())}</em>' if note else ""
        rows.append(f'<div class="ln{" on" if i in active else ""}"><b>{i + 1}</b>'
                    f'<span style="padding-left:{indent}ch">{esc(text.strip())} {note_html}</span></div>')
    style.block(f'<div class="sdn-code" style="--accent:{accent}"><div class="cap">{esc(title)}'
                f'<span>{esc(a["cost"])}</span></div>{"".join(rows)}</div>')


def words_card(key: str, accent: str, title: str = "The algorithm in words") -> None:
    items = "".join(f"<li>{esc(t)}</li>" for t in ALGOS[key]["words"])
    style.block(f'<div class="sdn-words" style="--accent:{accent}"><div class="cap">{esc(title)}</div>'
                f'<ol>{items}</ol></div>')
