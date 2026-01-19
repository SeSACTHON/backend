---
name: function-calling-agent
description: OpenAI/Gemini Function Calling을 활용한 에이전트 구현 가이드. LLM이 외부 API를 Tool로 호출하는 패턴. "function calling", "tool", "agent", "openai tools", "gemini tools" 키워드로 트리거.
---

# Function Calling Agent Guide

## 개요

LLM이 외부 API를 Tool로 호출하여 작업을 수행하는 에이전트 패턴.
OpenAI와 Gemini 모두 지원.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Function Calling Agent Loop                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User Message ──────────────────────────────────────────────────────┐   │
│       │                                                              │   │
│       ▼                                                              │   │
│  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │                    LLM with Tools                            │    │   │
│  │                                                              │    │   │
│  │  "사용자 요청을 분석하고, 필요한 Tool을 선택하여 호출합니다"  │    │   │
│  │                                                              │    │   │
│  │  Available Tools:                                            │    │   │
│  │   ├── tool_a(param1, param2, ...)                           │    │   │
│  │   ├── tool_b(param1, ...)                                   │    │   │
│  │   └── tool_c(...)                                           │    │   │
│  └─────────────────────────────────────────────────────────────┘    │   │
│       │                                                              │   │
│       ▼                                                              │   │
│  ┌─────────────┐    No tool calls?                                  │   │
│  │ Tool Calls? │ ──────────────────────► Return final response      │   │
│  └─────────────┘                                                     │   │
│       │ Yes                                                          │   │
│       ▼                                                              │   │
│  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │              Tool Executor (External APIs)                   │    │   │
│  │  - Execute tools with LLM-generated arguments                │    │   │
│  │  - Return results to LLM                                     │    │   │
│  └─────────────────────────────────────────────────────────────┘    │   │
│       │                                                              │   │
│       └──────────────────────────────────────────────────────────────┘   │
│                            (Loop until no more tool calls)              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Tool 정의 스키마

### OpenAI Format

```python
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "Tool이 수행하는 작업 설명 (LLM이 이해할 수 있게)",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "파라미터 설명",
                    },
                    "param2": {
                        "type": "number",
                        "description": "숫자 파라미터",
                    },
                    "param3": {
                        "type": "string",
                        "enum": ["option1", "option2", "option3"],
                        "description": "선택지가 정해진 파라미터",
                    },
                },
                "required": ["param1"],  # 필수 파라미터
            },
        },
    },
]
```

### Gemini Format

```python
GEMINI_TOOLS = [
    {
        "name": "tool_name",
        "description": "Tool이 수행하는 작업 설명",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "파라미터 설명",
                },
                "param2": {
                    "type": "number",
                    "description": "숫자 파라미터",
                },
            },
            "required": ["param1"],
        },
    },
]
```

## OpenAI Function Calling 구현

```python
import json
from openai import AsyncOpenAI

async def run_openai_agent(
    client: AsyncOpenAI,
    model: str,
    user_message: str,
    tools: list[dict],
    tool_executor: ToolExecutor,
    system_prompt: str = "",
    max_iterations: int = 5,
) -> dict:
    """OpenAI Function Calling Agent Loop.

    Args:
        client: OpenAI AsyncClient
        model: 모델명 (gpt-4o-mini, gpt-4o, etc.)
        user_message: 사용자 메시지
        tools: Tool 정의 리스트 (OpenAI format)
        tool_executor: Tool 실행기
        system_prompt: 시스템 프롬프트
        max_iterations: 최대 반복 횟수 (무한 루프 방지)

    Returns:
        {"success": bool, "response": str, "tool_results": list}
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    all_tool_results = []

    for iteration in range(max_iterations):
        # 1. LLM 호출 (with tools)
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",  # LLM이 자동으로 tool 선택
        )

        assistant_message = response.choices[0].message

        # 2. Tool call이 없으면 최종 응답
        if not assistant_message.tool_calls:
            return {
                "success": True,
                "response": assistant_message.content,
                "tool_results": all_tool_results,
            }

        # 3. Assistant 메시지를 대화 이력에 추가
        messages.append(assistant_message.model_dump())

        # 4. 각 Tool call 실행
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            # Tool 실행
            result = await tool_executor.execute(tool_name, arguments)

            all_tool_results.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": result.data if result.success else {"error": result.error},
                "success": result.success,
            })

            # 5. Tool 결과를 메시지에 추가
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": json.dumps(
                    result.data if result.success else {"error": result.error},
                    ensure_ascii=False,
                ),
            })

    # Max iterations 도달
    return {
        "success": True,
        "response": "최대 반복 횟수 도달",
        "tool_results": all_tool_results,
    }
```

