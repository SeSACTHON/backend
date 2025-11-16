# ArgoCD · Helm · Kustomize 통합 구조

> **참조 문서**  
> - `docs/architecture/gitops/ARGOCD_SYNC_WAVE_PLAN.md`  
> - `docs/architecture/gitops/SYNC_WAVE_SECRET_MATRIX.md`  
> - `docs/architecture/deployment/HELM_PLATFORM_STACK_GUIDE.md`  
> - `docs/architecture/deployment/KUSTOMIZE_BASE_OVERLAY_GUIDE.md`

ArgoCD 루트는 `backend/clusters/{env}/root-app.yaml`이며, 환경별 App-of-Apps가 아래 디렉터리를 재귀로 Sync 한다. 각 Wave에 필요한 ConfigMap/Secret 선행 조건은 `SYNC_WAVE_SECRET_MATRIX.md`의 표를 따른다.

---

## 1. 최상위 디렉터리

| 경로 | 설명 | Wave | 비고 |
|------|------|------|------|
| `clusters/{env}/root-app.yaml` | 환경별 App-of-Apps Application | - | `project: {env}` |
| `clusters/{env}/apps/*.yaml` | Wave별 Application / ApplicationSet 선언 | -1 ~ 60+ | 파일명에 Wave 포함 |
| `platform/crds/*` | ALB/Prometheus/Postgres/ESO CRD 원본 | -1 | `clusters/.../00-crds.yaml`이 참조 |
| `platform/helm/*` | 벤더 Helm 스택 (cert-manager, alb-controller 등) | 10~50 | helm `values/{env}.yaml` |
| `workloads/*` | 사내 리소스(Kustomize base/overlay) | 0~65 | Overlay 디렉토리로 dev/prod 분리 |

---

## 2. `clusters/{env}/apps` 구성 (Wave 순서)

| 파일 | Wave | 내용 | 필요한 CM/Secrets |
|------|------|------|--------------------|
| `00-crds.yaml` | -1 | `platform/crds/**` 재귀 Sync, Prometheus / Postgres / ESO CRD | 없음 |
| `05-namespaces.yaml` | 0 | `workloads/namespaces/overlays/{env}` | `cluster-config` ConfigMap (Environment label) |
| `08-rbac-storage.yaml` | 0 | ServiceAccount, RBAC, StorageClass (EBS-CSI) | `irsa-role-arn` Secret, `cluster-config` |
| `10-platform.yaml` | 10 | cert-manager, external-dns, external-secrets (ApplicationSet) | `route53-credentials`, `acme-email` |
| `15-alb-controller.yaml` | 15 | AWS Load Balancer Controller Helm | `alb-controller-values` (VPC ID, Subnet, SG) |
| `20-monitoring-operator.yaml` | 20 | kube-prometheus-stack Operator | `alertmanager-config`, `grafana-datasource` |
| `25-data-operators.yaml` | 25 | Postgres/Redis Operator Helm | `s3-backup-credentials` |
| `30-monitoring-cr.yaml` | 30 | `workloads/monitoring/(prometheus|grafana)` | Prometheus Rule & Dashboard ConfigMap |
| `35-data-cr.yaml` | 35 | `workloads/data/postgres|redis/overlays/{env}` | `postgresql-secret`, `redis-secret`, TLS Secret |
| `50-tools-atlantis.yaml` | 50 | `platform/helm/atlantis` | `atlantis-github-token`, `slack-webhook` |
| `58-secrets.yaml` | 58 | `workloads/secrets/(external-secrets|sops)/overlays/{env}` | External Secrets Operator 준비 (Wave 10) |
| `60-apis-appset.yaml` | 60+ | `workloads/apis/*/overlays/{env}` ApplicationSet | `ghcr-secret`, 서비스별 ConfigMap/Secret |

> prod 환경도 동일 구조로 두고 `values/prod.yaml`, `overlays/prod`를 참조한다.

---

## 3. `platform/helm` 구성

```
platform/
├─ helm/
│  ├─ alb-controller/
│  │  ├─ app.yaml            # Wave 15 Application 템플릿
│  │  └─ values/{dev,prod}.yaml
│  ├─ kube-prometheus-stack/ (Wave 20)
│  ├─ postgres-operator/     (Wave 25)
│  ├─ redis-operator/        (Wave 25)
│  ├─ external-secrets-operator/ (Wave 10)
│  ├─ cert-manager/          (Wave 10)
│  ├─ external-dns/          (Wave 10)
│  └─ atlantis/              (Wave 50)
└─ crds/
   ├─ alb-controller/*.yaml
   ├─ prometheus-operator/*.yaml
   ├─ postgres-operator/*.yaml
   └─ external-secrets/*.yaml
```

각 `app.yaml`은 다음 공통 규칙을 따른다.

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "<Wave>"
    sesacthon.io/required-secrets: "comma,separated,list"
