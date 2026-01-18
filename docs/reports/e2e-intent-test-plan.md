# E2E Intent Test Plan

> **Date:** 2026-01-18
> **Scope:** Chat API + Chat Worker + Event Router + SSE Gateway
> **Status:** Ready for Execution

---

## Executive Summary

Eco² Chat 서비스의 Intent별 E2E 테스트 계획입니다.
DIRECT exchange 배포 후 전체 파이프라인 검증을 목표로 합니다.

**테스트 범위:**
- 10개 Intent 분류 및 라우팅
- LangGraph 서브에이전트 병렬 실행
- Redis 이벤트 버스 (Streams → Pub/Sub)
- SSE 실시간 스트리밍

---

## 1. System Architecture

### 1.1 E2E Test Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     E2E Test Coverage                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [1] API Request       [2] Queue          [3] Processing         │
│  ┌─────────┐          ┌─────────┐        ┌─────────────────┐    │
│  │  curl   │──POST───▶│RabbitMQ │──────▶ │  chat-worker    │    │
│  │         │          │ DIRECT  │        │  (LangGraph)    │    │
│  └─────────┘          └─────────┘        └─────────────────┘    │
│       │                                          │               │
│    chat_id                                       │               │
│    job_id                                   XADD │               │
│       │                                          ▼               │
│       │                                  ┌─────────────────┐    │
│       │                                  │ Redis Streams   │    │
│       │                                  │ chat:events:*   │    │
│       │                                  └─────────────────┘    │
│       │                                          │               │
│       │                                    XREADGROUP            │
│       │                                          ▼               │
│       │                                  ┌─────────────────┐    │
│       │                                  │  Event Router   │    │
│       │                                  │  (Lua Script)   │    │
│       │                                  └─────────────────┘    │
│       │                                          │               │
│       │                                      PUBLISH             │
│       │                                          ▼               │
│  [6] SSE Response      [5] Pub/Sub       [4] State Update       │
│  ┌─────────┐          ┌─────────┐        ┌─────────────────┐    │
│  │ Browser │◀───SSE───│sse:events│◀──────│ chat:state:*    │    │
│  │  curl   │          │ {job_id}│        │ (KV Store)      │    │
│  └─────────┘          └─────────┘        └─────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Endpoint Mapping

| Step | Endpoint | Service | Description |
|------|----------|---------|-------------|
| 1 | `POST /api/v1/chat` | chat-api | 채팅 생성 → `chat_id` |
| 2 | `POST /api/v1/chat/{chat_id}/messages` | chat-api | 메시지 전송 → `job_id` |
| 3 | `GET /api/v1/chat/{job_id}/events` | sse-gateway | SSE 구독 |

### 1.3 Istio VirtualService Routing

```yaml
# Chat API
/api/v1/chat/**  →  chat-api.chat.svc.cluster.local:8000

# SSE Gateway (regex match)
/api/v1/{service}/{id}/events  →  sse-gateway.sse-consumer.svc.cluster.local:8000
```

---

## 2. Intent Classification

### 2.1 Intent Types (10개)

| Intent | Node | Description | External API |
|--------|------|-------------|--------------|
| `WASTE` | `waste_rag` | 분리배출 질문 | RAG (Pinecone) |
| `CHARACTER` | `character` | 캐릭터 정보 | gRPC (character-grpc) |
| `LOCATION` | `location` | 장소 검색 | Kakao Map API |
| `BULK_WASTE` | `bulk_waste` | 대형폐기물 | 행정안전부 API |
| `RECYCLABLE_PRICE` | `recyclable_price` | 재활용 시세 | 한국환경공단 API |
| `COLLECTION_POINT` | `collection_point` | 수거함 위치 | KECO API |
| `WEB_SEARCH` | `web_search` | 웹 검색 | Tavily/Brave API |
| `IMAGE_GENERATION` | `image_generation` | 이미지 생성 | OpenAI DALL-E |
| `GENERAL` | `general` | 일반 대화 | LLM Direct |

