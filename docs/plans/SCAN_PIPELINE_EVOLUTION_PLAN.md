# Scan Pipeline Evolution Plan

> Celery Chain → Hybrid → Full Event-Driven 진화 로드맵

## 1. 개요 (Overview)

본 문서는 Scan Pipeline의 단계적 진화 계획을 정의합니다. 현재 단일 Task로 처리되는 파이프라인을 4단계 Celery Chain으로 분리하고, 궁극적으로 Event-Driven Architecture로 전환하는 로드맵입니다.

### 1.1 발전 단계 요약

| Phase | 아키텍처 | Task/Event 처리 | 인프라 | 상태 |
|-------|---------|----------------|--------|------|
| **Phase 1** | Monolithic Task | 단일 Celery Task | RabbitMQ | ✅ 완료 |
| **Phase 2** | Celery Chain | 3+1단계 Task 분리 | RabbitMQ | 🔄 진행 중 (90%) |
| **Phase 3** | Hybrid | Task + Event 발행 | RabbitMQ + Kafka | 📋 계획 |
| **Phase 4** | Full Event-Driven | Kafka Consumer 기반 | Kafka Cluster | 📋 계획 |

---

## 1.2 Phase 2 개발 현황 (2024-12-22 기준)

### ✅ 완료된 항목

| 항목 | 상태 | 설명 |
|------|------|------|
| **vision_task** | ✅ | GPT Vision 이미지 분류 |
| **rule_task** | ✅ | RAG 기반 배출 규정 검색 |
| **answer_task** | ✅ | GPT Answer 생성 + Webhook |
| **reward_task** | ✅ | 캐릭터 리워드 평가 (Fire & Forget) |
| **DB 제거** | ✅ | 로그 기반 추적으로 전환 (EFK) |
| **Celery Chain** | ✅ | vision → rule → answer 체인 |
| **DLQ 구성** | ✅ | 단계별 Dead Letter Queue |

### 🔄 진행 중

| 항목 | 상태 | 설명 |
|------|------|------|
| **SSE 실시간 진행상황** | 🔄 | Redis Pub/Sub + StreamingResponse |
| **reward_task 캐릭터 획득** | 🔄 | owned 테이블에 캐릭터 추가 |

### 현재 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Client Request                                                             │
│       │                                                                     │
│       ▼                                                                     │
│  scan-api ─────────────────────────────────────────────────────────────┐    │
│       │                                                                │    │
│       │ chain(vision.s() | rule.s() | answer.s()).delay()             │    │
│       │                                                                │    │
│       ▼                                                                │    │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                           │    │
│  │  scan.   │──▶│  scan.   │──▶│  scan.   │──────────┐                │    │
│  │  vision  │   │   rule   │   │  answer  │          │                │    │
│  │  ~2.5s   │   │  ~0.1s   │   │  ~2s     │          │                │    │
│  └──────────┘   └──────────┘   └──────────┘          │                │    │
│                                      │               │                │    │
│                                      │ Webhook ◀─────┘                │    │
│                                      │                                │    │
│                                      │ 조건 충족 시 (재활용폐기물)       │    │
│                                      ▼                                │    │
│                              ┌──────────────┐                         │    │
│                              │   reward.    │ Fire & Forget           │    │
│                              │  character   │ (Chain 외부)             │    │
│                              │   ~0.5s      │                         │    │
│                              └──────────────┘                         │    │
│                                      │                                │    │
│                                      ▼ gRPC                           │    │
│                              ┌──────────────┐                         │    │
│                              │ character-api│                         │    │
│                              │ (리워드 평가) │                         │    │
│                              └──────────────┘                         │    │
│                                      │                                │    │
│                                      ▼ 🔄 TODO                        │    │
│                              ┌──────────────┐                         │    │
│                              │ owned 테이블 │                         │    │
│                              │ 캐릭터 획득   │                         │    │
│                              └──────────────┘                         │    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 목표 타임라인

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Timeline (Phase 2 완료까지)                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  0s      vision_task 시작                                                    │
│          ├── SSE: {"step": "vision", "progress": 0, "status": "processing"} │
│                                                                              │
│  2.5s    vision_task 완료 → rule_task 시작                                   │
│          ├── SSE: {"step": "vision", "progress": 33, "status": "completed"} │
│                                                                              │
│  2.6s    rule_task 완료 → answer_task 시작                                   │
│          ├── SSE: {"step": "rule", "progress": 50, "status": "completed"}   │
│                                                                              │
│  4.5s    answer_task 완료                                                    │
│          ├── SSE: {"step": "answer", "progress": 100, "status": "completed"}│
│          ├── Webhook 전송 (결과 포함)                                        │
│          └── reward_task.delay() 발행 (조건 충족 시)                         │
│                                                                              │
│  4.5s~   reward_task 별도 Worker에서 처리 (비동기)                           │
│  5.0s    gRPC → character-api                                               │
│  5.5s    reward_task 완료                                                    │
│          └── 캐릭터 owned 테이블에 추가 (TODO)                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Phase 1: Monolithic Task (현재)

