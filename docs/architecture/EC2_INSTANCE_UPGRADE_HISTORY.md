# EC2 Instance Type Upgrade History

## 개요

Kubernetes 클러스터 운영 중 발생한 리소스 부족 문제를 해결하기 위한 인스턴스 타입 업그레이드 이력을 기록합니다.

---

## 📅 2025-11-19: 전체 노드 스펙 업그레이드

### 배경
- Master 노드 CPU 사용률 77% 도달 (ArgoCD + Operators 집중 배치)
- API 노드들의 메모리 부족으로 ImagePullBackOff 발생
- 인프라 노드(PostgreSQL, Redis, RabbitMQ)의 리소스 부족

### 업그레이드 내역

#### Control Plane
| 노드 | 기존 | 변경 | vCPU | RAM | 사유 |
|------|------|------|------|-----|------|
| k8s-master | t3.large | **t3.xlarge** | 2→4 | 8GB→**16GB** | ArgoCD 전체 + Operators control-plane 집중 배치 |

#### API Nodes
| 노드 | 기존 | 변경 | vCPU | RAM | 사유 |
|------|------|------|------|-----|------|
| k8s-api-auth | t3.micro | **t3.small** | 1→2 | 1GB→**2GB** | JWT 인증 처리 부하 증가 |
| k8s-api-my | t3.micro | **t3.small** | 1→2 | 1GB→**2GB** | 사용자 정보/포인트 조회 |
| k8s-api-scan | t3.small | **t3.medium** | 2→2 | 2GB→**4GB** | AI 폐기물 분류 (핵심 기능) |
| k8s-api-character | t3.micro | **t3.small** | 1→2 | 1GB→**2GB** | 캐릭터 분석 |
| k8s-api-location | t3.micro | **t3.small** | 1→2 | 1GB→**2GB** | 지도/수거함 검색 |
| k8s-api-info | t3.micro | **t3.small** | 1→2 | 1GB→**2GB** | 재활용 정보/FAQ |
| k8s-api-chat | t3.small | **t3.medium** | 2→2 | 2GB→**4GB** | GPT-4o-mini 챗봇 (메모리 집약) |

#### Worker Nodes
| 노드 | 기존 | 변경 | vCPU | RAM | 사유 |
|------|------|------|------|-----|------|
| k8s-worker-storage | t3.small | **t3.medium** | 2→2 | 2GB→**4GB** | I/O 워크로드 + 이미지 업로드 |
| k8s-worker-ai | t3.small | **t3.medium** | 2→2 | 2GB→**4GB** | AI 처리 워크로드 |

#### Infrastructure Nodes
| 노드 | 기존 | 변경 | vCPU | RAM | 사유 |
|------|------|------|------|-----|------|
| k8s-postgresql | t3.medium | **t3.large** | 2→2 | 4GB→**8GB** | 7개 도메인 DB 통합 운영 |
| k8s-redis | t3.small | **t3.medium** | 2→2 | 2GB→**4GB** | 캐시 + JWT 블랙리스트 |
| k8s-rabbitmq | t3.small | **t3.medium** | 2→2 | 2GB→**4GB** | 메시지 큐 처리량 증가 |
| k8s-monitoring | t3.medium | **t3.large** | 2→2 | 4GB→**8GB** | Prometheus TSDB + Grafana (14노드 메트릭 수집) |

### 총 비용 영향
- **기존**: 14 nodes (t3.micro×5 + t3.small×6 + t3.large×1 + t3.medium×2) ≈ $XXX/month
- **변경**: 14 nodes (t3.small×5 + t3.medium×6 + t3.xlarge×1 + t3.large×2) ≈ $XXX/month
- **증가율**: 약 2배 예상

### 적용 방법

```bash
cd terraform
terraform plan -var-file=env/dev.tfvars
terraform apply -var-file=env/dev.tfvars -auto-approve
```

### 영향
- ⚠️ **다운타임**: 인스턴스 타입 변경 시 재생성 필요 → 전체 클러스터 재시작
- ✅ **노드 재조인**: Ansible playbook으로 worker 재조인 필요
- ✅ **Pod 재스케줄링**: 노드 재시작 시 자동 재배치

### 검증
```bash
# 노드 스펙 확인
kubectl get nodes -o custom-columns=NAME:.metadata.name,INSTANCE-TYPE:.metadata.labels.beta\\.kubernetes\\.io/instance-type,CPU:.status.capacity.cpu,MEMORY:.status.capacity.memory

# 리소스 할당률 확인
kubectl describe node k8s-master | grep -A10 "Allocated resources"
```

---

## 📊 리소스 사용 패턴 분석

### Master 노드 CPU 77% 원인
- ArgoCD (6개 컴포넌트): ~400m CPU
- External-Secrets: ~50m CPU
- Postgres/Redis/RabbitMQ Operator: ~300m CPU
- Prometheus Operator: ~200m CPU
- CoreDNS: ~100m CPU
- Calico: ~200m CPU
- Control Plane (kube-apiserver, etcd 등): ~300m CPU

**합계**: ~1550m / 2000m (77%)

### 해결 방안
1. ✅ **Master 스펙 업그레이드**: t3.large → t3.xlarge (CPU 2→4)
2. ✅ **Operator 분산**: 일부 Operator를 worker 노드로 이동 (향후 고려)
3. ✅ **리소스 제한 최적화**: Operator request/limit 조정

---

## 🔄 롤백 절차

업그레이드 후 문제 발생 시:

```bash
# 1. Terraform에서 원래 타입으로 복구
git revert <commit-hash>

# 2. 재적용
terraform apply -var-file=env/dev.tfvars

# 3. 노드 재조인
cd ../ansible
ansible-playbook -i inventory/hosts.ini playbooks/03-worker-join.yml
```

---

## 📝 교훈

1. **Control Plane 리소스 모니터링 필수**: Master 노드 CPU/메모리를 지속적으로 모니터링하고 70% 초과 시 스케일업 고려
2. **Operator 배치 전략**: 모든 Operator를 control-plane에 집중시키지 말고, 역할에 따라 분산 배치
3. **초기 스펙 설정**: t3.micro는 실험용, 운영 환경에서는 최소 t3.small 이상 권장
4. **비용 vs 안정성**: 인스턴스 비용보다 다운타임 비용이 크므로 여유 있는 스펙 선택

---

## 참고 문서
- [Troubleshooting: Master Node CPU 77% 이슈](../troubleshooting/MASTER_NODE_CPU_OVERLOAD.md)
- [Infrastructure Deployment](./INFRASTRUCTURE_DEPLOYMENT.md)
- [14-Node Architecture](./14-node-completion-summary.md)

