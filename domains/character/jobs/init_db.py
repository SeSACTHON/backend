"""Initialize dedicated schema and tables for the Character service."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from domains.character.core import get_settings
from domains.character.database.base import Base
from domains.character.models import Character  # noqa: F401
from domains.character.models import CharacterOwnership  # noqa: F401


async def init_db() -> int:
    """Drop and recreate the character schema."""
    settings = get_settings()
    drop_schema = settings.schema_reset_enabled
    print(
        "🔗 Connecting to database: "
        f"{settings.database_url.split('@')[1] if '@' in settings.database_url else 'database'}"
    )
    if drop_schema:
        print("⚠️  CHARACTER_SCHEMA_RESET_ENABLED is true → full schema reset allowed.")
    else:
        print("🛡️  Schema reset guard is active → skipping DROP SCHEMA.")

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

    try:
        async with engine.begin() as conn:
            if drop_schema:
                print("♻️  Dropping existing 'character' schema (if present)...")
                await conn.execute(text("DROP SCHEMA IF EXISTS character CASCADE"))
                print("📦 Creating 'character' schema...")
                await conn.execute(text("CREATE SCHEMA character"))
            else:
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS character"))

            print("📦 Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)

        print("✅ Character schema initialized successfully!")
        return 0
    except Exception as exc:  # pragma: no cover - diagnostic output
        print(f"❌ Error initializing character schema: {exc}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await engine.dispose()


def main() -> None:
    """CLI entrypoint."""
    sys.exit(asyncio.run(init_db()))


if __name__ == "__main__":
    main()