### 2.1 현재 구조

```
scan-api ──▶ [scan.vision Queue] ──▶ classify_task
                                          │
                                          ├─ Vision (GPT-4V)
                                          ├─ RAG (Rule Retrieval)
                                          ├─ Answer (GPT-4)
                                          └─ Reward (gRPC)
```

### 2.2 한계점

| 문제 | 설명 |
|------|------|
| **부분 실패 시 전체 재시도** | Vision 성공 후 Answer 실패 시 Vision부터 재실행 |
| **리소스 낭비** | GPU 호출 중복 (재시도 시) |
| **모니터링 불가** | 단계별 지연 시간 측정 어려움 |
| **확장성 제한** | 단계별 독립 스케일링 불가 |

---

## 3. Phase 2: Celery Chain (4단계 분리)

### 3.1 목표

- 파이프라인을 4단계로 분리하여 **부분 실패 격리**
- 단계별 **독립적 재시도** 및 **DLQ 관리**
- 단계별 **메트릭 수집** 가능

### 3.2 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Phase 2: Celery Chain                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  scan-api                                                                    │
│     │                                                                        │
│     │ chain(vision.s() | rule.s() | answer.s() | reward.s()).delay()        │
│     ▼                                                                        │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│  │  scan.   │──▶│  scan.   │──▶│  scan.   │──▶│  scan.   │                  │
│  │  vision  │   │   rule   │   │  answer  │   │  reward  │                  │
│  │  Queue   │   │  Queue   │   │  Queue   │   │  Queue   │                  │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘                  │
│       │              │              │              │                         │
│       ▼              ▼              ▼              ▼                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│  │ vision_  │   │  rule_   │   │ answer_  │   │ reward_  │                  │
│  │  task    │   │  task    │   │  task    │   │  task    │                  │
│  │ GPT-4V   │   │ RAG/JSON │   │  GPT-4   │   │  gRPC    │                  │
│  │ 5~15s    │   │  <1s     │   │ 3~10s    │   │  1~3s    │                  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘                  │
│       │              │              │              │                         │
│       │              │              │              │                         │
│       ▼              ▼              ▼              ▼                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│  │ dlq.scan │   │ dlq.scan │   │ dlq.scan │   │ dlq.scan │                  │
│  │ .vision  │   │  .rule   │   │ .answer  │   │ .reward  │                  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Task 정의

```python
# domains/scan/tasks/vision.py
@celery_app.task(
    name="scan.vision",
    queue="scan.vision",
    bind=True,
    base=BaseTask,
    max_retries=2,
    soft_time_limit=60,
    time_limit=90,
)
def vision_task(self, task_id: str, user_id: str, image_url: str) -> dict:
    """Step 1: GPT Vision 이미지 분류"""
    result = call_gpt_vision(image_url)
    
    return {
        "task_id": task_id,
        "user_id": user_id,
        "image_url": image_url,
        "classification": result,
        "stage": "vision",
        "completed_at": datetime.utcnow().isoformat(),
    }

# domains/scan/tasks/rule.py
@celery_app.task(
    name="scan.rule",
    queue="scan.rule",
    bind=True,
    base=BaseTask,
    max_retries=3,
    soft_time_limit=10,
    time_limit=30,
)
def rule_task(self, prev_result: dict) -> dict:
    """Step 2: Rule-based Retrieval (RAG)"""
    classification = prev_result["classification"]
    
    # JSON 기반 규칙 검색 (빠름)
    disposal_rules = retrieve_disposal_rules(classification)
    
    return {
        **prev_result,
        "disposal_rules": disposal_rules,
        "stage": "rule",
        "completed_at": datetime.utcnow().isoformat(),
    }

# domains/scan/tasks/answer.py
@celery_app.task(
    name="scan.answer",
    queue="scan.answer",
    bind=True,
    base=WebhookTask,
    max_retries=2,
    soft_time_limit=60,
    time_limit=90,
)
def answer_task(self, prev_result: dict, callback_url: str | None = None) -> dict:
    """Step 3: GPT Answer Generation"""
    answer = generate_answer(
        classification=prev_result["classification"],
        disposal_rules=prev_result["disposal_rules"],
    )
    
    result = {
        **prev_result,
        "answer": answer,
        "stage": "answer",
        "completed_at": datetime.utcnow().isoformat(),
    }
    
    # Webhook 전송 (reward 전에 사용자에게 먼저 응답)
    if callback_url:
        self.send_webhook(callback_url, result)
    
    return result

# domains/scan/tasks/reward.py
@celery_app.task(
    name="scan.reward",
    queue="scan.reward",
    bind=True,
    base=BaseTask,
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
def reward_task(self, prev_result: dict) -> dict:
    """Step 4: Character Reward Evaluation"""
    if not should_trigger_reward(prev_result["classification"]):
        return {**prev_result, "reward": None, "stage": "reward"}
    
    reward = call_character_service(prev_result)
    
    return {
        **prev_result,
        "reward": reward,
        "stage": "reward",
        "completed_at": datetime.utcnow().isoformat(),
    }
```

