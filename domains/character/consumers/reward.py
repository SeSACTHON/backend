"""
Character Reward Consumer

Celery Chain 기반 리워드 처리 (Pipeline Step 4)
- scan_reward_task: 보상 판정만 (빠른 응답)
- persist_reward_task: DB 저장 (비동기, Fire & Forget)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from celery import Celery

from domains._shared.celery.base_task import BaseTask
from domains._shared.celery.config import get_celery_settings

logger = logging.getLogger(__name__)

# Character domain Celery app
settings = get_celery_settings()
celery_app = Celery("character")
celery_app.config_from_object(settings.get_celery_config())


# ============================================================
# Scan Chain용 Reward Task (scan.reward) - 판정만
# ============================================================


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="scan.reward",
    queue="reward.character",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
def scan_reward_task(
    self: BaseTask,
    prev_result: dict[str, Any],
) -> dict[str, Any]:
    """Step 4: Reward Evaluation (Chain 마지막 단계).

    보상 **판정만** 수행하고 즉시 클라이언트에게 응답합니다.
    DB 저장은 별도 task(persist_reward_task)에서 비동기로 처리됩니다.

    Flow:
        1. 조건 검증 (_should_attempt_reward)
        2. 캐릭터 매칭 (DB 조회만, 저장 X)
        3. 즉시 응답 (SSE로 클라이언트에게 전달)
        4. persist_reward_task 발행 (Fire & Forget)

    Args:
        prev_result: answer_task의 결과

    Returns:
        최종 결과 (reward 포함) - Celery Events로 SSE에 전달됨
    """
    task_id = prev_result.get("task_id")
    user_id = prev_result.get("user_id")
    classification_result = prev_result.get("classification_result", {})
    disposal_rules = prev_result.get("disposal_rules")
    final_answer = prev_result.get("final_answer", {})
    metadata = prev_result.get("metadata", {})
    category = prev_result.get("category")

    log_ctx = {
        "task_id": task_id,
        "user_id": user_id,
        "celery_task_id": self.request.id,
        "stage": "reward",
    }
    logger.info("Scan reward task started", extra=log_ctx)

    # 1. 조건 확인
    reward = None
    if _should_attempt_reward(classification_result, disposal_rules, final_answer):
        # 2. 판정만 수행 (DB 저장 X)
        reward = _evaluate_reward_decision(
            task_id=task_id,
            user_id=user_id,
            classification_result=classification_result,
            disposal_rules_present=bool(disposal_rules),
            log_ctx=log_ctx,
        )

        # 3. DB 저장은 별도 task로 발행 (Fire & Forget)
        if reward and reward.get("received") and reward.get("character_id"):
            try:
                persist_reward_task.delay(
                    user_id=user_id,
                    character_id=reward["character_id"],
                    source="scan",
                    task_id=task_id,
                )
                logger.info(
                    "Persist reward task dispatched",
                    extra={**log_ctx, "character_id": reward["character_id"]},
                )
            except Exception:
                # 발행 실패해도 판정 결과는 반환 (eventual consistency)
                logger.exception("Failed to dispatch persist_reward_task", extra=log_ctx)

    # 4. 최종 결과 구성 (character_id는 내부용이므로 제거)
    reward_response = None
    if reward:
        reward_response = {
            "received": reward.get("received", False),
            "already_owned": reward.get("already_owned", False),
            "name": reward.get("name"),
            "dialog": reward.get("dialog"),
            "match_reason": reward.get("match_reason"),
            "character_type": reward.get("character_type"),
            "type": reward.get("type"),
        }

    result = {
        **prev_result,
        "reward": reward_response,
    }

    # 구조화된 로그
    logger.info(
        "scan_task_completed",
        extra={
            "event_type": "scan_completed",
            "task_id": task_id,
            "user_id": user_id,
            "category": category,
            "duration_total_ms": metadata.get("duration_total_ms"),
            "duration_vision_ms": metadata.get("duration_vision_ms"),
            "duration_rule_ms": metadata.get("duration_rule_ms"),
            "duration_answer_ms": metadata.get("duration_answer_ms"),
            "has_disposal_rules": disposal_rules is not None,
            "has_reward": reward_response is not None,
            "reward_received": reward_response.get("received") if reward_response else None,
        },
    )

    return result


# ============================================================
# Persist Reward Task - DB 저장 전담
# ============================================================


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="character.persist_reward",
    queue="reward.persist",
    max_retries=5,
    soft_time_limit=30,
    time_limit=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def persist_reward_task(
    self: BaseTask,
    user_id: str,
    character_id: str,
    source: str,
    task_id: str | None = None,
) -> dict[str, Any]:
    """보상 DB 저장 (Fire & Forget).

    scan_reward_task에서 판정 완료 후 발행됩니다.
    클라이언트 응답과 무관하게 비동기로 실행됩니다.

    처리 내용:
        1. character_ownerships 테이블에 소유권 저장
        2. my 도메인에 sync_to_my_task 발행

    Idempotency:
        - 이미 소유한 캐릭터는 skip (IntegrityError 무시)
        - 재시도해도 안전함
    """
    log_ctx = {
        "task_id": task_id,
        "user_id": user_id,
        "character_id": character_id,
        "source": source,
        "celery_task_id": self.request.id,
    }
    logger.info("Persist reward task started", extra=log_ctx)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _persist_reward_async(
                    user_id=user_id,
                    character_id=character_id,
                    source=source,
                )
            )
        finally:
            loop.close()

        logger.info(
            "Persist reward completed",
            extra={**log_ctx, "persisted": result.get("persisted", False)},
        )
        return result

    except Exception:
        logger.exception("Persist reward failed", extra=log_ctx)
        raise  # Celery가 재시도


async def _persist_reward_async(
    user_id: str,
    character_id: str,
    source: str,
) -> dict[str, Any]:
    """DB 저장 + my 도메인 동기화."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from domains.character.core.config import get_settings
    from domains.character.repositories.character import CharacterRepository
    from domains.character.repositories.ownership import OwnershipRepository

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        character_repo = CharacterRepository(session)
        ownership_repo = OwnershipRepository(session)

        # 캐릭터 조회
        character = await character_repo.get_by_id(UUID(character_id))
        if not character:
            return {"persisted": False, "reason": "character_not_found"}

        # 이미 소유 여부 확인
        existing = await ownership_repo.get_by_user_and_character(
            user_id=UUID(user_id), character_id=UUID(character_id)
        )
        if existing:
            # 이미 소유 → my 동기화만 재시도 (idempotent)
            _dispatch_sync_to_my(
                user_id=user_id,
                character=character,
                source=source,
            )
            return {"persisted": False, "reason": "already_owned"}

        # 소유권 저장
        try:
            await ownership_repo.insert_owned(
                user_id=UUID(user_id),
                character=character,
                source=source,
            )
            await session.commit()
        except IntegrityError:
            # Race condition: 동시 요청으로 인한 중복 INSERT
            await session.rollback()
            return {"persisted": False, "reason": "concurrent_insert"}

        # my 도메인 동기화
        _dispatch_sync_to_my(
            user_id=user_id,
            character=character,
            source=source,
        )

        return {"persisted": True}


