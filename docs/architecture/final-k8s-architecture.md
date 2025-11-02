# 🏗️ 최종 Kubernetes 아키텍처

> **AI Waste Coach Backend - 4-Tier 프로덕션 인프라**  
> **날짜**: 2025-10-31  
> **상태**: ✅ 프로덕션 배포 완료

## 📋 목차

1. [전체 아키텍처](#전체-아키텍처)
2. [4-Tier 구성](#4-tier-구성)
3. [서비스 배치](#서비스-배치)
4. [Task Queue 구조](#task-queue-구조)
5. [GitOps 파이프라인](#gitops-파이프라인)
6. [데이터 흐름](#데이터-흐름)

---

## 🌐 전체 아키텍처

```mermaid
graph TB
    subgraph Internet["Internet Layer"]
        Users["Users
Mobile App"]
    end
    
    subgraph AWS["AWS Cloud Services"]
        Route53["Route53
growbin.app"]
        ALB["Application Load Balancer
L7 + SSL/TLS"]
        ACM["ACM Certificate
*.growbin.app"]
        S3["S3 Bucket
Pre-signed URL
Image Storage"]
    end
    
    subgraph K8s["Kubernetes Cluster 4-Tier"]
        subgraph Tier1["Tier 1: Control + Monitoring"]
            CP["Control Plane
• kube-apiserver
• etcd
• scheduler
• controller"]
            ArgoCD["ArgoCD
GitOps CD"]
            Prom["Prometheus
Grafana"]
        end
        
        subgraph Tier2["Tier 2: Sync API"]
            AuthSvc["auth-service x2"]
            UsersSvc["users-service x1"]
            LocSvc["locations-service x1"]
        end
        
        subgraph Tier3["Tier 3: Async Workers"]
            WasteSvc["waste-service x2"]
            AIW["AI Workers x3
GPT-4o Vision"]
            BatchW["Batch Workers x2"]
        end
        
        subgraph Tier4["Tier 4: Stateful Storage"]
            RMQ["RabbitMQ HA x3
5 Queues"]
            DB["PostgreSQL
StatefulSet 50GB"]
            Redis["Redis
Result Backend"]
            Beat["Celery Beat x1"]
        end
    end
    
    subgraph GitHub["GitHub"]
        Code["Code Repo"]
        Charts["Helm Charts"]
        GHA["GitHub Actions"]
        GHCR["GHCR Registry"]
    end
    
    subgraph External["External APIs"]
        OpenAI["OpenAI
GPT-4o Vision"]
        KakaoMap["Kakao Map"]
    end
    
    Users --> Route53
    Route53 --> ALB
    ACM -.->|SSL Cert| ALB
    ALB --> Tier2
    ALB --> ArgoCD
    ALB --> Prom
    
    Tier2 -->|publish| Tier4
    Tier3 -->|consume| Tier4
    
    WasteSvc --> S3
    AIW --> OpenAI
    LocSvc --> KakaoMap
    
    AuthSvc --> DB
    WasteSvc --> DB
    WasteSvc --> Redis
    
    Code --> GHA
    GHA --> GHCR
    GHA --> Charts
    Charts --> ArgoCD
    ArgoCD -.->|deploy| Tier2
    ArgoCD -.->|deploy| Tier3
    
    GHCR -.->|pull| Tier2
    GHCR -.->|pull| Tier3
    
    style Internet fill:#0d47a1,color:#fff,stroke:#01579b,stroke-width:3px
    style AWS fill:#ff6f00,color:#fff,stroke:#e65100,stroke-width:3px
    style K8s fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:4px
    style Tier1 fill:#1976d2,color:#fff,stroke:#1565c0,stroke-width:3px
    style Tier2 fill:#388e3c,color:#fff,stroke:#2e7d32,stroke-width:3px
    style Tier3 fill:#f57c00,color:#fff,stroke:#ef6c00,stroke-width:3px
    style Tier4 fill:#c2185b,color:#fff,stroke:#ad1457,stroke-width:3px
    style GitHub fill:#6a1b9a,color:#fff,stroke:#4a148c,stroke-width:2px
    style External fill:#00838f,color:#fff,stroke:#006064,stroke-width:2px
```

---

## 🖥️ 4-Tier 구성

### Tier 1: Control + Monitoring

```mermaid
graph TB
    subgraph Master["Master Node - t3.large 8GB 80GB - $60/month"]
        CP["Control Plane
 
kube-apiserver
etcd
scheduler
controller-manager"]
        
        Monitor["Monitoring
 
Prometheus
Grafana
Metrics Server"]
        
        GitOps["GitOps
 
ArgoCD x3 pods
argocd-server
argocd-repo-server
argocd-app-controller"]
        
        ALBC["AWS LB Controller x1"]
        CertMgr["cert-manager x3"]
    end
    
    CP -.->|orchestrate| Monitor
    CP -.->|orchestrate| GitOps
    
    style Master fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:3px
    style CP fill:#1976d2,color:#fff,stroke:#1565c0,stroke-width:2px
    style Monitor fill:#42a5f5,color:#000,stroke:#1976d2,stroke-width:2px
    style GitOps fill:#5c6bc0,color:#fff,stroke:#3f51b5,stroke-width:2px
    style ALBC fill:#7e57c2,color:#fff,stroke:#673ab7,stroke-width:2px
    style CertMgr fill:#ab47bc,color:#fff,stroke:#9c27b0,stroke-width:2px
```

**리소스 할당:**
```
vCPU: 2 cores
Memory: 8GB
Disk: 80GB (gp3)
비용: $60/월

사용률:
├─ Control Plane: 0.5 CPU, 1.5GB
├─ etcd: 0.2 CPU, 0.5GB
├─ Prometheus: 0.3 CPU, 1.5GB
├─ Grafana: 0.2 CPU, 0.5GB
└─ ArgoCD: 0.3 CPU, 1GB

여유: 0.5 CPU, 3GB (30%)
```

### Tier 2: Sync API (Application)

```mermaid
graph TB
    subgraph Worker1["Worker-1 Node - t3.medium 4GB 40GB - $30/month"]
        Auth["auth-service x2
 
OAuth 2.0
JWT Token
FastAPI"]
        
        Users["users-service x1
 
Profile
History
FastAPI"]
        
        Locations["locations-service x1
 
Bin Search
Kakao Map
FastAPI"]
        
        APIW["API Workers x2
 
q.api
Kakao Map
OAuth Verify"]
    end
    
    style Worker1 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:3px
    style Auth fill:#4caf50,color:#000,stroke:#388e3c,stroke-width:2px
    style Users fill:#66bb6a,color:#000,stroke:#4caf50,stroke-width:2px
    style Locations fill:#81c784,color:#000,stroke:#66bb6a,stroke-width:2px
    style APIW fill:#a5d6a7,color:#000,stroke:#81c784,stroke-width:2px
```

**리소스 할당:**
```
vCPU: 2 cores
Memory: 4GB
Disk: 40GB (gp3)
비용: $30/월

배치:
├─ auth-service ×2: 200m CPU, 256Mi
├─ users-service ×1: 100m CPU, 128Mi
├─ locations-service ×1: 100m CPU, 128Mi
└─ API Workers ×2: 200m CPU, 256Mi

여유: 1.2 CPU, 2.8GB (60%)
패턴: Reactor (Sync, 즉시 응답 <100ms)
```

### Tier 3: Async Workers

```mermaid
graph TB
    subgraph Worker2["Worker-2 Node - t3.medium 4GB 40GB - $30/month"]
        Waste["waste-service x2
 
Image Analysis API
FastAPI"]
        
        AIWorker["AI Workers x3
 
q.ai
GPT-4o Vision
gevent pool
concurrency: 4"]
        
        BatchWorker["Batch Workers x2
 
q.batch, q.sched
processes pool
concurrency: 4"]
    end
    
    style Worker2 fill:#f57c00,color:#fff,stroke:#e65100,stroke-width:3px
    style Waste fill:#ff9800,color:#000,stroke:#f57c00,stroke-width:2px
    style AIWorker fill:#ffb74d,color:#000,stroke:#ff9800,stroke-width:2px
    style BatchWorker fill:#ffcc80,color:#000,stroke:#ffb74d,stroke-width:2px
```

**리소스 할당:**
```
vCPU: 2 cores
Memory: 4GB
Disk: 40GB (gp3)
비용: $30/월

배치:
├─ waste-service ×2: 400m CPU, 512Mi
├─ AI Workers ×3: 1500m CPU, 3Gi
└─ Batch Workers ×2: 600m CPU, 1Gi

여유: 0.4 CPU, 1.1GB (25%)
패턴: Task Queue (Async, 백그라운드)
```

### Tier 4: Stateful Storage

```mermaid
graph TB
    subgraph StorageNode["Storage Node - t3.large 8GB 100GB - $60/month"]
        RMQ["RabbitMQ HA Cluster
 
3 nodes (quorum)
5 queues
20GB x 3 PVC"]
        
        DB["PostgreSQL
 
StatefulSet
50GB PVC
auth, users, waste schemas"]
        
        RedisD["Redis
 
Deployment
Result Backend
Cache 7-day TTL"]
        
        BeatD["Celery Beat x1
 
Scheduler
DatabaseScheduler
Prevent Duplicate"]
    end
    
    RMQ -.->|depends| DB
    RMQ -.->|depends| RedisD
    
    style StorageNode fill:#c2185b,color:#fff,stroke:#880e4f,stroke-width:3px
    style RMQ fill:#e91e63,color:#fff,stroke:#c2185b,stroke-width:2px
    style DB fill:#ec407a,color:#fff,stroke:#d81b60,stroke-width:2px
    style RedisD fill:#f06292,color:#000,stroke:#ec407a,stroke-width:2px
    style BeatD fill:#f48fb1,color:#000,stroke:#f06292,stroke-width:2px
```

**리소스 할당:**
```
vCPU: 2 cores
Memory: 8GB
Disk: 100GB (gp3)
비용: $60/월

배치:
├─ RabbitMQ ×3: 600m CPU, 3Gi (HA)
├─ PostgreSQL: 500m CPU, 2Gi
├─ Redis: 200m CPU, 1Gi
└─ Celery Beat: 50m CPU, 128Mi

여유: 0.7 CPU, 2GB (25%)
패턴: Robin Storage (Stateful 격리)
```

---

## 🐰 Task Queue 구조

### Queue → Worker 매핑

```mermaid
graph LR
    subgraph Tier4RMQ["Tier 4: RabbitMQ HA"]
        Q1["q.ai
Priority: 10
GPT-4o Vision"]
        Q2["q.batch
Priority: 1
Batch Jobs"]
        Q3["q.api
Priority: 5
External API"]
        Q4["q.sched
Priority: 3
Scheduled"]
        Q5["q.dlq
Dead Letter"]
    end
    
    subgraph Tier3W["Tier 3: Workers"]
        AI["AI Workers x3
Worker-2"]
        Batch["Batch Workers x2
Worker-2"]
    end
    
    subgraph Tier2W["Tier 2: Workers"]
        API["API Workers x2
Worker-1"]
    end
    
    Q1 --> AI
    Q2 --> Batch
    Q3 --> API
    Q4 --> Batch
    
    Q1 -.->|failure| Q5
    Q2 -.->|failure| Q5
    Q3 -.->|failure| Q5
    Q4 -.->|failure| Q5
    
    style Tier4RMQ fill:#c2185b,color:#fff,stroke:#880e4f,stroke-width:3px
    style Tier3W fill:#f57c00,color:#fff,stroke:#e65100,stroke-width:3px
    style Tier2W fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:3px
    style Q1 fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:2px
    style Q2 fill:#5e35b1,color:#fff,stroke:#4527a0,stroke-width:2px
    style Q3 fill:#00838f,color:#fff,stroke:#006064,stroke-width:2px
    style Q4 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:2px
    style Q5 fill:#b71c1c,color:#fff,stroke:#7f0000,stroke-width:3px
    style AI fill:#ffa726,color:#000,stroke:#f57c00,stroke-width:2px
    style Batch fill:#ffb74d,color:#000,stroke:#ffa726,stroke-width:2px
    style API fill:#66bb6a,color:#000,stroke:#4caf50,stroke-width:2px
```

### Queue별 처리

```
q.ai (Tier 3, AI Workers x3):
├─ image.analyze (GPT-4o Vision, 2-5초)
├─ classification.identify (1-3초)
├─ feedback.generate (3-8초)
└─ 처리량: ~20 req/min

q.batch (Tier 3, Batch Workers x2):
├─ analytics.daily (30-60초)
├─ report.generate (60-120초)
└─ 처리량: ~2 req/min

q.api (Tier 2, API Workers x2):
├─ map.search (Kakao Map, 0.5초)
├─ oauth.verify (소셜 로그인, 0.3초)
└─ 처리량: ~100 req/min

q.sched (Tier 3, Batch Workers):
├─ cleanup.cache (매시간)
├─ backup.database (매일 02:00)
└─ stats.aggregate (매일 03:00)

q.dlq (Tier 4, 모니터링만):
└─ 실패 메시지 수집 및 재처리
```

---

## 🔄 GitOps 파이프라인

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant GH as GitHub Repo
    participant GHA as GitHub Actions
    participant GHCR as GHCR Registry
    participant Helm as Helm Charts
    participant Argo as ArgoCD Tier 1
    participant K8s as Kubernetes Tier 2-3
    participant ALB as AWS ALB
    
    Dev->>GH: 1. Code Push services/waste/
    GH->>GHA: 2. Trigger CI
    
    activate GHA
    GHA->>GHA: 3. Lint Black Flake8
    GHA->>GHA: 4. Test pytest
    GHA->>GHA: 5. Docker Build
    GHA->>GHCR: 6. Push waste:sha-abc123
    GHA->>Helm: 7. Update values.yaml tag
    deactivate GHA
    
    Note over Argo: 8. Git Poll 3min
    
    activate Argo
    Argo->>Helm: 9. Detect Change
    Argo->>Argo: 10. Helm Template
    Argo->>Argo: 11. Diff Calculate
    Argo->>K8s: 12. kubectl apply Auto Sync
    deactivate Argo
    
    activate K8s
    K8s->>GHCR: 13. Pull waste:sha-abc123
    K8s->>K8s: 14. Rolling Update
    K8s->>K8s: 15. Health Check
    K8s->>ALB: 16. Target Registration
    deactivate K8s
    
    K8s-->>Argo: 17. Sync Complete
    Argo-->>Dev: 18. Slack Notification
```

---

## 📊 데이터 흐름

### 이미지 분석 전체 흐름

```mermaid
sequenceDiagram
    actor User as 사용자
    participant App as Mobile App
    participant ALB as AWS ALB
    participant Waste as waste-service Tier 3
    participant RMQ as RabbitMQ Tier 4
    participant AIW as AI Worker Tier 3
    participant DB as PostgreSQL Tier 4
    participant Redis as Redis Tier 4
    participant S3 as AWS S3
    participant OpenAI as OpenAI API
    
    User->>App: 쓰레기 사진 촬영
    App->>ALB: POST /api/v1/waste/analyze
    ALB->>Waste: 라우팅
    
    Waste->>Waste: Job ID 생성
    Waste->>App: S3 Pre-signed URL
    App->>S3: 이미지 직접 업로드
    
    App->>Waste: POST /upload-complete/{job_id}
    Waste->>RMQ: Publish q.ai ai.analyze
    
    activate AIW
    RMQ->>AIW: Consume Priority 10
    AIW->>S3: 이미지 다운로드
    AIW->>Redis: 캐시 확인
    
    alt 캐시 히트 70%
        Redis-->>AIW: 결과 반환
        AIW->>App: 즉시 응답 1초
    else 캐시 미스 30%
        AIW->>OpenAI: GPT-4o Vision API
        OpenAI-->>AIW: 분류 결과
        AIW->>DB: 결과 저장
        AIW->>Redis: 캐싱 7일
    end
    deactivate AIW
    
    loop Polling 0.5초
        App->>Waste: GET /status/{job_id}
        Waste->>Redis: 진행률 조회
        Redis-->>App: progress: 80%
    end
    
    App->>Waste: GET /result/{job_id}
    Waste->>Redis: 최종 결과
    Redis-->>App: 결과 반환
    
    App->>User: 결과 표시
```

---

## 🗺️ 서비스 배치

### Namespace별 서비스

```mermaid
graph TB
    subgraph T1["Tier 1: Master"]
        NS_ArgoCD["argocd namespace
 
ArgoCD GitOps CD"]
        
        NS_Monitor["monitoring namespace
 
Prometheus
Grafana"]
    end
    
    subgraph T2["Tier 2: Worker-1"]
        NS_Auth["auth namespace
 
auth-service x2
OAuth JWT"]
        
        NS_Users["users namespace
 
users-service x1
Profile History"]
        
        NS_Loc["locations namespace
 
locations-service x1
Bin Search"]
    end
    
    subgraph T3["Tier 3: Worker-2"]
        NS_Waste["waste namespace
 
waste-service x2
AI Workers x3
Batch Workers x2"]
    end
    
    subgraph T4["Tier 4: Storage"]
        NS_Msg["messaging namespace
 
RabbitMQ x3 HA
5 Queues"]
        
        NS_Default["default namespace
 
PostgreSQL
Redis
Celery Beat"]
    end
    
    NS_Waste -->|tasks| NS_Msg
    NS_Auth --> NS_Default
    NS_Users --> NS_Default
    NS_Waste --> NS_Default
    
    style T1 fill:#1565c0,color:#fff,stroke:#0d47a1,stroke-width:2px
    style T2 fill:#2e7d32,color:#fff,stroke:#1b5e20,stroke-width:2px
    style T3 fill:#f57c00,color:#fff,stroke:#e65100,stroke-width:2px
    style T4 fill:#c2185b,color:#fff,stroke:#880e4f,stroke-width:2px
    style NS_ArgoCD fill:#5c6bc0,color:#fff,stroke:#3f51b5,stroke-width:2px
    style NS_Monitor fill:#7e57c2,color:#fff,stroke:#673ab7,stroke-width:2px
    style NS_Auth fill:#66bb6a,color:#000,stroke:#4caf50,stroke-width:2px
    style NS_Users fill:#81c784,color:#000,stroke:#66bb6a,stroke-width:2px
    style NS_Loc fill:#a5d6a7,color:#000,stroke:#81c784,stroke-width:2px
    style NS_Waste fill:#ffa726,color:#000,stroke:#f57c00,stroke-width:2px
    style NS_Msg fill:#ec407a,color:#fff,stroke:#d81b60,stroke-width:2px
    style NS_Default fill:#f06292,color:#000,stroke:#ec407a,stroke-width:2px
```

---

## 🎯 핵심 사양

### 클러스터

```
Kubernetes (kubeadm):
├─ Version: v1.28
├─ CNI: Calico VXLAN (BGP 비활성화)
├─ Nodes: 4개 (4-Tier)
├─ HA: non-HA (단일 Master)
└─ 패턴: Instagram + Robin Storage

총 리소스:
├─ vCPU: 8 cores
├─ Memory: 24GB
├─ Storage: 260GB
└─ 비용: $185/월
```

### 네트워킹

```
AWS Load Balancer Controller:
├─ Type: Application Load Balancer (L7)
├─ SSL/TLS: ACM (자동 갱신)
├─ Routing: Path-based
└─ Target: IP (Pod 직접 연결)

Path Routes:
├─ /argocd          → argocd-server (Tier 1)
├─ /grafana         → grafana (Tier 1)
├─ /api/v1/auth/*   → auth-service (Tier 2)
├─ /api/v1/users/*  → users-service (Tier 2)
├─ /api/v1/waste/*  → waste-service (Tier 3)
├─ /api/v1/locations/* → locations-service (Tier 2)
└─ /                → default-backend
```

### Stateful Services (Tier 4)

```
PostgreSQL:
├─ Type: StatefulSet
├─ PVC: 50GB EBS gp3
├─ Schemas: auth, users, waste
└─ Backup: etcd 백업 포함

Redis:
├─ Type: Deployment
├─ 용도: Celery Result Backend, Cache
└─ TTL: 7일

RabbitMQ:
├─ Type: StatefulSet (HA 3-node)
├─ PVC: 20GB × 3
├─ Queues: 5개 (Quorum Queue)
└─ Management UI: 포트 15672
```

---

## 📈 확장 전략

### Tier별 독립 스케일링

```
Tier 2 확장 (API 트래픽 증가):
├─ Worker-1 노드 추가
├─ auth-service HPA (2 → 5)
└─ 비용: +$30/월

Tier 3 확장 (AI 처리 증가):
├─ Worker-2 노드 추가
├─ AI Workers HPA (3 → 10)
└─ 비용: +$30/월

Tier 4 확장 (Storage 증가):
├─ PostgreSQL 읽기 복제본
├─ Redis Cluster (3-node)
└─ 비용: +$60/월
```

### HPA 설정

```yaml
# AI Worker HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-worker
  namespace: waste
spec:
  scaleTargetRef:
    kind: Deployment
    name: ai-worker
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: External
    external:
      metric:
        name: rabbitmq_queue_messages
        selector:
          matchLabels:
            queue: q.ai
      target:
        type: AverageValue
        averageValue: "10"
```

---

## 🔒 보안

### Network Policies

```yaml
# Tier 4 격리 (Robin Storage Pattern)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: storage-isolation
  namespace: messaging
spec:
  podSelector:
    matchLabels:
      app: rabbitmq
  policyTypes:
  - Ingress
  ingress:
  # Tier 2 Worker-1
  - from:
    - namespaceSelector:
        matchLabels:
          tier: sync-api
    ports:
    - protocol: TCP
      port: 5672
  # Tier 3 Worker-2
  - from:
    - namespaceSelector:
        matchLabels:
          tier: async-workers
    ports:
    - protocol: TCP
      port: 5672
```

---

## 📊 모니터링

### Prometheus Metrics

```
Tier 1 (Master):
├─ node_cpu_usage
├─ node_memory_usage
├─ etcd_health
└─ apiserver_latency

Tier 2 (Worker-1):
├─ pod_cpu_usage{tier="sync-api"}
├─ pod_memory_usage{tier="sync-api"}
├─ http_request_duration_seconds
└─ http_requests_total

Tier 3 (Worker-2):
├─ celery_task_duration_seconds{queue="q.ai"}
├─ celery_task_failures_total
├─ pod_cpu_usage{tier="async-workers"}
└─ pod_memory_usage{tier="async-workers"}

Tier 4 (Storage):
├─ rabbitmq_queue_messages{queue="q.ai"}
├─ rabbitmq_queue_messages{queue="q.dlq"}
├─ postgresql_connections_active
├─ redis_memory_used_bytes
└─ rabbitmq_cluster_status
```

### Grafana Dashboards

```
1. Cluster Overview
   ├─ 4-Tier Node Status
   ├─ Total Resource Usage
   └─ Pod Distribution

2. Tier별 Dashboard
   ├─ Tier 1: Control Plane Health
   ├─ Tier 2: API Performance
   ├─ Tier 3: Worker Queue Length
   └─ Tier 4: Storage Metrics

3. RabbitMQ Dashboard
   ├─ Queue Lengths (5개)
   ├─ Consumer Count
   ├─ Message Rates
   └─ DLQ Monitoring
```

---

## 🎯 요약

### 4-Tier Architecture

```
Tier 1: Control + Monitoring (Master, $60)
└─ Kubernetes Control Plane + Observability

Tier 2: Sync API (Worker-1, $30)
└─ FastAPI Reactor Pattern (즉시 응답)

Tier 3: Async Workers (Worker-2, $30)
└─ Celery Task Queue (백그라운드 처리)

Tier 4: Stateful Storage (Storage, $60)
└─ RabbitMQ HA + PostgreSQL + Redis (Robin 패턴)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총: $185/월, 8 vCPU, 24GB RAM
패턴: Instagram (분리) + Robin (격리)
```

### Task Queue

```
5개 Queue (RabbitMQ HA, Tier 4):
├─ q.ai (AI Vision, Priority 10)
├─ q.batch (배치, Priority 1)
├─ q.api (외부 API, Priority 5)
├─ q.sched (예약, Priority 3)
└─ q.dlq (실패 메시지)

7개 Celery Workers:
├─ Tier 2: API Workers ×2
├─ Tier 3: AI Workers ×3
├─ Tier 3: Batch Workers ×2
└─ Tier 4: Celery Beat ×1

장점:
✅ Queue 폭주 방지 (TTL + max-length)
✅ 장애 격리 (Queue별 분리)
✅ HA 클러스터 (3-node)
✅ 독립 스케일링 (Tier별)
```

---

## 📚 관련 문서

- [4-Tier 배포 아키텍처](deployment-architecture-4node.md) - 전체 시스템
- [Task Queue 설계](task-queue-design.md) - RabbitMQ + Celery
- [VPC 네트워크 설계](../infrastructure/vpc-network-design.md) - 보안 그룹
- [배포 가이드](../../DEPLOYMENT_GUIDE.md) - 자동 배포

---

**작성일**: 2025-10-31  
**구성**: 4-Tier Kubernetes + AWS ALB + RabbitMQ HA  
**총 비용**: $185/월  
**상태**: ✅ 프로덕션 배포 완료  
**패턴**: Instagram (Worker 분리) + Robin Storage (Stateful 격리)
