"""Core data model shared by every algorithm module."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    id: int
    x: float
    y: float
    kind: str  # "warehouse" or "customer"

    def coords(self) -> tuple[float, float]:
        return (self.x, self.y)