def _dispatch_sync_to_my(user_id: str, character: Any, source: str) -> None:
    """my 도메인 동기화 task 발행."""
    from domains.character.consumers.sync_my import sync_to_my_task

    try:
        sync_to_my_task.delay(
            user_id=user_id,
            character_id=str(character.id),
            character_code=character.code,
            character_name=character.name,
            character_type=character.type_label,
            character_dialog=character.dialog,
            source=source,
        )
    except Exception:
        logger.exception(
            "Failed to dispatch sync_to_my_task",
            extra={"user_id": user_id, "character_id": str(character.id)},
        )


# ============================================================
# 판정 로직 (DB 저장 없음)
# ============================================================


def _should_attempt_reward(
    classification_result: dict[str, Any],
    disposal_rules: dict | None,
    final_answer: dict[str, Any],
) -> bool:
    """리워드 평가 조건 확인."""
    import os

    reward_enabled = os.getenv("REWARD_FEATURE_ENABLED", "true").lower() == "true"
    if not reward_enabled:
        return False

    classification = classification_result.get("classification", {})
    major = classification.get("major_category", "").strip()
    middle = classification.get("middle_category", "").strip()

    if not major or not middle:
        return False

    if major != "재활용폐기물":
        return False

    if not disposal_rules:
        return False

    insufficiencies = final_answer.get("insufficiencies", [])
    for entry in insufficiencies:
        if isinstance(entry, str) and entry.strip():
            return False
        elif entry:
            return False

    return True


