"""Location Agent Node - LLM with Kakao API Tools.

LLM이 Kakao Map API를 Tool로 사용하여 장소 검색을 수행하는 에이전트 노드.

Architecture:
- LLM이 사용자 메시지를 분석하여 적절한 Tool 선택
- Tool 실행 결과를 LLM이 해석하여 자연어 context 생성
- OpenAI/Gemini 모두 지원 (Function Calling)

Tools:
- search_places: 키워드로 장소 검색 (재활용센터, 제로웨이스트샵 등)
- search_category: 카테고리로 주변 장소 검색 (카페, 음식점 등)
- geocode: 장소명을 좌표로 변환

Flow:
    Router → location_agent → Answer
             └─ LLM analyzes message
             └─ LLM calls tools (Kakao API)
             └─ LLM interprets results
             └─ Returns location_context
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from chat_worker.application.ports.kakao_local_client import (
    KakaoCategoryGroup,
    KakaoSearchResponse,
)
from chat_worker.infrastructure.orchestration.langgraph.context_helper import (
    create_context,
    create_error_context,
)

if TYPE_CHECKING:
    from chat_worker.application.ports.events import ProgressNotifierPort
    from chat_worker.application.ports.kakao_local_client import KakaoLocalClientPort

logger = logging.getLogger(__name__)


# ============================================================
# Tool Definitions
# ============================================================


class ToolName(str, Enum):
    """사용 가능한 Tool 이름."""

    SEARCH_PLACES = "search_places"
    SEARCH_CATEGORY = "search_category"
    GEOCODE = "geocode"


# OpenAI Function Calling 형식
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_places",
            "description": "키워드로 장소를 검색합니다. 재활용센터, 제로웨이스트샵, 특정 가게 등을 검색할 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 키워드 (예: '강남역 재활용센터', '홍대 제로웨이스트샵')",
                    },
                    "latitude": {
                        "type": "number",
                        "description": "검색 중심 위도 (선택사항)",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "검색 중심 경도 (선택사항)",
                    },
                    "radius": {
                        "type": "integer",
                        "description": "검색 반경 (미터, 기본 5000)",
                        "default": 5000,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_category",
            "description": "카테고리로 주변 장소를 검색합니다. 주변 카페, 음식점, 편의점 등을 찾을 때 사용합니다. 좌표가 필수입니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "MART",
                            "CONVENIENCE",
                            "SUBWAY",
                            "CAFE",
                            "RESTAURANT",
                            "HOSPITAL",
                            "PHARMACY",
                            "BANK",
                            "GAS_STATION",
                            "PARKING",
                        ],
                        "description": "카테고리 (MART: 대형마트, CONVENIENCE: 편의점, SUBWAY: 지하철역, CAFE: 카페, RESTAURANT: 음식점, HOSPITAL: 병원, PHARMACY: 약국)",
                    },
                    "latitude": {
                        "type": "number",
                        "description": "검색 중심 위도 (필수)",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "검색 중심 경도 (필수)",
                    },
                    "radius": {
                        "type": "integer",
                        "description": "검색 반경 (미터, 기본 5000)",
                        "default": 5000,
                    },
                },
                "required": ["category", "latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "geocode",
            "description": "장소명이나 주소를 좌표(위도, 경도)로 변환합니다. 사용자가 특정 지역 주변을 검색하고 싶을 때 먼저 좌표를 얻는 데 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "place_name": {
                        "type": "string",
                        "description": "장소명 또는 주소 (예: '강남역', '서울시 강남구')",
                    },
                },
                "required": ["place_name"],
            },
        },
    },
]

# Gemini Function Calling 형식
GEMINI_TOOLS = [
    {
        "name": "search_places",
        "description": "키워드로 장소를 검색합니다. 재활용센터, 제로웨이스트샵, 특정 가게 등을 검색할 때 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 키워드 (예: '강남역 재활용센터', '홍대 제로웨이스트샵')",
                },
                "latitude": {
                    "type": "number",
                    "description": "검색 중심 위도 (선택사항)",
                },
                "longitude": {
                    "type": "number",
                    "description": "검색 중심 경도 (선택사항)",
                },
                "radius": {
                    "type": "integer",
                    "description": "검색 반경 (미터, 기본 5000)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_category",
        "description": "카테고리로 주변 장소를 검색합니다. 주변 카페, 음식점, 편의점 등을 찾을 때 사용합니다. 좌표가 필수입니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "MART",
                        "CONVENIENCE",
                        "SUBWAY",
                        "CAFE",
                        "RESTAURANT",
                        "HOSPITAL",
                        "PHARMACY",
                        "BANK",
                        "GAS_STATION",
                        "PARKING",
                    ],
                    "description": "카테고리",
                },
                "latitude": {
                    "type": "number",
                    "description": "검색 중심 위도 (필수)",
                },
                "longitude": {
                    "type": "number",
                    "description": "검색 중심 경도 (필수)",
                },
                "radius": {
                    "type": "integer",
                    "description": "검색 반경 (미터, 기본 5000)",
                },
            },
            "required": ["category", "latitude", "longitude"],
        },
    },
    {
        "name": "geocode",
        "description": "장소명이나 주소를 좌표(위도, 경도)로 변환합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "place_name": {
                    "type": "string",
                    "description": "장소명 또는 주소 (예: '강남역', '서울시 강남구')",
                },
            },
            "required": ["place_name"],
        },
    },
]

# System prompt for location agent
LOCATION_AGENT_SYSTEM_PROMPT = """당신은 위치 기반 장소 검색을 도와주는 어시스턴트입니다.

