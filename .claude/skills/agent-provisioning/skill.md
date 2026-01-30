---
name: agent-provisioning
description: Agent 시스템 프로비저닝 가이드. Dependencies 싱글톤, HTTP 클라이언트 풀링, LLM 클라이언트 설정, 환경변수 관리, Worker 초기화 패턴. "dependencies", "provisioning", "http client", "connection pool", "worker setup" 키워드로 트리거.
---

# Agent Provisioning Guide

## 개요

Agent 시스템의 인프라 레이어 설정 가이드.
Dependencies 싱글톤, HTTP 클라이언트, LLM 클라이언트 프로비저닝 패턴.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Agent System Provisioning                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Environment Variables                          │   │
│  │  - OPENAI_API_KEY                                                 │   │
│  │  - GOOGLE_API_KEY                                                 │   │
│  │  - KAKAO_API_KEY                                                  │   │
│  │  - LANGCHAIN_TRACING_V2=true                                      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Dependencies (Singleton)                        │   │
│  │  - get_openai_client() → OpenAI                                   │   │
│  │  - get_gemini_client() → genai.Client                             │   │
│  │  - get_http_client() → httpx.AsyncClient                          │   │
│  │  - get_redis() → Redis                                            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    LLM Clients (Port/Adapter)                      │   │
│  │  - OpenAILLMClient(LLMClientPort)                                 │   │
│  │  - GeminiLLMClient(LLMClientPort)                                 │   │
│  │  - LangChainAdapter(LLMClientPort)                                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Graph Factory                                   │   │
│  │  - create_chat_graph(llm, retriever, clients...)                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 환경 변수

```bash
# ===== LLM API Keys =====
OPENAI_API_KEY=sk-xxxxx
GOOGLE_API_KEY=AIzaSy-xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx  # Optional

# ===== External APIs =====
KAKAO_API_KEY=xxxxx        # 카카오맵 API
TAVILY_API_KEY=tvly-xxxxx  # 웹 검색 API

# ===== LangSmith =====
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-xxxxx
LANGCHAIN_PROJECT=eco2-chat-worker

# ===== Infrastructure =====
REDIS_URL=redis://localhost:6379/0
POSTGRES_URL=postgresql://user:pass@localhost:5432/db

# ===== Worker Settings =====
WORKER_CONCURRENCY=4
LLM_DEFAULT_MODEL=gpt-5.2
LLM_DEFAULT_PROVIDER=openai
```

## HTTP 클라이언트 설정

### Timeout & Limits

```python
# apps/chat_worker/infrastructure/llm/config.py

import httpx

# HTTP Timeout 설정
HTTP_TIMEOUT = httpx.Timeout(
    connect=5.0,   # 연결 타임아웃
    read=60.0,     # 응답 읽기 타임아웃 (LLM은 길게)
    write=10.0,    # 요청 쓰기 타임아웃
    pool=5.0,      # 커넥션 풀 대기 타임아웃
)

# 커넥션 풀 제한
HTTP_LIMITS = httpx.Limits(
    max_connections=100,           # 최대 동시 연결
    max_keepalive_connections=20,  # Keep-alive 연결 유지
    keepalive_expiry=30.0,         # Keep-alive 만료 시간
)

# 재시도 설정
MAX_RETRIES = 2

# 모델별 컨텍스트 윈도우
MODEL_CONTEXT_WINDOWS = {
    "gpt-5.2": 256_000,
    "gpt-5.2-codex": 256_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gemini-3-flash-preview": 1_000_000,
    "gemini-3-pro-preview": 2_000_000,
    "gemini-1.5-pro": 2_000_000,
    "gemini-1.5-flash": 1_000_000,
}
```

### Shared HTTP Client

```python
# apps/chat_worker/setup/dependencies.py

import httpx
from functools import lru_cache

_shared_http_client: httpx.AsyncClient | None = None


def get_shared_http_client() -> httpx.AsyncClient:
    """공유 HTTP 클라이언트 싱글톤.

    모든 외부 API 호출에서 커넥션 풀 공유.
    """
    global _shared_http_client

    if _shared_http_client is None:
        _shared_http_client = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            limits=HTTP_LIMITS,
            http2=True,  # HTTP/2 활성화
        )

    return _shared_http_client


async def close_shared_http_client():
    """애플리케이션 종료 시 클라이언트 정리."""
    global _shared_http_client

    if _shared_http_client is not None:
        await _shared_http_client.aclose()
        _shared_http_client = None
```

## LLM 클라이언트 싱글톤

