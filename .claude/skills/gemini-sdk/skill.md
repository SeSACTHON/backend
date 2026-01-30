---
name: gemini-sdk
description: Google Gemini SDK (google-genai) 활용 가이드. Gemini 3/2 모델, Structured Output, Function Calling, Google Search Grounding, 이미지 생성 구현 시 참조. "gemini", "google ai", "genai", "google search", "imagen" 키워드로 트리거.
---

# Google Gemini SDK Guide (google-genai)

## 개요

Google Gemini SDK는 Gemini 모델 접근을 위한 공식 Python 라이브러리.
Gemini 3 시리즈부터 Parallel & Compositional Function Calling 지원.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Gemini SDK Architecture                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      genai.Client                                  │   │
│  │  - api_key: GOOGLE_API_KEY                                        │   │
│  │  - aio: 비동기 API (aio.models.generate_content)                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│            ┌─────────────────┼─────────────────┐                        │
│            ▼                 ▼                 ▼                        │
│  ┌─────────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ generate_content │  │  Function   │  │   Google    │                 │
│  │ (Text/Streaming) │  │   Calling   │  │   Search    │                 │
│  └─────────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                          │
│  Supported Models:                                                       │
│  - gemini-3-pro-preview (최신)                                          │
│  - gemini-3-flash-preview (빠름)                                        │
│  - gemini-2.0-flash-exp                                                 │
│  - gemini-1.5-pro / gemini-1.5-flash                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 설치

```bash
pip install google-genai
```

## 클라이언트 초기화

```python
from google import genai

# 클라이언트 생성
client = genai.Client(api_key="GOOGLE_API_KEY")

# 또는 환경변수 사용
import os
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
```

## 기본 텍스트 생성

### 동기 호출

```python
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="재활용 방법 알려줘",
)

print(response.text)
```

### 비동기 호출

```python
response = await client.aio.models.generate_content(
    model="gemini-3-flash-preview",
    contents="재활용 방법 알려줘",
)

print(response.text)
```

### 스트리밍

```python
response = await client.aio.models.generate_content_stream(
    model="gemini-3-flash-preview",
    contents="재활용 방법 알려줘",
)

async for chunk in response:
    if chunk.text:
        print(chunk.text, end="", flush=True)
```

## GenerateContentConfig

```python
from google.genai import types

config = types.GenerateContentConfig(
    # 시스템 프롬프트
    system_instruction="당신은 환경 전문가입니다.",

    # 온도 (0~2, 기본 1)
    temperature=0.7,

    # 최대 토큰
    max_output_tokens=2048,

    # Top-P
    top_p=0.95,

    # Top-K
    top_k=40,

    # 안전 설정
    safety_settings=[
        types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="BLOCK_ONLY_HIGH",
        ),
    ],

    # Tool 설정
    tools=[...],
    tool_config=types.ToolConfig(...),

    # Structured Output
    response_mime_type="application/json",
    response_schema=MySchema,
)

response = await client.aio.models.generate_content(
    model="gemini-3-flash-preview",
    contents="재활용 방법",
    config=config,
)
```

## Structured Output

### Pydantic 스키마 사용

```python
from pydantic import BaseModel
from google.genai import types

class IntentClassification(BaseModel):
    intent: str
    confidence: float
    reasoning: str

config = types.GenerateContentConfig(
    system_instruction="사용자 메시지의 의도를 분류합니다.",
    response_mime_type="application/json",
    response_schema=IntentClassification,
    temperature=0,  # 결정론적 출력
)

response = await client.aio.models.generate_content(
    model="gemini-3-flash-preview",
    contents="재활용센터 어디 있어?",
    config=config,
)

# JSON 파싱
import json
data = json.loads(response.text)
result = IntentClassification.model_validate(data)
```

### 스키마 직접 정의

```python
config = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema={
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["intent", "confidence"],
    },
)
```

## Function Calling

### Function Declaration 정의

