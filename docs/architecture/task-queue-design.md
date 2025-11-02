# 🐰 RabbitMQ + Celery Task Queue 설계

> **목표**: 4-Tier 아키텍처 기반 Task Queue  
> **구성**: RabbitMQ HA (3-node) + 5개 Queue + Celery Workers  
> **날짜**: 2025-10-31  
> **상태**: ✅ 프로덕션 배포 완료

## 📋 목차

1. [설계 원칙](#설계-원칙)
2. [4-Tier 배치](#4-tier-배치)
3. [큐 설계 (5개)](#큐-설계-5개)
4. [Celery 설정](#celery-설정)
5. [운영 가이드](#운영-가이드)

---

## 🎯 설계 원칙

### 3대 목표

```mermaid
graph TB
    A["RabbitMQ + Celery"] --> B{"설계 목표"}
    
    B --> C1["한 큐 폭주 방지
TTL + max-length + DLX"]
    B --> C2["SLO 분리
짧은 작업 vs 긴 작업"]
    B --> C3["장애 격리
외부 API 장애 시 다른 큐 정상"]
    
    C1 --> D["안정적인
서비스"]
    C2 --> D
    C3 --> D
    
    style A fill:#1a237e,color:#fff,stroke:#0d47a1,stroke-width:4px
    style B fill:#1565c0,color:#fff,stroke:#0277bd,stroke-width:3px
    style C1 fill:#c62828,color:#fff,stroke:#b71c1c,stroke-width:3px
    style C2 fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:3px
    style C3 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:3px
    style D fill:#6a1b9a,color:#fff,stroke:#4a148c,stroke-width:4px
```

### 핵심 전략

```
1. Queue 분리로 장애 격리
   ✅ q.ai: AI Vision (GPT-4o)
   ✅ q.batch: 배치 작업
   ✅ q.api: 외부 API
   ✅ q.sched: 예약 작업
   ✅ q.dlq: Dead Letter

2. Tier별 Worker 배치
   ✅ Tier 2 (Worker-1): API Workers
   ✅ Tier 3 (Worker-2): AI + Batch Workers
   ✅ Tier 4 (Storage): RabbitMQ HA, Celery Beat

3. HA Cluster (Robin Storage 패턴)
   ✅ RabbitMQ 3-node (Tier 4)
   ✅ Quorum Queues
   ✅ 장애 시 자동 복구
```

---

## 🏗️ 4-Tier 배치

### Tier별 역할

```mermaid
graph TB
    subgraph Tier1["Tier 1: Control + Monitoring"]
        Master["Master
t3.large 8GB
 
Control Plane
Prometheus
Grafana
ArgoCD"]
    end
    
    subgraph Tier2["Tier 2: Sync API Application"]
        Worker1["Worker-1
t3.medium 4GB
 
auth-service x2
users-service x1
locations-service x1
 
API Workers x2
(q.api)"]
    end
    
    subgraph Tier3["Tier 3: Async Workers"]
        Worker2["Worker-2
t3.medium 4GB
 
waste-service x2
 
AI Workers x3
(q.ai, GPT-4o Vision)
 
Batch Workers x2
(q.batch)"]
    end
    
    subgraph Tier4["Tier 4: Stateful Storage"]
        Storage["Storage
t3.large 8GB
 
RabbitMQ HA x3
(5 Queues)
 
PostgreSQL
(StatefulSet 50GB)
 
Redis
(Result Backend)
 
Celery Beat x1
(Scheduler)"]
    end
    
    Master -.->|manage| Worker1
    Master -.->|manage| Worker2
    Master -.->|manage| Storage
    
    Worker1 -->|publish tasks| Storage
    Worker2 -->|consume tasks| Storage
    
    style Tier1 fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:3px
    style Tier2 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:3px
    style Tier3 fill:#f57f17,color:#fff,stroke:#e65100,stroke-width:3px
    style Tier4 fill:#c2185b,color:#fff,stroke:#880e4f,stroke-width:3px
    style Master fill:#42a5f5,color:#000,stroke:#1976d2,stroke-width:2px
    style Worker1 fill:#66bb6a,color:#000,stroke:#388e3c,stroke-width:2px
    style Worker2 fill:#ffa726,color:#000,stroke:#f57c00,stroke-width:2px
    style Storage fill:#ec407a,color:#fff,stroke:#c2185b,stroke-width:2px
```

### Worker별 Queue 매핑

```
Tier 2: Worker-1 (Application)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: Sync API + 가벼운 외부 API
Worker:
└─ API Workers ×2
   ├─ Queue: q.api
   ├─ Pool: gevent
   ├─ Concurrency: 4
   └─ Tasks: Kakao Map, OAuth 등

Tier 3: Worker-2 (Async)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: AI 분석 + 배치 작업
Workers:
├─ AI Workers ×3
│  ├─ Queue: q.ai
│  ├─ Pool: gevent
│  ├─ Concurrency: 4
│  └─ Tasks: GPT-4o Vision, 분류, 피드백
│
└─ Batch Workers ×2
   ├─ Queue: q.batch, q.sched
   ├─ Pool: processes
   ├─ Concurrency: 4
   └─ Tasks: 통계, 리포트, 정리

Tier 4: Storage (Stateful)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: Message Broker + Database
Services:
├─ RabbitMQ ×3 (HA Cluster)
│  └─ Queues: q.ai, q.batch, q.api, q.sched, q.dlq
│
├─ PostgreSQL (StatefulSet)
├─ Redis (Result Backend + Cache)
└─ Celery Beat ×1 (스케줄러)
```

---

## 📦 큐 설계 (5개)

### 전체 구조

```mermaid
graph LR
    subgraph Producer["FastAPI Services Tier 2 & 3"]
        Waste["waste-service"]
        Auth["auth-service"]
    end
    
    subgraph RMQ["RabbitMQ HA Cluster Tier 4"]
        Exchange["Topic Exchange
tasks"]
        DLX["Direct Exchange
dlx"]
        
        Q1["q.ai
Priority: 10
AI Vision
TTL: 300s"]
        Q2["q.batch
Priority: 1
배치 작업
TTL: 3600s"]
        Q3["q.api
Priority: 5
외부 API
TTL: 300s"]
        Q4["q.sched
Priority: 3
예약 작업"]
        Q5["q.dlq
Dead Letter
실패 메시지"]
    end
    
    subgraph Workers["Celery Workers"]
        W1["AI Workers x3
Tier 3 Worker-2
gevent pool"]
        W2["Batch Workers x2
Tier 3 Worker-2
processes pool"]
        W3["API Workers x2
Tier 2 Worker-1
gevent pool"]
    end
    
    Waste --> Exchange
    Auth --> Exchange
    
    Exchange -->|"ai.*"| Q1
    Exchange -->|"batch.*"| Q2
    Exchange -->|"api.*"| Q3
    Exchange -->|"sched.*"| Q4
    
    Q1 -.->|failure/TTL| DLX
    Q2 -.->|failure/TTL| DLX
    Q3 -.->|failure/TTL| DLX
    Q4 -.->|failure/TTL| DLX
    DLX --> Q5
    
    Q1 --> W1
    Q2 --> W2
    Q3 --> W3
    Q4 --> W2
    
    style Exchange fill:#ef6c00,color:#fff,stroke:#e65100,stroke-width:4px
    style DLX fill:#c62828,color:#fff,stroke:#b71c1c,stroke-width:3px
    style Q1 fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:3px
    style Q2 fill:#5e35b1,color:#fff,stroke:#4527a0,stroke-width:2px
    style Q3 fill:#00838f,color:#fff,stroke:#006064,stroke-width:3px
    style Q4 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:2px
    style Q5 fill:#b71c1c,color:#fff,stroke:#7f0000,stroke-width:4px
    style W1 fill:#42a5f5,color:#000,stroke:#1976d2,stroke-width:2px
    style W2 fill:#ffa726,color:#000,stroke:#f57c00,stroke-width:2px
    style W3 fill:#66bb6a,color:#000,stroke:#388e3c,stroke-width:2px
```

---

## 📋 Queue 상세

### Queue 1: **q.ai** (AI Vision)

```yaml
큐 이름: q.ai
라우팅 키: ai.*
목적: GPT-4o Vision 분석
배치: Tier 4 (Storage RabbitMQ)
소비: Tier 3 (Worker-2 AI Workers)

담당 작업:
├─ image.analyze (GPT-4o Vision API)
├─ classification.identify
├─ feedback.generate
└─ result.save

Worker 프로파일 (Tier 3):
├─ Replicas: 3
├─ Node: Worker-2
├─ Pool: gevent (네트워크 I/O)
├─ Concurrency: 4
└─ Prefetch: 2

정책 (RabbitMQ):
├─ TTL: 300초 (5분)
├─ max-length: 5,000
├─ DLX: dlx → q.dlq
├─ Priority: 10 (highest)
└─ Type: Quorum Queue (HA)

재시도:
├─ Max Retries: 3
├─ Retry Backoff: True (지수)
└─ acks_late: True (처리 완료 후 ACK)
```

### Queue 2: **q.batch** (배치 작업)

```yaml
큐 이름: q.batch
라우팅 키: batch.*
목적: 시간이 걸리는 배치 작업
배치: Tier 4 (Storage RabbitMQ)
소비: Tier 3 (Worker-2 Batch Workers)

담당 작업:
├─ analytics.daily (일일 통계)
├─ report.generate (리포트 생성)
└─ data.cleanup (데이터 정리)

Worker 프로파일 (Tier 3):
├─ Replicas: 2
├─ Node: Worker-2
├─ Pool: processes (CPU 집약)
├─ Concurrency: 4
└─ Prefetch: 1 (공평성)

정책:
├─ TTL: 3600초 (1시간)
├─ max-length: 1,000
├─ Priority: 1 (lowest)
└─ Type: Quorum Queue

재시도:
├─ Max Retries: 2
├─ Time Limit: 600초 (10분)
└─ acks_late: True
```

### Queue 3: **q.api** (외부 API)

```yaml
큐 이름: q.api
라우팅 키: api.*
목적: 외부 API 호출 (Map, OAuth 등)
배치: Tier 4 (Storage RabbitMQ)
소비: Tier 2 (Worker-1 API Workers)

담당 작업:
├─ map.search (Kakao Map)
├─ oauth.verify (소셜 로그인)
└─ external.call (기타 API)

Worker 프로파일 (Tier 2):
├─ Replicas: 2
├─ Node: Worker-1
├─ Pool: gevent
├─ Concurrency: 4
└─ Prefetch: 2

정책:
├─ TTL: 300초
├─ max-length: 2,000
├─ Priority: 5
└─ Type: Quorum Queue

재시도:
├─ Max Retries: 3
└─ acks_late: True
```

### Queue 4: **q.sched** (예약 작업)

```yaml
큐 이름: q.sched
라우팅 키: sched.*
목적: Celery Beat 예약 작업
배치: Tier 4 (Storage RabbitMQ)
소비: Tier 3 (Worker-2 Batch Workers)
스케줄러: Tier 4 (Storage Celery Beat)

담당 작업:
├─ daily.stats (매일 02:00)
├─ cleanup.cache (매시간)
└─ cleanup.images (매일 03:00)

정책:
├─ TTL: 3600초
├─ max-length: 500
├─ Priority: 3
└─ Type: Quorum Queue

Celery Beat (Tier 4):
├─ Replicas: 1 (중복 방지!)
├─ Node: Storage
└─ Scheduler: DatabaseScheduler
```

### Queue 5: **q.dlq** (Dead Letter Queue)

```yaml
큐 이름: q.dlq
라우팅 키: dlq (Direct)
목적: 실패 메시지 수집 및 분석
배치: Tier 4 (Storage RabbitMQ)

유입 경로:
├─ q.ai 실패 (3회 재시도 후)
├─ q.batch 실패
├─ q.api 타임아웃
└─ q.sched 실패

정책:
├─ TTL: 없음 (영구 보관)
├─ max-length: 10,000
└─ Overflow: drop-head

모니터링:
✅ DLQ 길이 > 100 → Slack 알람
✅ Prometheus 메트릭
```

---

## ⚙️ Celery 설정

### Celery Workers 구성

```python
# Tier 2: Worker-1 - API Workers
app_api_worker = Celery("api_worker")
app_api_worker.conf.update(
    broker_url="amqp://admin:password@rabbitmq.messaging:5672//",
    result_backend="redis://redis.default:6379/1",
    worker_queues=["q.api"],
    worker_pool="gevent",
    worker_concurrency=4,
    worker_prefetch_multiplier=2,
    task_acks_late=True,
    task_time_limit=300,
)

# Tier 3: Worker-2 - AI Workers
app_ai_worker = Celery("ai_worker")
app_ai_worker.conf.update(
    broker_url="amqp://admin:password@rabbitmq.messaging:5672//",
    result_backend="redis://redis.default:6379/1",
    worker_queues=["q.ai"],
    worker_pool="gevent",
    worker_concurrency=4,
    worker_prefetch_multiplier=2,
    task_acks_late=True,
    task_time_limit=300,
)

# Tier 3: Worker-2 - Batch Workers
app_batch_worker = Celery("batch_worker")
app_batch_worker.conf.update(
    broker_url="amqp://admin:password@rabbitmq.messaging:5672//",
    result_backend="redis://redis.default:6379/1",
    worker_queues=["q.batch", "q.sched"],
    worker_pool="processes",
    worker_concurrency=4,
    worker_prefetch_multiplier=1,  # 공평성
    task_acks_late=True,
    task_time_limit=600,
)

# Tier 4: Storage - Celery Beat
app_beat = Celery("beat")
app_beat.conf.beat_schedule = {
    "daily-stats": {
        "task": "tasks.analytics.daily",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "q.sched"},
    },
    "hourly-cleanup": {
        "task": "tasks.cleanup.cache",
        "schedule": crontab(minute=0),
        "options": {"queue": "q.sched"},
    },
}
```

---

## 🚀 K8s Deployment

### AI Worker (Tier 3)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-worker
  namespace: waste
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-worker
      tier: async
  template:
    metadata:
      labels:
        app: ai-worker
        tier: async
    spec:
      nodeSelector:
        workload: async-workers  # Tier 3: Worker-2
      containers:
      - name: worker
        image: ghcr.io/your-org/waste-service:latest
        command:
        - celery
        - -A
        - workers.ai_worker
        - worker
        - --loglevel=info
        - --queues=q.ai
        - --concurrency=4
        - --pool=gevent
        env:
        - name: CELERY_BROKER_URL
          value: "amqp://admin:password@rabbitmq.messaging:5672//"
        - name: CELERY_RESULT_BACKEND
          value: "redis://redis.default:6379/1"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: waste-secrets
              key: openai-api-key
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 2Gi
```

### Batch Worker (Tier 3)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: batch-worker
  namespace: waste
spec:
  replicas: 2
  template:
    spec:
      nodeSelector:
        workload: async-workers  # Tier 3: Worker-2
      containers:
      - name: worker
        command:
        - celery
        - -A
        - workers.batch_worker
        - worker
        - --loglevel=info
        - --queues=q.batch,q.sched
        - --concurrency=4
        - --pool=processes
        - --prefetch-multiplier=1
        resources:
          requests:
            cpu: 300m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
```

### Celery Beat (Tier 4)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-beat
  namespace: messaging
spec:
  replicas: 1  # ⚠️ 반드시 1개!
  template:
    spec:
      nodeSelector:
        workload: storage  # Tier 4: Storage
      containers:
      - name: beat
        command:
        - celery
        - -A
        - workers.batch_worker
        - beat
        - --loglevel=info
        - --scheduler=django_celery_beat.schedulers:DatabaseScheduler
```

---

## 📊 Task 매핑

### 실제 Task 목록

| Task | 시간 | 큐 | Tier | Worker | 라우팅 키 |
|------|------|-----|------|--------|----------|
| image.analyze | 2-5초 | q.ai | 3 | AI ×3 | ai.analyze |
| classification.identify | 1-3초 | q.ai | 3 | AI ×3 | ai.classify |
| feedback.generate | 3-8초 | q.ai | 3 | AI ×3 | ai.feedback |
| map.search | 0.5초 | q.api | 2 | API ×2 | api.map.search |
| oauth.verify | 0.3초 | q.api | 2 | API ×2 | api.oauth |
| analytics.daily | 30-60초 | q.batch | 3 | Batch ×2 | batch.analytics |
| report.generate | 60-120초 | q.batch | 3 | Batch ×2 | batch.report |
| cleanup.cache | 10초 | q.sched | 3 | Batch ×2 | sched.cleanup |
| cleanup.images | 30초 | q.sched | 3 | Batch ×2 | sched.cleanup.images |

---

## 🔍 운영 가이드

### 모니터링

```bash
# RabbitMQ Management UI
kubectl port-forward -n messaging svc/rabbitmq 15672:15672
# http://localhost:15672

# Queue 길이 모니터링
kubectl exec -n messaging rabbitmq-0 -- \
  rabbitmqctl list_queues name messages consumers

# Prometheus 메트릭
rabbitmq_queue_messages{queue="q.ai"}
rabbitmq_queue_messages{queue="q.dlq"}
celery_task_duration_seconds{queue="q.ai"}
```

### 알람 설정

```
Critical:
├─ q.dlq 길이 > 100
├─ q.ai 길이 > 1,000
└─ RabbitMQ 노드 다운

Warning:
├─ q.batch 길이 > 500
├─ AI Worker 실패율 > 10%
└─ Task 처리 시간 > 10초
```

---

## 🎯 핵심 포인트

### 4-Tier 분리의 장점

```
1. 명확한 역할 분리
   ✅ Tier 1: Control Plane
   ✅ Tier 2: Sync API (즉시 응답)
   ✅ Tier 3: Async Workers (백그라운드)
   ✅ Tier 4: Stateful (데이터 안정성)

2. 독립 스케일링 (Instagram 패턴)
   ✅ API만 늘리기: Tier 2 확장
   ✅ AI 처리 늘리기: Tier 3 확장
   ✅ Storage만 확장: Tier 4 복제

3. 장애 격리
   ✅ Tier 2 장애 → Tier 3 정상
   ✅ 외부 API 장애 → q.api만 영향
   ✅ RabbitMQ HA → 자동 복구

4. Robin Storage 패턴
   ✅ Stateful 서비스 격리
   ✅ 백업 용이
   ✅ Control Plane 안정성
```

---

## 📚 참고 문서

- [4-Tier 배포 아키텍처](deployment-architecture-4node.md)
- [Final K8s Architecture](final-k8s-architecture.md)
- [RabbitMQ HA Configuration](../infrastructure/rabbitmq-ha-setup.md)
- [Celery Best Practices](https://docs.celeryq.dev/)

---

**작성일**: 2025-10-31  
**상태**: ✅ 프로덕션 배포 완료  
**비용**: $185/월 (4-Tier Architecture)  
**패턴**: Instagram (Worker 분리) + Robin (Storage 격리)