### 2.2 Dynamic Router (Enrichment Rules)

```python
# Intent → 자동 추가되는 enrichment 노드
ENRICHMENT_RULES = {
    "waste": ("weather",),      # 분리배출 → 날씨 팁
    "bulk_waste": ("weather",), # 대형폐기물 → 날씨 팁
}

# 조건부 Enrichment
if user_location is not None:
    add("weather")  # 위치 있으면 날씨 추가
```

### 2.3 Multi-Intent Fanout

```
사용자: "종이 버리는 법이랑 수거함도 알려줘"

Intent Node 결과:
  intent = "waste"
  additional_intents = ["collection_point"]

Dynamic Router 결과:
  Send("waste_rag", state)        # 주 intent
  Send("collection_point", state) # multi-intent
  Send("weather", state)          # enrichment

→ 3개 노드 병렬 실행!
```

---

## 3. Test Cases

### 3.1 Test Matrix

| # | Intent | Test Message | Expected Nodes | Location |
|---|--------|--------------|----------------|----------|
| 1 | WASTE | "플라스틱 분리배출 방법 알려줘" | waste_rag, weather | No |
| 2 | CHARACTER | "플라스틱 버리면 어떤 캐릭터 얻어?" | character | No |
| 3 | LOCATION | "근처 제로웨이스트샵 알려줘" | location | Yes |
| 4 | BULK_WASTE | "소파 버리려면 어떻게 해?" | bulk_waste, weather | No |
| 5 | RECYCLABLE_PRICE | "고철 시세 얼마야?" | recyclable_price | No |
| 6 | COLLECTION_POINT | "근처 의류수거함 어디야?" | collection_point | Yes |
| 7 | WEB_SEARCH | "최신 분리배출 정책 알려줘" | web_search | No |
| 8 | IMAGE_GENERATION | "페트병 버리는 법 이미지로 만들어줘" | image_generation | No |
| 9 | GENERAL | "안녕하세요" | general | No |
| 10 | MULTI_INTENT | "종이 버리는 법이랑 수거함도 알려줘" | waste_rag, collection_point, weather | Yes |

### 3.2 Expected SSE Event Sequence

```
event: intent
data: {"stage":"intent","status":"completed","progress":15}

event: waste_rag
data: {"stage":"waste_rag","status":"started","progress":20}

event: weather
data: {"stage":"weather","status":"started","progress":25}

event: waste_rag
data: {"stage":"waste_rag","status":"completed","progress":40}

event: weather
data: {"stage":"weather","status":"completed","progress":45}

event: aggregator
data: {"stage":"aggregator","status":"started","progress":55}

event: aggregator
data: {"stage":"aggregator","status":"completed","progress":65}

event: token
data: {"stage":"token","content":"플라스틱은","seq":1001}

event: token
data: {"stage":"token","content":" 재질에","seq":1002}

... (토큰 스트리밍)

event: done
data: {"stage":"done","status":"success","progress":100,"result":{...}}
```

---

## 4. Verification Checklist

### 4.1 RabbitMQ Exchange

```bash
# 클러스터에서 실행
kubectl exec -n rabbitmq eco2-rabbitmq-server-0 -- \
  rabbitmqadmin -u <user> -p <pass> list exchanges | grep chat_tasks

# Expected: type=direct
```

### 4.2 SSE Event Validation

| Item | Validation |
|------|------------|
| Intent 분류 | `intent` 이벤트의 `stage` 값 확인 |
| 병렬 실행 | 여러 `started` 이벤트 수신 (순서 무관) |
| Progress 증가 | 0 → 15 → 20~55 → 75 → 100 단조 증가 |
| Token 스트리밍 | `seq` 연속 증가, `content` 조각 |
| 완료 | `done` 이벤트의 `result` 필드 |

### 4.3 Redis State

```bash
# State 확인
kubectl exec -n redis rfr-streams-redis-0 -- \
  redis-cli HGETALL "chat:state:{job_id}"

# Expected keys: stage, status, progress, seq, result
```