### OpenAI 클라이언트

```python
# apps/chat_worker/setup/dependencies.py

from openai import AsyncOpenAI

_openai_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI | None:
    """OpenAI AsyncOpenAI 클라이언트 싱글톤."""
    global _openai_client

    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None

        # 공유 HTTP 클라이언트 사용
        http_client = get_shared_http_client()

        _openai_client = AsyncOpenAI(
            api_key=api_key,
            http_client=http_client,
            max_retries=MAX_RETRIES,
        )

    return _openai_client
```

### Gemini 클라이언트

```python
from google import genai

_gemini_client: genai.Client | None = None


def get_gemini_client() -> genai.Client | None:
    """Google Gemini 클라이언트 싱글톤."""
    global _gemini_client

    if _gemini_client is None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None

        _gemini_client = genai.Client(api_key=api_key)

    return _gemini_client
```

### Raw SDK vs Port/Adapter

```python
# Raw SDK 클라이언트: 직접 API 호출
openai_raw = get_openai_client()
response = await openai_raw.chat.completions.create(...)

# Port/Adapter: 비즈니스 로직 추상화
from chat_worker.infrastructure.llm.clients import OpenAILLMClient

llm_client = OpenAILLMClient(
    client=get_openai_client(),
    model="gpt-5.2",
)
intent = await llm_client.generate_structured(
    prompt=message,
    response_schema=IntentClassification,
)
```

## Port/Adapter 패턴

### LLMClientPort 인터페이스

```python
# apps/chat_worker/application/ports/llm/llm_client.py

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClientPort(ABC):
    """LLM 클라이언트 Port (인터페이스).

    모든 LLM 구현체가 준수해야 하는 계약.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """텍스트 생성."""
        ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0,
    ) -> T:
        """Structured Output 생성."""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """스트리밍 생성."""
        ...

    @abstractmethod
    async def generate_function_call(
        self,
        prompt: str,
        functions: list[dict[str, Any]],
        system_prompt: str | None = None,
        function_call: str | dict = "auto",
    ) -> tuple[str, dict] | None:
        """Function Calling."""
        ...

    @abstractmethod
    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[str],
        system_prompt: str | None = None,
    ) -> str:
        """Tool 사용 생성 (web_search 등)."""
        ...
```

### Adapter 구현 예시

```python
# apps/chat_worker/infrastructure/llm/clients/openai_client.py

class OpenAILLMClient(LLMClientPort):
    """OpenAI LLM 클라이언트 Adapter."""

    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        model: str = "gpt-5.2",
    ):
        self._client = client or get_openai_client()
        self._model = model

        if self._client is None:
            raise ValueError("OpenAI client not available")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""

    # ... 나머지 메서드 구현
```

## Graph Factory

### 의존성 주입 패턴

```python
# apps/chat_worker/infrastructure/orchestration/langgraph/factory.py

from langgraph.graph import StateGraph

def create_chat_graph(
    # 필수 의존성
    llm: LLMClientPort,
    retriever: RetrieverPort,

    # 선택적 외부 서비스
    vision_model: VisionModelPort | None = None,
    character_client: CharacterClientPort | None = None,
    location_client: LocationClientPort | None = None,
    web_search_client: WebSearchPort | None = None,
    bulk_waste_client: BulkWasteClientPort | None = None,
    weather_client: WeatherClientPort | None = None,
    collection_point_client: CollectionPointClientPort | None = None,
    image_generator: ImageGeneratorPort | None = None,

    # 인프라
    checkpointer: BaseCheckpointSaver | None = None,
    event_publisher: ProgressNotifierPort | None = None,

    # 기능 플래그
    enable_summarization: bool = False,
    enable_dynamic_routing: bool = True,
    enable_multi_intent: bool = True,
    enable_enrichment: bool = True,
) -> StateGraph:
    """Chat Graph 팩토리.

    Port 기반 의존성 주입으로 테스트 용이성 확보.
    """

    graph = StateGraph(ChatState)

    # === 필수 노드 ===
    graph.add_node("intent", create_intent_node(llm, event_publisher))
    graph.add_node("router", lambda s: s)
    graph.add_node("answer", create_answer_node(llm, event_publisher))

    # === 선택적 노드 (의존성 있을 때만) ===
    if vision_model:
        graph.add_node("vision", create_vision_node(vision_model))

    if retriever:
        graph.add_node("waste_rag", create_rag_node(retriever, llm, event_publisher))

    if character_client:
        graph.add_node("character", create_character_node(character_client, event_publisher))

    if location_client:
        graph.add_node("location", create_location_node(
            location_client,
            llm,
            event_publisher,
            get_openai_client(),
            get_gemini_client(),
        ))

    if weather_client:
        graph.add_node("weather", create_weather_node(weather_client))

    if bulk_waste_client:
        graph.add_node("bulk_waste", create_bulk_waste_node(
            bulk_waste_client,
            llm,
            event_publisher,
            get_openai_client(),
            get_gemini_client(),
        ))

    if image_generator:
        graph.add_node("image_generation", create_image_node(image_generator, event_publisher))

    # === 엣지 설정 ===
    graph.set_entry_point("intent")

    # Vision 조건부 라우팅
    if vision_model:
        graph.add_conditional_edges(
            "intent",
            lambda s: "vision" if s.get("image_url") else "router",
            {"vision": "vision", "router": "router"},
        )
        graph.add_edge("vision", "router")
    else:
        graph.add_edge("intent", "router")

    # Dynamic Router
    if enable_dynamic_routing:
        graph.add_conditional_edges(
            "router",
            create_dynamic_router(
                enable_multi_intent=enable_multi_intent,
                enable_enrichment=enable_enrichment,
            ),
        )

    # Aggregator → Answer
    for node in ["waste_rag", "character", "location", "bulk_waste", "weather", "general"]:
        if node in graph.nodes:
            graph.add_edge(node, "answer")

    graph.add_edge("answer", END)

    return graph.compile(checkpointer=checkpointer)
```

