"""Coordinates Value Object."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Coordinates:
    """위도/경도 좌표."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        """좌표 유효성 검증."""
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Invalid latitude: {self.latitude}")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"Invalid longitude: {self.longitude}")