```python
from google.genai import types

# Tool 정의
search_places_decl = types.FunctionDeclaration(
    name="search_places",
    description=(
        "키워드 기반 장소 검색. "
        "사용 시점: 재활용센터, 제로웨이스트샵 등 특정 장소를 찾을 때."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "검색 키워드 (예: '재활용센터')",
            },
            "latitude": {
                "type": "number",
                "description": "검색 중심 위도",
            },
            "longitude": {
                "type": "number",
                "description": "검색 중심 경도",
            },
        },
        "required": ["query"],
    },
)

geocode_decl = types.FunctionDeclaration(
    name="geocode",
    description="장소명을 좌표로 변환. 지역명 언급 시 먼저 호출.",
    parameters={
        "type": "object",
        "properties": {
            "place_name": {
                "type": "string",
                "description": "변환할 장소명 (예: '강남역')",
            },
        },
        "required": ["place_name"],
    },
)
```

### Tool 설정

```python
# Tool 생성
tool = types.Tool(function_declarations=[search_places_decl, geocode_decl])

# Function Calling Mode
# - AUTO: 모델이 텍스트/함수 자동 선택 (기본)
# - ANY: 항상 함수 호출
# - NONE: 함수 호출 금지
# - VALIDATED: 스키마 준수 보장

config = types.GenerateContentConfig(
    system_instruction="위치 기반 검색 에이전트입니다.",
    tools=[tool],
    tool_config=types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.AUTO,
            # 특정 함수만 허용 (ANY 모드에서)
            # allowed_function_names=["search_places"],
        ),
    ),
)
```

### Agent Loop 구현

```python
async def run_gemini_agent(
    client: genai.Client,
    model: str,
    message: str,
    tool_declarations: list[types.FunctionDeclaration],
    tool_executor: ToolExecutor,
    system_prompt: str,
    max_iterations: int = 5,
) -> dict:
    """Gemini Function Calling Agent Loop."""

    tool = types.Tool(function_declarations=tool_declarations)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[tool],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.AUTO,
            ),
        ),
        temperature=0,  # 결정론적 Tool 선택
    )

    contents = [message]
    all_tool_results = []

    for iteration in range(max_iterations):
        # 1. Gemini 호출
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]

        # 2. Function call 확인
        function_calls = []
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_calls.append(part.function_call)

        # Function call이 없으면 최종 응답
        if not function_calls:
            final_text = ""
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text += part.text
            return {
                "success": True,
                "response": final_text,
                "tool_results": all_tool_results,
            }

        # 3. 대화 이력에 Assistant 응답 추가
        contents.append(candidate.content)

        # 4. Function 실행 (병렬)
        function_response_parts = []
        for fc in function_calls:
            tool_name = fc.name
            arguments = dict(fc.args) if fc.args else {}

            result = await tool_executor.execute(tool_name, arguments)

            all_tool_results.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": result.data if result.success else {"error": result.error},
                "success": result.success,
            })

            # Function Response Part 생성
            function_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response=result.data if result.success else {"error": result.error},
                )
            )

        # 5. Function 결과를 대화 이력에 추가
        contents.append(types.Content(role="user", parts=function_response_parts))

    return {
        "success": True,
        "response": "최대 반복 횟수 도달",
        "tool_results": all_tool_results,
    }
```

## Google Search Grounding

### 실시간 웹 검색

```python
# Google Search Tool
google_search_tool = types.Tool(google_search=types.GoogleSearch())

config = types.GenerateContentConfig(
    system_instruction="최신 정보를 검색하여 답변합니다.",
    tools=[google_search_tool],
)

response = await client.aio.models.generate_content(
    model="gemini-3-flash-preview",
    contents="오늘 서울 날씨 알려줘",
    config=config,
)

# Grounding metadata 확인
if response.candidates[0].grounding_metadata:
    for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
        print(f"Source: {chunk.web.uri}")
```

### Grounding + Function Calling 조합

```python
# Google Search와 Custom Function 동시 사용
config = types.GenerateContentConfig(
    tools=[
        types.Tool(google_search=types.GoogleSearch()),  # 웹 검색
        types.Tool(function_declarations=[search_places_decl]),  # 커스텀 함수
    ],
)
```

## 이미지 생성 (Imagen)

### Gemini 3 Pro Image

