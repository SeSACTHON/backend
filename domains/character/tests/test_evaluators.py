"""Tests for Reward Evaluators (Strategy Pattern).

평가 전략 로직의 단위 테스트.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domains.character.schemas.reward import (
    CharacterRewardRequest,
    CharacterRewardSource,
    ClassificationSummary,
)
from domains.character.services.evaluators import (
    EvaluationContext,
    ScanRewardEvaluator,
    get_evaluator,
)

# 상수 정의
RECYCLABLE_WASTE_CATEGORY = "재활용폐기물"
MATCH_REASON_UNDEFINED = "미정의"


class TestScanRewardEvaluatorShouldEvaluate:
    """ScanRewardEvaluator.should_evaluate 테스트."""

    @pytest.fixture
    def evaluator(self):
        return ScanRewardEvaluator()

    @pytest.mark.asyncio
    async def test_returns_true_when_all_conditions_met(self, evaluator):
        """모든 조건 충족 시 True."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=RECYCLABLE_WASTE_CATEGORY,
                middle_category="플라스틱",
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = await evaluator.should_evaluate(payload)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_recyclable(self, evaluator):
        """재활용폐기물이 아닐 때 False."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category="일반폐기물",
                middle_category="음식물",
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = await evaluator.should_evaluate(payload)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_insufficiencies_present(self, evaluator):
        """부족한 정보가 있을 때 False."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=RECYCLABLE_WASTE_CATEGORY,
                middle_category="플라스틱",
            ),
            disposal_rules_present=True,
            insufficiencies_present=True,
        )

        result = await evaluator.should_evaluate(payload)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_disposal_rules(self, evaluator):
        """분리배출 규칙이 없을 때 False."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=RECYCLABLE_WASTE_CATEGORY,
                middle_category="플라스틱",
            ),
            disposal_rules_present=False,
            insufficiencies_present=False,
        )

        result = await evaluator.should_evaluate(payload)
        assert result is False


class TestScanRewardEvaluatorBuildMatchReason:
    """ScanRewardEvaluator.build_match_reason 테스트."""

    @pytest.fixture
    def evaluator(self):
        return ScanRewardEvaluator()

    def test_middle_and_minor(self, evaluator):
        """middle_category와 minor_category가 있을 때."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=RECYCLABLE_WASTE_CATEGORY,
                middle_category="플라스틱",
                minor_category="페트병",
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = evaluator.build_match_reason(payload)
        assert result == "플라스틱>페트병"

    def test_middle_only(self, evaluator):
        """middle_category만 있을 때."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=RECYCLABLE_WASTE_CATEGORY,
                middle_category="유리",
                minor_category=None,
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = evaluator.build_match_reason(payload)
        assert result == "유리"

    def test_major_only(self, evaluator):
        """major_category만 유효할 때."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category="일반폐기물",
                middle_category=" ",  # 공백
                minor_category=None,
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = evaluator.build_match_reason(payload)
        assert result == "일반폐기물"

    def test_all_empty_returns_undefined(self, evaluator):
        """모든 카테고리가 공백일 때."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=" ",
                middle_category=" ",
                minor_category=None,
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = evaluator.build_match_reason(payload)
        assert result == MATCH_REASON_UNDEFINED


class TestScanRewardEvaluatorMatchCharacters:
    """ScanRewardEvaluator.match_characters 테스트."""

    @pytest.fixture
    def evaluator(self):
        return ScanRewardEvaluator()

    @pytest.fixture
    def mock_context(self):
        context = MagicMock(spec=EvaluationContext)
        context.character_repo = MagicMock()
        context.ownership_repo = MagicMock()
        return context

    @pytest.mark.asyncio
    async def test_matches_by_middle_category(self, evaluator, mock_context):
        """middle_category로 캐릭터 매칭."""
        mock_character = MagicMock()
        mock_character.name = "플라봇"
        mock_context.character_repo.list_by_match_label = AsyncMock(return_value=[mock_character])

        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=RECYCLABLE_WASTE_CATEGORY,
                middle_category="플라스틱",
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = await evaluator.match_characters(payload, mock_context)

        assert len(result) == 1
        assert result[0].name == "플라봇"
        mock_context.character_repo.list_by_match_label.assert_called_once_with("플라스틱")

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_match_label(self, evaluator, mock_context):
        """match_label이 없으면 빈 리스트 반환."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=RECYCLABLE_WASTE_CATEGORY,
                middle_category=" ",  # 공백
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = await evaluator.match_characters(payload, mock_context)

        assert result == []
        mock_context.character_repo.list_by_match_label.assert_not_called()


class TestEvaluatorRegistry:
    """Evaluator Registry 테스트."""

    def test_get_scan_evaluator(self):
        """SCAN evaluator 조회."""
        evaluator = get_evaluator(CharacterRewardSource.SCAN)
        assert evaluator is not None
        assert isinstance(evaluator, ScanRewardEvaluator)

    def test_get_unknown_source_returns_none(self):
        """등록되지 않은 소스는 None 반환."""
        # 현재 SCAN만 등록되어 있으므로, 새 enum 값이 추가되면 None 반환
        # 테스트를 위해 mock 사용
        from domains.character.services.evaluators.registry import _evaluators

        # _evaluators는 내부 구현이므로 존재하지 않는 키 테스트
        assert _evaluators.get("nonexistent") is None


class TestEvaluatorEvaluate:
    """Evaluator.evaluate (Template Method) 테스트."""

    @pytest.fixture
    def evaluator(self):
        return ScanRewardEvaluator()

    @pytest.fixture
    def mock_context(self):
        context = MagicMock(spec=EvaluationContext)
        context.character_repo = MagicMock()
        context.ownership_repo = MagicMock()
        return context

    @pytest.mark.asyncio
    async def test_evaluate_returns_should_not_evaluate(self, evaluator, mock_context):
        """조건 미충족 시 should_evaluate=False."""
        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category="일반폐기물",
                middle_category="음식물",
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = await evaluator.evaluate(payload, mock_context)

        assert result.should_evaluate is False
        assert result.matches == []

    @pytest.mark.asyncio
    async def test_evaluate_returns_matches(self, evaluator, mock_context):
        """조건 충족 시 매칭된 캐릭터 반환."""
        mock_character = MagicMock()
        mock_character.name = "플라봇"
        mock_context.character_repo.list_by_match_label = AsyncMock(return_value=[mock_character])

        payload = CharacterRewardRequest(
            source=CharacterRewardSource.SCAN,
            user_id=uuid4(),
            task_id="test-123",
            classification=ClassificationSummary(
                major_category=RECYCLABLE_WASTE_CATEGORY,
                middle_category="플라스틱",
            ),
            disposal_rules_present=True,
            insufficiencies_present=False,
        )

        result = await evaluator.evaluate(payload, mock_context)

        assert result.should_evaluate is True
        assert len(result.matches) == 1
        assert result.match_reason == "플라스틱"
