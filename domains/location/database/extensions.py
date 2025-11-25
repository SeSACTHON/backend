from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

GEOSPATIAL_EXTENSIONS = ("cube", "earthdistance")


async def ensure_geospatial_extensions(engine: AsyncEngine) -> None:
    """
    Ensure Postgres geospatial helpers (cube/earthdistance) exist.

    Location queries rely on ll_to_earth/earth_distance, which are provided by
    these extensions. We run CREATE EXTENSION defensively; Postgres treats the
    command as idempotent when IF NOT EXISTS is included.
    """

    async with engine.begin() as conn:
        for extension in GEOSPATIAL_EXTENSIONS:
            await conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {extension}"))