---

## 5. Test Script

### 5.1 Location

```
scripts/e2e-intent-test.sh
```

### 5.2 Usage

```bash
# Interactive mode
./scripts/e2e-intent-test.sh <JWT_TOKEN>

# Run all tests
./scripts/e2e-intent-test.sh <JWT_TOKEN> --all

# Quick test (WASTE, GENERAL only)
./scripts/e2e-intent-test.sh <JWT_TOKEN> --quick

# Custom timeout
SSE_TIMEOUT=120 ./scripts/e2e-intent-test.sh <JWT_TOKEN>
```

### 5.3 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `https://api.dev.growbin.app` | API 엔드포인트 |
| `SSE_TIMEOUT` | `60` | SSE 구독 타임아웃 (초) |

---

## 6. Troubleshooting

### 6.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | JWT 만료 | 새 토큰 발급 |
| 404 Chat not found | chat_id 불일치 | 새 채팅 생성 |
| SSE timeout | Worker 지연 | SSE_TIMEOUT 증가 |
| No events | Exchange 미생성 | 첫 메시지 후 확인 |

### 6.2 Debug Commands

```bash
# chat-worker 로그
kubectl logs -n chat -l app=chat-worker -f --tail=100

# event-router 로그
kubectl logs -n event-router -l app=event-router -f --tail=50

# sse-gateway 로그
kubectl logs -n sse-consumer -l app=sse-gateway -f --tail=50

# Redis Pub/Sub 모니터링
kubectl exec -n redis rfr-pubsub-redis-0 -- \
  redis-cli PSUBSCRIBE "sse:events:*"
```

---

## 7. Test Results Template

```markdown
## E2E Test Results - [DATE]

### Environment
- Branch: `refactor/reward-fanout-exchange`
- Exchange Type: DIRECT
- Cluster: dev

### Results

| Intent | Status | Duration | Notes |
|--------|--------|----------|-------|
| WASTE | PASS | 3.2s | weather enrichment OK |
| CHARACTER | PASS | 2.1s | gRPC call OK |
| LOCATION | PASS | 4.5s | Kakao API OK |
| BULK_WASTE | PASS | 3.8s | |
| RECYCLABLE_PRICE | PASS | 2.5s | |
| COLLECTION_POINT | PASS | 3.1s | |
| WEB_SEARCH | PASS | 5.2s | |
| IMAGE_GENERATION | PASS | 8.5s | DALL-E 응답 지연 |
| GENERAL | PASS | 1.5s | |
| MULTI_INTENT | PASS | 4.8s | 3 nodes parallel |

### Issues Found
- None

### Screenshots
- [SSE Event Log](./screenshots/sse-events.png)
```

---

## 8. Next Steps

1. **테스트 실행**: `./scripts/e2e-intent-test.sh <TOKEN> --all`
2. **결과 기록**: 위 템플릿에 결과 작성
3. **이슈 발견 시**: Troubleshooting 섹션 참조
4. **PR 머지 후**: Production 배포 전 동일 테스트 수행

---

## Appendix: API Response Examples

### A.1 Create Chat Response

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": null,
  "created_at": "2026-01-18T10:30:00Z"
}
```

### A.2 Send Message Response

```json
{
  "job_id": "f1e2d3c4-b5a6-7890-1234-567890abcdef",
  "stream_url": "/api/v1/chat/f1e2d3c4-b5a6-7890-1234-567890abcdef/events",
  "status": "queued"
}
```

### A.3 SSE Done Event

```json
{
  "stage": "done",
  "status": "success",
  "progress": 100,
  "seq": 150,
  "result": {
    "answer": "플라스틱 분리배출 방법은...",
    "sources": ["waste_rag", "weather"],
    "metadata": {
      "intent": "waste",
      "nodes_executed": ["waste_rag", "weather", "aggregator", "answer"],
      "total_tokens": 1523
    }
  }
}
```
