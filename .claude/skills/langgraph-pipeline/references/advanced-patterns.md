# LangGraph Advanced Patterns

## 1. Send API (Dynamic Parallel Execution)

LangGraph의 Send API는 런타임에 동적으로 병렬 노드 실행을 결정할 수 있게 해준다.

### 기본 개념

```
                    ╔═══════════════════════════════════╗
                    ║   Send API (병렬 실행)              ║
                    ║   ┌─────┬─────┬─────┬─────┐       ║
                    ║   ▼     ▼     ▼     ▼     ▼       ║
                    ║ waste char  loc  bulk weather    ║
                    ╚═══════════════════════════════════╝
```

### Dynamic Router 구현

```python
from langgraph.types import Send

def create_dynamic_router(
    enable_multi_intent: bool = True,
    enable_enrichment: bool = True,
):
    """동적 라우터 생성.

    Send API를 사용하여 런타임에 여러 노드를 병렬 실행.
    """

    # Intent → Node 매핑
    INTENT_TO_NODE = {
        "waste": "waste_rag",
        "bulk_waste": "bulk_waste",
        "location": "location",
        "character": "character",
        "weather": "weather",
        "web_search": "web_search",
        "general": "general",
    }

    # Intent별 Enrichment 규칙
    ENRICHMENT_RULES = {
        "waste": ["weather"],  # 분리배출 시 날씨 팁 추가
        "bulk_waste": ["weather"],
    }

    def dynamic_router(state: dict) -> list[Send]:
        """동적 라우팅 함수.

        Returns:
            list[Send]: 병렬 실행할 노드 목록
        """
        sends: list[Send] = []
        activated_nodes: set[str] = set()

        primary_intent = state.get("intent", "general")
        additional_intents = state.get("additional_intents", [])

        # 1. Primary intent 노드
        primary_node = INTENT_TO_NODE.get(primary_intent, "general")
        sends.append(Send(primary_node, state))
        activated_nodes.add(primary_node)

        # 2. Multi-intent fanout (병렬 실행)
        if enable_multi_intent and additional_intents:
            for intent in additional_intents:
                node = INTENT_TO_NODE.get(intent, intent)
                if node not in activated_nodes:
                    sends.append(Send(node, state))
                    activated_nodes.add(node)

        # 3. Intent 기반 Enrichment
        if enable_enrichment and primary_intent in ENRICHMENT_RULES:
            for enrichment_node in ENRICHMENT_RULES[primary_intent]:
                if enrichment_node not in activated_nodes:
                    sends.append(Send(enrichment_node, state))
                    activated_nodes.add(enrichment_node)

        # 4. 조건부 Enrichment (state 기반)
        # 위치 정보가 있으면 날씨 노드 추가
        if (
            "weather" not in activated_nodes
            and state.get("user_location")
            and primary_intent not in ("weather", "general")
        ):
            sends.append(Send("weather", state))
            activated_nodes.add("weather")

        return sends

    return dynamic_router


# Graph에 적용
graph.add_conditional_edges(
    "router",
    create_dynamic_router(
        enable_multi_intent=True,
        enable_enrichment=True,
    ),
)
```

### Send API 주의사항

1. **반환값은 `list[Send]`**: 빈 리스트 반환 시 그래프 종료
2. **각 Send는 독립 실행**: 병렬로 실행되며, 순서 보장 없음
3. **State 복사**: 각 노드는 state의 복사본을 받음
4. **Aggregation 필요**: 병렬 실행 후 결과 수집 노드 필요


## 2. Annotated State with Reducers

LangGraph에서 채널(필드)별로 커스텀 병합 로직을 정의할 수 있다.

### ChatState 스키마 예시

