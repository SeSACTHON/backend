# Chat Agent Architecture Reference

> Chat Worker의 전체 아키텍처 및 컴포넌트 구조

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Chat Agent System Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Client                                                                      │
│  ┌─────────────────┐                                                        │
│  │  Frontend/curl  │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│  ─────────┼──────────────────────────────────────────────────────────────── │
│           │                                                                  │
│  Istio Gateway (api.growbin.app)                                            │
│  ┌────────▼────────┐                                                        │
│  │  eco2-gateway   │ Cookie → Header 변환 (EnvoyFilter)                     │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│  ─────────┼──────────────────────────────────────────────────────────────── │
│           │                                                                  │
│  VirtualService Routing                                                      │
│  ┌────────▼────────┐    ┌──────────────────┐                               │
│  │    chat-vs      │    │  sse-gateway-vs  │                               │
│  │ /api/v1/chat/*  │    │ /api/v1/sse/*    │                               │
│  └────────┬────────┘    └────────┬─────────┘                               │
│           │                      │                                          │
│  ─────────┼──────────────────────┼──────────────────────────────────────── │
│           │                      │                                          │
│  Services │                      │                                          │
│  ┌────────▼────────┐    ┌────────▼─────────┐                               │
│  │    chat-api     │    │   sse-gateway    │                               │
│  │  (namespace:    │    │  (namespace:     │                               │
│  │   chat)         │    │   sse-consumer)  │                               │
│  └────────┬────────┘    └────────▲─────────┘                               │
│           │                      │                                          │
│  ─────────┼──────────────────────┼──────────────────────────────────────── │
│           │                      │                                          │
│  Message Queue                   │ Pub/Sub                                  │
│  ┌────────▼────────┐    ┌────────┴─────────┐                               │
│  │    RabbitMQ     │    │  Redis Pub/Sub   │                               │
│  │  chat_tasks_q   │    │  sse:events:*    │                               │
│  │  (DIRECT)       │    │                  │                               │
│  └────────┬────────┘    └────────▲─────────┘                               │
│           │                      │                                          │
│  ─────────┼──────────────────────┼──────────────────────────────────────── │
│           │                      │                                          │
│  Worker   │                      │                                          │
│  ┌────────▼────────┐    ┌────────┴─────────┐                               │
│  │  chat-worker    │───▶│   event-router   │                               │
│  │  (LangGraph)    │    │  (Lua Script)    │                               │
│  │                 │    │                  │                               │
│  │  TaskIQ +       │    │  Redis Streams   │                               │
│  │  astream_events │    │  → Pub/Sub       │                               │
│  └─────────────────┘    └──────────────────┘                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## LangGraph Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LangGraph Chat Pipeline                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [Entry] ──▶ [vision_node] ──▶ [intent_node] ──▶ [router_node]              │
│                   │                  │                 │                     │
│                   │           Intent 분류        Dynamic Router              │
│                   │           (LLM + Keyword)    (Send API)                  │
│              이미지 분류            │                 │                     │
│              (선택)                 ▼                 ▼                     │
│                          ┌─────────────────────────────────┐                │
│                          │         Parallel Execution       │                │
│                          │  ┌────────┐ ┌────────┐ ┌──────┐ │                │
│                          │  │waste_  │ │collect │ │weath │ │                │
│                          │  │  rag   │ │ _point │ │  er  │ │                │
│                          │  └────┬───┘ └───┬────┘ └──┬───┘ │                │
│                          │       │         │         │      │                │
│                          │       └─────────┼─────────┘      │                │
│                          │                 │                │                │
│                          └─────────────────┼────────────────┘                │
│                                            ▼                                 │
│                                   [aggregator_node]                          │
│                                            │                                 │
│                                      컨텍스트 수집                            │
│                                            │                                 │
│                                            ▼                                 │
│                                    [answer_node]                             │
│                                            │                                 │
│                                    LLM 답변 생성                              │
│                                   (Token Streaming)                          │
│                                            │                                 │
│                                            ▼                                 │
│                                   [feedback_node]                            │
│                                            │                                 │
│                                    품질 평가                                  │
│                                  (Fallback Loop)                             │
│                                            │                                 │
│                                            ▼                                 │
│                                         [END]                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Node Details

### Core Nodes

| Node | Purpose | External API |
|------|---------|--------------|
| `vision_node` | 이미지 기반 폐기물 분류 | OpenAI Vision API |
| `intent_node` | Intent 분류 (9개 카테고리) | LLM (Structured Output) |
| `router_node` | Dynamic Routing (Send API) | - |
| `aggregator_node` | 컨텍스트 수집 및 검증 | - |
| `answer_node` | 최종 답변 생성 (토큰 스트리밍) | LLM |
| `feedback_node` | 답변 품질 평가 | LLM (Judge) |

### Subagent Nodes

| Node | Purpose | External API | Timeout |
|------|---------|--------------|---------|
| `waste_rag` | 분리배출 규칙 검색 | Local JSON | 8s |
| `character` | 캐릭터 정보 조회 | gRPC (character-grpc) | 5s |
| `location` | 장소 검색 | Kakao Local API | 5s |
| `bulk_waste` | 대형폐기물 정보 | 행정안전부 API | 8s |
| `recyclable_price` | 재활용 시세 | 한국환경공단 API | 5s |
| `collection_point` | 수거함 위치 | KECO API | 8s |
| `web_search` | 웹 검색 | DuckDuckGo/Tavily | 10s |
| `image_generation` | 이미지 생성 | OpenAI DALL-E / Gemini | 30s |
| `weather` | 날씨 정보 (enrichment) | 기상청 API | 8s |
| `general` | 일반 대화 | LLM Direct | 5s |

## Enrichment Rules

```python
ENRICHMENT_RULES = {
    "waste": ("weather",),       # 분리배출 → 날씨 팁
    "bulk_waste": ("weather",),  # 대형폐기물 → 날씨 팁
}

# Conditional Enrichment
if user_location is not None and intent not in {"weather", "general", "character"}:
    add("weather")  # 위치 있으면 날씨 자동 추가
```

## Kubernetes Resources

### Namespaces

| Namespace | Components |
|-----------|------------|
| `chat` | chat-api, chat-worker |
| `sse-consumer` | sse-gateway |
| `event-router` | event-router |
| `redis` | rfr-streams-redis, rfr-pubsub-redis |
| `rabbitmq` | eco2-rabbitmq |

### Pod DNS Reference

```
# Redis Master (직접 연결)
rfr-pubsub-redis-0.rfr-pubsub-redis.redis.svc.cluster.local:6379

# Redis Streams
rfr-streams-redis-0.rfr-streams-redis.redis.svc.cluster.local:6379

# RabbitMQ
eco2-rabbitmq.rabbitmq.svc.cluster.local:5672
```

## Event Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Event Flow                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  chat-worker                 event-router              sse-gateway           │
│  ┌──────────┐               ┌──────────┐              ┌──────────┐          │
│  │ LangGraph│               │Lua Script│              │  Pub/Sub │          │
│  │ Pipeline │               │          │              │ Listener │          │
│  └────┬─────┘               └────┬─────┘              └────┬─────┘          │
│       │                          │                         │                 │
│       │  XADD chat:events:{id}   │                         │                 │
│       ├─────────────────────────▶│                         │                 │
│       │                          │                         │                 │
│       │                          │  PUBLISH sse:events:{id}│                 │
│       │                          ├────────────────────────▶│                 │
│       │                          │                         │                 │
│       │                          │                         │  SSE Event      │
│       │                          │                         ├────────────────▶│
│       │                          │                         │        Client   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables (chat-worker)

| Variable | Description | Example |
|----------|-------------|---------|
| `CHAT_WORKER_RABBITMQ_URL` | RabbitMQ 연결 | `amqp://...` |
| `CHAT_WORKER_REDIS_URL` | Redis Pub/Sub 연결 | `redis://rfr-pubsub-redis-0...` |
| `CHAT_WORKER_OPENAI_API_KEY` | OpenAI API 키 | `sk-...` |
| `CHAT_WORKER_GOOGLE_API_KEY` | Google API 키 | - |
| `CHAT_WORKER_DEFAULT_PROVIDER` | LLM Provider | `openai` / `google` |

### ExternalSecret Reference

```yaml
# workloads/secrets/external-secrets/dev/chat-worker-secrets.yaml
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: chat-worker-secrets
  data:
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: eco2/dev/openai
        property: api_key
```