### 3.4 Pipeline 실행

```python
# domains/scan/services/scan.py
from celery import chain

async def _classify_async(self, task_id, user_id, image_url, callback_url):
    """4단계 Celery Chain 실행"""
    
    pipeline = chain(
        vision_task.s(str(task_id), str(user_id), image_url),
        rule_task.s(),
        answer_task.s(callback_url=callback_url),
        reward_task.s(),
    )
    
    # 비동기 실행
    pipeline.delay()
    
    return ClassificationResponse(
        task_id=str(task_id),
        status="processing",
        message="AI 분석이 진행 중입니다.",
    )
```

### 3.5 Queue 설정 (RabbitMQ Topology)

```yaml
# workloads/rabbitmq/base/topology/queues.yaml (추가)
---
apiVersion: rabbitmq.com/v1beta1
kind: Queue
metadata:
  name: scan-rule-queue
  namespace: rabbitmq
spec:
  name: scan.rule
  type: quorum
  durable: true
  vhost: eco2
  arguments:
    x-dead-letter-exchange: dlx
    x-dead-letter-routing-key: dlq.scan.rule
    x-message-ttl: 60000      # 1분 (빠른 작업)
    x-delivery-limit: 3
  rabbitmqClusterReference:
    name: eco2-rabbitmq
```

### 3.6 Phase 2의 특징

| 항목 | 설명 |
|------|------|
| **부분 실패 격리** | Vision 성공 → Rule 실패 시, Rule만 재시도 |
| **단계별 DLQ** | 각 단계별 독립적인 Dead Letter Queue |
| **메트릭 분리** | 단계별 처리 시간, 성공률 측정 가능 |
| **Webhook 타이밍** | Answer 완료 시 즉시 응답, Reward는 비동기 |

---

## 4. Phase 3: Command-Event Seperation

### 4.1 목표

- Celery Chain 유지하면서 **이벤트 발행 추가**
- 다른 도메인(my, character)이 **이벤트 구독** 가능
- **분석 파이프라인** 연동 준비

### 4.2 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Phase 3: Hybrid                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    RabbitMQ (Command/Task)                             │  │
│  │  scan.vision ──▶ scan.rule ──▶ scan.answer ──▶ scan.reward           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│       │                │                │                │                   │
│       │ on_success     │ on_success     │ on_success     │ on_success       │
│       ▼                ▼                ▼                ▼                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Kafka (Event Store)                                 │  │
│  │  events.scan.classified  events.scan.answered  events.scan.rewarded  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│       │                      │                      │                        │
│       ▼                      ▼                      ▼                        │
│  ┌──────────┐         ┌──────────┐           ┌──────────┐                   │
│  │Analytics │         │my-service│           │ Audit    │                   │
│  │Consumer  │         │ (CQRS)   │           │ Consumer │                   │
│  └──────────┘         └──────────┘           └──────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 이벤트 발행 추가

```python
# domains/scan/tasks/vision.py (Phase 3)
@celery_app.task(name="scan.vision", queue="scan.vision", bind=True)
def vision_task(self, task_id: str, user_id: str, image_url: str) -> dict:
    result = call_gpt_vision(image_url)
    
    output = {
        "task_id": task_id,
        "user_id": user_id,
        "classification": result,
        "stage": "vision",
    }
    
    # 📌 Phase 3: 이벤트 발행 추가 (Outbox 패턴)
    publish_event(
        event_type="ScanClassified",
        payload={
            "task_id": task_id,
            "user_id": user_id,
            "classification": result,
            "confidence": result.get("confidence", 0),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
    
    return output

# domains/_shared/events/publisher.py
def publish_event(event_type: str, payload: dict):
    """Outbox 테이블에 이벤트 저장 (CDC가 Kafka로 전파)"""
    from domains.scan.database.session import get_sync_session
    from domains.scan.models.outbox import ScanOutbox
    
    with get_sync_session() as session:
        outbox = ScanOutbox(
            aggregate_type="Scan",
            aggregate_id=payload.get("task_id"),
            event_type=event_type,
            payload=payload,
        )
        session.add(outbox)
        session.commit()
```

