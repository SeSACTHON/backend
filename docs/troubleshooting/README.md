# Troubleshooting 문서 저장소

> **Eco² Backend 14-Node Kubernetes 클러스터 운영 중 발생한 모든 문제와 해결 방안**

## 📁 문서 구조

```
docs/
└── troubleshooting/
    ├── README.md                         # 이 파일 (Navigation Hub)
    ├── TROUBLESHOOTING.md                # ⚡ Rapid Diagnostics Runbook
    ├── ARGOCD_DEPLOYMENT_ISSUES.md       # 🔥 ArgoCD 배포 문제 (2025-11-19)
    ├── ansible-label-sync.md             # 🔥 Ansible 라벨 동기화 (2025-11-16)
    ├── argocd-applicationset-patterns.md # 🔥 ApplicationSet 패턴 (2025-11-16)
    ├── gitops-deployment.md              # GitOps 배포 문제
    ├── cluster-cases.md                  # 클러스터 전역 실측 사례 (2025-11-16)
    ├── calico-operator-helm-conflict.md  # Calico Operator vs Helm 충돌
    ├── CALICO_TYPHA_PORT_5473_ISSUE.md   # 🔥 Calico Typha 포트 5473 문제 (2025-11-18)
    ├── terraform-issues.md               # Terraform 오류 모음
    ├── vpc-deletion-issues.md            # VPC 삭제 지연
    └── cloudfront-issues.md              # CloudFront 문제 모음
```

---

## ⚡ 빠른 참조

| 카테고리 | 즉시 확인 | 세부 문서 |
|----------|-----------|-----------|
| 클러스터 전체 영향 | 노드 NotReady / CoreDNS Pending / Pod 스케줄링 실패 / ArgoCD DNS Timeout | `ansible-label-sync.md` |
| ArgoCD / GitOps | **CrashLoopBackOff** / **ERR_TOO_MANY_REDIRECTS** / Application Unknown / OutOfSync / root-app 실패 / AppProject 누락 | **`ARGOCD_DEPLOYMENT_ISSUES.md`**, `argocd-applicationset-patterns.md`, `ansible-label-sync.md` |
| Infrastructure | ALB Controller / GHCR Pull / Kustomize 구조 / VPC 삭제 / CloudFront | `gitops-deployment.md`, `cluster-cases.md`, `terraform-issues.md`, `vpc-deletion-issues.md`, `cloudfront-issues.md` |
| Application | ArgoCD 리디렉션 / Prometheus 메모리 / Atlantis CrashLoop | `argocd-ingress-issues.md`, `monitoring-issues.md`, `atlantis-issues.md` |
| CNI/Calico | Operator vs Helm 충돌, VXLAN 구성, **Typha 포트 5473** | `calico-operator-helm-conflict.md`, `ansible-label-sync.md#3`, **`CALICO_TYPHA_PORT_5473_ISSUE.md`** |

> 현장 대응이 필요하면 `TROUBLESHOOTING.md`(Rapid Diagnostics Runbook)으로 곧장 이동해 절차를 따라가세요.

---

## 🔥 최신 문제 (2025-11-19)

### [ARGOCD_DEPLOYMENT_ISSUES.md](./ARGOCD_DEPLOYMENT_ISSUES.md) ⭐ NEW
**ArgoCD 배포 시 CrashLoopBackOff 및 리디렉션 루프 문제**

해결된 문제:
1. **CrashLoopBackOff**: Ansible의 Deployment 직접 패치로 command/args 충돌 발생
2. **ERR_TOO_MANY_REDIRECTS**: ALB HTTPS 종료 환경에서 무한 리디렉션 루프
3. ConfigMap 기반 insecure 모드 설정 부재
4. Ingress backend-protocol annotation 누락

**특징**: ✅ 실제 에러 로그 포함, ✅ Ansible Role 개선 방법, ✅ 예방 조치 문서화, ✅ 검증 체크리스트

**관련 문서**: [Local Cluster Bootstrap](../deployment/LOCAL_CLUSTER_BOOTSTRAP.md)

---

### [CALICO_TYPHA_PORT_5473_ISSUE.md](./CALICO_TYPHA_PORT_5473_ISSUE.md)
**Calico Typha 포트(5473) 연결 실패 문제**

해결된 문제:
1. Master 노드의 calico-node Pod이 Ready 상태가 되지 않음
2. Felix가 Typha에 연결하지 못함 (TCP 5473 timeout)
3. AWS 보안 그룹에 Typha 포트 미개방
4. Master ↔ Worker, Worker ↔ Worker 간 Typha 통신 차단

**특징**: ✅ 실제 에러 로그 포함, ✅ 네트워크 진단 과정, ✅ 공식 문서 링크, ✅ AWS CLI 해결 방법

**관련 문서**: [Calico Typha 아키텍처](../networking/CALICO_TYPHA_ARCHITECTURE.md)

---

### [ansible-label-sync.md](./ansible-label-sync.md)
**Ansible 노드 라벨과 Kubernetes Manifest 동기화**

해결된 문제:
1. 노드 라벨과 nodeSelector 불일치 (9개 서비스 영향)
2. Ansible root-app.yaml 경로 오류
3. CNI 순환 의존성 (Chicken-and-Egg)
4. ArgoCD AppProject 미생성
5. ArgoCD NetworkPolicy DNS Timeout
6. Application targetRevision 불일치
7. Kustomize 디렉토리 구조 문제
8. ApplicationSet 템플릿 따옴표 오류
9. CoreDNS Pending (모든 노드 Taint)

