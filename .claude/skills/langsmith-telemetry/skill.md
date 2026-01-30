---
name: langsmith-telemetry
description: LangSmith 통합 및 LLM Observability 가이드. 토큰 추적, 비용 계산, Run Tree, Tracing 데코레이터, OTEL 연동 구현 시 참조. "langsmith", "tracing", "observability", "token usage", "cost tracking" 키워드로 트리거.
---

# LangSmith Telemetry Guide

## 개요

LangSmith는 LangChain/LangGraph 애플리케이션의 Observability 플랫폼.
LLM 호출, 토큰 사용량, 비용, 레이턴시를 추적.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LangSmith Observability Stack                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Application                                   │   │
│  │  - LangGraph Pipeline                                             │   │
│  │  - LLM Clients (OpenAI, Gemini)                                   │   │
│  │  - Tool Executions                                                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                    @traceable decorators                                │
│                    RunTree context                                      │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    LangSmith API                                   │   │
│  │  - Run traces                                                      │   │
│  │  - Token counts                                                    │   │
│  │  - Latency metrics                                                 │   │
│  │  - Cost estimates                                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    LangSmith Dashboard                             │   │
│  │  - Trace visualization                                            │   │
│  │  - Token usage graphs                                             │   │
│  │  - Cost analysis                                                   │   │
│  │  - Error tracking                                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 환경 변수

```bash
# LangSmith 활성화 (필수)
LANGCHAIN_TRACING_V2=true

# API Key (필수)
LANGCHAIN_API_KEY=ls-xxxxx

# 프로젝트명
LANGCHAIN_PROJECT=eco2-chat-worker

# Endpoint (기본값 사용 권장)
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# OTEL 연동 (선택)
LANGSMITH_OTEL_ENABLED=true
```

## 설치

```bash
pip install langsmith langchain-core
```

## 설정 확인 유틸리티

```python
# apps/chat_worker/infrastructure/telemetry/langsmith.py

import os

LANGSMITH_ENABLED: bool = os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
LANGSMITH_API_KEY: str | None = os.environ.get("LANGCHAIN_API_KEY")
LANGSMITH_PROJECT: str = os.environ.get("LANGCHAIN_PROJECT", "eco2-chat-worker")


def is_langsmith_enabled() -> bool:
    """LangSmith 활성화 여부 확인."""
    return LANGSMITH_ENABLED and bool(LANGSMITH_API_KEY)


def get_langsmith_config() -> dict:
    """LangSmith 설정 반환."""
    return {
        "enabled": is_langsmith_enabled(),
        "project": LANGSMITH_PROJECT,
        "endpoint": os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
    }
```

## 모델 가격표 (2025)

```python
# 토큰당 가격 (USD per 1M tokens)
MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-5.2": {"input": 1.75, "output": 14.00},
    "gpt-5.2-codex": {"input": 2.00, "output": 16.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o1": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 3.00, "output": 12.00},

    # Gemini
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},

    # Anthropic
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
}

# 이미지 생성 가격
IMAGE_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-3-pro-image-preview": {"1k": 0.134, "4k": 0.24, "default": 0.134},
    "gpt-image-1.5": {"1024x1024": 0.04, "1024x1792": 0.08, "default": 0.04},
    "dall-e-3": {"1024x1024": 0.04, "1024x1792": 0.08, "default": 0.04},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """토큰 사용량 기반 비용 계산."""
    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def calculate_image_cost(model: str, resolution: str = "default") -> float:
    """이미지 생성 비용 계산."""
    pricing = IMAGE_MODEL_PRICING.get(model, {})
    return pricing.get(resolution, pricing.get("default", 0))
```

## Tracing 데코레이터

### @traceable 기본 사용

```python
from langsmith import traceable


@traceable(name="classify_intent")
async def classify_intent(message: str) -> dict:
    """의도 분류 (자동 추적)."""
    response = await llm.generate_structured(
        prompt=message,
        response_schema=IntentClassification,
    )
    return response.model_dump()
```

### 커스텀 메타데이터 추가

