"""ORM Mapper 테스트.

Mapper는 인프라 계층(ORM)과 도메인 계층(Entity)을 연결합니다.
잘못된 매핑은 데이터 손실이나 타입 오류로 이어질 수 있습니다.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from apps.character.domain.entities import Character, CharacterOwnership
from apps.character.domain.enums import CharacterOwnershipStatus
from apps.character.infrastructure.persistence_postgres.mappers import (
    character_model_to_entity,
    ownership_model_to_entity,
)


@pytest.fixture
def character_model() -> MagicMock:
    """CharacterModel mock."""
    model = MagicMock()
    model.id = uuid4()
    model.code = "char-pet"
    model.name = "페트"
    model.description = "페트병 캐릭터"
    model.type_label = "재활용"
    model.dialog = "안녕! 나는 페트야!"
    model.match_label = "무색페트병"
    model.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    model.updated_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
    return model


@pytest.fixture
def ownership_model(character_model: MagicMock) -> MagicMock:
    """CharacterOwnershipModel mock."""
    model = MagicMock()
    model.id = uuid4()
    model.user_id = uuid4()
    model.character_id = character_model.id
    model.character_code = "char-pet"
    model.source = "scan-reward"
    model.status = "owned"
    model.acquired_at = datetime(2024, 1, 15, tzinfo=timezone.utc)
    model.updated_at = datetime(2024, 1, 15, tzinfo=timezone.utc)
    model.character = character_model
    return model


class TestCharacterModelToEntity:
    """character_model_to_entity 테스트.

    검증 포인트:
    1. 모든 필드가 올바르게 매핑되는지
    2. 타입이 올바른지 (UUID, datetime 등)
    3. Optional 필드 처리
    """

    def test_maps_all_required_fields(
        self, character_model: MagicMock
    ) -> None:
        """필수 필드 매핑.

        검증:
        - id, code, name, type_label, dialog가 올바르게 매핑

        이유:
        캐릭터의 핵심 정보가 누락되면 클라이언트에서
        캐릭터를 표시할 수 없습니다.
        """
        entity = character_model_to_entity(character_model)

        assert isinstance(entity, Character)
        assert entity.id == character_model.id
        assert entity.code == "char-pet"
        assert entity.name == "페트"
        assert entity.type_label == "재활용"
        assert entity.dialog == "안녕! 나는 페트야!"

    def test_maps_optional_fields(
        self, character_model: MagicMock
    ) -> None:
        """Optional 필드 매핑.

        검증:
        - description, match_label이 올바르게 매핑

        이유:
        match_label은 캐릭터 매칭에 사용되므로
        정확한 매핑이 필수입니다.
        """
        entity = character_model_to_entity(character_model)

        assert entity.description == "페트병 캐릭터"
        assert entity.match_label == "무색페트병"

    def test_maps_timestamps(
        self, character_model: MagicMock
    ) -> None:
        """타임스탬프 매핑.

        검증:
        - created_at, updated_at이 datetime 타입으로 매핑

        이유:
        타임스탬프는 캐시 무효화, 정렬 등에 사용됩니다.
        """
        entity = character_model_to_entity(character_model)

        assert entity.created_at == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert entity.updated_at == datetime(2024, 6, 1, tzinfo=timezone.utc)

    def test_handles_none_optional_fields(
        self, character_model: MagicMock
    ) -> None:
        """None인 Optional 필드 처리.

        검증:
        - description=None, match_label=None도 정상 처리

        이유:
        일부 캐릭터(예: 기본 캐릭터)는 match_label이 없습니다.
        """
        character_model.description = None
        character_model.match_label = None

        entity = character_model_to_entity(character_model)

        assert entity.description is None
        assert entity.match_label is None


class TestOwnershipModelToEntity:
    """ownership_model_to_entity 테스트.

    검증 포인트:
    1. 모든 필드 매핑
    2. character 관계 매핑
    3. status enum 변환
    """

    def test_maps_all_fields(
        self, ownership_model: MagicMock
    ) -> None:
        """모든 필드 매핑.

        검증:
        - user_id, character_id, character_code, source 등 매핑

        이유:
        소유권 정보는 사용자의 캐릭터 목록 표시에 사용됩니다.
        모든 정보가 정확해야 합니다.
        """
        entity = ownership_model_to_entity(ownership_model)

        assert isinstance(entity, CharacterOwnership)
        assert entity.id == ownership_model.id
        assert entity.user_id == ownership_model.user_id
        assert entity.character_id == ownership_model.character_id
        assert entity.character_code == "char-pet"
        assert entity.source == "scan-reward"

    def test_converts_status_to_enum(
        self, ownership_model: MagicMock
    ) -> None:
        """status 문자열을 Enum으로 변환.

        검증:
        - DB의 "owned" 문자열이 CharacterOwnershipStatus.OWNED로 변환

        이유:
        Enum을 사용하면 유효하지 않은 상태값을 컴파일 타임에 방지합니다.
        """
        entity = ownership_model_to_entity(ownership_model)

        assert entity.status == CharacterOwnershipStatus.OWNED
        assert isinstance(entity.status, CharacterOwnershipStatus)

    def test_maps_character_relationship(
        self, ownership_model: MagicMock
    ) -> None:
        """character 관계 매핑.

        검증:
        - ownership의 character 속성이 Character 엔티티로 매핑

        이유:
        소유권과 캐릭터 정보를 함께 조회하는 경우가 많습니다.
        관계 매핑이 올바라야 N+1 쿼리를 피할 수 있습니다.
        """
        entity = ownership_model_to_entity(ownership_model)

        assert entity.character is not None
        assert isinstance(entity.character, Character)
        assert entity.character.code == "char-pet"
        assert entity.character.name == "페트"

    def test_handles_missing_character_relationship(
        self, ownership_model: MagicMock
    ) -> None:
        """character 관계가 없는 경우.

        검증:
        - model.character가 None이면 entity.character도 None

        이유:
        조인 없이 소유권만 조회하는 경우도 있습니다.
        이때 character는 None입니다.
        """
        ownership_model.character = None

        entity = ownership_model_to_entity(ownership_model)

        assert entity.character is None
        # 다른 필드는 정상
        assert entity.character_id == ownership_model.character_id
        assert entity.character_code == "char-pet"
