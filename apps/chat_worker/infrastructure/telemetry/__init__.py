"""Telemetry - OpenTelemetry 분산 추적.

ADR P2: 노드별 span 속성 추가.

사용 예:
    ```python
    from chat_worker.infrastructure.telemetry import get_tracer, with_span

    @with_span("waste_rag_node")
    async def waste_rag_node(state: dict[str, Any]) -> dict[str, Any]:
        ...

    # 또는 수동 span 생성
    tracer = get_tracer()
    with tracer.start_as_current_span("my_span") as span:
        span.set_attribute("key", "value")
    ```
"""

from chat_worker.infrastructure.telemetry.tracer import (
    get_tracer,
    set_span_attributes,
    with_span,
)

__all__ = [
    "get_tracer",
    "set_span_attributes",
    "with_span",
]