```python
@traceable(
    name="answer_generation",
    metadata={"feature": "chat", "version": "2.0"},
    tags=["production", "chat"],
)
async def generate_answer(context: dict, question: str) -> str:
    """답변 생성."""
    ...
```

### LLM 호출 추적

```python
from functools import wraps
from langsmith import traceable
from langsmith.run_trees import RunTree


def traceable_llm(model: str):
    """LLM 호출 전용 데코레이터.

    토큰 사용량과 비용을 자동 추적.
    """
    def decorator(func):
        @wraps(func)
        @traceable(name=f"llm:{model}", run_type="llm")
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # RunTree에 메트릭 추가
            run_tree = RunTree.get_current_run_tree()
            if run_tree and hasattr(result, "usage"):
                usage = result.usage
                track_token_usage(
                    run_tree,
                    model=model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                )

            return result
        return wrapper
    return decorator


def track_token_usage(
    run_tree: RunTree,
    model: str,
    input_tokens: int,
    output_tokens: int,
):
    """토큰 사용량을 RunTree에 기록."""
    cost = calculate_cost(model, input_tokens, output_tokens)

    run_tree.extra = run_tree.extra or {}
    run_tree.extra["metrics"] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost,
        "model": model,
    }


# 사용 예시
@traceable_llm(model="gpt-5.2")
async def generate_with_gpt(prompt: str):
    return await openai_client.chat.completions.create(
        model="gpt-5.2",
        messages=[{"role": "user", "content": prompt}],
    )
```

### Tool 호출 추적

```python
def traceable_tool(name: str, tool_type: str = "tool"):
    """Tool 호출 추적 데코레이터."""
    def decorator(func):
        @wraps(func)
        @traceable(name=f"tool:{name}", run_type="tool", metadata={"tool_type": tool_type})
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


@traceable_tool(name="kakao_search", tool_type="external_api")
async def search_places(query: str, lat: float, lon: float):
    """카카오 장소 검색."""
    ...
```

### 이미지 생성 추적

```python
def traceable_image(model: str):
    """이미지 생성 추적 데코레이터."""
    def decorator(func):
        @wraps(func)
        @traceable(name=f"image:{model}", run_type="tool")
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            run_tree = RunTree.get_current_run_tree()
            if run_tree:
                resolution = kwargs.get("resolution", "default")
                cost = calculate_image_cost(model, resolution)
                run_tree.extra = run_tree.extra or {}
                run_tree.extra["metrics"] = {
                    "cost_usd": cost,
                    "model": model,
                    "resolution": resolution,
                }

            return result
        return wrapper
    return decorator
```

## LangGraph Run Config

```python
def get_run_config(
    job_id: str,
    session_id: str | None = None,
    user_id: str | None = None,
    intent: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """LangGraph 실행 config 생성.

    LangSmith에서 추적할 메타데이터 포함.
    """
    run_tags = list(tags) if tags else []

    # Intent 태그 추가
    if intent:
        run_tags.append(f"intent:{intent}")

    return {
        "run_name": f"chat:{job_id}",
        "tags": run_tags,
        "metadata": {
            "job_id": job_id,
            "user_id": user_id,
            "intent": intent,
        },
        "configurable": {
            "thread_id": session_id if session_id else None,
        },
    }


# 사용 예시
config = get_run_config(
    job_id="job-123",
    session_id="sess-456",
    user_id="user-789",
    intent="waste",
    tags=["env:production", "model:gpt-5.2"],
)

result = await pipeline.ainvoke(state, config=config)
```

## Feature-Intent 매핑

