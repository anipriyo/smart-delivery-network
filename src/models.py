"""Core data model shared by every algorithm module."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    """A warehouse or customer.

    The algorithms only ever read ``x`` and ``y`` (kilometres on a flat local
    plane, see ``src/geo.py``). The remaining fields describe the real
    OpenStreetMap place behind the point and are used for display only.
    """

    id: int
    x: float
    y: float
    kind: str  # "warehouse" or "customer"
    name: str = ""
    lat: float | None = None
    lon: float | None = None
    category: str = ""

    def coords(self) -> tuple[float, float]:
        return (self.x, self.y)

    @property
    def label(self) -> str:
        return f"W{self.id}" if self.kind == "warehouse" else f"C{self.id}"
