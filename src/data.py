"""Point-set generation: reproducible random data and a fixed demo set."""

import random

from .models import Point


def generate_random(
    n_warehouses: int = 5,
    n_customers: int = 40,
    width: float = 100.0,
    height: float = 100.0,
    seed: int = 42,
) -> tuple[list[Point], list[Point]]:
    rng = random.Random(seed)
    warehouses = [
        Point(id=i, x=round(rng.uniform(0, width), 2), y=round(rng.uniform(0, height), 2), kind="warehouse")
        for i in range(n_warehouses)
    ]
    customers = [
        Point(
            id=n_warehouses + i,
            x=round(rng.uniform(0, width), 2),
            y=round(rng.uniform(0, height), 2),
            kind="customer",
        )
        for i in range(n_customers)
    ]
    return warehouses, customers


def demo_set() -> tuple[list[Point], list[Point]]:
    """A fixed, hand-picked 5 warehouse / 30 customer layout with a clear
    hull, visibly separated Voronoi regions, and an obvious closest pair --
    good for screenshots and live demos where randomness is unwelcome.
    """
    warehouses = [
        Point(0, 20, 80, "warehouse"),
        Point(1, 75, 85, "warehouse"),
        Point(2, 50, 50, "warehouse"),
        Point(3, 15, 20, "warehouse"),
        Point(4, 85, 20, "warehouse"),
    ]
    customer_coords = [
        (5, 90), (12, 75), (18, 95), (25, 88), (8, 60),
        (65, 95), (72, 78), (80, 92), (88, 82), (60, 70),
        (45, 60), (50, 45), (55, 55), (40, 48), (48, 38),
        (10, 25), (18, 10), (25, 30), (5, 15), (22, 18),
        (78, 15), (90, 25), (82, 5), (95, 18), (70, 10),
        (35, 75), (60, 25), (30, 55), (65, 45), (40, 15),
    ]
    customers = [
        Point(id=5 + i, x=float(x), y=float(y), kind="customer")
        for i, (x, y) in enumerate(customer_coords)
    ]
    return warehouses, customers
