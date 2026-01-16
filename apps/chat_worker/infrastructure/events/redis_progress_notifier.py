"""Redis Progress Notifier - ProgressNotifierPort 구현체.

SSE 스트리밍을 위한 Redis Streams 이벤트 발행.
scan_worker와 동일한 shard 기반 패턴 사용.

Event Types:
- stage: 파이프라인 단계 진행 상황 (intent, rag, answer 등)
- token: LLM 응답 토큰 스트리밍 (SSE delta)
- needs_input: 사용자 추가 입력 요청 (Human-in-the-Loop)

아키텍처:
```
chat_worker → Redis Streams (chat:events:{shard})
                    │
                    ▼
             Event Router (XREADGROUP)
                    │
                    ▼
             Redis Pub/Sub (sse:events:{job_id})
                    │
                    ▼
             Chat API (SSE Gateway)
```

Port: application/ports/events/progress_notifier.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any

from chat_worker.application.ports.events.progress_notifier import ProgressNotifierPort

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# 설정 (scan_worker와 동일한 패턴)
# ─────────────────────────────────────────────────────────────────

STREAM_PREFIX = "chat:events"
PUBLISHED_KEY_PREFIX = "chat:published:"
STREAM_MAXLEN = 10000
PUBLISHED_TTL = 7200  # 2시간

# Stage 순서 (단조증가 seq)
# Token은 별도 namespace (1000+)로 분리하여 충돌 방지
#
# Pipeline Flow:
# queued → intent → [vision?] → [subagents...] → aggregate → [feedback?] → answer → done
#
# Subagents (intent에 따라 선택적/병렬 실행):
# - rag, character, location, kakao_place, bulk_waste, weather,
#   recyclable_price, collection_point, web_search, image_generation
STAGE_ORDER = {
    # Core Pipeline
    "queued": 0,
    "intent": 1,
    "vision": 2,  # 이미지 첨부 시
    # Subagents (intent에 따라 선택적/병렬 실행)
    "rag": 3,  # waste intent
    "character": 4,  # greeting 등
    "location": 5,  # location intent (gRPC)
    "kakao_place": 6,  # place_search intent
    "bulk_waste": 7,  # bulk_waste intent
    "weather": 8,  # weather intent
    "recyclable_price": 9,  # price intent
    "collection_point": 10,  # collection_point intent
    "web_search": 11,  # web_search intent
    "image_generation": 12,  # image intent
    # Aggregation & Answer
    "aggregate": 13,  # 서브에이전트 결과 병합
    "feedback": 14,  # 품질 평가
    "answer": 15,  # 최종 답변 생성
    "done": 16,  # 완료
    "needs_input": 17,  # Human-in-the-Loop
}

# Token seq 시작값 (Stage seq와 충돌 방지)
# Stage: 0~179 (18개 stage * 10)
# Token: 1000+
TOKEN_SEQ_START = 1000

# 샤딩 설정 (event_router/config.py와 일치)
DEFAULT_SHARD_COUNT = int(os.environ.get("CHAT_SHARD_COUNT", "4"))


# ─────────────────────────────────────────────────────────────────
# 멱등성 Lua Script (scan_worker와 동일)
# ─────────────────────────────────────────────────────────────────

IDEMPOTENT_XADD_SCRIPT = """
local publish_key = KEYS[1]  -- chat:published:{job_id}:{stage}:{seq}
local stream_key = KEYS[2]   -- chat:events:{shard}

-- 이미 발행했는지 체크
if redis.call('EXISTS', publish_key) == 1 then
    local existing_msg_id = redis.call('GET', publish_key)
    return {0, existing_msg_id}  -- 이미 발행됨
end

-- XADD 실행 (MAXLEN ~ 로 효율적 trim)
local msg_id = redis.call('XADD', stream_key, 'MAXLEN', '~', ARGV[1],
    '*',
    'job_id', ARGV[2],
    'stage', ARGV[3],
    'status', ARGV[4],
    'seq', ARGV[5],
    'ts', ARGV[6],
    'progress', ARGV[7],
    'result', ARGV[8],
    'message', ARGV[9]
)