## Gemini Function Calling 구현

```python
from google import genai
from google.genai import types

async def run_gemini_agent(
    client: genai.Client,
    model: str,
    user_message: str,
    tools: list[dict],
    tool_executor: ToolExecutor,
    system_prompt: str = "",
    max_iterations: int = 5,
) -> dict:
    """Gemini Function Calling Agent Loop.

    Args:
        client: Gemini Client
        model: 모델명 (gemini-3-flash-preview, etc.)
        user_message: 사용자 메시지
        tools: Tool 정의 리스트 (Gemini format)
        tool_executor: Tool 실행기
        system_prompt: 시스템 프롬프트
        max_iterations: 최대 반복 횟수

    Returns:
        {"success": bool, "response": str, "tool_results": list}
    """
    # Tool 설정
    gemini_tools = types.Tool(function_declarations=tools)
    config = types.GenerateContentConfig(
        tools=[gemini_tools],
        system_instruction=system_prompt if system_prompt else None,
    )

    contents = [user_message]
    all_tool_results = []

    for iteration in range(max_iterations):
        # 1. Gemini 호출
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]
        part = candidate.content.parts[0]

        # 2. Function call이 없으면 최종 응답
        if not hasattr(part, "function_call") or part.function_call is None:
            return {
                "success": True,
                "response": part.text if hasattr(part, "text") else "",
                "tool_results": all_tool_results,
            }

        # 3. Function call 실행
        function_call = part.function_call
        tool_name = function_call.name
        arguments = dict(function_call.args) if function_call.args else {}

        # Tool 실행
        result = await tool_executor.execute(tool_name, arguments)

        all_tool_results.append({
            "tool": tool_name,
            "arguments": arguments,
            "result": result.data if result.success else {"error": result.error},
            "success": result.success,
        })

        # 4. 대화 이력 업데이트
        contents.append(candidate.content)

        # 5. Function 결과 추가
        function_response = types.Part.from_function_response(
            name=tool_name,
            response=result.data if result.success else {"error": result.error},
        )
        contents.append(types.Content(role="user", parts=[function_response]))

    return {
        "success": True,
        "response": "최대 반복 횟수 도달",
        "tool_results": all_tool_results,
    }
```

## Tool Executor 패턴

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolResult:
    """Tool 실행 결과."""
    tool_name: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class ToolExecutor:
    """Tool 실행기 기본 클래스."""

    def __init__(self, **clients):
        """외부 API 클라이언트 주입."""
        self._clients = clients

    async def execute(self, tool_name: str, arguments: dict) -> ToolResult:
        """Tool 실행.

        Args:
            tool_name: Tool 이름
            arguments: LLM이 생성한 인자

        Returns:
            ToolResult
        """
        # Tool 이름에 해당하는 메서드 호출
        method = getattr(self, f"_execute_{tool_name}", None)
        if method is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
            )

        try:
            return await method(arguments)
        except Exception as e:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    async def _execute_tool_a(self, args: dict) -> ToolResult:
        """Tool A 구현."""
        # 외부 API 호출
        client = self._clients.get("api_a_client")
        response = await client.some_method(args["param1"])
        return ToolResult(
            tool_name="tool_a",
            success=True,
            data={"result": response},
        )