spec:
  source:
    helm:
      valueFiles:
        - values/{{env}}.yaml
```

Secrets/ConfigMap 선행 조건은 `SYNC_WAVE_SECRET_MATRIX.md`의 “필요한 CM/Secret” 열을 그대로 사용한다. 예) ALB Controller → `/sesacthon/{env}/network/(vpc-id|public-subnets|alb-sg)` Parameter → ExternalSecret → `alb-controller-values` Secret.

---

## 4. `workloads` 구성 (Kustomize)

| 디렉터리 | 역할 | Wave | 비고 |
|----------|------|------|------|
| `workloads/namespaces` | Namespace 정의 + Tier label | 0 | base + overlay(dev/prod) |
| `workloads/rbac-storage` | SA/RBAC, StorageClass, IRSA annotations | 0 | `commonLabels.tier` 유지 |
| `workloads/network-policies` | default-deny + 허용 정책 | 5 | Calico L3/L4 정책 |
| `workloads/data/postgres` | `PostgresCluster` CR | 35 | Operator: Postgres (Wave 25) |
| `workloads/data/redis` | `RedisCluster` 또는 StatefulSet | 35 | Operator: Redis |
| `workloads/monitoring/prometheus` | Prometheus, ServiceMonitor, Rule | 30 | `selector.matchLabels.tier=*` |
| `workloads/monitoring/grafana` | Datasource/Dashboard CM or Grafana CR | 30 | `grafana-dashboard` ConfigMap |
| `workloads/ingress/ingressclassparams` | ALB IngressClassParams | 16 | Subnet/SG ConfigMap 참조 |
| `workloads/ingress/apps` | 서비스별 Ingress (Route) | 65+ | TLS Secret 사전 요구 |
| `workloads/secrets/external-secrets` | ExternalSecret CR (ASM/SSM) | 58 | `/sesacthon/{env}/*` Parameter |
| `workloads/secrets/sops` | 암호화 Secret (선택) | 58 | `sops.yaml` 정책 |
| `workloads/apis/{service}/overlays/{env}` | Deployment/Service/CM | 60+ | `sync-wave` per service 가능 |

### API Overlay 공통 항목
- `kustomization.yaml`에 `namespace`, `commonLabels` (`tier=business-logic`, `domain=*`) 지정  
- `deployment-patch.yaml`에서 `image: ghcr.io/...` 및 Secret 참조  
- `configmap-env.yaml`로 비민감 설정을 제공하고, Secret은 ExternalSecret 출력 사용 (`envFrom.secretRef`)  
- `argocd.argoproj.io/sync-wave`를 60 이상으로 지정하고, 상위 ApplicationSet (`60-apis-appset.yaml`)에서 `wave` 파라미터를 주입

---

## 5. 예시: `clusters/dev/apps/25-data-operators.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: dev-data-operators
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "25"
    sesacthon.io/required-secrets: "s3-backup-credentials"
spec:
  generators:
    - list:
        elements:
          - name: postgres-operator
            path: platform/helm/postgres-operator
          - name: redis-operator
            path: platform/helm/redis-operator
  template:
    metadata:
      name: dev-{{name}}
    spec:
      project: dev
      source:
        repoURL: https://github.com/SeSACTHON/backend.git
        path: '{{path}}'
        helm:
          valueFiles:
            - values/dev.yaml
      destination:
        server: https://kubernetes.default.svc
        namespace: data-system
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

---

## 6. 운영 체크리스트

1. **Wave 일관성**: 모든 `clusters/{env}/apps/*.yaml`에 `argocd.argoproj.io/sync-wave`가 `ARGOCD_SYNC_WAVE_PLAN.md`의 값과 동일한지 확인한다.  
2. **Secret 선행**: `sesacthon.io/required-secrets` 어노테이션을 기반으로 ArgoCD PreSync 훅 또는 External Secrets Ready 상태를 검증한다.  
3. **환경 Overlay**: dev/prod의 `values/{env}.yaml`, `workloads/**/overlays/{env}`가 존재하는지 CI에서 확인한다.  
4. **App-of-Apps 검증**: `argocd app get dev-root-app`으로 하위 Application 상태 및 wave 순서 확인.  
5. **문서 연계**: 변경 시 `ARGOCD_SYNC_WAVE_PLAN.md`, `SYNC_WAVE_SECRET_MATRIX.md`, `RBAC_NAMESPACE_POLICY.md`를 동시 업데이트한다.

---

> 이 문서는 GitOps 디렉터리 구조와 Wave 기반 배포 규칙을 단일 레퍼런스로 제공한다. 신규 컴포넌트 추가 시, 먼저 Wave와 필요한 ConfigMap/Secret을 정의하고 해당 경로에 매니페스트를 추가한 뒤, `clusters/{env}/apps`에 Application을 등록한다.

