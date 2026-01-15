"""Image Generator Adapters.

OpenAI Responses API를 사용한 이미지 생성 구현체.

의사결정:
- Responses API의 네이티브 image_generation tool 활용
- 모델이 프롬프트 최적화 후 이미지 생성
- 이미지 + 설명 텍스트 동시 생성 가능
"""

from chat_worker.infrastructure.llm.image_generator.openai_responses import (
    OpenAIResponsesImageGenerator,
)

__all__ = ["OpenAIResponsesImageGenerator"]
