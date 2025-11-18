# Master Node CPU 77% 과부하 트러블슈팅

## 🚨 문제 상황

### 증상
```bash
$ kubectl describe node k8s-master | grep -A10 "Allocated resources"
Allocated resources:
  (Total limits may be over 100 percent, i.e., overcommitted.)
  Resource           Requests     Limits
  --------           --------     ------
  cpu                1550m (77%)  1200m (60%)
  memory             978Mi (12%)  1256Mi (16%)
```

- Master 노드(t3.large, 2 vCPU)의 CPU 할당률이 **77%**에 도달
- ArgoCD, External-Secrets, 각종 Operator들이 모두 control-plane에 집중 배치됨
- 새로운 파드 스케줄링 시 리소스 부족으로 `Pending` 상태 발생
- 기존 파드들의 `Terminating` 상태가 오래 지속되어 롤링 업데이트 지연

### 발생 시점
- **일시**: 2025-11-19 06:00 KST
- **트리거**: ArgoCD 전체 컴포넌트를 control-plane으로 재배치 후 리소스 압박 발생
- **영향 범위**: control-plane 노드에서 실행되는 모든 워크로드

---

## 🔍 근본 원인 분석

### 1. Control Plane에 집중된 워크로드

**Master 노드 Pod 목록 (예시)**:
```bash
$ kubectl get pods -A -o wide --field-selector spec.nodeName=k8s-master --no-headers | wc -l
25개 Pod
```

**주요 CPU 소비자**:
| 컴포넌트 | CPU Request | 개수 | 합계 |
|---------|-------------|------|------|
| ArgoCD (6개 컴포넌트) | ~70m | 6 | 420m |
| Postgres Operator | 100m | 1 | 100m |
| Redis Operator | 100m | 1 | 100m |
| RabbitMQ Operator | 100m | 1 | 100m |
| External-Secrets | 50m | 1 | 50m |
| Prometheus Operator | 200m | 1 | 200m |
| kube-apiserver | 250m | 1 | 250m |
| etcd | 100m | 1 | 100m |
| kube-controller-manager | 100m | 1 | 100m |
| kube-scheduler | 50m | 1 | 50m |
| CoreDNS | 50m | 2 | 100m |
| Calico Controller | 100m | 1 | 100m |

**총 Request**: ~1550m / 2000m CPU = **77%**

### 2. 왜 모두 Control Plane에 배치했나?

**의도**:
- API/Worker 노드에는 `domain` taint가 걸려 있어, 전용 워크로드만 스케줄링
- Operator/플랫폼 컴포넌트는 안정적인 control-plane에 배치하여 격리

**문제**:
- Control-plane 노드 스펙(t3.large, 2 vCPU)이 부족
- Operator가 많아질수록 CPU 압박 증가
- Pod 재시작/롤링 업데이트 시 리소스 경합 발생

### 3. Terminating Pod가 오래 남는 이유
- CPU 부족 → 새 Pod가 빠르게 뜨지 못함
- 롤링 업데이트 시 `maxUnavailable=0` → 기존 Pod 종료 전까지 대기
- 노드 압박으로 kubelet 응답 지연 → graceful shutdown 시간 초과

---

## ✅ 해결 방법

### 방법 1: Master 노드 스펙 업그레이드 (채택)

**변경**: `t3.large` (2 vCPU, 8GB) → `t3.xlarge` (4 vCPU, 16GB)

**장점**:
- 즉시 리소스 여유 확보 (77% → ~38%)
- 모든 Operator를 control-plane에 유지 (관리 단순화)
- 향후 Operator 추가 시에도 여유 공간 확보

**단점**:
- 비용 증가 (~2배)
- 인스턴스 재생성으로 인한 다운타임

**적용**:
```hcl
# terraform/main.tf
module "master" {
  instance_type = "t3.xlarge" # 16GB (Control Plane + ArgoCD + Operators)
}
```

```bash
cd terraform
terraform apply -var-file=env/dev.tfvars
```

### 방법 2: Operator 분산 배치 (향후 고려)

일부 Operator를 worker 노드로 이동:

```yaml
# clusters/dev/apps/24-postgres-operator.yaml
spec:
  source:
    helm:
      valuesObject:
        nodeSelector:
          role: worker  # control-plane에서 worker로 변경
        tolerations:
          - key: domain
            operator: Exists
```

**대상**:
- Postgres Operator → worker-storage
- Redis Operator → worker-storage
- RabbitMQ Operator → worker-storage

**주의**:
- Worker 노드에 taint가 있으면 적절한 toleration 필요
- Operator가 관리하는 CR과 같은 노드에 배치하면 장애 격리 약화

