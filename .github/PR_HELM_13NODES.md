# Pull Request: Helm Charts 13-Node Templates

## 📋 개요
- **브랜치**: `cicd/helm-13nodes-templates` → `develop`
- **타입**: CI/CD
- **목적**: 13-Node 마이크로서비스를 위한 Helm Chart 템플릿 생성

## 🎯 변경 사항

### 1. Chart 정의

#### charts/ecoeco-backend/Chart.yaml
```yaml
name: ecoeco-backend
version: 1.0.0
description: 13-Node Microservices Architecture
```

### 2. Values 파일

#### charts/ecoeco-backend/values-13nodes.yaml

**API Services (6개)**:
```yaml
api:
  waste:
    replicas: 2
    resources:
      requests: {cpu: 200m, memory: 256Mi}
    nodeSelector:
      domain: waste
  # auth, userinfo, location, recycle-info, chat-llm
```

**Worker Services (2개)**:
```yaml
worker:
  storage:
    replicas: 2
    poolType: eventlet
    concurrency: 1000
    nodeSelector:
      workload: worker-storage
  
  ai:
    replicas: 2
    poolType: prefork
    concurrency: 4
    nodeSelector:
      workload: worker-ai
```

**Ingress**:
```yaml
ingress:
  enabled: true
  className: alb
  host: api.ecoeco.app
  paths:
    - path: /api/v1/waste
      backend: waste-api
    # 6개 API 경로 매핑
```

### 3. API Deployment 템플릿

#### charts/ecoeco-backend/templates/api/deployment.yaml
```yaml
{{- range $name, $config := .Values.api }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $config.name }}
spec:
  replicas: {{ $config.replicas }}
  template:
    spec:
      nodeSelector:
        {{- toYaml $config.nodeSelector | nindent 8 }}
      containers:
        - name: {{ $config.name }}
          livenessProbe:
            httpGet:
              path: /health
          readinessProbe:
            httpGet:
              path: /ready
{{- end }}
```

**특징**:
- 동적 템플릿 (6개 API 자동 생성)
- Health Check 포함
- NodeSelector로 도메인별 배치

### 4. Worker Deployment 템플릿

#### charts/ecoeco-backend/templates/worker/deployment.yaml
```yaml
{{- range $name, $config := .Values.worker }}
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - env:
            - name: CELERY_POOL
              value: {{ $config.poolType }}
            - name: CELERY_CONCURRENCY
              value: {{ $config.concurrency | quote }}
          volumeMounts:
            - name: wal-storage
              mountPath: /var/lib/ecoeco
      volumes:
        - name: wal-storage
          emptyDir: {}
{{- end }}
```

**특징**:
- Celery Pool Type 환경변수
- WAL Volume Mount (`/var/lib/ecoeco`)
- Celery health check (inspect ping/active)

### 5. Ingress 템플릿

#### charts/ecoeco-backend/templates/ingress.yaml
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
spec:
  ingressClassName: alb
  rules:
    - host: api.ecoeco.app
      http:
        paths:
        {{- range .Values.ingress.paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ .backend }}
{{- end }}
```

## 📁 Helm Chart 구조

```
charts/ecoeco-backend/
├── Chart.yaml
├── values-13nodes.yaml
└── templates/
    ├── api/
    │   └── deployment.yaml  # 6 APIs + 6 Services
    ├── worker/
    │   └── deployment.yaml  # 2 Workers + 2 Services
    └── ingress.yaml         # ALB Ingress
```

## 🚀 사용 방법

### 설치
```bash
helm install ecoeco-backend charts/ecoeco-backend \
  -f charts/ecoeco-backend/values-13nodes.yaml
```

### 업그레이드
```bash
helm upgrade ecoeco-backend charts/ecoeco-backend \
  -f charts/ecoeco-backend/values-13nodes.yaml
```

### 템플릿 확인
```bash
helm template ecoeco-backend charts/ecoeco-backend \
  -f charts/ecoeco-backend/values-13nodes.yaml
```

## ✅ 테스트 체크리스트

- [ ] `helm lint charts/ecoeco-backend`
- [ ] `helm template` 출력 확인
- [ ] API Deployment 6개 생성 확인
- [ ] Worker Deployment 2개 생성 확인
- [ ] Ingress 경로 매핑 확인
- [ ] NodeSelector 설정 확인
- [ ] Health Check 경로 확인

## 🔗 관련 PR

- ⬅️ Ansible 13-Node 업데이트 (노드 라벨 필요)
- ⬅️ ArgoCD Application 정의 (배포 자동화)
- ➡️ FastAPI Health Check 구현 (다음)

## 📝 비고

- WAL Volume은 `emptyDir`로 설정 (PV로 업그레이드 가능)
- Secrets는 placeholder (Sealed Secrets 권장)
- HPA는 별도 PR에서 추가 예정

---

**리뷰어**: @team
**우선순위**: High
**의존성**: Ansible 노드 라벨링 완료 후 배포 가능

