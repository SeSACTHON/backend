"""Value Object Base Class.

Value Object의 특징:
- 불변(Immutable)
- 동등성은 값으로 비교 (ID가 아님)
- 자기 검증(Self-validation)

Reference:
    https://github.com/ivan-borovets/fastapi-clean-example/blob/master/src/app/domain/value_objects/base.py
"""

from __future__ import annotations

from abc import ABC


class ValueObject(ABC):
    """Value Object 베이스 클래스.

    - slots=True: 메모리 효율성
    - frozen=True: 불변성 보장 (dataclass에서 사용)
    - eq=True: 값 기반 동등성 (dataclass에서 사용)

    dataclass로 구현 시:
        @dataclass(frozen=True, slots=True)
        class Email(ValueObject):
            value: str

            def __post_init__(self) -> None:
                self._validate()
    """

    __slots__ = ()

    def __repr__(self) -> str:
        """민감 정보 보호를 위해 오버라이드 권장."""
        return f"{self.__class__.__name__}(...)"
