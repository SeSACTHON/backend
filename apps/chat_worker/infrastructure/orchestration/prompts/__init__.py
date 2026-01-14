"""Hybrid Prompt System.

ADR 기반 하이브리드 프롬프트 구조:
- Global: 캐릭터 정의 (이코) - 모든 Intent에 공통
- Local: Intent별 지침 (waste/character/location/general)

References:
- docs/plans/chat-worker-prompt-strategy-adr.md
- docs/foundations/24-multi-agent-prompt-patterns.md
"""

from chat_worker.infrastructure.orchestration.prompts.loader import PromptBuilder

__all__ = ["PromptBuilder"]