**특징**: ✅ 실제 클러스터 데이터 포함, ✅ Ansible 자동화 개선

---

### [argocd-applicationset-patterns.md](./argocd-applicationset-patterns.md)
**ArgoCD ApplicationSet 패턴 문제**

해결된 문제:
1. Application이 ApplicationSet을 직접 참조하는 오류
2. Multi-source 패턴 Helm values 경로 문제
3. ApplicationSet app.yaml 파일 미push (7개 파일)

**특징**: ✅ Single-source vs Multi-source 비교, ✅ 베스트 프랙티스

---

### [gitops-deployment.md](./gitops-deployment.md)
**GitOps 배포 일반 문제**

포함 내용:
- Kustomize 상위 디렉토리 참조 오류
- ApplicationSet kustomize.images 문법
- CI Workflow YAML 파싱
- GHCR ImagePullBackOff
- RabbitMQ Bitnami 이미지 중단
- ALB Controller VPC ID 하드코딩
- NetworkPolicy egress 차단

---

## 📖 사용 방법

### 1. 문제 발생 시

```bash
# Step 1: 증상 확인
kubectl get pods -A | grep -v Running
kubectl get applications -n argocd | grep -v Synced

# Step 2: 에러 메시지 수집
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --tail=50

# Step 3: 관련 문서 검색
# 이 README의 '빠른 참조' 표 또는 문서 카탈로그에서 해당 증상 선택
```

### 2. 카테고리별 접근

**Ansible 관련**:
- → `ansible-label-sync.md`
- → `ARGOCD_DEPLOYMENT_ISSUES.md` (ArgoCD Role 개선)

**ArgoCD 관련**:
- → `ARGOCD_DEPLOYMENT_ISSUES.md` (배포 문제)
- → `argocd-applicationset-patterns.md`
- → `ansible-label-sync.md` (Bootstrap)

**GitOps 배포**:
- → `gitops-deployment.md`

**Infrastructure / 운영 사례**:
- → `cluster-cases.md`
- → `terraform-issues.md`
- → `vpc-deletion-issues.md`
- → `cloudfront-issues.md`

### 3. 긴급 상황

각 문서의 **"긴급 복구"** 섹션:
- 즉시 실행 가능한 명령어
- 최소한의 설명
- 예상 복구 시간

예시:
```bash
# CoreDNS Pending 긴급 복구 (ansible-label-sync.md#9)
kubectl patch deployment coredns -n kube-system --type merge -p '...'
sleep 30 && kubectl get pods -n kube-system -l k8s-app=kube-dns
```

---

## 🎯 문서 작성 규칙

### 필수 포함 사항

1. **증상** (실제 에러 메시지)
2. **원인** (근본 원인 분석)
3. **해결** (단계별 명령어)
4. **검증** (복구 확인 방법)
5. **커밋** (관련 Git 커밋 해시)

### 실제 데이터 포함

- ✅ `kubectl get` 출력
- ✅ Pod describe 이벤트
- ✅ 로그 샘플
- ✅ 노드 라벨 (실제 클러스터)
- ✅ Git 커밋 해시

### 문서 업데이트

새로운 문제 발생 시:
1. 해당 카테고리 파일에 추가
2. 이 README의 문서 목록/빠른 참조 표에 링크 추가
3. 실제 클러스터 데이터(로그/이벤트/커밋) 수집 및 포함

---

## 📊 통계

**문서 개수**: 10개 (2025-11-19 기준)  
**해결된 문제**: 31개  
**실제 클러스터 검증**: 5개 문서  
**Ansible 자동화 개선**: 150줄+  

---

## 🔄 변경 이력

### 2025-11-19
- ✅ **ARGOCD_DEPLOYMENT_ISSUES.md 생성** (CrashLoopBackOff, 리디렉션 루프)
- ✅ **Ansible ArgoCD Role 전면 개선** (ConfigMap 기반, 멱등성 보장)
- ✅ LOCAL_CLUSTER_BOOTSTRAP.md 트러블슈팅 가이드 링크 추가
- ✅ CHANGELOG.md v0.7.5 버전 업데이트
- ✅ VERSION 파일 업데이트 (0.7.4 → 0.7.5)

### 2025-11-18
- ✅ **CALICO_TYPHA_PORT_5473_ISSUE.md 생성** (실제 에러 로그, 네트워크 진단)
- ✅ **CALICO_TYPHA_ARCHITECTURE.md 생성** (Mermaid 다이어그램, 공식 문서)
- ✅ AWS 보안 그룹 Typha 포트 5473 추가
- ✅ Terraform 모듈 업데이트 (security-groups)

### 2025-11-16
- ✅ ansible-label-sync.md 생성 (실제 클러스터 데이터 포함)
- ✅ argocd-applicationset-patterns.md 생성
- ✅ gitops-deployment.md 생성
- ✅ TROUBLESHOOTING.md → Rapid Diagnostics Runbook으로 전환
- ✅ 이 README를 싱글 허브로 재편
- ✅ Ansible playbook 126줄 개선

---

**다음 단계**: 
- Terraform, VPC, CloudFront, Monitoring, Atlantis 문서 분리
- 실제 클러스터 데이터 지속 수집
- 자동화 스크립트 추가

