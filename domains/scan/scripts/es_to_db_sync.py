#!/usr/bin/env python3
"""
Elasticsearch → PostgreSQL 동기화 스크립트

EFK 파이프라인으로 수집된 scan 로그를 PostgreSQL scan.scan_tasks 테이블로 변환.
CronJob 또는 수동 실행으로 주기적 동기화 가능.

Usage:
    python -m domains.scan.scripts.es_to_db_sync --since 1h
    python -m domains.scan.scripts.es_to_db_sync --since 2024-12-22T00:00:00Z

환경변수:
    ELASTICSEARCH_URL: ES 클러스터 URL (default: http://elasticsearch:9200)
    DATABASE_URL: PostgreSQL 연결 문자열
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# ES 인덱스 패턴 (Fluent Bit 설정에 따라 조정)
ES_INDEX_PATTERN = "fluentbit-scan-*"

# 동기화할 이벤트 타입
SYNC_EVENT_TYPES = ["scan_completed", "scan_failed"]


def parse_time_arg(since: str) -> datetime:
    """시간 인자 파싱 (1h, 2d, ISO8601 등)."""
    if since.endswith("h"):
        hours = int(since[:-1])
        return datetime.now(timezone.utc) - timedelta(hours=hours)
    elif since.endswith("d"):
        days = int(since[:-1])
        return datetime.now(timezone.utc) - timedelta(days=days)
    elif since.endswith("m"):
        minutes = int(since[:-1])
        return datetime.now(timezone.utc) - timedelta(minutes=minutes)
    else:
        return datetime.fromisoformat(since.replace("Z", "+00:00"))


async def fetch_logs_from_es(
    es_url: str,
    index_pattern: str,
    since: datetime,
    event_types: list[str],
) -> list[dict[str, Any]]:
    """Elasticsearch에서 로그 조회."""
    import httpx

    query = {
        "query": {
            "bool": {
                "must": [
                    {"range": {"@timestamp": {"gte": since.isoformat()}}},
                    {"terms": {"labels.event_type": event_types}},
                ]
            }
        },
        "sort": [{"@timestamp": "asc"}],
        "size": 10000,  # 배치 사이즈
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{es_url}/{index_pattern}/_search",
            json=query,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    hits = data.get("hits", {}).get("hits", [])
    return [hit["_source"] for hit in hits]


async def upsert_to_db(logs: list[dict[str, Any]], database_url: str) -> int:
    """로그를 PostgreSQL에 upsert."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.dialects.postgresql import insert

    from domains.scan.models.scan_task import ScanTask
    from domains.scan.schemas.enums import TaskStatus

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    upserted = 0

    async with async_session() as session:
        for log in logs:
            labels = log.get("labels", {})
            task_id = labels.get("task_id")
            if not task_id:
                continue

            try:
                event_type = labels.get("event_type")
                status = (
                    TaskStatus.COMPLETED
                    if event_type == "scan_completed"
                    else TaskStatus.FAILED if event_type == "scan_failed" else TaskStatus.PENDING
                )

                stmt = (
                    insert(ScanTask)
                    .values(
                        id=UUID(task_id),
                        user_id=UUID(labels.get("user_id", "00000000-0000-0000-0000-000000000000")),
                        status=status,
                        category=labels.get("category"),
                        completed_at=datetime.fromisoformat(
                            log["@timestamp"].replace("Z", "+00:00")
                        ),
                        # pipeline_result는 로그에 전체가 없으므로 메타데이터만
                        pipeline_result={
                            "metadata": {
                                "duration_total": labels.get("duration_total_ms"),
                                "duration_vision": labels.get("duration_vision_ms"),
                                "duration_rag": labels.get("duration_rag_ms"),
                                "duration_answer": labels.get("duration_answer_ms"),
                            }
                        },
                    )
                    .on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "status": status,
                            "category": labels.get("category"),
                            "completed_at": datetime.fromisoformat(
                                log["@timestamp"].replace("Z", "+00:00")
                            ),
                            "updated_at": datetime.now(timezone.utc),
                        },
                    )
                )
                await session.execute(stmt)
                upserted += 1

            except Exception as e:
                logger.warning(f"Failed to upsert task {task_id}: {e}")
                continue

        await session.commit()

    await engine.dispose()
    return upserted


async def main():
    parser = argparse.ArgumentParser(description="ES → DB 동기화")
    parser.add_argument("--since", default="1h", help="동기화 시작 시간 (1h, 2d, ISO8601)")
    parser.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 조회만")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    es_url = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")
    database_url = os.environ.get("DATABASE_URL", "")

    if not database_url and not args.dry_run:
        logger.error("DATABASE_URL 환경변수 필요")
        return

    since = parse_time_arg(args.since)
    logger.info(f"Fetching logs since {since.isoformat()}")

    logs = await fetch_logs_from_es(es_url, ES_INDEX_PATTERN, since, SYNC_EVENT_TYPES)
    logger.info(f"Found {len(logs)} logs")

    if args.dry_run:
        for log in logs[:5]:
            labels = log.get("labels", {})
            logger.info(f"  - {labels.get('task_id')}: {labels.get('event_type')}")
        if len(logs) > 5:
            logger.info(f"  ... and {len(logs) - 5} more")
        return

    upserted = await upsert_to_db(logs, database_url)
    logger.info(f"Upserted {upserted} tasks to DB")


if __name__ == "__main__":
    asyncio.run(main())