```

## LangGraph 노드로 통합

```python
def create_agent_node(
    tool_executor: ToolExecutor,
    tools: list[dict],
    event_publisher: ProgressNotifierPort,
    openai_client: AsyncOpenAI | None = None,
    gemini_client: genai.Client | None = None,
    default_model: str = "gpt-4o-mini",
    default_provider: str = "openai",
    system_prompt: str = "",
):
    """Function Calling Agent 노드 팩토리.

    Args:
        tool_executor: Tool 실행기
        tools: Tool 정의 리스트
        event_publisher: Progress 알림기
        openai_client: OpenAI 클라이언트 (선택)
        gemini_client: Gemini 클라이언트 (선택)
        default_model: 기본 모델
        default_provider: 기본 프로바이더
        system_prompt: 시스템 프롬프트

    Returns:
        LangGraph 노드 함수
    """

    async def agent_node(state: dict) -> dict:
        """LangGraph 노드."""
        job_id = state.get("job_id", "")
        message = state.get("message", "")

        # 프론트엔드가 보낸 모델/프로바이더 사용
        provider = state.get("llm_provider", default_provider)
        model = state.get("llm_model", default_model)

        await event_publisher.notify_stage(
            task_id=job_id,
            stage="agent",
            status="started",
            message="처리 중...",
        )

        try:
            if provider == "gemini" and gemini_client:
                result = await run_gemini_agent(
                    client=gemini_client,
                    model=model,
                    user_message=message,
                    tools=convert_to_gemini_format(tools),
                    tool_executor=tool_executor,
                    system_prompt=system_prompt,
                )
            elif openai_client:
                result = await run_openai_agent(
                    client=openai_client,
                    model=model,
                    user_message=message,
                    tools=tools,
                    tool_executor=tool_executor,
                    system_prompt=system_prompt,
                )
            else:
                # Fallback 로직
                result = {"success": False, "error": "No LLM client available"}

            await event_publisher.notify_stage(
                task_id=job_id,
                stage="agent",
                status="completed",
            )

            return {
                "agent_context": {
                    "success": result.get("success"),
                    "response": result.get("response"),
                    "tool_results": result.get("tool_results", []),
                },
            }

        except Exception as e:
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="agent",
                status="failed",
                result={"error": str(e)},
            )
            return {"agent_context": {"success": False, "error": str(e)}}

    return agent_node
```

## Dependencies 설정

```python
# dependencies.py

# Raw SDK 클라이언트 싱글톤
_openai_async_client = None
_gemini_client = None


def get_openai_async_client() -> AsyncOpenAI | None:
    """OpenAI AsyncOpenAI 클라이언트 싱글톤."""
    global _openai_async_client
    if _openai_async_client is None:
        settings = get_settings()
        if not settings.openai_api_key:
            return None

        from openai import AsyncOpenAI
        import httpx

        http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        _openai_async_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            http_client=http_client,
            max_retries=3,
        )
    return _openai_async_client


def get_gemini_client() -> genai.Client | None:
    """Google Gemini Client 싱글톤."""
    global _gemini_client
    if _gemini_client is None:
        settings = get_settings()
        if not settings.google_api_key:
            return None

        from google import genai
        _gemini_client = genai.Client(api_key=settings.google_api_key)

    return _gemini_client
```

## 실제 적용 예시: Location Agent

```python
# Tool 정의
LOCATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_places",
            "description": "키워드로 장소 검색",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "geocode",
            "description": "장소명을 좌표로 변환",
            "parameters": {
                "type": "object",
                "properties": {"place_name": {"type": "string"}},
                "required": ["place_name"],
            },
        },
    },
]

# Tool Executor
class KakaoToolExecutor(ToolExecutor):
    async def _execute_search_places(self, args: dict) -> ToolResult:
        response = await self._clients["kakao"].search_keyword(
            query=args["query"],
            x=args.get("longitude"),
            y=args.get("latitude"),
        )
        return ToolResult(tool_name="search_places", success=True, data={...})

    async def _execute_geocode(self, args: dict) -> ToolResult:
        response = await self._clients["kakao"].search_keyword(
            query=args["place_name"], size=1
        )
        if response.places:
            return ToolResult(
                tool_name="geocode",
                success=True,
                data={"lat": ..., "lon": ...},
            )
        return ToolResult(tool_name="geocode", success=False, error="Not found")

# 노드 생성
location_node = create_agent_node(
    tool_executor=KakaoToolExecutor(kakao=kakao_client),
    tools=LOCATION_TOOLS,
    event_publisher=event_publisher,
    openai_client=openai_client,
    gemini_client=gemini_client,
    system_prompt="당신은 위치 기반 검색을 도와주는 어시스턴트입니다...",
)
```

## Best Practices

1. **Tool Description**: LLM이 언제 Tool을 사용해야 하는지 명확하게 설명
2. **Parameter Description**: 각 파라미터의 용도와 형식을 상세히 기술
3. **Error Handling**: Tool 실행 실패 시 의미 있는 에러 메시지 반환
4. **Max Iterations**: 무한 루프 방지를 위해 최대 반복 횟수 설정
5. **Fallback**: LLM 클라이언트 없을 때 대체 로직 제공

## Reference

- OpenAI: https://platform.openai.com/docs/guides/function-calling
- Gemini: https://ai.google.dev/gemini-api/docs/function-calling
- LangGraph: https://langchain-ai.github.io/langgraph/