사용자의 요청을 분석하여 적절한 도구를 선택하고 실행하세요.

사용 가능한 도구:
1. search_places: 키워드로 장소 검색 (재활용센터, 제로웨이스트샵 등)
2. search_category: 카테고리로 주변 검색 (카페, 음식점 등) - 좌표 필수
3. geocode: 장소명 → 좌표 변환

검색 전략:
- 사용자가 특정 지역을 언급하면 먼저 geocode로 좌표를 얻은 후 검색
- 사용자 위치(user_location)가 있으면 그 좌표를 활용
- "근처", "주변" 같은 표현이 있으면 좌표 기반 검색 필요

예시:
- "강남역 근처 재활용센터" → geocode("강남역") → search_places("재활용센터", lat, lon)
- "주변 카페 찾아줘" (user_location 있음) → search_category("CAFE", lat, lon)
- "제로웨이스트샵 알려줘" → search_places("제로웨이스트샵")

결과를 사용자가 이해하기 쉬운 형태로 정리해서 제공하세요."""


# ============================================================
# Tool Result Dataclass
# ============================================================


@dataclass
class ToolResult:
    """Tool 실행 결과."""

    tool_name: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


# ============================================================
# Tool Executor
# ============================================================


class KakaoToolExecutor:
    """Kakao API Tool 실행기."""

    def __init__(self, kakao_client: "KakaoLocalClientPort"):
        self._kakao_client = kakao_client

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Tool 실행.

        Args:
            tool_name: Tool 이름
            arguments: Tool 인자

        Returns:
            ToolResult
        """
        try:
            if tool_name == ToolName.SEARCH_PLACES:
                return await self._search_places(arguments)
            elif tool_name == ToolName.SEARCH_CATEGORY:
                return await self._search_category(arguments)
            elif tool_name == ToolName.GEOCODE:
                return await self._geocode(arguments)
            else:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Unknown tool: {tool_name}",
                )
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    async def _search_places(self, args: dict[str, Any]) -> ToolResult:
        """키워드 장소 검색."""
        query = args.get("query", "")
        lat = args.get("latitude")
        lon = args.get("longitude")
        radius = args.get("radius", 5000)

        response = await self._kakao_client.search_keyword(
            query=query,
            x=lon,  # Kakao API는 x=경도, y=위도
            y=lat,
            radius=radius,
            size=10,
            sort="distance" if lat and lon else "accuracy",
        )

        return ToolResult(
            tool_name=ToolName.SEARCH_PLACES,
            success=True,
            data=self._format_search_response(response),
        )

    async def _search_category(self, args: dict[str, Any]) -> ToolResult:
        """카테고리 장소 검색."""
        category = args.get("category", "")
        lat = args.get("latitude")
        lon = args.get("longitude")
        radius = args.get("radius", 5000)

        if lat is None or lon is None:
            return ToolResult(
                tool_name=ToolName.SEARCH_CATEGORY,
                success=False,
                error="카테고리 검색에는 좌표(latitude, longitude)가 필수입니다.",
            )

        # Category enum 매핑
        category_code = getattr(KakaoCategoryGroup, category, None)
        if category_code is None:
            return ToolResult(
                tool_name=ToolName.SEARCH_CATEGORY,
                success=False,
                error=f"알 수 없는 카테고리: {category}",
            )

        response = await self._kakao_client.search_category(
            category_group_code=category_code.value,
            x=lon,
            y=lat,
            radius=radius,
            size=10,
            sort="distance",
        )

        return ToolResult(
            tool_name=ToolName.SEARCH_CATEGORY,
            success=True,
            data=self._format_search_response(response),
        )

    async def _geocode(self, args: dict[str, Any]) -> ToolResult:
        """장소명 → 좌표 변환 (Geocoding)."""
        place_name = args.get("place_name", "")

        # search_keyword로 geocoding (첫 번째 결과 사용)
        response = await self._kakao_client.search_keyword(
            query=place_name,
            size=1,
        )

        if not response.places:
            return ToolResult(
                tool_name=ToolName.GEOCODE,
                success=False,
                error=f"'{place_name}'에 대한 좌표를 찾을 수 없습니다.",
            )

        place = response.places[0]
        return ToolResult(
            tool_name=ToolName.GEOCODE,
            success=True,
            data={
                "place_name": place.place_name,
                "address": place.road_address_name or place.address_name,
                "latitude": place.latitude,
                "longitude": place.longitude,
            },
        )

    def _format_search_response(self, response: KakaoSearchResponse) -> dict[str, Any]:
        """검색 응답을 LLM이 이해하기 쉬운 형태로 변환."""
        places = []
        for p in response.places[:10]:  # 최대 10개
            places.append({
                "name": p.place_name,
                "address": p.road_address_name or p.address_name,
                "phone": p.phone,
                "distance": p.distance_text,
                "category": p.category_name,
                "url": p.place_url,
                "latitude": p.latitude,
                "longitude": p.longitude,
            })

        return {
            "query": response.query,
            "total_count": response.meta.total_count if response.meta else 0,
            "places": places,
            "found": len(places) > 0,
        }