### 방법 3: 리소스 Request/Limit 최적화

과도한 request를 조정:

```yaml
# 예: ArgoCD Repo Server
resources:
  requests:
    cpu: 50m    # 기존 100m → 50m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

**주의**:
- Request를 너무 낮추면 CPU throttling 발생
- Limit도 함께 조정해야 OOMKilled 방지

---

## 📊 업그레이드 후 예상 리소스 상태

### Master 노드 (t3.xlarge, 4 vCPU)
```
Allocated resources:
  cpu                1550m (38%)  # 77% → 38%
  memory             978Mi (6%)   # 12% → 6%
```

### API 노드들 (t3.small/medium)
- 기존 t3.micro(1GB)에서 메모리 부족 해소
- 컨테이너 이미지 풀 가능
- Pod 안정적 실행

### Infrastructure 노드들 (t3.medium/large)
- PostgreSQL: 7개 도메인 DB 안정적 운영
- Redis: 캐시 + JWT 블랙리스트 처리량 증가
- RabbitMQ: 메시지 큐 버퍼 확보
- Monitoring: Prometheus TSDB 14노드 메트릭 수집

---

## 🔧 적용 절차

### 1. Terraform 변경
```bash
# 로컬
git pull origin refactor/gitops-sync-wave
git add terraform/main.tf
git commit -m "feat: Upgrade EC2 instance types"
git push origin refactor/gitops-sync-wave
```

### 2. Terraform Apply (서버 또는 CI/CD)
```bash
cd terraform
terraform plan -var-file=env/dev.tfvars | grep -E "must be replaced|will be updated"
terraform apply -var-file=env/dev.tfvars
```

### 3. 인스턴스 재생성 대기
- **예상 시간**: 노드당 5~10분
- **순서**: Terraform이 의존성 순서대로 재생성
- **모니터링**: AWS Console EC2 인스턴스 상태 확인

### 4. Kubernetes 클러스터 복구
```bash
# Master 노드 재초기화 (필요 시)
ansible-playbook -i inventory/hosts.ini playbooks/02-master-init.yml

# Worker 노드 재조인
ansible-playbook -i inventory/hosts.ini playbooks/03-worker-join.yml

# 노드 상태 확인
kubectl get nodes
```

### 5. ArgoCD 재동기화
```bash
# 모든 Application 재동기화
argocd app sync dev-root
argocd app list
```

### 6. 검증
```bash
# 1. 노드 리소스 확인
kubectl describe node k8s-master | grep -A10 "Allocated resources"

# 2. Pod 정상 동작 확인
kubectl get pods -A | grep -v Running

# 3. ArgoCD 상태
kubectl get application -n argocd
```

---

## 🎯 사전 예방 조치

### 1. 리소스 모니터링 알림 설정
```yaml
# Prometheus AlertRule
- alert: NodeCPUAllocationHigh
  expr: sum(kube_pod_container_resource_requests{resource="cpu"}) by (node) / sum(kube_node_status_allocatable{resource="cpu"}) by (node) > 0.7
  for: 5m
  annotations:
    summary: "Node {{ $labels.node }} CPU allocation > 70%"
```

### 2. 정기 용량 계획
- **주간**: `kubectl describe nodes` 리소스 할당률 체크
- **월간**: 워크로드 증가 추세 분석
- **분기**: 인스턴스 타입 재검토

### 3. Operator 배치 전략
- **기본 원칙**: Control-plane은 k8s 핵심 컴포넌트 + ArgoCD만 유지
- **Operator**: 가능하면 전용 worker 노드 또는 monitoring 노드에 분산
- **예외**: External-Secrets는 모든 네임스페이스 접근 필요 → control-plane 유지

### 4. Pod 리소스 Request 가이드라인
| 워크로드 타입 | CPU Request | Memory Request |
|--------------|-------------|----------------|
| Control Plane 컴포넌트 | 250m | 512Mi |
| Operator | 50~100m | 128~256Mi |
| API 서비스 | 100~200m | 256~512Mi |
| Database | 500m+ | 1Gi+ |
| Monitoring | 200~500m | 512Mi~2Gi |

---

## 📚 관련 문서

- [EC2 Instance Upgrade History](../architecture/EC2_INSTANCE_UPGRADE_HISTORY.md)
- [14-Node Architecture](../architecture/14-node-completion-summary.md)
- [Node Taint Management](../architecture/NODE_TAINT_MANAGEMENT.md)
- [Infrastructure Deployment](../architecture/INFRASTRUCTURE_DEPLOYMENT.md)

---

## 🔖 태그
`#troubleshooting` `#resource-management` `#capacity-planning` `#ec2-upgrade` `#cpu-overload`

