# 🏗️ 최종 Kubernetes 아키텍처

> **AI Waste Coach Backend - 4-Node 프로덕션 인프라**  
> **날짜**: 2025-10-31  
> **상태**: ✅ 프로덕션 배포 완료

## 📋 목차

1. [전체 아키텍처](#전체-아키텍처)
2. [4-Node 클러스터 구성](#4-node-클러스터-구성)
3. [마이크로서비스 배치](#마이크로서비스-배치)
4. [Task Queue 구조](#task-queue-구조)
5. [GitOps 파이프라인](#gitops-파이프라인)
6. [데이터 흐름](#데이터-흐름)

---

## 🌐 전체 아키텍처

```mermaid
graph TB
    subgraph Internet["🌐 인터넷"]
        Users[사용자<br/>Mobile App]
    end
    
    subgraph AWS["AWS Cloud"]
        Route53[Route53<br/>growbin.app]
        ACM[ACM Certificate<br/>*.growbin.app]
        ALB[Application Load Balancer<br/>L7 Routing + SSL]
        S3[S3 Bucket<br/>이미지 저장<br/>Pre-signed URL]
    end
    
    subgraph K8s["Kubernetes Cluster (4-Node, Self-Managed)"]
        subgraph Master["Master Node (t3.large, 8GB)"]
            CP[Control Plane<br/>API Server<br/>etcd<br/>Scheduler<br/>Controller]
            ArgoCD[ArgoCD<br/>GitOps Engine]
            Prom[Prometheus<br/>Grafana]
        end
        
        subgraph Worker1["Worker-1 (t3.medium, 4GB) - Application"]
            AuthSvc[auth-service ×2]
            UsersSvc[users-service ×1]
            LocSvc[locations-service ×1]
        end
        
        subgraph Worker2["Worker-2 (t3.medium, 4GB) - Async Workers"]
            CeleryAI[celery-ai-worker ×3<br/>GPT-4o Vision]
            CeleryBatch[celery-batch-worker ×2]
            WasteSvc[waste-service ×2]
        end
        
        subgraph Storage["Storage Node (t3.large, 8GB) - Stateful"]
            RabbitMQ[RabbitMQ HA<br/>3-node cluster<br/>5 Queues]
            DB[(PostgreSQL<br/>StatefulSet)]
            Redis[(Redis<br/>Result Backend)]
        end
        
        ALBC[AWS Load Balancer<br/>Controller]
    end
    
    subgraph GitHub["GitHub"]
        Code[Code Repository]
        Charts[Helm Charts]
        GHA[GitHub Actions<br/>CI Pipeline]
        GHCR[GHCR<br/>Container Registry]
    end
    
    subgraph External["외부 서비스"]
        OpenAI[OpenAI API<br/>GPT-4o Vision]
        KakaoMap[Kakao Map API]
    end
    
    Users --> Route53
    Route53 --> ALB
    ACM -.->|SSL Cert| ALB
    ALB --> ALBC
    
    ALBC -->|/api/v1/auth| AuthSvc
    ALBC -->|/api/v1/users| UsersSvc
    ALBC -->|/api/v1/waste| WasteSvc
    ALBC -->|/argocd| ArgoCD
    ALBC -->|/grafana| Prom
    
    WasteSvc --> RabbitMQ
    CeleryAI --> RabbitMQ
    CeleryBatch --> RabbitMQ
    
    AuthSvc --> DB
    WasteSvc --> DB
    WasteSvc --> Redis
    WasteSvc --> S3
    
    CeleryAI --> OpenAI
    LocSvc --> KakaoMap
    
    Code --> GHA
    GHA --> GHCR
    GHA --> Charts
    Charts --> ArgoCD
    ArgoCD -.->|배포| WasteSvc
    
    GHCR -.->|Pull Image| WasteSvc
    
    style Users fill:#cce5ff,stroke:#007bff,stroke-width:4px
    style ALB fill:#ff9900,stroke:#ff6600,stroke-width:4px
    style Master fill:#e3f2fd,stroke:#0d47a1,stroke-width:3px
    style Worker1 fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    style Worker2 fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style Storage fill:#fce4ec,stroke:#880e4f,stroke-width:3px
    style ArgoCD fill:#e6d5ff,stroke:#8844ff,stroke-width:3px
    style RabbitMQ fill:#ffe0b3,stroke:#fd7e14,stroke-width:3px
```

---

## 🖥️ 4-Node 클러스터 구성

### 노드별 역할 (Instagram + Robin Storage 패턴)

```mermaid
graph TB
    subgraph Tier1["Tier 1: Control + Monitoring"]
        Master[Master Node<br/>t3.large, 8GB, 80GB<br/>$60/월<br/><br/>Control Plane:<br/>- kube-apiserver<br/>- etcd<br/>- scheduler<br/>- controller<br/><br/>Monitoring:<br/>- Prometheus<br/>- Grafana<br/>- Metrics Server<br/><br/>GitOps:<br/>- ArgoCD]
    end
    
    subgraph Tier2["Tier 2: Sync API (Application)"]
        Worker1[Worker-1 Node<br/>t3.medium, 4GB, 40GB<br/>$30/월<br/><br/>FastAPI Pods:<br/>- auth-service ×2<br/>- users-service ×1<br/>- locations-service ×1<br/><br/>Pattern:<br/>Reactor (Sync API)]
    end
    
    subgraph Tier3["Tier 3: Async Workers"]
        Worker2[Worker-2 Node<br/>t3.medium, 4GB, 40GB<br/>$30/월<br/><br/>Celery Workers:<br/>- AI Worker ×3<br/>- Batch Worker ×2<br/>- waste-service ×2<br/><br/>Pattern:<br/>Task Queue]
    end
    
    subgraph Tier4["Tier 4: Stateful Storage"]
        Storage[Storage Node<br/>t3.large, 8GB, 100GB<br/>$60/월<br/><br/>Stateful Services:<br/>- RabbitMQ ×3 (HA)<br/>- PostgreSQL<br/>- Redis<br/><br/>Pattern:<br/>Robin Storage]
    end
    
    Master -.->|orchestrate| Worker1
    Master -.->|orchestrate| Worker2
    Master -.->|orchestrate| Storage
    Worker1 -->|publish task| Storage
    Worker2 -->|consume task| Storage
    
    style Master fill:#e3f2fd,stroke:#0d47a1,stroke-width:3px
    style Worker1 fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    style Worker2 fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style Storage fill:#fce4ec,stroke:#880e4f,stroke-width:3px
```

### 리소스 할당 및 비용

```
Tier 1: Master (Control + Monitoring)
├─ Instance: t3.large (2 vCPU, 8GB RAM, 80GB EBS)
├─ 비용: $60/월
├─ 사용률:
│  ├─ Control Plane: 0.5 CPU, 1.5GB
│  ├─ etcd: 0.2 CPU, 0.5GB
│  ├─ Prometheus: 0.3 CPU, 1.5GB
│  ├─ Grafana: 0.2 CPU, 0.5GB
│  └─ ArgoCD: 0.3 CPU, 1GB
└─ 여유: 0.5 CPU, 3GB (30%)

Tier 2: Worker-1 (Application)
├─ Instance: t3.medium (2 vCPU, 4GB RAM, 40GB EBS)
├─ 비용: $30/월
├─ 사용률:
│  ├─ auth-service ×2: 0.4 CPU, 0.6GB
│  ├─ users-service ×1: 0.2 CPU, 0.3GB
│  └─ locations-service ×1: 0.2 CPU, 0.3GB
└─ 여유: 1.2 CPU, 2.8GB (60%)

Tier 3: Worker-2 (Async)
├─ Instance: t3.medium (2 vCPU, 4GB RAM, 40GB EBS)
├─ 비용: $30/월
├─ 사용률:
│  ├─ celery-ai-worker ×3: 0.8 CPU, 1.5GB
│  ├─ celery-batch-worker ×2: 0.4 CPU, 0.8GB
│  └─ waste-service ×2: 0.4 CPU, 0.6GB
└─ 여유: 0.4 CPU, 1.1GB (25%)

Tier 4: Storage (Stateful)
├─ Instance: t3.large (2 vCPU, 8GB RAM, 100GB EBS)
├─ 비용: $60/월
├─ 사용률:
│  ├─ RabbitMQ ×3: 0.6 CPU, 3GB
│  ├─ PostgreSQL ×1: 0.5 CPU, 2GB
│  └─ Redis ×1: 0.2 CPU, 1GB
└─ 여유: 0.7 CPU, 2GB (25%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 리소스:
├─ 노드: 4개
├─ vCPU: 8 cores
├─ Memory: 24GB
├─ Storage: 260GB
└─ 비용: $185/월 (EC2 $180 + S3 $5)
```

---

## 🐰 Task Queue 구조

### RabbitMQ + Celery (5개 큐)

```mermaid
graph LR
    subgraph Producer["API Services"]
        Waste[waste-service]
        Recycling[recycling-service]
    end
    
    subgraph RMQ["RabbitMQ HA (Storage Node)"]
        Exchange[Topic Exchange<br/>'tasks']
        
        Q1[q.ai<br/>Priority: 10<br/>AI Vision<br/>TTL: 300s]
        Q2[q.batch<br/>Priority: 1<br/>배치 작업<br/>TTL: 3600s]
        Q3[q.api<br/>Priority: 5<br/>외부 API<br/>TTL: 300s]
        Q4[q.sched<br/>Priority: 3<br/>예약 작업]
        Q5[q.dlq<br/>Dead Letter<br/>실패 메시지]
    end
    
    subgraph Workers["Celery Workers"]
        W1[AI Worker ×3<br/>Worker-2<br/>gevent pool]
        W2[Batch Worker ×2<br/>Worker-2<br/>processes pool]
        W3[API Worker ×2<br/>Worker-1]
    end
    
    Waste --> Exchange
    Recycling --> Exchange
    
    Exchange -->|ai.*| Q1
    Exchange -->|batch.*| Q2
    Exchange -->|api.*| Q3
    Exchange -->|sched.*| Q4
    
    Q1 -.->|DLX| Q5
    Q2 -.->|DLX| Q5
    Q3 -.->|DLX| Q5
    
    Q1 --> W1
    Q2 --> W2
    Q3 --> W3
    Q4 --> W2
    
    style Exchange fill:#ffe0b3,stroke:#fd7e14,stroke-width:4px
    style Q1 fill:#ffd1d1,stroke:#dc3545,stroke-width:3px
    style Q5 fill:#ffb3b3,stroke:#dc3545,stroke-width:4px
    style W1 fill:#cce5ff,stroke:#007bff,stroke-width:2px
```

### Queue별 작업

```
q.ai (Worker-2, prefetch=2):
├─ image.analyze (GPT-4o Vision, 2-5초)
├─ image.classify (Vision Model, 1-3초)
└─ 처리량: ~20 req/min

q.batch (Worker-2, prefetch=1):
├─ analytics.daily (30-60초)
├─ report.generate (60-120초)
└─ 처리량: ~2 req/min

q.api (Worker-1, prefetch=4):
├─ map.search (Kakao Map, 0.5초)
├─ oauth.verify (소셜 로그인, 0.3초)
└─ 처리량: ~100 req/min

q.sched (Worker-2):
├─ cleanup.cache (매시간)
├─ backup.database (매일 02:00)
└─ stats.aggregate (매일 03:00)

q.dlq:
└─ 실패 메시지 수집 및 재처리
```

---

## 🔄 GitOps 파이프라인

### CI/CD 전체 흐름

```mermaid
sequenceDiagram
    actor Dev as 개발자
    participant GH as GitHub<br/>Repository
    participant GHA as GitHub Actions
    participant GHCR as GHCR<br/>ghcr.io
    participant Helm as Helm Charts<br/>(Git)
    participant Argo as ArgoCD<br/>(Master)
    participant K8s as Kubernetes
    participant ALB as AWS ALB
    
    Dev->>GH: 1. services/waste/ 수정 & Push
    GH->>GHA: 2. ci-waste.yml 트리거
    
    activate GHA
    GHA->>GHA: 3. Lint (Black, Flake8)
    GHA->>GHA: 4. Test (pytest)
    GHA->>GHA: 5. Docker Build
    GHA->>GHCR: 6. Push waste:sha-abc123
    GHA->>Helm: 7. values.yaml 업데이트<br/>image.tag: sha-abc123
    deactivate GHA
    
    Note over Argo: 8. Git 폴링 (3분마다)
    
    activate Argo
    Argo->>Helm: 9. 변경 감지!
    Argo->>Argo: 10. Helm Template 렌더링
    Argo->>Argo: 11. Diff 계산
    Argo->>K8s: 12. kubectl apply (자동 Sync)
    deactivate Argo
    
    activate K8s
    K8s->>GHCR: 13. Pull waste:sha-abc123
    K8s->>K8s: 14. Rolling Update (무중단)
    K8s->>K8s: 15. Health Check
    K8s->>ALB: 16. Target Registration
    deactivate K8s
    
    K8s-->>Argo: 17. Sync 완료
    Argo-->>Dev: 18. Slack 알림: ✅ 배포 성공
```

---

## 🗺️ 마이크로서비스 배치

### Namespace별 서비스

```mermaid
graph TB
    subgraph NS1["argocd namespace"]
        Argo[ArgoCD<br/>GitOps CD<br/>Master Node]
    end
    
    subgraph NS2["auth namespace (Worker-1)"]
        Auth[auth-service ×2<br/>OAuth, JWT<br/>FastAPI]
    end
    
    subgraph NS3["users namespace (Worker-1)"]
        Users[users-service ×1<br/>프로필, 이력<br/>FastAPI]
    end
    
    subgraph NS4["waste namespace (Worker-2)"]
        Waste[waste-service ×2<br/>이미지 분석<br/>FastAPI]
        AIW[celery-ai-worker ×3<br/>GPT-4o Vision]
    end
    
    subgraph NS5["locations namespace (Worker-1)"]
        Loc[locations-service ×1<br/>수거함 검색<br/>FastAPI]
    end
    
    subgraph NS6["messaging namespace (Storage)"]
        RMQ[RabbitMQ ×3<br/>HA Cluster<br/>5 Queues]
    end
    
    subgraph NS7["default namespace (Storage)"]
        DB[(PostgreSQL<br/>StatefulSet)]
        Redis[(Redis<br/>Deployment)]
    end
    
    subgraph NS8["monitoring namespace (Master)"]
        Prom[Prometheus]
        Graf[Grafana]
    end
    
    Waste --> RMQ
    AIW --> RMQ
    
    Auth --> DB
    Users --> DB
    Waste --> DB
    
    Waste --> Redis
    
    style NS1 fill:#e6d5ff,stroke:#8844ff,stroke-width:2px
    style NS4 fill:#ffd1d1,stroke:#dc3545,stroke-width:3px
    style NS6 fill:#ffe0b3,stroke:#fd7e14,stroke-width:3px
    style NS7 fill:#ccf5f0,stroke:#20c997,stroke-width:3px
```

---

## 📊 데이터 흐름

### 이미지 분석 요청 전체 흐름

```mermaid
sequenceDiagram
    actor User as 사용자
    participant App as Mobile App
    participant ALB as AWS ALB
    participant Waste as waste-service<br/>(Worker-2)
    participant RMQ as RabbitMQ<br/>(Storage)
    participant AIW as AI Worker<br/>(Worker-2)
    participant DB as PostgreSQL<br/>(Storage)
    participant Redis as Redis<br/>(Storage)
    participant S3 as AWS S3
    participant OpenAI as OpenAI API
    
    User->>App: 쓰레기 사진 촬영
    App->>ALB: POST /api/v1/waste/analyze
    ALB->>Waste: 라우팅
    
    Waste->>Waste: Job ID 생성
    Waste->>App: S3 Presigned URL
    App->>S3: 이미지 직접 업로드
    
    App->>Waste: POST /upload-complete/{job_id}
    Waste->>RMQ: Publish: q.ai<br/>ai.analyze
    
    activate AIW
    RMQ->>AIW: Consume (Priority 10)
    AIW->>S3: 이미지 다운로드
    AIW->>AIW: 전처리
    AIW->>Redis: 캐시 확인
    
    alt 캐시 히트 (70%)
        Redis-->>AIW: 결과 반환
        AIW-->>App: 즉시 응답 (1초)
    else 캐시 미스 (30%)
        AIW->>OpenAI: GPT-4o Vision API
        OpenAI-->>AIW: 분류 결과
        AIW->>DB: 결과 저장
        AIW->>Redis: 캐싱 (7일)
    end
    deactivate AIW
    
    loop Polling (0.5초마다)
        App->>Waste: GET /status/{job_id}
        Waste->>Redis: 진행률 조회
        Redis-->>App: progress: 80%
    end
    
    App->>Waste: GET /result/{job_id}
    Waste->>Redis: 최종 결과 조회
    Redis-->>App: 결과 반환
    
    App->>User: 결과 표시
```

---

## 🎯 핵심 사양

### 클러스터

```
Kubernetes (kubeadm):
├─ 버전: v1.28
├─ CNI: Calico VXLAN (BGP 비활성화)
├─ 노드: 4개 (1M + 3W)
├─ HA: non-HA (단일 Master)
└─ 패턴: Instagram (Worker 분리) + Robin (Storage 격리)

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
├─ /argocd       → argocd-server (Master)
├─ /grafana      → grafana-service (Master)
├─ /api/v1/auth  → auth-service (Worker-1)
├─ /api/v1/users → users-service (Worker-1)
├─ /api/v1/waste → waste-service (Worker-2)
└─ /              → default-backend
```

### Stateful Services

```
PostgreSQL (Storage Node):
├─ Type: StatefulSet
├─ PVC: 50GB EBS gp3
└─ Schema: 분리 (auth, users, waste)

Redis (Storage Node):
├─ Type: Deployment
├─ 용도: Celery Result Backend, Caching
└─ TTL: 7일

RabbitMQ (Storage Node):
├─ Type: StatefulSet (HA 3-node)
├─ PVC: 20GB × 3
└─ Queues: 5개 (ai, batch, api, sched, dlq)
```

---

## 📈 확장 계획

### HPA (Horizontal Pod Autoscaler)

```yaml
# waste-service HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: waste-service
  namespace: waste
spec:
  scaleTargetRef:
    kind: Deployment
    name: waste-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Cluster Scaling

```
노드 추가 시나리오:
1. Worker-1 복제 → Application 확장
2. Worker-2 복제 → Async 확장
3. Storage 복제 → DB 읽기 복제본

Spot Instance 활용:
├─ t3.medium Spot: $9/월 (70% 할인)
└─ 비중요 Worker에 적용
```

---

## 🔒 보안

### Network Policies

```yaml
# Storage Namespace 격리
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
  - from:
    - podSelector:
        matchLabels:
          app: waste-service
    - podSelector:
        matchLabels:
          app: celery-worker
    ports:
    - protocol: TCP
      port: 5672
```

---

## 📊 모니터링

### Prometheus + Grafana (Master Node)

```
Metrics:
├─ Node: CPU, Memory, Disk, Network
├─ Pod: 상태, Restart, Ready
├─ RabbitMQ: Queue 길이, 처리율
├─ Celery: Task 성공/실패율
├─ ALB: Request/s, Latency, 5xx
└─ PostgreSQL: 커넥션, Query 시간

Alerts:
├─ q.dlq 길이 > 100
├─ Pod CrashLoopBackOff
├─ Node CPU > 85%
├─ Disk > 80%
└─ ALB 5xx > 1%
```

---

## 🎯 요약

```
4-Node Kubernetes Cluster:
├─ Self-Managed (kubeadm)
├─ Calico VXLAN CNI
├─ AWS ALB Controller
├─ Instagram + Robin 패턴
└─ $185/월

서비스:
├─ API Services: 6 Pods
├─ Celery Workers: 7 Pods
├─ RabbitMQ: 3-node HA
├─ PostgreSQL: StatefulSet
└─ Redis: Cache + Result Backend

GitOps:
├─ ArgoCD (자동 배포)
├─ GitHub Actions (CI)
├─ Helm Charts
└─ GHCR (무료)

성능:
├─ 동시 사용자: 100-500명
├─ 처리 시간: < 5초
├─ 캐시 히트율: 70%
└─ 가용성: 99%+
```

---

## 📚 관련 문서

- [4-Node 배포 아키텍처](deployment-architecture-4node.md) - 상세 다이어그램
- [Self-Managed K8s 선택 배경](why-self-managed-k8s.md) - EKS vs kubeadm
- [VPC 네트워크 설계](../infrastructure/vpc-network-design.md) - 보안 그룹
- [Task Queue 설계](task-queue-design.md) - RabbitMQ + Celery

---

**작성일**: 2025-10-31  
**구성**: 4-Node Kubernetes (kubeadm) + ArgoCD + Calico VXLAN + AWS ALB  
**총 비용**: $185/월  
**상태**: ✅ 프로덕션 배포 완료
