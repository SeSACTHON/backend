"""Image Generator Port - 이미지 생성 추상 인터페이스.

Clean Architecture:
- Application Layer에서 정의하는 추상 Port
- Infrastructure Layer에서 OpenAI Responses API로 구현

의사결정 배경:
- Chat Completions API는 이미지 생성 미지원
- Responses API의 네이티브 image_generation tool 활용
- 기존 LangGraph 파이프라인 구조 유지하면서 서브에이전트로 추가
- 같은 OpenAI API 키로 Chat Completions + Responses API 혼용 가능
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageGenerationResult:
    """이미지 생성 결과 DTO.

    Attributes:
        image_url: 생성된 이미지 URL
        description: 모델이 생성한 이미지 설명 (Responses API)
        revised_prompt: 모델이 수정한 프롬프트 (디버깅용)
    """

    image_url: str
    description: str | None = None
    revised_prompt: str | None = None


class ImageGeneratorPort(ABC):
    """이미지 생성 Port.

    사용자 프롬프트를 기반으로 이미지를 생성합니다.

    구현체:
    - OpenAIResponsesImageGenerator: Responses API 네이티브 tool
    - OpenAIDirectImageGenerator: Images API 직접 호출 (fallback)

    사용 예시:
    ```python
    result = await generator.generate(
        prompt="페트병 분리배출 방법 인포그래픽",
        size="1024x1024",
        quality="medium",
    )
    print(result.image_url)
    print(result.description)
    ```
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "medium",
    ) -> ImageGenerationResult:
        """이미지 생성.

        Args:
            prompt: 생성할 이미지 설명
            size: 이미지 크기 (1024x1024, 1024x1792, 1792x1024)
            quality: 품질 (low, medium, high)

        Returns:
            ImageGenerationResult: 생성 결과

        Raises:
            ImageGenerationError: 생성 실패 시
        """
        pass


class ImageGenerationError(Exception):
    """이미지 생성 실패 예외."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause
