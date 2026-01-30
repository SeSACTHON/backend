---
name: openai-agents-sdk
description: OpenAI Agents SDK (2025~) 활용 가이드. Agent + Runner + WebSearchTool + RunContextWrapper 패턴. Structured Output, Function Tool, Handoff 구현 시 참조. "agents sdk", "openai agent", "runner", "web_search", "function_tool", "handoff" 키워드로 트리거.
---

# OpenAI Agents SDK Guide (2025~)

## 개요

OpenAI Agents SDK는 2025년 출시된 새로운 에이전트 프레임워크.
기존 Function Calling의 상위 레벨 추상화 제공.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    OpenAI Agents SDK Architecture                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         Agent                                      │   │
│  │  - name: "agent_name"                                             │   │
│  │  - instructions: "시스템 프롬프트"                                   │   │
│  │  - model: OpenAIResponsesModel                                    │   │
│  │  - tools: [function_tool, WebSearchTool, ...]                     │   │
│  │  - output_type: StructuredOutputSchema (Optional)                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        Runner                                      │   │
│  │  - Runner.run(agent, input, context, max_turns)                   │   │
│  │  - Runner.run_streamed(agent, input, context) → async iterator    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    RunContextWrapper                               │   │
│  │  - ctx.context: 사용자 정의 컨텍스트                                 │   │
│  │  - 모든 function_tool에서 접근 가능                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 설치

```bash
pip install openai-agents
```

## 핵심 컴포넌트

### 1. Agent 정의

```python
from agents import Agent
from agents.models.openai_responses import OpenAIResponsesModel
from openai import AsyncOpenAI

# OpenAI 클라이언트
openai_client = AsyncOpenAI(api_key="...")

# Agent 정의
agent = Agent(
    name="eco_agent",
    instructions="당신은 Eco² 앱의 AI 어시스턴트입니다.",
    model=OpenAIResponsesModel(
        model="gpt-5.2",  # 또는 gpt-4o, gpt-4o-mini
        openai_client=openai_client,
    ),
    tools=[...],  # function_tool, WebSearchTool 등
    output_type=ResponseSchema,  # Structured Output (Optional)
)
```

### 2. Runner 실행

```python
from agents import Runner, RunConfig

# 동기 실행 (결과만 반환)
result = await Runner.run(
    starting_agent=agent,
    input="재활용 방법 알려줘",
    context=my_context,  # RunContextWrapper로 접근
    max_turns=10,  # 최대 턴 수 (무한 루프 방지)
    run_config=RunConfig(
        tracing_disabled=True,  # LangSmith 사용 시 False
    ),
)

print(result.final_output)  # Agent의 최종 응답
```

### 3. 스트리밍 실행

```python
# 스트리밍 실행 (토큰 단위)
from agents.events import ResponseTextDeltaEvent

result = Runner.run_streamed(
    agent,
    input=user_message,
    context=my_context,
    run_config=RunConfig(tracing_disabled=True),
)

async for event in result.stream_events():
    if event.type == "raw_response_event":
        if isinstance(event.data, ResponseTextDeltaEvent):
            yield event.data.delta  # 스트리밍 토큰
```

## Function Tool 정의

### @function_tool 데코레이터

```python
from agents import function_tool, RunContextWrapper
from dataclasses import dataclass

# 1. 컨텍스트 타입 정의
@dataclass
class AgentContext:
    tool_executor: ToolExecutor
    tool_results: list  # Tool 실행 결과 수집

# 2. Function Tool 정의
@function_tool
async def search_places(
    ctx: RunContextWrapper[AgentContext],
    query: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> str:
    """키워드 기반 장소 검색.

    사용 시점: 재활용센터, 제로웨이스트샵 등 특정 장소를 찾을 때.
    주의: 지역명 언급 시 먼저 geocode로 좌표 획득 후 호출.

    Args:
        ctx: 실행 컨텍스트
        query: 검색 키워드 (예: '재활용센터')
        latitude: 검색 중심 위도 (선택)
        longitude: 검색 중심 경도 (선택)

    Returns:
        검색 결과 JSON 문자열
    """
    # Tool 실행
    result = await ctx.context.tool_executor.execute(
        "search_places",
        {"query": query, "latitude": latitude, "longitude": longitude},
    )

    # 결과 수집 (디버깅/로깅용)
    ctx.context.tool_results.append({
        "tool": "search_places",
        "arguments": {"query": query, "latitude": latitude, "longitude": longitude},
        "result": result.data if result.success else {"error": result.error},
        "success": result.success,
    })

    # LLM에게 반환 (JSON 문자열)
    return json.dumps(
        result.data if result.success else {"error": result.error},
        ensure_ascii=False,
    )
```

### Function Tool 주의사항

1. **Docstring이 Tool Description이 됨**: OpenAI Strict Mode와 동일한 규칙 적용
2. **반환 타입은 `str`**: LLM에게 전달되는 결과는 항상 문자열
3. **ctx.context로 외부 리소스 접근**: DB, API 클라이언트 등 주입

## WebSearchTool (Built-in)

```python
from agents import Agent, WebSearchTool
from agents.models.openai_responses import OpenAIResponsesModel

# WebSearchTool 설정
web_search = WebSearchTool(
    search_context_size="medium",  # "small", "medium", "large"
    user_location=None,  # 검색 위치 힌트 (선택)
)

# Agent에 추가
agent = Agent(
    name="web_search_agent",
    instructions="웹 검색으로 최신 정보를 찾아 답변합니다.",
    model=OpenAIResponsesModel(model="gpt-5.2", openai_client=client),
    tools=[web_search],
)
```