```python
from google.genai import types

# 이미지 생성 모델
IMAGE_MODEL = "gemini-3-pro-image-preview"

config = types.GenerateContentConfig(
    response_modalities=["image", "text"],  # 이미지 + 텍스트
)

response = await client.aio.models.generate_content(
    model=IMAGE_MODEL,
    contents="귀여운 재활용 마스코트 캐릭터를 그려줘",
    config=config,
)

# 이미지 추출
for part in response.candidates[0].content.parts:
    if hasattr(part, "inline_data") and part.inline_data:
        image_data = part.inline_data.data
        mime_type = part.inline_data.mime_type  # image/png 등

        # 파일로 저장
        import base64
        with open("character.png", "wb") as f:
            f.write(base64.b64decode(image_data))
```

### 이미지 해상도 설정

```python
config = types.GenerateContentConfig(
    response_modalities=["image"],
    image_generation_config=types.ImageGenerationConfig(
        # 해상도 (1024x1024, 1024x1792, 1792x1024)
        output_mime_type="image/png",
    ),
)
```

## Eco² 실제 구현 패턴

### GeminiLLMClient

```python
# apps/chat_worker/infrastructure/llm/clients/gemini_client.py

class GeminiLLMClient(LLMClientPort):
    """Gemini LLM 클라이언트."""

    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        api_key: str | None = None,
    ):
        self._model = model
        self._client = genai.Client(api_key=api_key or os.environ["GOOGLE_API_KEY"])

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0,
        max_tokens: int = 2048,
    ) -> T:
        """Structured Output 생성."""
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )

        data = json.loads(response.text or "{}")
        return response_schema.model_validate(data)

    async def generate_function_call(
        self,
        prompt: str,
        functions: list[dict],
        system_prompt: str | None = None,
        function_call: str | dict = "auto",
    ) -> tuple[str, dict] | None:
        """Function Calling."""
        # OpenAI format → Gemini FunctionDeclaration
        function_declarations = []
        for func in functions:
            func_decl = types.FunctionDeclaration(
                name=func["name"],
                description=func.get("description", ""),
                parameters=func.get("parameters"),
            )
            function_declarations.append(func_decl)

        tool = types.Tool(function_declarations=function_declarations)

        # Mode 설정
        fc_mode = types.FunctionCallingConfigMode.AUTO
        allowed_names = None
        if isinstance(function_call, dict) and "name" in function_call:
            fc_mode = types.FunctionCallingConfigMode.ANY
            allowed_names = [function_call["name"]]
        elif function_call == "none":
            fc_mode = types.FunctionCallingConfigMode.NONE

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=fc_mode,
                    allowed_function_names=allowed_names,
                ),
            ),
            temperature=0,
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )

        # Function call 추출
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    return (
                        part.function_call.name,
                        dict(part.function_call.args) if part.function_call.args else {},
                    )
        return None

    async def generate_with_tools_stream(
        self,
        prompt: str,
        tools: list[str],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Tool 사용 스트리밍."""
        tool_configs = []
        for tool in tools:
            if tool == "web_search":
                tool_configs.append(types.Tool(google_search=types.GoogleSearch()))

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tool_configs if tool_configs else None,
        )

        response = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=prompt,
            config=config,
        )

        async for chunk in response:
            if chunk.text:
                yield chunk.text
```

## 모델 가격 (2025)

| Model | Input ($/1M tokens) | Output ($/1M tokens) |
|-------|---------------------|----------------------|
| gemini-3-pro-preview | $2.00 | $12.00 |
| gemini-3-flash-preview | $0.50 | $3.00 |
| gemini-2.0-flash | $0.10 | $0.40 |
| gemini-1.5-pro | $1.25 | $5.00 |
| gemini-1.5-flash | $0.075 | $0.30 |

## Best Practices

1. **temperature=0**: Function Calling 시 결정론적 Tool 선택
2. **Parallel Calling**: 여러 Function을 한 번에 호출 (Gemini 3)
3. **VALIDATED Mode**: 스키마 준수가 중요할 때 사용
4. **Google Search**: 실시간 정보 필요 시 Grounding 활용
5. **max_output_tokens**: 적절히 설정하여 비용 관리

## Reference

- [Google Gemini API Docs](https://ai.google.dev/gemini-api/docs)
- [Function Calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Structured Output](https://ai.google.dev/gemini-api/docs/json-mode)
- [google-genai PyPI](https://pypi.org/project/google-genai/)
