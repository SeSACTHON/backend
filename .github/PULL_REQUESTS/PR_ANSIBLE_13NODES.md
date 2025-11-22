# Pull Request: Ansible 13-Node Support

## 📋 개요
- **브랜치**: `infra/ansible-13nodes-update` → `develop`
- **타입**: Infrastructure
- **목적**: 13-Node 아키텍처에 맞춘 Ansible 설정 업데이트

## 🎯 변경 사항

### 1. Terraform Inventory Template

#### terraform/templates/hosts.tpl
```ini
[api_nodes]  # 신규 추가
k8s-api-waste ansible_host=... domain=waste
k8s-api-auth ansible_host=... domain=auth
k8s-api-userinfo ansible_host=... domain=userinfo
k8s-api-location ansible_host=... domain=location
k8s-api-recycle-info ansible_host=... domain=recycle-info
k8s-api-chat-llm ansible_host=... domain=chat-llm

[workers]  # 재구성
k8s-worker-storage ansible_host=... worker_type=io-bound
k8s-worker-ai ansible_host=... worker_type=network-bound
```

### 2. 노드 라벨링 Playbook

#### ansible/playbooks/label-nodes.yml (신규)

**API Nodes 라벨**:
```yaml
workload: api
domain: {waste|auth|userinfo|location|recycle-info|chat-llm}
role: api
```

**Worker Nodes 라벨**:
```yaml
workload: worker-{storage|ai}
worker-type: {io-bound|network-bound}
pool-type: {eventlet|prefork}
role: worker
```

**Infrastructure Nodes 라벨**:
```yaml
workload: {message-queue|database|cache|monitoring}
role: infrastructure
Taint: domain={integration|data|observability}:NoSchedule
```

### 3. CNI Playbook 업데이트

#### ansible/playbooks/04-cni-install.yml
```yaml
# 기존
EXPECTED_WORKERS: 6
EXPECTED_TOTAL_NODES: 7

# 변경
EXPECTED_WORKERS: 12  # 6 API + 2 Worker + 4 Infra
EXPECTED_TOTAL_NODES: 13  # 1 Master + 12 Workers
```

### 4. Site Playbook 업데이트

#### ansible/site.yml
```yaml
# Worker Join 그룹 확장
hosts: workers,api_nodes,rabbitmq,postgresql,redis,monitoring

# 노드 라벨링 통합
- import_tasks: playbooks/label-nodes.yml
```

## 🏗️ 노드 라벨 전략

### 라벨 구조
```
API Nodes:
└─ domain 라벨로 Pod 스케줄링
   └─ waste-api → domain=waste

Worker Nodes:
└─ workload 라벨로 Pod 스케줄링
   └─ storage-worker → workload=worker-storage

Infrastructure Nodes:
└─ Taint로 전용 노드 보장
   └─ Toleration 필요
```

### NodeSelector 예시
```yaml
# API Deployment
nodeSelector:
  domain: waste

# Worker Deployment
nodeSelector:
  workload: worker-storage
  worker-type: io-bound
```

## ✅ 테스트 체크리스트

- [ ] Terraform apply 후 inventory 생성 확인
- [ ] `ansible-playbook site.yml` 실행
- [ ] 모든 노드 Ready 상태 확인 (13개)
- [ ] `kubectl get nodes --show-labels` 라벨 확인
- [ ] Infrastructure 노드 Taint 확인

## 🔄 배포 흐름

```bash
# 1. Terraform으로 인프라 생성
cd terraform && terraform apply

# 2. Ansible Inventory 생성
terraform output -raw ansible_inventory > ../ansible/inventory/hosts

# 3. Ansible 실행
cd ../ansible && ansible-playbook -i inventory/hosts site.yml

# 4. 노드 확인
kubectl get nodes --show-labels
```

## 🔗 관련 PR

- ⬅️ Terraform 13-Node 업데이트 (의존)
- ➡️ ArgoCD Application 정의 (다음)
- ➡️ Helm Charts 13-Node 템플릿 (다음)

## 📝 비고

- `label-nodes.yml`은 자동 라벨링 및 검증 포함
- 기존 7-Node 설정과 호환 (조건부)
- Taint는 Infrastructure 노드만 적용

---

**리뷰어**: @team
**우선순위**: High
**의존성**: Terraform 13-Node PR 먼저 병합 필요

