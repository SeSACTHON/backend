"""Location HTTP Schemas."""

from __future__ import annotations

from pydantic import BaseModel


class LocationEntry(BaseModel):
    """위치 정보 응답 스키마."""

    id: int
    name: str
    source: str
    road_address: str | None
    latitude: float | None
    longitude: float | None
    distance_km: float
    distance_text: str | None
    store_category: str
    pickup_categories: list[str]
    is_holiday: bool | None
    is_open: bool | None
    start_time: str | None
    end_time: str | None
    phone: str | None

    model_config = {"from_attributes": True}
