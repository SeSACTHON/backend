# 🚀 CI/CD 파이프라인 아키텍처

> **GitOps 기반 완전 자동화 배포 파이프라인**  
> **최종 업데이트**: 2025-11-05  
> **상태**: ✅ 프로덕션 준비 완료

---

## 📋 목차

1. [전체 CI/CD 파이프라인](#전체-cicd-파이프라인)
2. [GitHub Actions CI](#github-actions-ci)
3. [ArgoCD GitOps CD](#argocd-gitops-cd)
4. [배포 흐름](#배포-흐름)
5. [롤백 전략](#롤백-전략)

---

## 🌐 전체 CI/CD 파이프라인

### 개요 다이어그램

```mermaid
graph TB
    subgraph Developer["👨‍💻 개발자"]
        Dev[코드 작성]
        Commit[Git Commit]
        Push[Git Push]
    end
    
    subgraph GitHub["GitHub"]
        Repo[Repository<br/>backend.git]
        GHA[GitHub Actions<br/>CI Pipeline]
        GHCR[GitHub Container Registry<br/>ghcr.io]
    end
    
    subgraph K8s["Kubernetes Cluster"]
        ArgoCD[ArgoCD<br/>GitOps Engine]
        Deployments[Deployments<br/>Services<br/>ConfigMaps]
        Pods[Running Pods]
    end
    
    subgraph Monitoring["모니터링"]
        Prometheus[Prometheus]
        Grafana[Grafana]
        Alerts[Alertmanager]
    end
    
    Dev --> Commit
    Commit --> Push
    Push --> Repo
    Repo --> GHA
    
    GHA -->|1. Build| Docker[Docker Build]
    Docker -->|2. Push| GHCR
    GHA -->|3. Update| Helm[Helm Values]
    
    Helm -->|4. Detect Change| ArgoCD
    ArgoCD -->|5. Sync| Deployments
    Deployments -->|6. Deploy| Pods
    
    Pods -->|메트릭| Prometheus
    Prometheus --> Grafana
    Prometheus --> Alerts
    
    style Dev fill:#e1f5ff
    style GHA fill:#ffeaa7
    style ArgoCD fill:#74b9ff
    style Pods fill:#a29bfe
    style Prometheus fill:#fd79a8
```

---

## 📦 CI Pipeline (GitHub Actions)

### 전체 CI 워크플로우

```mermaid
graph LR
    subgraph Trigger["트리거"]
        Push[Push to<br/>main/develop]
        PR[Pull Request]
    end
    
    subgraph PathFilter["경로 필터링"]
        Detect[dorny/paths-filter]
        InfraChanged{인프라<br/>변경?}
        CodeChanged{코드<br/>변경?}
        DocsChanged{문서<br/>변경?}
    end
    
    subgraph Jobs["Jobs"]
        Lint[Lint<br/>Python/YAML]
        Test[Unit Tests<br/>pytest]
        Build[Docker Build]
        Push2GHCR[Push to GHCR]
        UpdateHelm[Update Helm Values]
    end
    
    Push --> Detect
    PR --> Detect
    
    Detect --> InfraChanged
    Detect --> CodeChanged
    Detect --> DocsChanged
    
    CodeChanged -->|Yes| Lint
    CodeChanged -->|Yes| Test
    
    Lint --> Build
    Test --> Build
    
    Build -->|main| Push2GHCR
    Push2GHCR --> UpdateHelm
    
    InfraChanged -->|Yes| TFLint[Terraform Lint]
    InfraChanged -->|Yes| AnsibleLint[Ansible Lint]
    
    DocsChanged -->|Yes| DocsCheck[Docs Check]
    
    style Push fill:#6c5ce7
    style Lint fill:#fdcb6e
    style Build fill:#00b894
    style Push2GHCR fill:#0984e3
    style UpdateHelm fill:#74b9ff
```

### CI 단계 상세

```mermaid
sequenceDiagram
    participant Dev as 개발자
    participant Git as GitHub
    participant GHA as GitHub Actions
    participant GHCR as Container Registry
    participant Helm as Helm Chart Repo
    
    Dev->>Git: git push origin main
    Git->>GHA: Webhook 트리거
    
    Note over GHA: 1️⃣ 경로 필터링
    GHA->>GHA: dorny/paths-filter 실행
    GHA->>GHA: 변경된 경로 확인
    
    alt 코드 변경
        Note over GHA: 2️⃣ Lint & Test
        GHA->>GHA: flake8 (Python)
        GHA->>GHA: pytest (Unit Tests)
        
        Note over GHA: 3️⃣ Docker Build
        GHA->>GHA: docker build -t image:tag
        GHA->>GHA: docker tag image:latest
        
        Note over GHA: 4️⃣ Push to Registry
        GHA->>GHCR: docker push ghcr.io/org/image:tag
        GHCR-->>GHA: 성공
        
        Note over GHA: 5️⃣ Update Helm Values
        GHA->>Helm: values.yaml 업데이트
        GHA->>Git: Commit & Push
        Git-->>GHA: 성공
    else 인프라 변경
        GHA->>GHA: terraform fmt -check
        GHA->>GHA: ansible-lint
    else 문서 변경
        GHA->>GHA: markdownlint
    end
    
    GHA-->>Dev: ✅ CI 완료
```

---

## 🔄 CD Pipeline (ArgoCD GitOps)

### ArgoCD 배포 플로우

```mermaid
graph TB
    subgraph GitRepo["Git Repository"]
        HelmChart[Helm Charts]
        Values[values.yaml]
    end
    
    subgraph ArgoCD["ArgoCD"]
        AppController[Application Controller]
        RepoServer[Repo Server]
        Sync[Sync Engine]
    end
    
    subgraph K8s["Kubernetes Cluster"]
        Namespace[Namespace]
        Deployment[Deployment]
        Service[Service]
        ConfigMap[ConfigMap]
        Secret[Secret]
        Pod[Pods]
    end
    
    subgraph Health["Health Check"]
        LivenessProbe[Liveness Probe]
        ReadinessProbe[Readiness Probe]
    end
    
    HelmChart --> RepoServer
    Values --> RepoServer
    
    RepoServer -->|1. Detect Change| AppController
    AppController -->|2. Generate Manifests| Sync
    
    Sync -->|3. Apply| Namespace
    Namespace --> Deployment
    Deployment --> Service
    Deployment --> ConfigMap
    Deployment --> Secret
    
    Deployment -->|4. Create| Pod
    Pod -->|5. Health Check| LivenessProbe
    Pod --> ReadinessProbe
    
    ReadinessProbe -->|6. Ready| Service
    
    style RepoServer fill:#74b9ff
    style Sync fill:#0984e3
    style Pod fill:#a29bfe
    style ReadinessProbe fill:#00b894
```

### ArgoCD Sync 상세

```mermaid
sequenceDiagram
    participant Git as Git Repository
    participant ArgoCD as ArgoCD
    participant K8s as Kubernetes API
    participant Pod as Pods
    
    Note over ArgoCD: 폴링 (3분마다)
    ArgoCD->>Git: Fetch latest changes
    Git-->>ArgoCD: Helm Chart + Values
    
    ArgoCD->>ArgoCD: Render Helm Template
    ArgoCD->>ArgoCD: Compare with Cluster State
    
    alt 변경 감지
        Note over ArgoCD: OutOfSync 상태
        ArgoCD->>ArgoCD: 자동 Sync (Auto-Sync 설정 시)
        
        Note over ArgoCD: 1️⃣ Pre-Sync Hook
        ArgoCD->>K8s: Run Pre-Sync Jobs
        K8s-->>ArgoCD: Job 완료
        
        Note over ArgoCD: 2️⃣ Sync
        ArgoCD->>K8s: Apply Manifests
        K8s->>Pod: Create/Update Pods
        
        Note over ArgoCD: 3️⃣ Sync Wave
        ArgoCD->>K8s: Apply in Order (Wave 0, 1, 2...)
        
        Note over ArgoCD: 4️⃣ Health Check
        loop Health Check
            ArgoCD->>K8s: Check Resource Status
            K8s-->>ArgoCD: Progressing...
        end
        K8s-->>ArgoCD: Healthy
        
        Note over ArgoCD: 5️⃣ Post-Sync Hook
        ArgoCD->>K8s: Run Post-Sync Jobs
        K8s-->>ArgoCD: Job 완료
        
        Note over ArgoCD: ✅ Synced 상태
    else 변경 없음
        Note over ArgoCD: Synced 상태 유지
    end
```

---

## 🚀 배포 흐름 (End-to-End)

### 전체 배포 프로세스

```mermaid
graph TB
    subgraph Phase1["Phase 1: 개발"]
        Code[코드 작성]
        LocalTest[로컬 테스트]
        Commit[Git Commit]
    end
    
    subgraph Phase2["Phase 2: CI (GitHub Actions)"]
        Push[Git Push]
        Lint[Linting]
        Test[Testing]
        Build[Docker Build]
        Push2Registry[Push to GHCR]
    end
    
    subgraph Phase3["Phase 3: 이미지 업데이트"]
        UpdateValues[Update values.yaml]
        CommitValues[Commit values.yaml]
        PushValues[Push to Git]
    end
    
    subgraph Phase4["Phase 4: CD (ArgoCD)"]
        DetectChange[변경 감지]
        RenderHelm[Helm Template 렌더링]
        ApplyManifests[Manifests 적용]
        CreatePods[Pod 생성]
    end
    
    subgraph Phase5["Phase 5: 배포 완료"]
        HealthCheck[Health Check]
        ReadinessProbe[Readiness Probe]
        ServiceReady[Service Ready]
        Monitor[Monitoring]
    end
    
    Code --> LocalTest
    LocalTest --> Commit
    Commit --> Push
    
    Push --> Lint
    Lint --> Test
    Test --> Build
    Build --> Push2Registry
    
    Push2Registry --> UpdateValues
    UpdateValues --> CommitValues
    CommitValues --> PushValues
    
    PushValues --> DetectChange
    DetectChange --> RenderHelm
    RenderHelm --> ApplyManifests
    ApplyManifests --> CreatePods
    
    CreatePods --> HealthCheck
    HealthCheck --> ReadinessProbe
    ReadinessProbe --> ServiceReady
    ServiceReady --> Monitor
    
    style Phase1 fill:#e1f5ff
    style Phase2 fill:#ffeaa7
    style Phase3 fill:#81ecec
    style Phase4 fill:#74b9ff
    style Phase5 fill:#a29bfe
```

### 배포 타임라인

```mermaid
gantt
    title 배포 프로세스 타임라인 (총 ~8분)
    dateFormat  mm:ss
    axisFormat  %M:%S
    
    section 개발
    코드 작성               :a1, 00:00, 2m
    로컬 테스트             :a2, after a1, 1m
    
    section CI (3분)
    Lint & Test             :b1, after a2, 1m
    Docker Build            :b2, after b1, 1m
    Push to GHCR            :b3, after b2, 30s
    Update Helm Values      :b4, after b3, 30s
    
    section CD (3분)
    ArgoCD 변경 감지        :c1, after b4, 30s
    Helm Template 렌더링    :c2, after c1, 30s
    Manifests 적용          :c3, after c2, 1m
    Pod 생성 & Health Check :c4, after c3, 1m
    
    section 완료
    서비스 준비 완료        :milestone, d1, after c4, 0s
```

---

## 🔁 롤백 전략

### ArgoCD 롤백 프로세스

```mermaid
graph TB
    subgraph Detection["문제 감지"]
        Alert[Alertmanager<br/>경고 발생]
        HealthFail[Health Check<br/>실패]
        UserReport[사용자<br/>오류 보고]
    end
    
    subgraph Decision["롤백 결정"]
        Investigate[문제 조사]
        Decide{롤백<br/>필요?}
    end
    
    subgraph Rollback["롤백 실행"]
        ArgoCD[ArgoCD UI/CLI]
        SelectVersion[이전 버전<br/>선택]
        Sync[Sync to<br/>Previous Version]
    end
    
    subgraph Verification["검증"]
        HealthCheck[Health Check]
        SmokeTest[Smoke Test]
        Monitor[모니터링]
    end
    
    Alert --> Investigate
    HealthFail --> Investigate
    UserReport --> Investigate
    
    Investigate --> Decide
    
    Decide -->|Yes| ArgoCD
    Decide -->|No| Fix[코드 수정]
    
    ArgoCD --> SelectVersion
    SelectVersion --> Sync
    
    Sync --> HealthCheck
    HealthCheck --> SmokeTest
    SmokeTest --> Monitor
    
    Monitor -->|성공| Complete[✅ 롤백 완료]
    Monitor -->|실패| ArgoCD
    
    style Alert fill:#ff7675
    style Decide fill:#fdcb6e
    style Sync fill:#74b9ff
    style Complete fill:#00b894
```

### 롤백 방법

```mermaid
sequenceDiagram
    participant Ops as 운영자
    participant ArgoCD as ArgoCD
    participant Git as Git Repository
    participant K8s as Kubernetes
    
    Note over Ops: 문제 발생 감지
    Ops->>ArgoCD: 롤백 요청
    
    alt 방법 1: ArgoCD UI 롤백
        ArgoCD->>ArgoCD: History 조회
        Ops->>ArgoCD: 이전 버전 선택
        ArgoCD->>K8s: Rollback to Revision N
        K8s-->>ArgoCD: 롤백 완료
    else 방법 2: Git Revert
        Ops->>Git: git revert <commit>
        Git->>ArgoCD: Webhook 트리거
        ArgoCD->>ArgoCD: 변경 감지
        ArgoCD->>K8s: Sync to reverted state
        K8s-->>ArgoCD: 동기화 완료
    else 방법 3: Helm Rollback
        Ops->>K8s: helm rollback <release> <revision>
        K8s-->>ArgoCD: Deployment 변경 감지
        ArgoCD->>ArgoCD: OutOfSync 상태
        ArgoCD->>Git: 현재 상태로 Sync
    end
    
    Note over ArgoCD: Health Check 시작
    ArgoCD->>K8s: Check Pod Status
    K8s-->>ArgoCD: All Healthy
    
    ArgoCD-->>Ops: ✅ 롤백 완료
```

---

## 📊 배포 전략

### Blue-Green 배포

```mermaid
graph TB
    subgraph Current["현재 (Blue)"]
        BlueService[Service<br/>selector: version=v1]
        BluePods[Pods v1<br/>3 replicas]
    end
    
    subgraph New["신규 (Green)"]
        GreenPods[Pods v2<br/>3 replicas]
    end
    
    subgraph Switch["전환"]
        UpdateService[Service 업데이트<br/>selector: version=v2]
    end
    
    subgraph Verification["검증"]
        Test[테스트]
        Rollback{성공?}
    end
    
    BlueService --> BluePods
    GreenPods -->|배포| Test
    Test --> Rollback
    
    Rollback -->|Yes| UpdateService
    UpdateService --> GreenPods
    
    Rollback -->|No| Delete[Green 삭제]
    Delete --> BluePods
    
    style BluePods fill:#74b9ff
    style GreenPods fill:#00b894
    style UpdateService fill:#fdcb6e
```

### Canary 배포

```mermaid
graph TB
    subgraph Phase1["Phase 1: 10%"]
        Service1[Service]
        Stable1[Stable v1<br/>9 replicas]
        Canary1[Canary v2<br/>1 replica]
    end
    
    subgraph Phase2["Phase 2: 50%"]
        Service2[Service]
        Stable2[Stable v1<br/>5 replicas]
        Canary2[Canary v2<br/>5 replicas]
    end
    
    subgraph Phase3["Phase 3: 100%"]
        Service3[Service]
        Stable3[Stable v2<br/>10 replicas]
    end
    
    Service1 --> Stable1
    Service1 --> Canary1
    
    Canary1 -->|모니터링 OK| Service2
    Service2 --> Stable2
    Service2 --> Canary2
    
    Canary2 -->|모니터링 OK| Service3
    Service3 --> Stable3
    
    Canary1 -->|문제 발생| Rollback1[롤백]
    Canary2 -->|문제 발생| Rollback2[롤백]
    
    style Canary1 fill:#fdcb6e
    style Canary2 fill:#ffeaa7
    style Stable3 fill:#00b894
```

---

## 🔧 CI/CD 설정

### GitHub Actions Workflow

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  # 경로 필터링
  changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      infra: ${{ steps.filter.outputs.infra }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v2
        id: filter
        with:
          filters: |
            backend:
              - 'services/**'
              - 'Dockerfile'
            infra:
              - 'terraform/**'
              - 'ansible/**'

  # CI: Build & Push
  build:
    needs: changes
    if: needs.changes.outputs.backend == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Lint
        run: flake8 .
      
      - name: Test
        run: pytest
      
      - name: Build Docker Image
        run: |
          docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .
          docker tag ghcr.io/${{ github.repository }}:${{ github.sha }} \
                     ghcr.io/${{ github.repository }}:latest
      
      - name: Push to GHCR
        run: |
          echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker push ghcr.io/${{ github.repository }}:${{ github.sha }}
          docker push ghcr.io/${{ github.repository }}:latest
      
      - name: Update Helm Values
        if: github.ref == 'refs/heads/main'
        run: |
          sed -i "s|tag:.*|tag: ${{ github.sha }}|" charts/values.yaml
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add charts/values.yaml
          git commit -m "chore: update image tag to ${{ github.sha }}"
          git push
```

### ArgoCD Application

```yaml
# argocd/applications/backend.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: backend
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/SeSACTHON/backend.git
    targetRevision: main
    path: charts/backend
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

---

## 📈 모니터링 및 알림

### 배포 모니터링

```mermaid
graph TB
    subgraph Metrics["메트릭 수집"]
        Prometheus[Prometheus]
        ServiceMonitor[ServiceMonitor]
        PodMonitor[PodMonitor]
    end
    
    subgraph Visualization["시각화"]
        Grafana[Grafana]
        Dashboard1[Deployment Dashboard]
        Dashboard2[Application Dashboard]
    end
    
    subgraph Alerting["알림"]
        AlertManager[Alertmanager]
        Rules[Alert Rules]
        Slack[Slack]
        Email[Email]
    end
    
    ServiceMonitor --> Prometheus
    PodMonitor --> Prometheus
    
    Prometheus --> Grafana
    Grafana --> Dashboard1
    Grafana --> Dashboard2
    
    Prometheus --> AlertManager
    Rules --> AlertManager
    
    AlertManager --> Slack
    AlertManager --> Email
    
    style Prometheus fill:#fd79a8
    style Grafana fill:#74b9ff
    style AlertManager fill:#ff7675
```

### 주요 메트릭

```yaml
# Prometheus Alert Rules
groups:
  - name: deployment
    interval: 30s
    rules:
      # 배포 실패
      - alert: DeploymentFailed
        expr: kube_deployment_status_replicas_available == 0
        for: 5m
        annotations:
          summary: "Deployment {{ $labels.deployment }} has no available replicas"
      
      # Pod Crash Loop
      - alert: PodCrashLooping
        expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
        for: 5m
        annotations:
          summary: "Pod {{ $labels.pod }} is crash looping"
      
      # 높은 에러율
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected: {{ $value }}%"
```

---

## 🎯 Best Practices

### CI/CD 권장사항

1. **경로 필터링 사용**
   - 불필요한 빌드 방지
   - 리소스 절약

2. **자동화 테스트**
   - 단위 테스트 (pytest)
   - 통합 테스트
   - E2E 테스트

3. **이미지 태깅 전략**
   - Git SHA 사용
   - Semantic Versioning
   - Latest 태그 병행

4. **보안**
   - 이미지 스캔 (Trivy)
   - Secret 관리 (Sealed Secrets)
   - RBAC 적용

5. **롤백 전략**
   - Blue-Green 배포
   - Canary 배포
   - 자동 롤백 설정

6. **모니터링**
   - 배포 메트릭 수집
   - 알림 설정
   - 대시보드 구성

---

## 📚 관련 문서

- [인프라 배포 다이어그램](INFRASTRUCTURE_DEPLOYMENT_DIAGRAM.md)
- [최종 K8s 아키텍처](final-k8s-architecture.md)
- [GitOps ArgoCD Helm](../deployment/gitops-argocd-helm.md)
- [GitHub Actions 설정](../../.github/workflows/)

---

**문서 버전**: 1.0  
**최종 업데이트**: 2025-11-05  
**작성자**: Infrastructure Team  
**상태**: ✅ 프로덕션 준비 완료

