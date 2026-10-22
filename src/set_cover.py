"""Greedy set cover: pick candidate warehouse sites to cover all customers.

NP-hard in general; greedy picking the set covering the most uncovered
elements each round gives an H(n) ~ ln(n) approximation ratio.
"""

import math

from .models import Point


def customers_within_radius(site: Point, customers: list[Point], radius: float) -> set[int]:
    return {
        c.id
        for c in customers
        if math.hypot(c.x - site.x, c.y - site.y) <= radius
    }


def greedy_set_cover(
    candidates: list[Point],
    customers: list[Point],
    radius: float,
) -> tuple[list[Point], list[dict]]:
    """Return (chosen_sites, rounds) where rounds logs each pick for display.

    Each round dict: {"site": Point, "new_covered": set[int], "total_covered": int}
    """
    universe = {c.id for c in customers}
    coverage = {cand.id: customers_within_radius(cand, customers, radius) for cand in candidates}

    covered: set[int] = set()
    chosen: list[Point] = []
    rounds: list[dict] = []
    remaining = {cand.id: cand for cand in candidates}

    while covered != universe and remaining:
        best_id = max(remaining, key=lambda cid: len(coverage[cid] - covered))
        new_covered = coverage[best_id] - covered
        if not new_covered:
            break  # no candidate can cover anything new
        covered |= new_covered
        chosen.append(remaining[best_id])
        rounds.append(
            {
                "site": remaining[best_id],
                "new_covered": new_covered,
                "total_covered": len(covered),
            }
        )
        del remaining[best_id]

    return chosen, rounds