## Worker 초기화

### Celery Worker Setup

```python
# apps/chat_worker/setup/worker.py

from celery import Celery
from celery.signals import worker_init, worker_shutdown

app = Celery("chat_worker")


@worker_init.connect
def init_worker(**kwargs):
    """Worker 시작 시 초기화."""
    import asyncio

    # 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 싱글톤 클라이언트 초기화 (lazy하게 생성되지만 미리 warmup)
    _ = get_openai_client()
    _ = get_gemini_client()
    _ = get_shared_http_client()

    # LangSmith 설정 확인
    if is_langsmith_enabled():
        logger.info("LangSmith tracing enabled", extra={
            "project": os.environ.get("LANGCHAIN_PROJECT"),
        })


@worker_shutdown.connect
def shutdown_worker(**kwargs):
    """Worker 종료 시 정리."""
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(close_shared_http_client())
```

### FastAPI Lifespan

```python
# apps/sse_gateway/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리."""

    # Startup
    logger.info("Starting SSE Gateway...")

    # Redis 연결
    redis = await get_redis()
    app.state.redis = redis

    yield

    # Shutdown
    logger.info("Shutting down SSE Gateway...")
    await close_shared_http_client()
    await redis.close()


app = FastAPI(lifespan=lifespan)
```

## 테스트용 Mock 주입

```python
# tests/conftest.py

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm_client():
    """Mock LLM 클라이언트."""
    client = AsyncMock(spec=LLMClientPort)
    client.generate.return_value = "Mock response"
    client.generate_structured.return_value = IntentClassification(
        intent="waste",
        confidence=0.95,
        reasoning="테스트",
    )
    return client


@pytest.fixture
def mock_retriever():
    """Mock Retriever."""
    retriever = AsyncMock(spec=RetrieverPort)
    retriever.search.return_value = [
        {"content": "Mock document", "score": 0.9},
    ]
    return retriever


@pytest.fixture
def test_graph(mock_llm_client, mock_retriever):
    """테스트용 Graph."""
    return create_chat_graph(
        llm=mock_llm_client,
        retriever=mock_retriever,
        # 외부 서비스 없이 테스트
        character_client=None,
        location_client=None,
        enable_dynamic_routing=False,  # 단순 라우팅
    )
```

## Best Practices

1. **싱글톤 사용**: LLM 클라이언트는 커넥션 풀 공유를 위해 싱글톤
2. **Lazy 초기화**: 필요할 때만 클라이언트 생성
3. **Port/Adapter 분리**: 비즈니스 로직과 인프라 분리
4. **환경변수 검증**: 필수 키 누락 시 명확한 에러
5. **Graceful Shutdown**: 리소스 정리 보장
6. **HTTP/2 활성화**: 다중화로 성능 향상

## Reference

- [httpx AsyncClient](https://www.python-httpx.org/async/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [google-genai PyPI](https://pypi.org/project/google-genai/)
- [Celery Signals](https://docs.celeryq.dev/en/stable/userguide/signals.html)