```python
# LangSmith 대시보드에서 기능별 필터링을 위한 매핑
INTENT_FEATURE_MAP: dict[str, dict[str, Any]] = {
    "waste": {
        "feature": "rag",
        "subagents": ["waste_rag", "weather"],
        "has_feedback": True,
        "description": "분리배출 RAG 검색",
    },
    "bulk_waste": {
        "feature": "external_api",
        "subagents": ["bulk_waste", "weather"],
        "has_feedback": False,
        "description": "대형폐기물 (행정안전부 API)",
    },
    "location": {
        "feature": "external_api",
        "subagents": ["location"],
        "has_feedback": False,
        "description": "장소 검색 (카카오맵)",
    },
    "character": {
        "feature": "grpc",
        "subagents": ["character"],
        "has_feedback": False,
        "description": "캐릭터 응답 (gRPC)",
    },
    "weather": {
        "feature": "external_api",
        "subagents": ["weather"],
        "has_feedback": False,
        "description": "날씨 정보 (기상청)",
    },
    "web_search": {
        "feature": "web_search",
        "subagents": ["web_search"],
        "has_feedback": False,
        "description": "웹 검색 (OpenAI/Gemini)",
    },
    "image_generation": {
        "feature": "image",
        "subagents": ["image_generation"],
        "has_feedback": False,
        "description": "이미지 생성 (Gemini Imagen)",
    },
    "general": {
        "feature": "llm",
        "subagents": ["general"],
        "has_feedback": False,
        "description": "일반 LLM 응답",
    },
}


def get_feature_tags(intent: str) -> list[str]:
    """Intent에 해당하는 feature 태그 반환."""
    mapping = INTENT_FEATURE_MAP.get(intent, {})
    tags = []

    if feature := mapping.get("feature"):
        tags.append(f"feature:{feature}")

    for subagent in mapping.get("subagents", []):
        tags.append(f"subagent:{subagent}")

    return tags
```

## OTEL 연동 (선택)

```python
# OpenTelemetry와 LangSmith 통합
import os

if os.environ.get("LANGSMITH_OTEL_ENABLED", "").lower() == "true":
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # OTEL 설정
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint="localhost:4317")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # LangSmith + OTEL 연결
    from langsmith.wrappers import wrap_opentelemetry
    wrap_opentelemetry()
```

## Eco² 실제 구현

```python
# apps/chat_worker/application/commands/process_chat.py

class ProcessChatCommand:
    """채팅 처리 Command."""

    async def execute(self, job: ChatJob) -> ChatResult:
        """채팅 처리 실행."""

        # LangSmith config 생성
        config = get_run_config(
            job_id=job.job_id,
            session_id=job.thread_id,
            user_id=job.user_id,
            intent=None,  # 아직 모름
            tags=[
                f"env:{os.environ.get('ENV', 'development')}",
                f"model:{job.llm_model or 'default'}",
            ],
        )

        # State 초기화
        state = ChatState(
            job_id=job.job_id,
            user_id=job.user_id,
            thread_id=job.thread_id,
            message=job.message,
            image_url=job.image_url,
            user_location=job.user_location,
            llm_model=job.llm_model,
            llm_provider=job.llm_provider,
        )

        # Pipeline 실행 (LangSmith 자동 추적)
        result = await self._pipeline.ainvoke(state, config=config)

        # Intent 알게 된 후 태그 업데이트 (run_tree 사용)
        if is_langsmith_enabled():
            from langsmith import Client
            client = Client()

            # 현재 run에 intent 태그 추가
            # (실제로는 run_tree.patch() 사용)
            intent = result.get("intent", "unknown")
            feature_tags = get_feature_tags(intent)
            # client.update_run(run_id, tags=feature_tags)

        return ChatResult(
            answer=result.get("answer", ""),
            intent=result.get("intent"),
        )
```

## Best Practices

1. **환경별 프로젝트 분리**: `LANGCHAIN_PROJECT=eco2-{env}`
2. **태그 일관성**: `feature:xxx`, `intent:xxx`, `model:xxx` 형식
3. **비용 추적**: 모든 LLM 호출에 토큰/비용 메트릭 추가
4. **에러 컨텍스트**: 실패 시 상세 정보 포함
5. **샘플링**: 프로덕션에서 100% 추적은 비용 부담 → 샘플링 고려

## Reference

- [LangSmith Docs](https://docs.smith.langchain.com/)
- [LangSmith Python SDK](https://github.com/langchain-ai/langsmith-sdk)
- [OpenTelemetry Integration](https://docs.smith.langchain.com/observability/how_to_guides/tracing/trace_with_opentelemetry)
