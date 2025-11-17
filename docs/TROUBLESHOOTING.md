# Troubleshooting Guide - Eco² Backend

> **14-Node Microservices Architecture + GitOps 구축 과정에서 발생한 문제 및 해결 방안**

## 📋 빠른 참조

현재 발생한 문제의 카테고리를 선택하세요:

### 🔴 긴급 문제 (클러스터 전체 영향)

- **노드가 NotReady** → [CNI 순환 의존성](./troubleshooting/ansible-label-sync.md#3-cni-순환-의존성-chicken-and-egg)
- **CoreDNS Pending** → [CoreDNS Taint 문제](./troubleshooting/ansible-label-sync.md#9-coredns-pending-모든-노드-taint)
- **Pod 스케줄링 실패** → [노드 라벨 불일치](./troubleshooting/ansible-label-sync.md#1-노드-라벨과-nodeselector-불일치)
- **ArgoCD DNS Timeout** → [NetworkPolicy 차단](./troubleshooting/ansible-label-sync.md#5-argocd-networkpolicy-dns-timeout)

### 🟡 ArgoCD/GitOps 문제

- **Applications가 Unknown** → [ApplicationSet 패턴 오류](./troubleshooting/argocd-applicationset-patterns.md)
- **Applications가 OutOfSync** → [targetRevision 불일치](./troubleshooting/ansible-label-sync.md#6-application-targetrevision-불일치)
- **root-app 배포 실패** → [Ansible 경로 오류](./troubleshooting/ansible-label-sync.md#2-ansible-root-appyaml-경로-오류)
- **AppProject 없음** → [AppProject 미생성](./troubleshooting/ansible-label-sync.md#4-argocd-appproject-미생성)

### 🟢 Infrastructure 문제

- **ALB Controller 실패** → [ALB 문제 모음](./troubleshooting/gitops-deployment.md#10-alb-controller-vpc-id-하드코딩)
- **ImagePullBackOff** → [GHCR 권한 문제](./troubleshooting/gitops-deployment.md#4-ghcr-imagepullbackoff)
- **Kustomize 에러** → [디렉토리 구조](./troubleshooting/ansible-label-sync.md#7-kustomize-디렉토리-구조-문제)
- **VPC 삭제 실패** → [VPC 삭제 지연](./troubleshooting/vpc-deletion-issues.md)

---

## 📚 상세 문서

### 🆕 최신 문제 (2025-11-16)

#### [Ansible 노드 라벨과 Kubernetes Manifest 동기화](./troubleshooting/ansible-label-sync.md) 🔥
- 노드 라벨과 nodeSelector 불일치로 인한 Pod 스케줄링 실패
- Ansible root-app.yaml 경로 오류
- CNI 순환 의존성 (Bootstrap Chicken-and-Egg)
- ArgoCD AppProject 미생성
- ArgoCD NetworkPolicy DNS Timeout
- CoreDNS Pending (모든 노드 Taint)
- **실제 클러스터 데이터 포함** ✅

#### [ArgoCD ApplicationSet 패턴 문제](./troubleshooting/argocd-applicationset-patterns.md) 🔥
- Application이 ApplicationSet을 직접 참조하는 문제
- Multi-source 패턴 Helm values 오류
- ApplicationSet app.yaml 파일 미push
- **실제 클러스터 검증 결과 포함** ✅

#### [GitOps 배포 문제](./troubleshooting/gitops-deployment.md)
- Kustomize 상위 디렉토리 참조 오류
- ApplicationSet kustomize.images 문법 오류
- CI Workflow YAML 파싱 오류
- GHCR ImagePullBackOff (권한 문제)
- RabbitMQ Bitnami Debian 이미지 중단
- ALB Controller egress 차단 (NetworkPolicy)

### 🔧 Infrastructure 문제

#### [Terraform 관련 문제](./troubleshooting/terraform-issues.md)
- Duplicate Resource Configuration
- Provider Configuration Not Present
- Reference to Undeclared Resource
- Missing Resource Instance Key
- Invalid Attribute Combination (S3 Lifecycle)
- No Configuration Files

#### [VPC 삭제 지연 문제](./troubleshooting/vpc-deletion-issues.md)
- NAT Gateway 삭제 지연 (3-5분)
- ENI 삭제 실패
- ACM Certificate 삭제 지연
- 리소스 삭제 순서 최적화

#### [CloudFront 관련 문제](./troubleshooting/cloudfront-issues.md)
- CloudFront 생성 시간 (5-15분)
- CloudFront 삭제 필요성
- CloudFront 검색 로직 부족
- ACM Certificate 삭제 실패

### 🎯 Application 문제

#### [ArgoCD 리디렉션 루프](./troubleshooting/argocd-ingress-issues.md)
- HTTPS → HTTP NAT 설정
- ALB Listener 단일화
- Health Check 일원화

#### [Prometheus 메모리 부족](./troubleshooting/monitoring-issues.md)
- Prometheus Pod Pending
- Monitoring 노드 리소스 부족
- CPU/Memory request 조정

#### [Atlantis 문제 모음](./troubleshooting/atlantis-issues.md)
- Pod CrashLoopBackOff
- kubectl 찾을 수 없음
- Deployment 파일 미존재
- ConfigMap YAML 파싱 에러

---

## 🚀 빠른 진단

### 클러스터 상태 확인

```bash
# 1. 노드 상태
kubectl get nodes -o wide

# 2. 전체 Pod 상태
kubectl get pods -A

# 3. ArgoCD Applications
kubectl get applications -n argocd

# 4. ApplicationSets
kubectl get applicationset -n argocd

# 5. 노드 라벨 확인
kubectl get nodes --show-labels | grep sesacthon.io
```

### 일반적인 해결 순서

1. **에러 메시지 확인**
```bash
   kubectl describe pod <pod-name> -n <namespace>
   kubectl logs <pod-name> -n <namespace>
   kubectl describe application <app-name> -n argocd
   ```

2. **관련 문서 검색**
   - 이 문서의 빠른 참조에서 유사한 증상 찾기
   - 상세 문서 확인

3. **긴급 복구**
   - 각 문서의 "긴급 복구" 섹션 참조
   - 수동 명령어로 즉시 해결

4. **근본 원인 해결**
   - Ansible playbook 수정
   - 문서 업데이트
   - 커밋 및 push

---

## 📊 문제 통계 (2025-11-16 기준)

### 해결된 주요 문제

| 카테고리 | 문제 수 | 영향 | 자동화 |
|---------|--------|------|--------|
| Ansible 라벨 동기화 | 9개 | 전체 클러스터 | ✅ |
| ArgoCD Bootstrap | 5개 | GitOps 체인 | ✅ |
| ApplicationSet 패턴 | 3개 | Platform 배포 | ✅ |
| GitOps 배포 | 11개 | 개별 서비스 | 부분 |
| Infrastructure | 15개+ | AWS 리소스 | 부분 |

### Ansible Playbook 개선

**ansible/roles/argocd/tasks/main.yml**:
- ✅ CNI pre-check 추가 (26줄)
- ✅ AppProject 자동 생성 (67줄)
- ✅ NetworkPolicy 자동 삭제
- ✅ root-app 경로 수정

**ansible/playbooks/02-master-init.yml**:
- ✅ CoreDNS toleration 패치 (33줄)

**총 개선**: +126줄 (자동화 로직)

---

## 🔗 관련 문서

### 아키텍처
- [14-Node 완료 요약](./architecture/14-node-completion-summary.md)
- [노드 라벨 체계](./infrastructure/k8s-label-annotation-system.md)

### 배포
- [Ansible 부트스트랩 가이드](./deployment/ansible/)
- [GitOps 구조 가이드](./deployment/gitops/)
- [로컬 클러스터 부트스트랩](./deployment/LOCAL_CLUSTER_BOOTSTRAP.md)

### CI/CD
- [GitHub Actions CI](./ci-cd/GITHUB_ACTIONS_CI_QUALITY_GATE.md)
- [GitOps 체크리스트](./refactor/gitops-sync-wave-TODO.md)

---

## 💡 베스트 프랙티스

### 부트스트랩 전 체크리스트

```bash
# 1. vCPU 한도 확인
aws service-quotas get-service-quota \
    --service-code ec2 \
    --quota-code L-1216C47A \
    --region ap-northeast-2

# 2. 이전 리소스 완전 정리
./scripts/maintenance/destroy-with-cleanup.sh

# 3. 노드 라벨 문서 동기화 확인
# - docs/infrastructure/k8s-label-annotation-system.md
# - ansible/playbooks/fix-node-labels.yml
# - workloads/apis/*/base/deployment.yaml

# 4. Git 브랜치 확인
git status
git push origin <branch>

# 5. Ansible 실행
ansible-playbook -i ansible/inventory/hosts.ini ansible/site.yml
```

### 문제 발생 시 대응

```bash
# 1. 로그 수집
kubectl get events -A --sort-by='.lastTimestamp'
kubectl logs -n argocd sts/argocd-application-controller --tail=50

# 2. 상태 확인
kubectl get applications -n argocd
kubectl get nodes --show-labels

# 3. 관련 문서 확인
# - troubleshooting/ 디렉토리
# - TROUBLESHOOTING.md (이 파일)

# 4. 긴급 복구 실행
# 각 문서의 "긴급 복구" 섹션 참조
```

---

## 📞 지원

문제가 해결되지 않으면:
- GitHub Issues: https://github.com/SeSACTHON/backend/issues
- 문서 저장소: `docs/troubleshooting/`
- Slack: #backend-support

---

**최종 업데이트**: 2025-11-16  
**버전**: v0.7.4  
**아키텍처**: 14-Node GitOps + Ansible Bootstrap
