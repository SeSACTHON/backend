"""
Character Cache Warmup Job

배포 시 PostSync Hook으로 실행되어 Worker 로컬 캐시를 워밍업합니다.
DB에서 캐릭터 목록을 조회하여 RabbitMQ fanout exchange로 브로드캐스트합니다.
"""

from __future__ import annotations

import asyncio
import os
import sys


async def warmup_cache() -> None:
    """DB에서 캐릭터 목록 조회 후 캐시 이벤트 발행."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from domains._shared.cache import get_cache_publisher

    db_url = os.getenv("CHARACTER_DATABASE_URL")
    broker_url = os.getenv("CELERY_BROKER_URL")

    if not db_url:
        print("ERROR: CHARACTER_DATABASE_URL not set")
        sys.exit(1)

    if not broker_url:
        print("ERROR: CELERY_BROKER_URL not set")
        sys.exit(1)

    print("Loading characters from DB...")
    engine = create_async_engine(db_url, echo=False)

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT id, code, name, match_label, metadata FROM characters")
            )
            rows = result.fetchall()

        # metadata JSON에서 type, dialog 추출
        characters = []
        for row in rows:
            meta = row[4] or {}
            characters.append(
                {
                    "id": str(row[0]),
                    "code": row[1],
                    "name": row[2],
                    "match_label": row[3],
                    "type_label": meta.get("type", ""),
                    "dialog": meta.get("dialog", ""),
                }
            )

        print(f"Found {len(characters)} characters")
        for c in characters[:3]:
            print(f"  - {c['name']} (match_label: {c['match_label']})")

        # 캐시 refresh 이벤트 발행
        publisher = get_cache_publisher(broker_url)
        publisher.publish_full_refresh(characters)
        print("Cache refresh event published!")

    finally:
        await engine.dispose()


def main() -> None:
    """Entry point."""
    asyncio.run(warmup_cache())


if __name__ == "__main__":
    main()