-- 발행 마킹 (TTL: 2시간)
redis.call('SETEX', publish_key, ARGV[10], msg_id)

return {1, msg_id}  -- 새로 발행됨
"""

# Token 스트리밍용 Script (멱등성 없음 - 순서대로 발행)
TOKEN_XADD_SCRIPT = """
local stream_key = KEYS[1]   -- chat:events:{shard}

local msg_id = redis.call('XADD', stream_key, 'MAXLEN', '~', ARGV[1],
    '*',
    'job_id', ARGV[2],
    'stage', 'token',
    'status', 'streaming',
    'seq', ARGV[3],
    'ts', ARGV[4],
    'content', ARGV[5]
)

return msg_id
"""


def _get_shard_for_job(job_id: str, shard_count: int | None = None) -> int:
    """job_id에 대한 shard 계산.

    scan_worker와 동일한 해시 함수 사용.
    """
    if shard_count is None:
        shard_count = DEFAULT_SHARD_COUNT
    hash_bytes = hashlib.md5(job_id.encode()).digest()[:8]
    hash_int = int.from_bytes(hash_bytes, byteorder="big")
    return hash_int % shard_count


def _get_stream_key(job_id: str, shard_count: int | None = None) -> str:
    """Sharded Stream key 생성."""
    shard = _get_shard_for_job(job_id, shard_count)
    return f"{STREAM_PREFIX}:{shard}"


class RedisProgressNotifier(ProgressNotifierPort):
    """Redis Streams 기반 진행률 알림.

    scan_worker와 동일한 shard 기반 패턴:
    - job_id → hash → shard 번호 결정
    - chat:events:{shard}에 이벤트 발행
    - Event Router가 Consumer Group으로 소비
    """

    def __init__(
        self,
        redis: "Redis",
        shard_count: int | None = None,
        maxlen: int = STREAM_MAXLEN,
    ):
        """초기화.

        Args:
            redis: Redis 클라이언트 (async)
            shard_count: Shard 수 (기본: 4)
            maxlen: 스트림 최대 길이 (오래된 메시지 자동 삭제)
        """
        self._redis = redis
        self._shard_count = shard_count or DEFAULT_SHARD_COUNT
        self._maxlen = maxlen
        self._stage_script = None
        self._token_script = None
        self._token_seq: dict[str, int] = {}  # job_id → token seq counter
        logger.info(
            "RedisProgressNotifier initialized",
            extra={"shards": self._shard_count, "maxlen": maxlen},
        )

    async def _ensure_scripts(self) -> None:
        """Lua Script 등록."""
        if self._stage_script is None:
            self._stage_script = self._redis.register_script(IDEMPOTENT_XADD_SCRIPT)
        if self._token_script is None:
            self._token_script = self._redis.register_script(TOKEN_XADD_SCRIPT)

    async def notify_stage(
        self,
        task_id: str,
        stage: str,
        status: str,
        progress: int | None = None,
        result: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> str:
        """단계 이벤트 발행 (멱등성 보장).

        Args:
            task_id: 작업 ID (job_id)
            stage: 단계명 (intent, rag, character, location, answer, done)
            status: 상태 (started, completed, failed)
            progress: 진행률 0~100 (선택)
            result: 완료 시 결과 데이터 (선택)
            message: UI 표시 메시지 (선택)

        Returns:
            발행된 메시지 ID
        """
        await self._ensure_scripts()

        stream_key = _get_stream_key(task_id, self._shard_count)
        shard = _get_shard_for_job(task_id, self._shard_count)

        # 단조증가 seq 계산
        base_seq = STAGE_ORDER.get(stage, 99) * 10
        seq = base_seq + (1 if status == "completed" else 0)

        # 멱등성 키
        publish_key = f"{PUBLISHED_KEY_PREFIX}{task_id}:{stage}:{seq}"

        # 이벤트 데이터
        ts = str(time.time())
        progress_str = str(progress) if progress is not None else ""
        result_str = json.dumps(result, ensure_ascii=False) if result else ""
        message_str = message or ""

        # Lua Script 실행
        result_tuple = await self._stage_script(
            keys=[publish_key, stream_key],
            args=[
                str(self._maxlen),  # ARGV[1]
                task_id,  # ARGV[2] - job_id
                stage,  # ARGV[3]
                status,  # ARGV[4]
                str(seq),  # ARGV[5]
                ts,  # ARGV[6]
                progress_str,  # ARGV[7]
                result_str,  # ARGV[8]
                message_str,  # ARGV[9]
                str(PUBLISHED_TTL),  # ARGV[10]
            ],
        )

        is_new, msg_id = result_tuple
        if isinstance(msg_id, bytes):
            msg_id = msg_id.decode()

        if is_new:
            logger.debug(
                "stage_event_published",
                extra={
                    "job_id": task_id,
                    "shard": shard,
                    "stage": stage,
                    "status": status,
                    "seq": seq,
                    "msg_id": msg_id,
                },
            )
        else:
            logger.debug(
                "stage_event_duplicate_skipped",
                extra={
                    "job_id": task_id,
                    "shard": shard,
                    "stage": stage,
                    "existing_msg_id": msg_id,
                },
            )

        return msg_id

    async def notify_token(
        self,
        task_id: str,
        content: str,
    ) -> str:
        """토큰 스트리밍 이벤트 발행.

        LLM 응답의 각 토큰을 실시간으로 전달.
        멱등성 없음 (순서대로 모든 토큰 발행).

        Args:
            task_id: 작업 ID (job_id)
            content: 토큰 내용

        Returns:
            발행된 메시지 ID
        """
        await self._ensure_scripts()

        stream_key = _get_stream_key(task_id, self._shard_count)

        # 토큰 seq (job별 카운터)
        # Stage seq (0~79)와 충돌 방지를 위해 1000+부터 시작
        if task_id not in self._token_seq:
            self._token_seq[task_id] = TOKEN_SEQ_START
        self._token_seq[task_id] += 1
        seq = self._token_seq[task_id]

        ts = str(time.time())

        msg_id = await self._token_script(
            keys=[stream_key],
            args=[
                str(self._maxlen),  # ARGV[1]
                task_id,  # ARGV[2] - job_id
                str(seq),  # ARGV[3]
                ts,  # ARGV[4]
                content,  # ARGV[5]
            ],
        )

        if isinstance(msg_id, bytes):
            msg_id = msg_id.decode()

        return msg_id

    async def notify_needs_input(
        self,
        task_id: str,
        input_type: str,
        message: str,
        timeout: int = 60,
    ) -> str:
        """Human-in-the-Loop 입력 요청 이벤트 발행.

        Frontend가 이 이벤트를 수신하면:
        1. 권한 요청 UI 표시
        2. 사용자 입력 수집
        3. POST /chat/{job_id}/input으로 전송

        Args:
            task_id: 작업 ID (job_id)
            input_type: 입력 타입 (location, confirmation, selection)
            message: 사용자에게 표시할 메시지
            timeout: 입력 대기 시간 (초)

        Returns:
            발행된 메시지 ID
        """
        # needs_input은 특별한 stage로 처리
        result = {
            "input_type": input_type,
            "timeout": timeout,
        }

        return await self.notify_stage(
            task_id=task_id,
            stage="needs_input",
            status="waiting",
            message=message,
            result=result,
        )

    def clear_token_counter(self, task_id: str) -> None:
        """토큰 카운터 정리 (작업 완료 시 호출)."""
        if task_id in self._token_seq:
            del self._token_seq[task_id]
