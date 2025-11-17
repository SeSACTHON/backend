# Troubleshooting 문서 저장소

> **Eco² Backend 14-Node Kubernetes 클러스터 운영 중 발생한 모든 문제와 해결 방안**

## 📁 문서 구조

```
docs/
├── TROUBLESHOOTING.md              # 📌 메인 인덱스 (빠른 참조)
└── troubleshooting/
    ├── README.md                   # 이 파일
    ├── ansible-label-sync.md       # 🔥 Ansible 라벨 동기화 (2025-11-16)
    ├── argocd-applicationset-patterns.md  # 🔥 ApplicationSet 패턴 (2025-11-16)
    └── gitops-deployment.md        # GitOps 배포 문제
```

---

## 🔥 최신 문제 (2025-11-16)

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
# TROUBLESHOOTING.md의 "빠른 참조"에서 증상으로 검색
# 또는 문서 파일명으로 직접 접근
```

### 2. 카테고리별 접근

**Ansible 관련**:
- → `ansible-label-sync.md`

**ArgoCD 관련**:
- → `argocd-applicationset-patterns.md`
- → `ansible-label-sync.md` (Bootstrap)

**GitOps 배포**:
- → `gitops-deployment.md`

**Infrastructure**:
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
2. 메인 TROUBLESHOOTING.md에 링크 추가
3. 실제 클러스터 데이터 수집 및 포함

---

## 📊 통계

**문서 개수**: 3개 (2025-11-16)  
**해결된 문제**: 23개  
**실제 클러스터 검증**: 3개 문서  
**Ansible 자동화 개선**: 126줄  

---

## 🔄 변경 이력

### 2025-11-16
- ✅ ansible-label-sync.md 생성 (실제 클러스터 데이터 포함)
- ✅ argocd-applicationset-patterns.md 생성
- ✅ gitops-deployment.md 생성
- ✅ TROUBLESHOOTING.md 간략화 (2847줄 → 200줄)
- ✅ Ansible playbook 126줄 개선

---

**다음 단계**: 
- Terraform, VPC, CloudFront, Monitoring, Atlantis 문서 분리
- 실제 클러스터 데이터 지속 수집
- 자동화 스크립트 추가