def _evaluate_reward_decision(
    task_id: str,
    user_id: str,
    classification_result: dict[str, Any],
    disposal_rules_present: bool,
    log_ctx: dict,
) -> dict[str, Any] | None:
    """캐릭터 매칭 판정 (DB 저장 없음)."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _match_character_async(
                    user_id=user_id,
                    classification_result=classification_result,
                    disposal_rules_present=disposal_rules_present,
                )
            )
        finally:
            loop.close()

        logger.info(
            "Reward decision completed",
            extra={
                **log_ctx,
                "received": result.get("received") if result else False,
                "character_name": result.get("name") if result else None,
            },
        )
        return result

    except Exception:
        logger.exception("Reward decision failed", extra=log_ctx)
        return None


async def _match_character_async(
    user_id: str,
    classification_result: dict[str, Any],
    disposal_rules_present: bool,
) -> dict[str, Any]:
    """캐릭터 매칭만 수행 (DB 저장 없음).

    Returns:
        {
            "received": bool,
            "already_owned": bool,
            "character_id": str | None,  # persist_reward_task에서 사용
            "name": str | None,
            "dialog": str | None,
            ...
        }
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from domains.character.core.config import get_settings
    from domains.character.repositories.character import CharacterRepository
    from domains.character.repositories.ownership import OwnershipRepository
    from domains.character.services.evaluators import get_evaluator
    from domains.character.schemas.reward import (
        CharacterRewardRequest,
        CharacterRewardSource,
        ClassificationSummary,
    )

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    classification = classification_result.get("classification", {})
    situation_tags = classification_result.get("situation_tags", [])

    async with async_session() as session:
        character_repo = CharacterRepository(session)
        ownership_repo = OwnershipRepository(session)

        # Evaluator 조회
        evaluator = get_evaluator(CharacterRewardSource.SCAN)
        if evaluator is None:
            return {"received": False, "reason": "no_evaluator"}

        # 캐릭터 목록 조회
        characters = await character_repo.list_all()
        if not characters:
            return {"received": False, "reason": "no_characters"}

        # 평가 요청 생성
        request = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=UUID(user_id),
            task_id="",  # 판정에는 불필요
            classification=ClassificationSummary(
                major_category=classification.get("major_category", ""),
                middle_category=classification.get("middle_category", ""),
                minor_category=classification.get("minor_category"),
            ),
            situation_tags=situation_tags,
            disposal_rules_present=disposal_rules_present,
            insufficiencies_present=False,
        )

        # 평가 실행
        eval_result = evaluator.evaluate(request, characters)

        if not eval_result.should_evaluate or not eval_result.matches:
            return {"received": False, "reason": "no_match"}

        # 첫 번째 매칭 캐릭터
        matched_character = eval_result.matches[0]

        # 이미 소유 여부 확인
        existing = await ownership_repo.get_by_user_and_character(
            user_id=UUID(user_id), character_id=matched_character.id
        )

        return {
            "received": not existing,  # 소유하지 않은 경우만 received=True
            "already_owned": existing is not None,
            "character_id": str(matched_character.id),  # persist_reward_task에서 사용
            "name": matched_character.name,
            "dialog": matched_character.dialog,
            "match_reason": eval_result.match_reason,
            "character_type": matched_character.type_label,
            "type": str(matched_character.type_label or "").strip(),
        }


# ============================================================
# Legacy Task (하위 호환성)
# ============================================================


@celery_app.task(
    bind=True,
    name="character.reward.process",
    queue="reward.character",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
def reward_consumer_task(
    self,
    task_id: str,
    user_id: str,
    classification: dict[str, Any],
    situation_tags: list[str],
    disposal_rules_present: bool,
) -> dict[str, Any]:
    """Legacy: Fire & Forget 방식의 reward task.

    DEPRECATED: Chain 방식으로 전환됨.
    기존 메시지 호환성을 위해 유지.
    """
    logger.warning(
        "Legacy reward consumer task called",
        extra={"task_id": task_id, "user_id": user_id},
    )

    result = _evaluate_reward_decision(
        task_id=task_id,
        user_id=user_id,
        classification_result={
            "classification": classification,
            "situation_tags": situation_tags,
        },
        disposal_rules_present=disposal_rules_present,
        log_ctx={"task_id": task_id, "user_id": user_id},
    )

    if result and result.get("received") and result.get("character_id"):
        persist_reward_task.delay(
            user_id=user_id,
            character_id=result["character_id"],
            source="scan",
            task_id=task_id,
        )

    return result or {"received": False, "reason": "evaluation_failed"}
