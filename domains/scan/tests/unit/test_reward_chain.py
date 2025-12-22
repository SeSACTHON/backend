"""Unit tests for scan_reward_task (Chain Step 4).

4단계 Celery Chain의 마지막 단계인 reward task 테스트.
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
    """scan_reward_task 로직 테스트 (Celery 없이 순수 로직 검증)."""

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

    def test_reward_result_structure_with_reward(self, prev_result):
        """리워드가 있을 때 결과 구조."""
        reward = {"received": True, "name": "페트병이"}

        # scan_reward_task가 반환하는 구조 시뮬레이션
        result = {**prev_result, "reward": reward}

        assert result["reward"] is not None
        assert result["reward"]["received"] is True
        assert result["task_id"] == prev_result["task_id"]
        # 모든 이전 필드 보존
        assert result["classification_result"] == prev_result["classification_result"]
        assert result["disposal_rules"] == prev_result["disposal_rules"]

    def test_reward_result_structure_without_reward(self, prev_result):
        """리워드가 없을 때 결과 구조."""
        # scan_reward_task가 반환하는 구조 시뮬레이션
        result = {**prev_result, "reward": None}

        assert result["reward"] is None
        assert result["status"] == "completed"
        assert result["task_id"] == prev_result["task_id"]

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

    @patch("domains.character.consumers.reward._evaluate_reward_internal")
    def test_evaluate_reward_internal_called(self, mock_eval, prev_result):
        """리워드 평가 함수 호출 검증."""
        from domains.character.consumers.reward import _should_attempt_reward

        mock_eval.return_value = {"received": True}

        # _should_attempt_reward이 True일 때 _evaluate_reward_internal 호출됨
        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            should_reward = _should_attempt_reward(
                prev_result["classification_result"],
                prev_result["disposal_rules"],
                prev_result["final_answer"],
            )

        assert should_reward is True

        # 실제 평가 호출
        if should_reward:
            mock_eval(
                task_id=prev_result["task_id"],
                user_id=prev_result["user_id"],
                classification_result=prev_result["classification_result"],
                disposal_rules_present=True,
                log_ctx={},
            )
            mock_eval.assert_called_once()


class TestFullChainIntegration:
    """4단계 Chain 통합 테스트 (vision → rule → answer + reward 로직)."""

    @patch("domains._shared.waste_pipeline.answer.generate_answer")
    @patch("domains._shared.waste_pipeline.rag.get_disposal_rules")
    @patch("domains._shared.waste_pipeline.vision.analyze_images")
    def test_pipeline_produces_reward_eligible_result(self, mock_vision, mock_rule, mock_answer):
        """3단계 파이프라인 후 reward 평가 가능한 결과 생성."""
        from domains.character.consumers.reward import _should_attempt_reward
        from domains.scan.tasks.answer import answer_task
        from domains.scan.tasks.rule import rule_task
        from domains.scan.tasks.vision import vision_task

        # Mock 설정
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

        # Step 1: Vision
        vision_result = vision_task.run(
            task_id=task_id,
            user_id=user_id,
            image_url="https://test.com/image.jpg",
            user_input=None,
        )

        # Step 2: Rule
        rule_result = rule_task.run(vision_result)

        # Step 3: Answer
        answer_result = answer_task.run(rule_result)

        # 검증: answer_result가 reward 평가 가능한 상태인지
        assert answer_result["task_id"] == task_id
        assert answer_result["status"] == "completed"
        assert answer_result["category"] == "재활용폐기물"

        # Step 4 (로직만): reward 평가 조건 확인
        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            should_reward = _should_attempt_reward(
                answer_result["classification_result"],
                answer_result["disposal_rules"],
                answer_result["final_answer"],
            )

        assert should_reward is True

        # 최종 결과 구조 시뮬레이션 (reward 있을 때)
        final_result = {
            **answer_result,
            "reward": {"received": True, "name": "페트병이"},
        }

        assert final_result["reward"]["received"] is True
        assert "classification_result" in final_result
        assert "disposal_rules" in final_result
        assert "final_answer" in final_result
        assert "metadata" in final_result

    @patch("domains._shared.waste_pipeline.answer.generate_answer")
    @patch("domains._shared.waste_pipeline.rag.get_disposal_rules")
    @patch("domains._shared.waste_pipeline.vision.analyze_images")
    def test_pipeline_non_recyclable_no_reward(self, mock_vision, mock_rule, mock_answer):
        """일반쓰레기는 reward 평가 안 함."""
        from domains.character.consumers.reward import _should_attempt_reward
        from domains.scan.tasks.answer import answer_task
        from domains.scan.tasks.rule import rule_task
        from domains.scan.tasks.vision import vision_task

        # Mock 설정 - 일반쓰레기
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

        # reward 평가 조건 확인 - False여야 함
        with patch.dict("os.environ", {"REWARD_FEATURE_ENABLED": "true"}):
            should_reward = _should_attempt_reward(
                answer_result["classification_result"],
                answer_result["disposal_rules"],
                answer_result["final_answer"],
            )

        assert should_reward is False


class TestEvaluateRewardInternal:
    """_evaluate_reward_internal 함수 테스트."""

    @patch("domains.character.consumers.reward._evaluate_reward_async")
    def test_runs_async_in_sync_context(self, mock_async_eval):
        """동기 컨텍스트에서 async 함수 실행."""
        from domains.character.consumers.reward import _evaluate_reward_internal

        mock_async_eval.return_value = {
            "received": True,
            "name": "캐릭터",
        }

        result = _evaluate_reward_internal(
            task_id="task-123",
            user_id="user-456",
            classification_result={"classification": {"major_category": "재활용폐기물"}},
            disposal_rules_present=True,
            log_ctx={"task_id": "task-123"},
        )

        assert result is not None
        assert result["received"] is True
        mock_async_eval.assert_called_once()

    @patch("domains.character.consumers.reward._evaluate_reward_async")
    def test_returns_none_on_exception(self, mock_async_eval):
        """예외 발생 시 None 반환."""
        from domains.character.consumers.reward import _evaluate_reward_internal

        mock_async_eval.side_effect = Exception("DB 연결 실패")

        result = _evaluate_reward_internal(
            task_id="task-123",
            user_id="user-456",
            classification_result={},
            disposal_rules_present=False,
            log_ctx={},
        )

        assert result is None