```python
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages, AnyMessage


def priority_preemptive_reducer(
    existing: dict | None,
    new: dict | None,
) -> dict | None:
    """OS-inspired preemptive scheduling for channel merging.

    결정 순서:
    1. _reset 마커: 명시적 필드 리셋
    2. success 비교: True가 False를 선점
    3. priority 비교: 낮은 값(높은 우선순위)이 선점
    4. sequence 비교: 큰 값(Lamport Clock)이 승리
    """
    # Reset 마커
    if isinstance(new, dict) and new.get("_reset"):
        return None

    if new is None:
        return existing
    if existing is None:
        return new

    # Success preemption
    new_success = new.get("success", True)
    existing_success = existing.get("success", True)
    if new_success and not existing_success:
        return new
    if existing_success and not new_success:
        return existing

    # Priority preemption (낮은 값 = 높은 우선순위)
    existing_priority = existing.get("_priority", 50)
    new_priority = new.get("_priority", 50)

    if new_priority < existing_priority:
        return new
    if new_priority > existing_priority:
        return existing

    # Lamport Clock (sequence)
    existing_seq = existing.get("_sequence", 0)
    new_seq = new.get("_sequence", 0)
    return new if new_seq >= existing_seq else existing


class ChatState(TypedDict, total=False):
    """Agent Pipeline State 스키마.

    total=False: 모든 필드가 Optional
    """

    # === Core Layer ===
    job_id: str
    user_id: str
    thread_id: str
    message: str
    image_url: str | None
    user_location: dict[str, float] | None
    llm_model: str | None
    llm_provider: str | None

    # === Intent Layer ===
    intent: str
    intent_confidence: float
    is_complex: bool
    has_multi_intent: bool
    additional_intents: list[str]

    # === Context Channels (Annotated Reducer) ===
    # 각 채널은 독립적으로 병합됨
    disposal_rules: Annotated[dict[str, Any] | None, priority_preemptive_reducer]
    bulk_waste_context: Annotated[dict[str, Any] | None, priority_preemptive_reducer]
    location_context: Annotated[dict[str, Any] | None, priority_preemptive_reducer]
    character_context: Annotated[dict[str, Any] | None, priority_preemptive_reducer]
    weather_context: Annotated[dict[str, Any] | None, priority_preemptive_reducer]
    web_search_results: Annotated[dict[str, Any] | None, priority_preemptive_reducer]

    # === Output Layer ===
    answer: str

    # === Message History (LangGraph 내장 Reducer) ===
    messages: Annotated[list[AnyMessage], add_messages]
```

### Reducer 패턴

1. **add_messages**: 메시지 리스트 누적 (LangGraph 내장)
2. **priority_preemptive_reducer**: 우선순위 기반 선점
3. **last_value_reducer**: 마지막 값 사용 (기본)

```python
def last_value_reducer(existing: T | None, new: T | None) -> T | None:
    """마지막 값이 승리 (기본 동작)."""
    return new if new is not None else existing

def accumulate_reducer(existing: list | None, new: list | None) -> list:
    """리스트 누적."""
    result = existing or []
    if new:
        result.extend(new)
    return result
```


## 3. Priority Scheduling System

OS 스케줄링 개념을 LangGraph에 적용하여 노드 우선순위와 데드라인을 관리.

```python
from enum import IntEnum
import time


class Priority(IntEnum):
    """우선순위 레벨 (낮은 값 = 높은 우선순위)."""
    CRITICAL = 0      # 필수 컨텍스트 (답변 생성에 필수)
    HIGH = 25         # 주요 서비스 (gRPC, 검색)
    NORMAL = 50       # 기본값
    LOW = 75          # Enrichment (부가 정보)
    BACKGROUND = 100  # 로깅, 메트릭


# 노드별 기본 우선순위
NODE_PRIORITY: dict[str, Priority] = {
    "waste_rag": Priority.CRITICAL,
    "bulk_waste": Priority.CRITICAL,
    "location": Priority.CRITICAL,
    "collection_point": Priority.CRITICAL,
    "character": Priority.HIGH,
    "general": Priority.HIGH,
    "web_search": Priority.HIGH,
    "recyclable_price": Priority.NORMAL,
    "image_generation": Priority.NORMAL,
    "weather": Priority.LOW,
}

# 노드별 데드라인 (ms)
NODE_DEADLINE_MS: dict[str, int] = {
    "image_generation": 30000,  # LLM/Image: 30s
    "character": 5000,          # gRPC Internal: 5s
    "location": 5000,
    "weather": 8000,            # External API: 8-10s
    "web_search": 10000,
    "waste_rag": 8000,          # RAG/Vector Search
    "bulk_waste": 8000,
    "collection_point": 8000,
    "recyclable_price": 5000,   # Local Data: 5s
    "general": 10000,
}


def calculate_effective_priority(
    base_priority: int,
    created_at: float,
    deadline_ms: int,
    is_fallback: bool = False,
) -> int:
    """Aging 알고리즘 적용.

    데드라인의 80% 초과 시 우선순위 부스트.
    """
    priority = base_priority

    # Aging (데드라인 기반)
    elapsed_ms = (time.time() - created_at) * 1000
    deadline_ratio = elapsed_ms / deadline_ms if deadline_ms > 0 else 0

    if deadline_ratio > 0.8:  # 80% 초과
        boost_ratio = (deadline_ratio - 0.8) / 0.2
        aging_boost = min(20, int(boost_ratio * 20))
        priority -= aging_boost

    # Fallback 패널티
    if is_fallback:
        priority += 15

    return max(0, min(100, priority))
```

### 노드에서 Priority 사용

```python
async def waste_rag_node(state: dict) -> dict:
    """RAG 검색 노드."""
    created_at = time.time()
    priority = NODE_PRIORITY.get("waste_rag", Priority.NORMAL)

    try:
        result = await retriever.search(state["message"])

        return {
            "disposal_rules": {
                "success": True,
                "data": result,
                "_priority": priority,
                "_sequence": int(time.time() * 1000),  # Lamport Clock
            },
        }
    except Exception as e:
        # 실패 시 낮은 우선순위로 에러 컨텍스트 전달
        return {
            "disposal_rules": {
                "success": False,
                "error": str(e),
                "_priority": Priority.LOW,
                "_sequence": int(time.time() * 1000),
            },
        }
```


## 4. Aggregator Pattern

Send API로 병렬 실행된 노드들의 결과를 수집하는 패턴.

```python
def create_aggregator_node():
    """결과 수집 노드 생성."""

    async def aggregator_node(state: dict) -> dict:
        """병렬 노드 결과 수집 및 정리."""

        # 각 채널에서 성공한 컨텍스트만 수집
        contexts = []

        if state.get("disposal_rules", {}).get("success"):
            contexts.append(("waste", state["disposal_rules"]))

        if state.get("location_context", {}).get("success"):
            contexts.append(("location", state["location_context"]))

        if state.get("weather_context", {}).get("success"):
            contexts.append(("weather", state["weather_context"]))

        if state.get("web_search_results", {}).get("success"):
            contexts.append(("web_search", state["web_search_results"]))

        # 컨텍스트가 너무 많으면 요약 (Context Compression)
        if len(contexts) > 3:
            # summarize_node로 전달
            return {"needs_summarization": True, "collected_contexts": contexts}

        return {"collected_contexts": contexts}

    return aggregator_node
```


## 5. Full Graph Example

```python
from langgraph.graph import END, StateGraph

def create_chat_graph(
    llm: LLMClientPort,
    retriever: RetrieverPort,
    location_client: LocationClientPort | None = None,
    weather_client: WeatherClientPort | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> StateGraph:
    """Full Intent-Routed Graph with Dynamic Routing."""

    graph = StateGraph(ChatState)

    # === Nodes ===
    graph.add_node("intent", create_intent_node(llm))
    graph.add_node("vision", create_vision_node(llm))
    graph.add_node("router", lambda s: s)  # Pass-through
    graph.add_node("waste_rag", create_rag_node(retriever))
    graph.add_node("location", create_location_node(location_client))
    graph.add_node("weather", create_weather_node(weather_client))
    graph.add_node("aggregator", create_aggregator_node())
    graph.add_node("answer", create_answer_node(llm))

    # === Edges ===
    graph.set_entry_point("intent")

    # Vision 조건부 진입
    graph.add_conditional_edges(
        "intent",
        lambda s: "vision" if s.get("image_url") else "router",
        {"vision": "vision", "router": "router"},
    )
    graph.add_edge("vision", "router")

    # Dynamic Router (Send API)
    graph.add_conditional_edges(
        "router",
        create_dynamic_router(enable_multi_intent=True, enable_enrichment=True),
    )

    # 병렬 노드 → Aggregator
    for node in ["waste_rag", "location", "weather", "general"]:
        if node in graph.nodes:
            graph.add_edge(node, "aggregator")

    # Aggregator → Answer → END
    graph.add_edge("aggregator", "answer")
    graph.add_edge("answer", END)

    return graph.compile(checkpointer=checkpointer)
```


## Reference

- [LangGraph Send API](https://langchain-ai.github.io/langgraph/concepts/low_level/#send)
- [LangGraph State Reducers](https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers)
- [LangGraph Checkpointing](https://langchain-ai.github.io/langgraph/concepts/persistence/)