### 4.4 이벤트 스키마

```python
# domains/scan/events/schemas.py
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class ScanClassified(BaseModel):
    """Vision 분류 완료 이벤트"""
    event_id: UUID
    event_type: str = "ScanClassified"
    timestamp: datetime
    
    task_id: str
    user_id: str
    classification: dict
    confidence: float

class ScanAnswered(BaseModel):
    """Answer 생성 완료 이벤트"""
    event_id: UUID
    event_type: str = "ScanAnswered"
    timestamp: datetime
    
    task_id: str
    user_id: str
    classification: dict
    disposal_rules: dict
    answer: str

class ScanRewarded(BaseModel):
    """Reward 처리 완료 이벤트"""
    event_id: UUID
    event_type: str = "ScanRewarded"
    timestamp: datetime
    
    task_id: str
    user_id: str
    reward_granted: bool
    character_id: str | None
    character_name: str | None
```

### 4.5 Phase 2 vs Phase 3 차이

| 항목 | Phase 2 (Celery Chain) | Phase 3 (Hybrid) |
|------|------------------------|------------------|
| **Task 처리** | RabbitMQ | RabbitMQ (동일) |
| **이벤트 발행** | ❌ 없음 | ✅ Kafka (Outbox) |
| **다중 Consumer** | ❌ 불가 | ✅ N개 가능 |
| **이벤트 재생** | ❌ 불가 | ✅ Offset 리셋 |
| **분석 연동** | ❌ 별도 구현 | ✅ 같은 이벤트 구독 |
| **인프라** | RabbitMQ만 | RabbitMQ + Kafka |
| **복잡도** | 낮음 | 중간 |
| **비용** | $15/월 | $45/월 (+Kafka) |

---

## 5. Phase 4: Full Event-Driven

### 5.1 목표

- RabbitMQ 제거, **Kafka만으로 전체 파이프라인 처리**
- **Saga Choreography** 패턴 적용
- **Event Sourcing** 완전 적용

### 5.2 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Phase 4: Event-Driven                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  scan-api                                                                    │
│     │                                                                        │
│     │ publish(ScanRequested)                                                │
│     ▼                                                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      Kafka Events Cluster                              │  │
│  │                                                                        │  │
│  │  events.scan.     events.scan.     events.scan.     events.scan.      │  │
│  │   requested   ──▶  classified  ──▶   answered   ──▶   rewarded       │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│       │                  │                  │                  │             │
│       ▼                  ▼                  ▼                  ▼             │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│  │ Vision   │      │  Rule    │      │ Answer   │      │ Reward   │        │
│  │ Consumer │      │ Consumer │      │ Consumer │      │ Consumer │        │
│  └──────────┘      └──────────┘      └──────────┘      └──────────┘        │
│       │                  │                  │                  │             │
│       │ publish          │ publish          │ publish          │ publish    │
│       │ Classified       │ RulesRetrieved   │ Answered         │ Rewarded   │
│       ▼                  ▼                  ▼                  ▼             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      Kafka Events Cluster                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                              │                                               │
│              ┌───────────────┼───────────────┐                              │
│              ▼               ▼               ▼                              │
│        ┌──────────┐   ┌──────────┐   ┌──────────┐                          │
│        │Analytics │   │my-service│   │ Webhook  │                          │
│        │ (ML)     │   │ (CQRS)   │   │ Consumer │                          │
│        └──────────┘   └──────────┘   └──────────┘                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Consumer 구현

```python
# domains/scan/consumers/vision_consumer.py
class VisionConsumer(KafkaConsumer):
    """Vision 처리 Consumer"""
    
    topic = "events.scan.requested"
    group_id = "scan-vision-consumer"
    
    async def handle(self, event: ScanRequested) -> None:
        # GPT Vision 호출
        classification = await call_gpt_vision(event.image_url)
        
        # 다음 이벤트 발행
        await self.publish(ScanClassified(
            task_id=event.task_id,
            user_id=event.user_id,
            classification=classification,
            confidence=classification.get("confidence", 0),
        ))

# domains/scan/consumers/answer_consumer.py
class AnswerConsumer(KafkaConsumer):
    """Answer 처리 Consumer (Rule 결과 구독)"""
    
    topic = "events.scan.rules_retrieved"
    group_id = "scan-answer-consumer"
    
    async def handle(self, event: RulesRetrieved) -> None:
        # GPT Answer 생성
        answer = await generate_answer(
            event.classification,
            event.disposal_rules,
        )
        
        # 다음 이벤트 발행
        await self.publish(ScanAnswered(
            task_id=event.task_id,
            user_id=event.user_id,
            answer=answer,
        ))
        
        # Webhook 전송
        await send_webhook(event.callback_url, answer)
```

