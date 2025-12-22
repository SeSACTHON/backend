"""
Character Reward Consumer

Celery Chain 기반 리워드 처리 + Webhook 전송 (Pipeline Step 4)
scan 도메인의 Chain에서 호출됨
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
# Scan Chain용 Reward Task (scan.reward)
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

    캐릭터 리워드 조건을 평가하고 최종 결과를 반환합니다.
    클라이언트는 SSE를 통해 진행상황과 최종 결과를 수신합니다.

    Args:
        prev_result: answer_task의 결과
            - task_id: str
            - user_id: str
            - status: str
            - category: str
            - classification_result: dict
            - disposal_rules: dict | None
            - final_answer: dict
            - metadata: dict

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

    # Reward 평가
    reward = None
    if _should_attempt_reward(classification_result, disposal_rules, final_answer):
        reward = _evaluate_reward_internal(
            task_id=task_id,
            user_id=user_id,
            classification_result=classification_result,
            disposal_rules_present=bool(disposal_rules),
            log_ctx=log_ctx,
        )

    # 최종 결과 구성
    result = {
        **prev_result,
        "reward": reward,
    }

    # 구조화된 로그 출력 (EFK 파이프라인으로 수집)
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
            "has_reward": reward is not None,
            "reward_received": reward.get("received") if reward else None,
        },
    )

    # 결과는 Celery Events의 task-succeeded 이벤트로 SSE에 전달됨
    # Webhook 불필요 - 클라이언트가 SSE로 실시간 수신
    return result


def _should_attempt_reward(
    classification_result: dict[str, Any],
    disposal_rules: dict | None,
    final_answer: dict[str, Any],
) -> bool:
    """리워드 평가 조건 확인.

    동기 로직(scan/services/scan.py)과 동일한 조건:
    1. reward_feature_enabled == True
    2. insufficiencies가 없어야 함
    3. major_category == "재활용폐기물"
    4. disposal_rules가 있어야 함
    """
    import os

    # Feature flag 확인 (환경변수, 기본값 True)
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

    # insufficiencies 체크 (동기 로직과 동일)
    insufficiencies = final_answer.get("insufficiencies", [])
    for entry in insufficiencies:
        if isinstance(entry, str) and entry.strip():
            return False
        elif entry:
            return False

    return True


def _evaluate_reward_internal(
    task_id: str,
    user_id: str,
    classification_result: dict[str, Any],
    disposal_rules_present: bool,
    log_ctx: dict,
) -> dict[str, Any] | None:
    """CharacterService를 통해 리워드 평가."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _evaluate_reward_async(
                    task_id=task_id,
                    user_id=user_id,
                    classification_result=classification_result,
                    disposal_rules_present=disposal_rules_present,
                )
            )
        finally:
            loop.close()

        logger.info(
            "Reward evaluation completed",
            extra={
                **log_ctx,
                "received": result.get("received") if result else False,
                "character_name": result.get("name") if result else None,
            },
        )

        return result

    except Exception:
        logger.exception("Reward evaluation failed", extra=log_ctx)
        return None


async def _evaluate_reward_async(
    task_id: str,
    user_id: str,
    classification_result: dict[str, Any],
    disposal_rules_present: bool,
) -> dict[str, Any]:
    """Async reward processing logic via CharacterService."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from domains.character.core.config import get_settings
    from domains.character.schemas.reward import (
        CharacterRewardRequest,
        CharacterRewardSource,
        ClassificationSummary,
    )
    from domains.character.services.character import CharacterService

    settings = get_settings()

    # DB 세션 생성
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    classification = classification_result.get("classification", {})
    situation_tags = classification_result.get("situation_tags", [])

    async with async_session() as session:
        service = CharacterService.create_for_test(session)

        request = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=UUID(user_id),
            task_id=task_id,
            classification=ClassificationSummary(
                major_category=classification.get("major_category", ""),
                middle_category=classification.get("middle_category", ""),
                minor_category=classification.get("minor_category"),
            ),
            situation_tags=situation_tags,
            disposal_rules_present=disposal_rules_present,
            insufficiencies_present=False,
        )

        response = await service.evaluate_reward(request)

        return {
            "received": response.received,
            "already_owned": response.already_owned,
            "name": response.name,
            "dialog": response.dialog,
            "match_reason": response.match_reason,
            "character_type": response.character_type,
            "type": response.type,
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

    return _evaluate_reward_internal(
        task_id=task_id,
        user_id=user_id,
        classification_result={
            "classification": classification,
            "situation_tags": situation_tags,
        },
        disposal_rules_present=disposal_rules_present,
        log_ctx={"task_id": task_id, "user_id": user_id},
    ) or {"received": False, "reason": "evaluation_failed"}
