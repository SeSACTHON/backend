# Pull Request: Terraform 13-Node Architecture

## 📋 개요
- **브랜치**: `infra/terraform-13nodes-update` → `develop`
- **타입**: Infrastructure
- **목적**: 7-Node에서 13-Node 마이크로서비스 아키텍처로 확장

## 🎯 변경 사항

### 1. EC2 인스턴스 확장 (7 → 13 노드)

#### 기존 (7 nodes)
```
- 1 Master
- 2 Workers (worker-1, worker-2)
- 4 Infrastructure (rabbitmq, postgresql, redis, monitoring)
```

#### 변경 후 (13 nodes)
```
- 1 Master (Control Plane)
- 6 API Nodes (도메인별)
  * api-waste (t3.small, 2GB)
  * api-auth (t3.micro, 1GB)
  * api-userinfo (t3.micro, 1GB)
  * api-location (t3.micro, 1GB)
  * api-recycle-info (t3.micro, 1GB)
  * api-chat-llm (t3.small, 2GB)
- 2 Worker Nodes (워크로드별)
  * worker-storage (t3.medium, 4GB) - I/O Bound
  * worker-ai (t3.medium, 4GB) - Network Bound
- 4 Infrastructure Nodes
  * rabbitmq (t3.small, 2GB)
  * postgresql (t3.medium, 4GB) ⬆️ 업그레이드
  * redis (t3.small, 2GB)
  * monitoring (t3.large, 8GB)
```

### 2. 주요 파일 변경

#### terraform/main.tf
- `module "api_waste"` ~ `module "api_chat_llm"` 추가 (6개)
- `module "worker_storage"`, `module "worker_ai"` 추가 (2개)
- PostgreSQL 인스턴스 업그레이드 (t3.small → t3.medium)
- 도메인별 태그 추가 (`Domain`, `Workload`)

#### terraform/outputs.tf
- 13개 노드 전체 Public/Private IP 출력
- `ansible_inventory` 템플릿 업데이트
- `cluster_info` 리소스 요약 업데이트

#### terraform/templates/hosts.tpl
- `[api_nodes]` 그룹 추가 (6개 API)
- `[workers]` 그룹 재구성 (2개 Worker)
- 도메인 및 워크로드 속성 추가

## 💰 리소스 변경

| 항목 | 기존 (7-Node) | 변경 (13-Node) |
|------|---------------|----------------|
| 노드 수 | 7 | 13 |
| 총 vCPU | 14 cores | 18 cores |
| 총 메모리 | 24GB | 26GB |
| 총 스토리지 | 370GB | 410GB |
| 월 비용 | ~$150 | ~$180 |

## 🏗️ 아키텍처 장점

### 마이크로서비스 분리
- ✅ 도메인별 독립 배포
- ✅ 장애 격리
- ✅ 스케일링 유연성

### 워크로드 최적화
- ✅ I/O Bound (eventlet) vs Network Bound (prefork) 분리
- ✅ 리소스 할당 최적화

### 도메인별 DB 지원
- ✅ PostgreSQL 업그레이드로 도메인별 DB 분리 준비

## ✅ 테스트 체크리스트

- [ ] `terraform init` 성공
- [ ] `terraform validate` 성공
- [ ] `terraform plan` 출력 확인 (13개 인스턴스)
- [ ] `terraform apply` 실행 (DRY RUN 권장)
- [ ] Ansible inventory 생성 확인

## 🔗 관련 PR

- Ansible 13-Node 업데이트 (다음 PR)
- ArgoCD Application 정의 (다음 PR)
- Helm Charts 13-Node 템플릿 (다음 PR)

## 📝 비고

- CloudFront ACM 인증서를 위한 `us-east-1` provider 포함
- 모든 노드에 태그 전략 적용 (`Role`, `Workload`, `Domain`)
- 기존 7-Node 설정과 호환 (조건부 적용 가능)

---

**리뷰어**: @team
**우선순위**: High
**배포 전 확인**: Terraform plan 검토 필수