# ============================================================
# OpenAI Function Calling Handler
# ============================================================


async def run_openai_agent(
    openai_client: Any,  # openai.AsyncOpenAI
    model: str,
    message: str,
    user_location: dict[str, float] | None,
    tool_executor: KakaoToolExecutor,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """OpenAI Function Calling으로 Location Agent 실행.

    Args:
        openai_client: OpenAI AsyncClient
        model: 모델명
        message: 사용자 메시지
        user_location: 사용자 위치 {latitude, longitude}
        tool_executor: Kakao Tool 실행기
        max_iterations: 최대 반복 횟수

    Returns:
        Agent 결과 (places, summary 등)
    """
    # 사용자 위치 정보를 메시지에 포함
    user_message = message
    if user_location:
        lat = user_location.get("latitude") or user_location.get("lat")
        lon = user_location.get("longitude") or user_location.get("lon")
        if lat and lon:
            user_message = f"{message}\n\n[현재 위치: 위도 {lat}, 경도 {lon}]"

    messages = [
        {"role": "system", "content": LOCATION_AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    all_tool_results: list[dict[str, Any]] = []

    for iteration in range(max_iterations):
        logger.debug(f"OpenAI agent iteration {iteration + 1}")

        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        # Tool call이 없으면 최종 응답
        if not assistant_message.tool_calls:
            return {
                "success": True,
                "summary": assistant_message.content,
                "tool_results": all_tool_results,
            }

        # Tool calls 처리
        messages.append(assistant_message.model_dump())

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            logger.info(
                "Executing tool",
                extra={"tool": tool_name, "args": arguments},
            )

            # Tool 실행
            result = await tool_executor.execute(tool_name, arguments)
            all_tool_results.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": result.data if result.success else {"error": result.error},
                "success": result.success,
            })

            # Tool 결과를 메시지에 추가
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
        "summary": "검색 결과를 처리했습니다.",
        "tool_results": all_tool_results,
    }


# ============================================================
# Gemini Function Calling Handler
# ============================================================


