# 🐰 RabbitMQ + Celery Task Queue 설계

> **Tier 3: Message Queue Middleware Layer**  
> **구성**: RabbitMQ HA (3-node) + 5개 Queue  
> **날짜**: 2025-10-31  
> **상태**: ✅ 프로덕션 배포 완료

## 📋 목차

1. [4-Tier에서의 위치](#4-tier에서의-위치)
2. [설계 원칙](#설계-원칙)
3. [큐 설계 (5개)](#큐-설계-5개)
4. [Celery Workers (Tier 2)](#celery-workers-tier-2)
5. [운영 가이드](#운영-가이드)

---

## 🏗️ 4-Tier에서의 위치

### Layered Architecture

```mermaid
graph TB
    subgraph Tier1["Tier 1: Control Plane"]
        CP["Master<br/>Orchestration<br/>Monitoring"]
    end
    
    subgraph Tier2["Tier 2: Data Plane"]
        Sync["Worker-1<br/>Sync API<br/>auth, users<br/>locations"]
        Async["Worker-2<br/>Async Processing<br/>waste-service<br/>AI Workers x3<br/>Batch Workers x2"]
    end
    
    subgraph Tier3["Tier 3: Message Queue"]
        MQ["Storage Node<br/>RabbitMQ HA x3<br/><br/>5 Queues:<br/>q.ai, q.batch<br/>q.api, q.sched<br/>q.dlq"]
    end
    
    subgraph Tier4["Tier 4: Persistence"]
        Storage["Storage Node<br/>PostgreSQL<br/>Redis<br/>Celery Beat"]
    end
    
    Tier1 -.->|orchestrate| Tier2
    Tier2 -->|publish| Tier3
    Tier3 -->|consume| Tier2
    Tier2 <-->|CRUD| Tier4
    Tier3 -.->|store metadata| Tier4
    
    style Tier1 fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:4px
    style Tier2 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:4px
    style Tier3 fill:#f57c00,color:#fff,stroke:#e65100,stroke-width:4px
    style Tier4 fill:#c2185b,color:#fff,stroke:#880e4f,stroke-width:4px
    style CP fill:#42a5f5,color:#000,stroke:#1976d2,stroke-width:2px
    style Sync fill:#81c784,color:#000,stroke:#66bb6a,stroke-width:2px
    style Async fill:#a5d6a7,color:#000,stroke:#81c784,stroke-width:2px
    style MQ fill:#ffb74d,color:#000,stroke:#ffa726,stroke-width:2px
    style Storage fill:#f48fb1,color:#000,stroke:#ec407a,stroke-width:2px
```

### Tier 3의 역할

```
책임 (Responsibility):
✅ Message Routing (라우팅 키 기반)
✅ Delivery Guarantee (메시지 보장)
✅ Queue Management (5개 큐 관리)
✅ Load Balancing (Worker간 분배)
✅ Fault Tolerance (DLX, HA)

관심사 (Concern):
✅ "메시지를 어떻게 안전하게 전달할 것인가?"
✅ "어떻게 메시지 순서와 우선순위를 관리할 것인가?"

위치:
✅ Tier 2 (Data Plane)와 완전 분리
✅ Tier 4 (Storage)와 완전 분리
✅ Middleware Layer (중간 계층)
```

---

## 🎯 설계 원칙

### 3대 목표

```mermaid
graph TB
    A["RabbitMQ<br/>Tier 3: Middleware"] --> B{"설계 목표"}
    
    B --> C1["한 큐 폭주 방지<br/>TTL + max-length + DLX"]
    B --> C2["SLO 분리<br/>짧은 작업 vs 긴 작업"]
    B --> C3["장애 격리<br/>외부 API 장애 시<br/>다른 큐 정상"]
    
    C1 --> D["안정적인<br/>비동기 통신"]
    C2 --> D
    C3 --> D
    
    style A fill:#ef6c00,color:#fff,stroke:#e65100,stroke-width:4px
    style B fill:#f57c00,color:#fff,stroke:#ef6c00,stroke-width:3px
    style C1 fill:#c62828,color:#fff,stroke:#b71c1c,stroke-width:3px
    style C2 fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:3px
    style C3 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:3px
    style D fill:#6a1b9a,color:#fff,stroke:#4a148c,stroke-width:4px
```

---

## 📦 큐 설계 (5개)

### Tier 3: RabbitMQ HA Cluster

```mermaid
graph LR
    subgraph Tier2["Tier 2: Data Plane"]
        Waste["waste-service<br/>FastAPI"]
        Auth["auth-service<br/>FastAPI"]
    end
    
    subgraph Tier3["Tier 3: Message Queue RabbitMQ HA"]
        Exchange["Topic Exchange<br/>tasks"]
        DLX["Direct Exchange<br/>dlx"]
        
        Q1["q.ai<br/>Priority: 10<br/>AI Vision<br/>TTL: 300s"]
        Q2["q.batch<br/>Priority: 1<br/>배치 작업<br/>TTL: 3600s"]
        Q3["q.api<br/>Priority: 5<br/>외부 API<br/>TTL: 300s"]
        Q4["q.sched<br/>Priority: 3<br/>예약 작업"]
        Q5["q.dlq<br/>Dead Letter<br/>실패 메시지"]
    end
    
    subgraph Tier2W["Tier 2: Celery Workers"]
        AIW["AI Workers x3<br/>Worker-2<br/>gevent"]
        BatchW["Batch Workers x2<br/>Worker-2<br/>processes"]
        APIW["API Workers x2<br/>Worker-1<br/>gevent"]
    end
    
    Waste -->|publish| Exchange
    Auth -->|publish| Exchange
    
    Exchange -->|"ai.*"| Q1
    Exchange -->|"batch.*"| Q2
    Exchange -->|"api.*"| Q3
    Exchange -->|"sched.*"| Q4
    
    Q1 -.->|failure/TTL| DLX
    Q2 -.->|failure/TTL| DLX
    Q3 -.->|failure/TTL| DLX
    Q4 -.->|failure/TTL| DLX
    DLX --> Q5
    
    Q1 -->|consume| AIW
    Q2 -->|consume| BatchW
    Q3 -->|consume| APIW
    Q4 -->|consume| BatchW
    
    style Tier2 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:3px
    style Tier3 fill:#f57c00,color:#fff,stroke:#e65100,stroke-width:4px
    style Tier2W fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:3px
    style Exchange fill:#ef6c00,color:#fff,stroke:#e65100,stroke-width:3px
    style DLX fill:#c62828,color:#fff,stroke:#b71c1c,stroke-width:3px
    style Q1 fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:2px
    style Q2 fill:#5e35b1,color:#fff,stroke:#4527a0,stroke-width:2px
    style Q3 fill:#00838f,color:#fff,stroke:#006064,stroke-width:2px
    style Q4 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:2px
    style Q5 fill:#b71c1c,color:#fff,stroke:#7f0000,stroke-width:3px
    style AIW fill:#a5d6a7,color:#000,stroke:#81c784,stroke-width:2px
    style BatchW fill:#c5e1a5,color:#000,stroke:#aed581,stroke-width:2px
    style APIW fill:#81c784,color:#000,stroke:#66bb6a,stroke-width:2px
```

### Queue별 상세

```
q.ai (Tier 3 → Tier 2 Worker-2):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
목적: AI Vision 분석
소비자: AI Workers ×3 (Tier 2 Data Plane)
라우팅: ai.*
Priority: 10 (highest)
TTL: 300초
Type: Quorum Queue (HA)

q.batch (Tier 3 → Tier 2 Worker-2):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
목적: 배치 작업
소비자: Batch Workers ×2 (Tier 2 Data Plane)
라우팅: batch.*
Priority: 1 (lowest)
TTL: 3600초
Type: Quorum Queue

q.api (Tier 3 → Tier 2 Worker-1):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
목적: 외부 API 호출 (Map, OAuth)
소비자: API Workers ×2 (Tier 2 Data Plane)
라우팅: api.*
Priority: 5
TTL: 300초
Type: Quorum Queue

q.sched (Tier 3 → Tier 2 Worker-2):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
목적: 예약 작업
소비자: Batch Workers ×2
라우팅: sched.*
Priority: 3
Type: Quorum Queue

q.dlq (Tier 3, 모니터링):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
목적: 실패 메시지 수집
소비자: None (수동 재처리)
Type: Classic Queue
```

---

## 🔄 Tier간 메시지 흐름

```mermaid
sequenceDiagram
    participant API as Tier 2 Sync API<br/>waste-service
    participant MQ as Tier 3 MQ<br/>RabbitMQ
    participant Worker as Tier 2 Async<br/>AI Worker
    participant DB as Tier 4 Storage<br/>PostgreSQL
    participant Redis as Tier 4 Storage<br/>Redis
    
    API->>MQ: 1. Publish q.ai<br/>ai.analyze
    Note over MQ: Tier 3 책임:<br/>메시지 라우팅<br/>우선순위 관리<br/>Delivery Guarantee
    
    MQ->>Worker: 2. Consume<br/>Priority 10
    
    activate Worker
    Worker->>Redis: 3. 캐시 확인
    
    alt Cache Hit
        Redis-->>Worker: 결과 반환
    else Cache Miss
        Worker->>Worker: GPT-4o Vision
        Worker->>DB: 4. 결과 저장
        Worker->>Redis: 5. 캐싱
    end
    deactivate Worker
    
    Worker->>MQ: 6. ACK
    
    Note over Tier 3 MQ: 메시지 제거<br/>DLQ 처리 (실패 시)
```

---

## 🖥️ Celery Workers (Tier 2)

### Worker 배치

```
Tier 2: Data Plane (Business Logic)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Worker-1 Node (Sync API + 가벼운 비동기):
├─ auth-service ×2 (FastAPI, 동기)
├─ users-service ×1 (FastAPI, 동기)
├─ locations-service ×1 (FastAPI, 동기)
└─ API Workers ×2 (Celery, q.api)
   └─ 역할: 가벼운 외부 API (Map, OAuth 프로필 동기화)

Worker-2 Node (무거운 비동기):
├─ waste-service ×2 (FastAPI, 동기 API)
├─ AI Workers ×3 (Celery, q.ai)
│  └─ 역할: GPT-4o Vision 분석
└─ Batch Workers ×2 (Celery, q.batch, q.sched)
   └─ 역할: 배치 작업, 예약 작업

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
모두 Tier 2 (Data Plane)
Tier 3 (MQ)는 순수하게 메시지 전달만!
```

### Celery 설정

```python
# Tier 2 Workers → Tier 3 MQ 연결
broker_url = "amqp://admin:password@rabbitmq.messaging:5672//"  # Tier 3
result_backend = "redis://redis.default:6379/1"  # Tier 4

# Tier 2: Worker-1 - API Workers
app_api_worker = Celery("api_worker")
app_api_worker.conf.update(
    broker_url=broker_url,  # Tier 3 MQ
    result_backend=result_backend,  # Tier 4 Storage
    worker_queues=["q.api"],
    worker_pool="gevent",
    worker_concurrency=4,
)

# Tier 2: Worker-2 - AI Workers  
app_ai_worker = Celery("ai_worker")
app_ai_worker.conf.update(
    broker_url=broker_url,  # Tier 3 MQ
    result_backend=result_backend,  # Tier 4 Storage
    worker_queues=["q.ai"],
    worker_pool="gevent",
    worker_concurrency=4,
)

# Tier 2: Worker-2 - Batch Workers
app_batch_worker = Celery("batch_worker")
app_batch_worker.conf.update(
    broker_url=broker_url,  # Tier 3 MQ
    result_backend=result_backend,  # Tier 4 Storage
    worker_queues=["q.batch", "q.sched"],
    worker_pool="processes",
    worker_concurrency=4,
    worker_prefetch_multiplier=1,  # 공평성
)
```

---

## 📊 Tier 3 RabbitMQ HA 구성

### High Availability Cluster

```yaml
# Storage Node에 배치
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: rabbitmq
  namespace: messaging
spec:
  serviceName: rabbitmq
  replicas: 3  # HA Cluster
  selector:
    matchLabels:
      app: rabbitmq
      tier: middleware  # Tier 3
  template:
    spec:
      nodeSelector:
        workload: storage
      containers:
      - name: rabbitmq
        image: rabbitmq:3.12-management
        env:
        - name: RABBITMQ_DEFAULT_USER
          value: admin
        - name: RABBITMQ_DEFAULT_PASS
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: password
        ports:
        - containerPort: 5672  # AMQP
        - containerPort: 15672  # Management
        volumeMounts:
        - name: data
          mountPath: /var/lib/rabbitmq
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 2Gi
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
      storageClassName: gp3
```

### Queue 정의 (Tier 3)

```python
from kombu import Exchange, Queue

# Tier 3: Exchange 정의
tasks_exchange = Exchange("tasks", type="topic")
dlx_exchange = Exchange("dlx", type="direct")

# Tier 3: Queue 정의
task_queues = (
    Queue(
        "q.ai",
        tasks_exchange,
        routing_key="ai.*",
        queue_arguments={
            "x-queue-type": "quorum",  # HA
            "x-dead-letter-exchange": "dlx",
            "x-dead-letter-routing-key": "dlq",
            "x-message-ttl": 300_000,
            "x-max-length": 5_000,
            "x-max-priority": 10,
        },
    ),
    Queue(
        "q.batch",
        tasks_exchange,
        routing_key="batch.*",
        queue_arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": "dlx",
            "x-dead-letter-routing-key": "dlq",
            "x-message-ttl": 3_600_000,
            "x-max-length": 1_000,
        },
    ),
    Queue(
        "q.api",
        tasks_exchange,
        routing_key="api.*",
        queue_arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": "dlx",
            "x-dead-letter-routing-key": "dlq",
            "x-message-ttl": 300_000,
            "x-max-length": 2_000,
        },
    ),
    Queue(
        "q.sched",
        tasks_exchange,
        routing_key="sched.*",
        queue_arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": "dlx",
            "x-dead-letter-routing-key": "dlq",
        },
    ),
    Queue("q.dlq", dlx_exchange, routing_key="dlq"),
)
```

---

## 🎯 Tier별 책임

### Clear Separation

```
Tier 1: Control Plane
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
책임: Orchestration
관심사: "어디에 배치하고 어떻게 관리할 것인가?"
구성: kube-apiserver, etcd, scheduler

Tier 2: Data Plane (Business Logic)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
책임: Business Processing
관심사: "요청을 어떻게 처리할 것인가?"
구성:
├─ Sync API (Worker-1): auth, users, locations
└─ Async Workers (Worker-2): AI, Batch Workers

Tier 3: Message Queue (Middleware)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
책임: Message Delivery
관심사: "메시지를 어떻게 안전하게 전달할 것인가?"
구성: RabbitMQ HA ×3, 5 Queues
위치: Storage Node (물리적으로는 Tier 4와 같은 노드)

Tier 4: Persistence (Storage)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
책임: Data Persistence
관심사: "데이터를 어떻게 영속적으로 저장할 것인가?"
구성: PostgreSQL, Redis, Celery Beat
위치: Storage Node (물리적으로는 Tier 3과 같은 노드)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
핵심:
✅ 물리적 노드 ≠ 논리적 Tier
✅ Storage 노드 = Tier 3 + Tier 4 (논리적 분리)
✅ 각 Tier는 명확한 단일 책임
```

---

## 📚 관련 문서

- [4-Tier 배포 아키텍처](deployment-architecture-4node.md)
- [Final K8s Architecture](final-k8s-architecture.md)
- [Celery Best Practices](https://docs.celeryq.dev/)

---

**작성일**: 2025-10-31  
**상태**: ✅ 프로덕션 배포 완료  
**Tier**: 3 (Message Queue Middleware)  
**패턴**: Message-Oriented Middleware + HA Cluster