## Structured Output

### output_type으로 스키마 강제

```python
from pydantic import BaseModel

class IntentClassification(BaseModel):
    intent: str
    confidence: float
    reasoning: str

# Agent에 output_type 지정
agent = Agent(
    name="intent_classifier",
    instructions="사용자 메시지의 의도를 분류합니다.",
    model=OpenAIResponsesModel(model="gpt-5.2", openai_client=client),
    output_type=IntentClassification,  # Structured Output
)

result = await Runner.run(agent, input="재활용 방법 알려줘")
intent: IntentClassification = result.final_output  # 타입 보장
```

## Agent Handoff (Multi-Agent)

```python
from agents import Agent, handoff

# Specialist Agents
waste_agent = Agent(name="waste_agent", instructions="분리배출 전문가...")
location_agent = Agent(name="location_agent", instructions="위치 검색 전문가...")

# Router Agent with Handoff
router_agent = Agent(
    name="router",
    instructions="사용자 요청을 적절한 전문가에게 전달합니다.",
    model=OpenAIResponsesModel(model="gpt-5.2", openai_client=client),
    handoffs=[
        handoff(waste_agent, "분리배출 관련 질문"),
        handoff(location_agent, "위치/장소 검색 요청"),
    ],
)

# Router가 자동으로 적절한 Agent에게 위임
result = await Runner.run(router_agent, input="강남역 근처 재활용센터")
```

## Eco² 실제 구현 패턴

### Bulk Waste Agent Node

```python
# apps/chat_worker/infrastructure/orchestration/langgraph/nodes/bulk_waste_agent_node.py

@dataclass
class BulkWasteAgentContext:
    tool_executor: BulkWasteToolExecutor
    tool_results: list

async def run_agents_sdk_agent(
    openai_client: AsyncOpenAI,
    model: str,
    message: str,
    tool_executor: BulkWasteToolExecutor,
    system_prompt: str,
) -> dict:
    """Agents SDK로 대형폐기물 Agent 실행."""

    # Function Tools 정의
    @function_tool
    async def get_collection_info(
        ctx: RunContextWrapper[BulkWasteAgentContext],
        sigungu: str,
    ) -> str:
        """지역별 대형폐기물 수거 방법 조회.

        사용 시점: '대형폐기물 어떻게 버려요?', '수거 신청 방법' 등 질문 시.
        """
        result = await ctx.context.tool_executor.execute(
            "get_collection_info", {"sigungu": sigungu}
        )
        ctx.context.tool_results.append({...})
        return json.dumps(result.data or {"error": result.error}, ensure_ascii=False)

    @function_tool
    async def search_fee(
        ctx: RunContextWrapper[BulkWasteAgentContext],
        sigungu: str,
        item_name: str,
    ) -> str:
        """대형폐기물 수수료 검색.

        사용 시점: '소파 버리는 비용', '침대 수수료' 등 가격 질문 시.
        """
        result = await ctx.context.tool_executor.execute(
            "search_fee", {"sigungu": sigungu, "item_name": item_name}
        )
        ctx.context.tool_results.append({...})
        return json.dumps(result.data or {"error": result.error}, ensure_ascii=False)

    # Agent 생성
    agent = Agent[BulkWasteAgentContext](
        name="bulk_waste_agent",
        instructions=system_prompt,
        model=OpenAIResponsesModel(model=model, openai_client=openai_client),
        tools=[get_collection_info, search_fee],
    )

    # Context 준비
    ctx = BulkWasteAgentContext(
        tool_executor=tool_executor,
        tool_results=[],
    )

    # 실행
    result = await Runner.run(
        starting_agent=agent,
        input=message,
        context=ctx,
        max_turns=10,
        run_config=RunConfig(tracing_disabled=True),
    )

    return {
        "success": True,
        "summary": result.final_output,
        "tool_results": ctx.tool_results,
    }
```

## Primary/Fallback 패턴

```python
async def run_agent_with_fallback(
    message: str,
    tool_executor: ToolExecutor,
    openai_client: AsyncOpenAI,
    model: str,
    system_prompt: str,
    tools_openai: list[dict],  # Function Calling 용
) -> dict:
    """Primary: Agents SDK, Fallback: Function Calling."""

    try:
        # Primary: Agents SDK
        return await run_agents_sdk_agent(
            openai_client=openai_client,
            model=model,
            message=message,
            tool_executor=tool_executor,
            system_prompt=system_prompt,
        )
    except ImportError:
        # Agents SDK 미설치
        logger.warning("Agents SDK not installed, using Function Calling")
    except Exception as e:
        logger.warning(f"Agents SDK failed: {e}, falling back")

    # Fallback: 기존 Function Calling
    return await run_function_calling_agent(
        openai_client=openai_client,
        model=model,
        message=message,
        tools=tools_openai,
        tool_executor=tool_executor,
        system_prompt=system_prompt,
    )
```

## Dependencies

```python
# pyproject.toml
[project.optional-dependencies]
agents = ["openai-agents>=0.1.0"]

# requirements.txt
openai>=1.50.0
openai-agents>=0.1.0
```

## Reference

- [OpenAI Agents SDK Docs](https://openai.github.io/openai-agents-python/)
- [Agents SDK Reference](https://openai.github.io/openai-agents-python/ref/)
- [WebSearchTool](https://openai.github.io/openai-agents-python/ref/tool/#agents.tool.WebSearchTool)
- [function_tool](https://openai.github.io/openai-agents-python/ref/tool/#agents.tool.function_tool)