async def run_gemini_agent(
    gemini_client: Any,  # google.genai.Client
    model: str,
    message: str,
    user_location: dict[str, float] | None,
    tool_executor: KakaoToolExecutor,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """Gemini Function Calling으로 Location Agent 실행.

    Args:
        gemini_client: Gemini Client
        model: 모델명
        message: 사용자 메시지
        user_location: 사용자 위치 {latitude, longitude}
        tool_executor: Kakao Tool 실행기
        max_iterations: 최대 반복 횟수

    Returns:
        Agent 결과 (places, summary 등)
    """
    from google.genai import types

    # 사용자 위치 정보를 메시지에 포함
    user_message = message
    if user_location:
        lat = user_location.get("latitude") or user_location.get("lat")
        lon = user_location.get("longitude") or user_location.get("lon")
        if lat and lon:
            user_message = f"{message}\n\n[현재 위치: 위도 {lat}, 경도 {lon}]"

    # Gemini Tool 설정
    tools = types.Tool(function_declarations=GEMINI_TOOLS)
    config = types.GenerateContentConfig(
        tools=[tools],
        system_instruction=LOCATION_AGENT_SYSTEM_PROMPT,
    )

    contents = [user_message]
    all_tool_results: list[dict[str, Any]] = []

    for iteration in range(max_iterations):
        logger.debug(f"Gemini agent iteration {iteration + 1}")

        response = await gemini_client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        # Function call 확인
        candidate = response.candidates[0]
        part = candidate.content.parts[0]

        if not hasattr(part, "function_call") or part.function_call is None:
            # 최종 텍스트 응답
            return {
                "success": True,
                "summary": part.text if hasattr(part, "text") else "",
                "tool_results": all_tool_results,
            }

        # Function call 처리
        function_call = part.function_call
        tool_name = function_call.name
        arguments = dict(function_call.args) if function_call.args else {}

        logger.info(
            "Executing tool (Gemini)",
            extra={"tool": tool_name, "args": arguments},
        )

        # Tool 실행
        result = await tool_executor.execute(tool_name, arguments)
        all_tool_results.append({
            "tool": tool_name,
            "arguments": arguments,
            "result": result.data if result.success else {"error": result.error},
            "success": result.success,
        })

        # 대화 이력에 추가
        contents.append(candidate.content)

        # Function 결과 추가
        function_response = types.Part.from_function_response(
            name=tool_name,
            response=result.data if result.success else {"error": result.error},
        )
        contents.append(types.Content(role="user", parts=[function_response]))

    # Max iterations 도달
    return {
        "success": True,
        "summary": "검색 결과를 처리했습니다.",
        "tool_results": all_tool_results,
    }


# ============================================================
# Location Agent Node Factory
# ============================================================


def create_location_agent_node(
    kakao_client: "KakaoLocalClientPort",
    event_publisher: "ProgressNotifierPort",
    openai_client: Any | None = None,
    gemini_client: Any | None = None,
    default_model: str = "gpt-4o-mini",
    default_provider: str = "openai",
):
    """Location Agent 노드 팩토리.

    LLM이 Kakao API를 Tool로 사용하여 장소 검색을 수행.

    Args:
        kakao_client: Kakao Local API 클라이언트
        event_publisher: 이벤트 발행기
        openai_client: OpenAI AsyncClient (선택)
        gemini_client: Gemini Client (선택)
        default_model: 기본 모델명
        default_provider: 기본 프로바이더 ("openai" | "gemini")

    Returns:
        location_agent_node 함수
    """
    tool_executor = KakaoToolExecutor(kakao_client)

    async def location_agent_node(state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph Location Agent 노드.

        Args:
            state: 현재 LangGraph 상태

        Returns:
            업데이트된 상태 (location_context)
        """
        job_id = state.get("job_id", "")
        message = state.get("message", "")
        user_location = state.get("user_location")

        # Progress: 시작
        await event_publisher.notify_stage(
            task_id=job_id,
            stage="location",
            status="started",
            progress=45,
            message="장소 검색 중...",
        )

        try:
            # Provider 선택 (state에서 override 가능)
            provider = state.get("llm_provider", default_provider)
            model = state.get("llm_model", default_model)

            if provider == "gemini" and gemini_client is not None:
                result = await run_gemini_agent(
                    gemini_client=gemini_client,
                    model=model,
                    message=message,
                    user_location=user_location,
                    tool_executor=tool_executor,
                )
            elif openai_client is not None:
                result = await run_openai_agent(
                    openai_client=openai_client,
                    model=model,
                    message=message,
                    user_location=user_location,
                    tool_executor=tool_executor,
                )
            else:
                # Fallback: 직접 키워드 검색
                logger.warning("No LLM client available, falling back to direct search")
                response = await kakao_client.search_keyword(query=message, size=10)
                result = {
                    "success": True,
                    "summary": None,
                    "tool_results": [{
                        "tool": "search_places",
                        "result": tool_executor._format_search_response(response),
                        "success": True,
                    }],
                }

            # 결과에서 장소 정보 추출
            places = []
            for tr in result.get("tool_results", []):
                if tr.get("success") and tr.get("result", {}).get("places"):
                    places.extend(tr["result"]["places"])

            # Progress: 완료
            found = len(places) > 0
            await event_publisher.notify_stage(
                task_id=job_id,
                stage="location",
                status="completed",
                progress=55,
                result={
                    "found": found,
                    "count": len(places),
                },
                message=f"{len(places)}개 장소 검색 완료" if found else "검색 결과 없음",
            )

            # location_context 생성
            context_data = {
                "found": found,
                "places": places[:10],  # 최대 10개
                "summary": result.get("summary"),
                "tool_calls": [
                    {"tool": tr["tool"], "success": tr["success"]}
                    for tr in result.get("tool_results", [])
                ],
            }

            return {
                "location_context": create_context(
                    data=context_data,
                    producer="location",
                    job_id=job_id,
                ),
            }

        except Exception as e:
            logger.exception("Location agent failed")

            await event_publisher.notify_stage(
                task_id=job_id,
                stage="location",
                status="failed",
                result={"error": str(e)},
            )

            return {
                "location_context": create_error_context(
                    producer="location",
                    job_id=job_id,
                    error=str(e),
                ),
            }

    return location_agent_node


__all__ = [
    "create_location_agent_node",
    "OPENAI_TOOLS",
    "GEMINI_TOOLS",
    "KakaoToolExecutor",
]
