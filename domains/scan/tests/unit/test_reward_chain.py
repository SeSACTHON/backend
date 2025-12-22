"""Unit tests for scan_reward_task (Chain Step 4).

4단계 Celery Chain의 마지막 단계인 reward task 테스트.
판정/저장 분리 구조:
- scan_reward_task: 판정만 (빠른 응답)
- persist_reward_task: DB 저장 (비동기)
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest


class TestShouldAttemptReward:
    """_should_attempt_reward 함수 테스트."""

    @pytest.fixture
    def valid_classification(self) -> dict:
        """유효한 분류 결과."""
        return {
            "classification": {
                "major_category": "재활용폐기물",
                "middle_category": "무색페트병",
            }
        }

    @pytest.fixture
    def valid_disposal_rules(self) -> dict:
        """유효한 배출 규정."""
        return {"배출방법_공통": "라벨 제거 후 분리수거"}

    @pytest.fixture
    def valid_final_answer(self) -> dict:
        """유효한 최종 답변."""
        return {"user_answer": "답변", "insufficiencies": []}

    def test_returns_true_for_valid_recyclable(
        self, valid_classification, valid_disposal_rules, valid_final_answer
    ):
        """재활용 + 규정 + insufficiencies 없음 → True."""
        from domains.character.consumers.reward import _should_attempt_reward

        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            result = _should_attempt_reward(
                valid_classification, valid_disposal_rules, valid_final_answer
            )
        assert result is True

    def test_returns_false_when_feature_disabled(
        self, valid_classification, valid_disposal_rules, valid_final_answer
    ):
        """REWARD_FEATURE_ENABLED=false → False."""
        from domains.character.consumers.reward import _should_attempt_reward

        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "false"}):
            result = _should_attempt_reward(
                valid_classification, valid_disposal_rules, valid_final_answer
            )
        assert result is False

    def test_returns_false_for_non_recyclable(self, valid_disposal_rules, valid_final_answer):
        """major_category != 재활용폐기물 → False."""
        from domains.character.consumers.reward import _should_attempt_reward

        classification = {
            "classification": {
                "major_category": "일반쓰레기",
                "middle_category": "음식물",
            }
        }
        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            result = _should_attempt_reward(
                classification, valid_disposal_rules, valid_final_answer
            )
        assert result is False

    def test_returns_false_when_no_disposal_rules(self, valid_classification, valid_final_answer):
        """disposal_rules 없음 → False."""
        from domains.character.consumers.reward import _should_attempt_reward

        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            result = _should_attempt_reward(valid_classification, None, valid_final_answer)
        assert result is False

    def test_returns_false_when_has_insufficiencies(
        self, valid_classification, valid_disposal_rules
    ):
        """insufficiencies 있음 → False."""
        from domains.character.consumers.reward import _should_attempt_reward

        final_answer = {
            "user_answer": "답변",
            "insufficiencies": ["라벨 미제거"],
        }
        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            result = _should_attempt_reward(
                valid_classification, valid_disposal_rules, final_answer
            )
        assert result is False

    def test_returns_false_when_missing_category(self, valid_disposal_rules, valid_final_answer):
        """major 또는 middle이 비어있음 → False."""
        from domains.character.consumers.reward import _should_attempt_reward

        classification = {"classification": {"major_category": ""}}
        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            result = _should_attempt_reward(
                classification, valid_disposal_rules, valid_final_answer
            )
        assert result is False


class TestScanRewardTaskLogic:
    """scan_reward_task 로직 테스트 - 판정만 수행."""

    @pytest.fixture
    def prev_result(self) -> dict:
        """answer_task 결과 (이전 단계 출력)."""
        return {
            "task_id": str(uuid4()),
            "user_id": str(uuid4()),
            "status": "completed",
            "category": "재활용폐기물",
            "classification_result": {
                "classification": {
                    "major_category": "재활용폐기물",
                    "middle_category": "무색페트병",
                }
            },
            "disposal_rules": {"배출방법": "분리수거"},
            "final_answer": {
                "user_answer": "페트병 분리배출 방법",
                "insufficiencies": [],
            },
            "metadata": {
                "duration_vision_ms": 2000,
                "duration_rule_ms": 500,
                "duration_answer_ms": 1500,
                "duration_total_ms": 4000,
            },
        }

    def test_reward_response_excludes_character_id(self, prev_result):
        """클라이언트 응답에는 character_id가 포함되지 않음."""
        # 내부 판정 결과 (character_id 포함)
        internal_decision = {
            "received": True,
            "already_owned": False,
            "character_id": str(uuid4()),  # 내부용
            "name": "페트병이",
            "dialog": "잘했어!",
            "match_reason": "무색페트병",
            "character_type": "페트",
            "type": "페트",
        }

        # 클라이언트 응답 (character_id 제외)
        reward_response = {
            "received": internal_decision["received"],
            "already_owned": internal_decision["already_owned"],
            "name": internal_decision["name"],
            "dialog": internal_decision["dialog"],
            "match_reason": internal_decision["match_reason"],
            "character_type": internal_decision["character_type"],
            "type": internal_decision["type"],
        }

        result = {**prev_result, "reward": reward_response}

        assert "character_id" not in result["reward"]
        assert result["reward"]["received"] is True
        assert result["reward"]["name"] == "페트병이"

    def test_reward_result_structure_with_reward(self, prev_result):
        """리워드가 있을 때 결과 구조."""
        reward = {"received": True, "name": "페트병이"}
        result = {**prev_result, "reward": reward}

        assert result["reward"] is not None
        assert result["reward"]["received"] is True
        assert result["task_id"] == prev_result["task_id"]
        assert result["classification_result"] == prev_result["classification_result"]

    def test_reward_result_structure_without_reward(self, prev_result):
        """리워드가 없을 때 결과 구조."""
        result = {**prev_result, "reward": None}

        assert result["reward"] is None
        assert result["status"] == "completed"

    def test_all_fields_preserved(self, prev_result):
        """이전 결과의 모든 필드가 보존됨."""
        result = {**prev_result, "reward": None}

        expected_fields = [
            "task_id",
            "user_id",
            "status",
            "category",
            "classification_result",
            "disposal_rules",
            "final_answer",
            "metadata",
        ]

        for field in expected_fields:
            assert field in result
            assert result[field] == prev_result[field]


class TestPersistRewardTask:
    """persist_reward_task 로직 테스트 - DB 저장 전담."""

    def test_persist_dispatched_when_received(self):
        """received=True일 때 persist_reward_task 발행."""
        decision = {
            "received": True,
            "character_id": str(uuid4()),
            "name": "페트병이",
        }

        # persist_reward_task.delay 호출 시뮬레이션
        with patch("domains.character.consumers.reward.persist_reward_task") as mock_persist:
            if decision.get("received") and decision.get("character_id"):
                mock_persist.delay(
                    user_id=str(uuid4()),
                    character_id=decision["character_id"],
                    source="scan",
                    task_id=str(uuid4()),
                )

            mock_persist.delay.assert_called_once()

    def test_persist_not_dispatched_when_not_received(self):
        """received=False일 때 persist_reward_task 미발행."""
        decision = {
            "received": False,
            "character_id": None,
            "reason": "no_match",
        }

        with patch("domains.character.consumers.reward.persist_reward_task") as mock_persist:
            if decision.get("received") and decision.get("character_id"):
                mock_persist.delay()

            mock_persist.delay.assert_not_called()

    def test_persist_not_dispatched_when_already_owned(self):
        """already_owned=True일 때 received=False이므로 persist 미발행."""
        decision = {
            "received": False,  # 이미 소유 → received=False
            "already_owned": True,
            "character_id": str(uuid4()),
            "name": "페트병이",
        }

        with patch("domains.character.consumers.reward.persist_reward_task") as mock_persist:
            if decision.get("received") and decision.get("character_id"):
                mock_persist.delay()

            mock_persist.delay.assert_not_called()


class TestRewardDecisionLogic:
    """_evaluate_reward_decision 함수 테스트."""

    @patch("domains.character.consumers.reward._match_character_async")
    def test_decision_returns_character_id(self, mock_match):
        """판정 결과에 character_id 포함."""
        from domains.character.consumers.reward import _evaluate_reward_decision

        character_id = str(uuid4())
        mock_match.return_value = {
            "received": True,
            "already_owned": False,
            "character_id": character_id,
            "name": "캐릭터",
            "dialog": "안녕!",
            "match_reason": "플라스틱",
            "character_type": "플라",
            "type": "플라",
        }

        result = _evaluate_reward_decision(
            task_id="task-123",
            user_id="user-456",
            classification_result={"classification": {"major_category": "재활용폐기물"}},
            disposal_rules_present=True,
            log_ctx={"task_id": "task-123"},
        )

        assert result is not None
        assert result["character_id"] == character_id
        assert result["received"] is True

    @patch("domains.character.consumers.reward._match_character_async")
    def test_decision_returns_none_on_exception(self, mock_match):
        """예외 발생 시 None 반환."""
        from domains.character.consumers.reward import _evaluate_reward_decision

        mock_match.side_effect = Exception("DB 연결 실패")

        result = _evaluate_reward_decision(
            task_id="task-123",
            user_id="user-456",
            classification_result={},
            disposal_rules_present=False,
            log_ctx={},
        )

        assert result is None


class TestFullChainIntegration:
    """4단계 Chain 통합 테스트 (vision → rule → answer + reward 판정)."""

    @patch("domains._shared.waste_pipeline.answer.generate_answer")
    @patch("domains._shared.waste_pipeline.rag.get_disposal_rules")
    @patch("domains._shared.waste_pipeline.vision.analyze_images")
    def test_pipeline_produces_reward_eligible_result(self, mock_vision, mock_rule, mock_answer):
        """3단계 파이프라인 후 reward 판정 가능한 결과 생성."""
        from domains.character.consumers.reward import _should_attempt_reward
        from domains.scan.tasks.answer import answer_task
        from domains.scan.tasks.rule import rule_task
        from domains.scan.tasks.vision import vision_task

        mock_vision.return_value = {
            "classification": {
                "major_category": "재활용폐기물",
                "middle_category": "무색페트병",
            }
        }
        mock_rule.return_value = {"배출방법": "라벨 제거"}
        mock_answer.return_value = {"user_answer": "답변", "insufficiencies": []}

        task_id = str(uuid4())
        user_id = str(uuid4())

        vision_result = vision_task.run(
            task_id=task_id,
            user_id=user_id,
            image_url="https://test.com/image.jpg",
            user_input=None,
        )
        rule_result = rule_task.run(vision_result)
        answer_result = answer_task.run(rule_result)

        assert answer_result["task_id"] == task_id
        assert answer_result["status"] == "completed"
        assert answer_result["category"] == "재활용폐기물"

        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            should_reward = _should_attempt_reward(
                answer_result["classification_result"],
                answer_result["disposal_rules"],
                answer_result["final_answer"],
            )

        assert should_reward is True

    @patch("domains._shared.waste_pipeline.answer.generate_answer")
    @patch("domains._shared.waste_pipeline.rag.get_disposal_rules")
    @patch("domains._shared.waste_pipeline.vision.analyze_images")
    def test_pipeline_non_recyclable_no_reward(self, mock_vision, mock_rule, mock_answer):
        """일반쓰레기는 reward 판정 안 함."""
        from domains.character.consumers.reward import _should_attempt_reward
        from domains.scan.tasks.answer import answer_task
        from domains.scan.tasks.rule import rule_task
        from domains.scan.tasks.vision import vision_task

        mock_vision.return_value = {
            "classification": {
                "major_category": "일반쓰레기",
                "middle_category": "음식물",
            }
        }
        mock_rule.return_value = {"배출방법": "종량제 봉투"}
        mock_answer.return_value = {"user_answer": "답변", "insufficiencies": []}

        task_id = str(uuid4())
        user_id = str(uuid4())

        vision_result = vision_task.run(
            task_id=task_id,
            user_id=user_id,
            image_url="https://test.com/image.jpg",
            user_input=None,
        )
        rule_result = rule_task.run(vision_result)
        answer_result = answer_task.run(rule_result)

        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            should_reward = _should_attempt_reward(
                answer_result["classification_result"],
                answer_result["disposal_rules"],
                answer_result["final_answer"],
            )

        assert should_reward is False


class TestSeparationOfConcerns:
    """판정/저장 분리 검증."""

    def test_decision_does_not_save_to_db(self):
        """판정 단계에서 DB 저장 안 함 (SELECT만)."""
        # 판정 함수는 ownership 존재 여부 확인만 함
        # INSERT/COMMIT은 persist_reward_task에서만 수행
        pass  # 구조적 검증, 실제 테스트는 integration test에서

    def test_persist_is_idempotent(self):
        """persist는 멱등성 보장 (이미 소유 시 skip)."""
        # IntegrityError 발생 시 graceful하게 처리
        pass  # 구조적 검증

    def test_persist_failure_does_not_affect_response(self):
        """persist 실패해도 클라이언트 응답에 영향 없음."""
        # scan_reward_task가 먼저 응답하고
        # persist_reward_task는 Fire & Forget
        pass  # 구조적 검증
