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


def greedy_cover(universe: set, sets: dict) -> list[tuple[object, set]]:
    """Plain greedy set cover over named sets.

    Returns the picks in order as (name, newly covered elements). Stops when
    everything is covered or no remaining set adds anything new. Ties go to
    the set listed first.
    """
    covered: set = set()
    remaining = dict(sets)
    picks: list[tuple[object, set]] = []
    while covered != universe and remaining:
        best = max(remaining, key=lambda k: len((remaining[k] & universe) - covered))
        new = (remaining.pop(best) & universe) - covered
        if not new:
            break  # no candidate can cover anything new
        covered |= new
        picks.append((best, new))
    return picks


def greedy_set_cover(
    candidates: list[Point],
    customers: list[Point],
    radius: float,
) -> tuple[list[Point], list[dict]]:
    """Return (chosen_sites, rounds) where rounds logs each pick for display.

    Each candidate covers the customers within ``radius`` (km).
    Each round dict: {"site": Point, "new_covered": set[int], "total_covered": int}
    """
    by_id = {cand.id: cand for cand in candidates}
    coverage = {cand.id: customers_within_radius(cand, customers, radius) for cand in candidates}
    picks = greedy_cover({c.id for c in customers}, coverage)

    chosen: list[Point] = []
    rounds: list[dict] = []
    total = 0
    for site_id, new in picks:
        total += len(new)
        chosen.append(by_id[site_id])
        rounds.append({"site": by_id[site_id], "new_covered": new, "total_covered": total})
    return chosen, rounds