### 5.4 Phase 3 vs Phase 4 차이

| 항목 | Phase 3 (Hybrid) | Phase 4 (Full EDA) |
|------|------------------|-------------------|
| **Task 처리** | RabbitMQ | ❌ 제거 |
| **Pipeline 트리거** | Celery Chain | Kafka Event |
| **단계 간 결합** | 강결합 (return) | 느슨한 결합 (Event) |
| **Consumer 확장** | Worker 추가 | Consumer Group 자동 |
| **새 단계 추가** | Chain 수정 | Consumer만 추가 |
| **인프라** | RabbitMQ + Kafka | Kafka만 |
| **복잡도** | 중간 | 높음 |
| **운영 난이도** | 중간 | 높음 |

---

## 6. 마이그레이션 전략

### 6.1 단계별 전환

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        마이그레이션 타임라인                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Phase 1 ──────────▶ Phase 2 ──────────▶ Phase 3 ──────────▶ Phase 4       │
│  (현재)              (Q1 2025)           (Q2 2025)           (Q3+ 2025)     │
│                                                                              │
│  Monolithic    →    Celery Chain   →    Hybrid        →    Full EDA        │
│  Task                4단계 분리          + Event 발행       Kafka Only       │
│                                                                              │
│  인프라 변경:                                                                │
│  - RabbitMQ         - RabbitMQ          - RabbitMQ         - Kafka Cluster  │
│    (유지)             Queue 추가          + Kafka 추가       (RMQ 제거)      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 롤백 전략

| Phase | 롤백 방법 |
|-------|---------|
| 2 → 1 | Chain을 단일 Task로 교체 |
| 3 → 2 | Event 발행 코드 비활성화 |
| 4 → 3 | RabbitMQ 재활성화, Kafka Consumer 중지 |

---

## 7. 참고 문서

### 프로젝트 내 문서

- [KAFKA_CLUSTER_SEPARATION_PLAN.md](./KAFKA_CLUSTER_SEPARATION_PLAN.md) - Kafka 클러스터 분리 계획
- [CDC_ARCHITECTURE_PLAN.md](./CDC_ARCHITECTURE_PLAN.md) - CDC 아키텍처
- [eda-roadmap.md](./eda-roadmap.md) - EDA 로드맵

### Foundations (이론적 기초)

| 주제 | 링크 | Phase 적용 |
|------|------|-----------|
| **Enterprise Integration Patterns** | [블로그](https://rooftopsnow.tistory.com/50) | Phase 2: Competing Consumers, DLQ |
| **Transactional Outbox** | [블로그](https://rooftopsnow.tistory.com/56) | Phase 3: 이벤트 발행 패턴 |
| **Debezium Outbox Event Router** | [블로그](https://rooftopsnow.tistory.com/57) | Phase 3-4: CDC 기반 이벤트 전파 |
| **SAGAS** | [블로그](https://rooftopsnow.tistory.com/55) | Phase 4: Choreography 패턴 |
| **Life Beyond Distributed Transactions** | [블로그](https://rooftopsnow.tistory.com/53) | Phase 3-4: Eventual Consistency |
| **CQRS** | [블로그](https://rooftopsnow.tistory.com/51) | Phase 3-4: Event Sourcing 연동 |
| **DDD Aggregate** | [블로그](https://rooftopsnow.tistory.com/52) | 전체: 트랜잭션 경계 설계 |
| **Uber DOMA** | [블로그](https://rooftopsnow.tistory.com/49) | 전체: 도메인 분리 원칙 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2024-12-19 | 1.0 | 초안 작성 |
| 2024-12-22 | 1.1 | Phase 2 개발 현황 추가, 실제 구현 반영 |
|            |     | - DB 제거, 로그 기반 추적으로 전환 |
|            |     | - Celery Chain 3+1 구조 (reward는 Fire & Forget) |
|            |     | - SSE 실시간 진행상황 전달 방안 결정 |
|            |     | - reward_task 캐릭터 owned 처리 TODO 추가 |
