# 배포 구조 분석 보고서

## 📊 현재 배포 방식 요약

### 설치 방식별 분류

| 컴포넌트 | 설치 방식 | 관리 도구 | 파일 위치 |
|---------|----------|----------|----------|
| **RabbitMQ** | Operator | RabbitmqCluster CR | `ansible/roles/rabbitmq/tasks/main.yml` |
| **Prometheus** | Helm Chart | PrometheusOperator CR | `ansible/playbooks/08-monitoring.yml` |
| **AWS ALB Controller** | Helm Chart | Deployment | `ansible/playbooks/07-alb-controller.yml` |
| **ArgoCD** | kubectl apply | ArgoCD CR | `ansible/roles/argocd/tasks/main.yml` |
| **Redis** | kubectl apply | Deployment | `ansible/roles/redis/tasks/main.yml` |
| **Cert-manager** | kubectl apply | CertManager CR | `ansible/playbooks/05-addons.yml` |
| **Metrics Server** | kubectl apply | Deployment | `ansible/playbooks/05-addons.yml` |
| **Calico CNI** | kubectl apply | DaemonSet | `ansible/playbooks/04-cni-install.yml` |
| **EBS CSI Driver** | kubectl apply | DaemonSet | `ansible/playbooks/05-1-ebs-csi-driver.yml` |

---

## 🔍 상세 분석

### 1. Operator 패턴 (1개)

#### RabbitMQ Cluster Operator
- **설치**: `kubectl apply` (GitHub release YAML)
- **관리**: `RabbitmqCluster` CR (Custom Resource)
- **이점**:
  - 공식 Operator (RabbitMQ 팀 유지보수)
  - 롤링 업데이트, 자동 복구
  - 공식 Docker Hub 이미지 사용
- **파일**: `ansible/roles/rabbitmq/tasks/main.yml`

```yaml
# 설치
kubectl apply -f https://github.com/rabbitmq/cluster-operator/releases/latest/download/cluster-operator.yml

# 배포
apiVersion: rabbitmq.com/v1beta1
kind: RabbitmqCluster
spec:
  image: rabbitmq:3.13-management
  replicas: 3
```

---

### 2. Helm Chart (2개)

#### Prometheus Stack (kube-prometheus-stack)
- **설치**: Helm Chart
- **관리**: Prometheus Operator (Helm Chart 내부 포함)
- **CR 사용**: 
  - `Prometheus` CR
  - `ServiceMonitor` CR
  - `Alertmanager` CR
- **특징**: Helm으로 설치되지만, Operator가 CR로 관리
- **파일**: `ansible/playbooks/08-monitoring.yml`

```bash
helm install prometheus prometheus-community/kube-prometheus-stack
```

#### AWS Load Balancer Controller
- **설치**: Helm Chart
- **관리**: Deployment (Helm으로 관리)
- **CR 사용**: `IngressClass`, `TargetGroupBinding` (AWS 전용)
- **파일**: `ansible/playbooks/07-alb-controller.yml`

```bash
helm install aws-load-balancer-controller eks/aws-load-balancer-controller
```

---

### 3. kubectl apply (직접 배포, 6개)

#### ArgoCD
- **설치**: 공식 manifest YAML
- **관리**: ArgoCD CR (Application, AppProject 등)
- **파일**: `ansible/roles/argocd/tasks/main.yml`

#### Redis
- **설치**: 직접 Deployment 생성
- **관리**: Deployment (Operator/Helm 없음)
- **파일**: `ansible/roles/redis/tasks/main.yml`

#### Cert-manager
- **설치**: 공식 manifest YAML
- **관리**: CertManager CR (Certificate, Issuer 등)
- **파일**: `ansible/playbooks/05-addons.yml`

#### Metrics Server
- **설치**: 공식 manifest YAML
- **관리**: Deployment (표준 Kubernetes 리소스)
- **파일**: `ansible/playbooks/05-addons.yml`

#### Calico CNI
- **설치**: 공식 manifest YAML
- **관리**: DaemonSet (표준 Kubernetes 리소스)
- **파일**: `ansible/playbooks/04-cni-install.yml`

#### EBS CSI Driver
- **설치**: Kustomize 배포
- **관리**: DaemonSet (표준 Kubernetes 리소스)
- **파일**: `ansible/playbooks/05-1-ebs-csi-driver.yml`

---

## ✅ 충돌 분석

### Operator와 Helm 병행 사용 가능 여부

**결론: 충돌 없음** ✅

이유:
1. **다른 리소스 관리**: 
   - RabbitMQ Operator → `RabbitmqCluster` CR
   - Prometheus Operator → `Prometheus` CR
   - 각각 독립적으로 동작

2. **네임스페이스 분리**:
   - RabbitMQ: `messaging`
   - Prometheus: `monitoring`
   - 충돌할 리소스 없음

3. **역할 분리**:
   - Operator: 애플리케이션 관리 (RabbitMQ)
   - Helm: 패키지 관리 및 템플릿 (Prometheus, ALB Controller)
   - kubectl apply: 직접 제어 필요한 리소스

---

## 📈 통계

| 설치 방식 | 개수 | 비율 |
|----------|------|------|
| **Operator** | 1 | 11% |
| **Helm** | 2 | 22% |
| **kubectl apply** | 6 | 67% |

---

## 💡 권장 사항

### 현재 구조 평가

✅ **장점**:
- 각 컴포넌트에 최적의 설치 방식 사용
- Operator와 Helm 병행 사용으로 충돌 없음
- 필요한 컴포넌트 모두 정상 동작

⚠️ **개선 여지**:
- 설치 방식이 다양하여 일관성 부족
- Redis는 Operator나 Helm으로 전환 가능 (선택 사항)

### 일관성 향상 옵션

#### 옵션 1: Operator 중심 (권장)
```yaml
Stateful Services → Operator 사용
- RabbitMQ: ✅ Operator (현재)
- Redis: Operator로 전환 (Bitnami Redis Operator)
- PostgreSQL: Operator로 전환 (CrunchyData 또는 Zalando)
```

#### 옵션 2: Helm 중심
```yaml
모든 애플리케이션 → Helm Chart 사용
- RabbitMQ: Helm Chart로 전환
- Redis: Helm Chart 사용
- Prometheus: ✅ Helm (현재)
```

#### 옵션 3: 현재 구조 유지 (현실적)
- ✅ 충돌 없음
- ✅ 각 컴포넌트 특성에 맞는 방식 사용
- ⚠️ 다소 혼재되어 있으나 실무에서 흔한 패턴

---

## 🎯 결론

**현재 구조는 정상이며 충돌 없음**

- **Operator**: RabbitMQ (1개)
- **Helm**: Prometheus, ALB Controller (2개)
- **kubectl apply**: 인프라/기본 구성요소 (6개)

**각 설치 방식이 적절한 용도로 사용되고 있으며, Operator와 Helm을 병행해도 문제없습니다.**

---

**마지막 업데이트**: 2025-11-03  
**분석 기준**: `ansible/site.yml`, `ansible/continue-install.yml`, 각 role/playbook

