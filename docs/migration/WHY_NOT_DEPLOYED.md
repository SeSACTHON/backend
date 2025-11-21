# 🚨 배포 안 된 이유: 아직 커밋/푸시 안 함!

## 현재 상태

### ❌ 문제
```bash
# 클러스터 상태
postgres-cluster-0        # ← 여전히 Zalando Operator Pod 실행 중
dev-postgresql-0          # ← 없음 (새 Helm chart Pod가 배포 안됨)

# Git 상태
git status --short
 D clusters/dev/apps/24-postgres-operator.yaml
 D clusters/dev/apps/35-data-cr.yaml
?? clusters/dev/apps/27-postgresql.yaml    # ← 아직 커밋 안됨!
?? clusters/prod/apps/27-postgresql.yaml
?? docs/migration/
```

### 원인
**변경사항이 로컬에만 있고 원격 저장소(GitHub)에 푸시되지 않음**

```
Local Changes → ❌ Not Committed/Pushed → GitHub (develop)
                                              ↓
                                          ArgoCD 감지 못함
                                              ↓
                                          배포 안됨
```

---

## ✅ 해결 방법

### 1. 변경사항 커밋 및 푸시

```bash
# 현재 디렉토리 확인
cd /Users/mango/workspace/SeSACTHON/backend

# 모든 변경사항 스테이징
git add -A

# 커밋
git commit -m "refactor(infra): migrate PostgreSQL from Zalando Operator to Bitnami Helm

- Remove Zalando Postgres Operator (24-postgres-operator.yaml)
- Remove Custom Resource applications (35-data-cr.yaml)  
- Remove postgres-cluster CR definitions
- Add Bitnami PostgreSQL Helm charts (27-postgresql.yaml)
- Update database URL and name (postgres-cluster → dev-postgresql, sesacthon → ecoeco)
- Clean up platform/cr directory
- Add migration documentation

BREAKING CHANGE: PostgreSQL service endpoint changed
- Old: postgres-cluster.postgres.svc.cluster.local
- New: dev-postgresql.postgres.svc.cluster.local
"

# develop 브랜치에 푸시
git push origin develop
```

### 2. ArgoCD 동기화 확인

푸시 후 3분 이내에 ArgoCD가 변경사항을 감지합니다.

#### 방법 A: ArgoCD UI에서 확인
```
https://argocd.yourdomain.com

1. Applications 목록에서 확인:
   - dev-postgresql (새로 생성됨) ← 이게 나타나야 함
   - dev-postgres-operator (삭제됨)
   - dev-data-crs (삭제됨)

2. dev-postgresql 클릭
   - Status: Syncing → Healthy
   - Resources 확인
```

#### 방법 B: kubectl로 ArgoCD Application 확인
```bash
# 27-postgresql Application이 생성되었는지 확인
kubectl -n argocd get application dev-postgresql

# 예상 출력:
# NAME              SYNC STATUS   HEALTH STATUS
# dev-postgresql    Synced        Healthy
```

### 3. 배포 진행 상황 모니터링

```bash
# PostgreSQL Pod 생성 확인 (실시간)
kubectl -n postgres get pods -w

# 예상 진행 과정:
# 1단계: 기존 postgres-cluster-0 삭제 (prune: true)
# NAME                 READY   STATUS        RESTARTS   AGE
# postgres-cluster-0   1/1     Terminating   0          38h

# 2단계: 새 dev-postgresql-0 생성
# NAME                 READY   STATUS              RESTARTS   AGE
# dev-postgresql-0     0/1     ContainerCreating   0          10s

# 3단계: 초기화 완료
# NAME                 READY   STATUS    RESTARTS   AGE
# dev-postgresql-0     1/1     Running   0          2m
```

### 4. 배포 완료 확인

```bash
# Pod 확인
kubectl -n postgres get pods
# dev-postgresql-0   1/1   Running

# Service 확인
kubectl -n postgres get svc
# dev-postgresql   ClusterIP   10.100.xxx.xxx   5432/TCP

# PVC 확인
kubectl -n postgres get pvc
# data-dev-postgresql-0   Bound   20Gi

# 데이터베이스 접속 테스트
kubectl -n postgres exec -it dev-postgresql-0 -- psql -U sesacthon -d ecoeco -c "\dn"

# 예상 출력:
#          List of schemas
#   Name   |    Owner
# ---------+-------------
#  auth    | sesacthon
#  public  | pg_database_owner
```

---

## 📊 예상 타임라인

```
T+0분:  git push origin develop
        └─ GitHub에 변경사항 반영

T+1-3분: ArgoCD 변경 감지
        ├─ 24-postgres-operator.yaml 삭제 감지
        ├─ 35-data-cr.yaml 삭제 감지
        └─ 27-postgresql.yaml 추가 감지

T+3-5분: 리소스 정리 (Prune)
        ├─ Postgres Operator 제거
        └─ postgres-cluster-0 Pod 삭제

T+5-8분: 새 리소스 생성
        ├─ PostgreSQL StatefulSet 생성
        ├─ dev-postgresql-0 Pod 시작
        └─ initdb 스크립트 실행

T+8-10분: 배포 완료
        └─ dev-postgresql-0 Running
```

---

## 🔍 수동 동기화 (선택적)

기다리지 않고 즉시 동기화하려면:

### ArgoCD CLI
```bash
# 설치 (필요시)
brew install argocd

# 로그인
argocd login argocd.yourdomain.com

# 수동 Sync
argocd app sync dev-postgresql

# 전체 refresh
argocd app list --refresh
```

### ArgoCD UI
```
1. dev-postgresql Application 선택
2. "Sync" 버튼 클릭
3. "Synchronize" 확인
```

### kubectl (ArgoCD가 CRD 사용)
```bash
# Application 상태 확인
kubectl -n argocd get application dev-postgresql -o yaml

# 수동 sync (annotation 추가)
kubectl -n argocd annotate application dev-postgresql \
  argocd.argoproj.io/refresh=hard --overwrite
```

---

## ⚠️ 주의사항

### 데이터 손실 주의!
```bash
# 기존 postgres-cluster의 데이터가 삭제됩니다!
# 백업이 필요하다면 먼저 백업하세요:

kubectl -n postgres exec -it postgres-cluster-0 -- \
  pg_dumpall -U postgres > backup-$(date +%Y%m%d-%H%M%S).sql
```

### 다운타임
```
예상 다운타임: 5-10분
- 기존 PostgreSQL 종료
- 새 PostgreSQL 시작
- 초기화 완료
```

### auth-api 재시작 필요
```bash
# DATABASE_URL이 변경되었으므로
kubectl -n auth rollout restart deployment auth-api

# 또는 Pod 재시작 대기 (자동 재시작 정책에 따라)
```

---

## ✅ 체크리스트

- [ ] 백업 (필요시)
- [ ] git add -A
- [ ] git commit
- [ ] git push origin develop
- [ ] ArgoCD에서 dev-postgresql Application 확인
- [ ] kubectl -n postgres get pods -w
- [ ] dev-postgresql-0 Running 확인
- [ ] 데이터베이스 접속 테스트
- [ ] auth-api 재시작
- [ ] 애플리케이션 동작 확인

---

## 🎯 지금 바로 실행

```bash
cd /Users/mango/workspace/SeSACTHON/backend
git add -A
git commit -m "refactor(infra): migrate PostgreSQL to Bitnami Helm"
git push origin develop

# 그 다음 클러스터에서:
kubectl -n postgres get pods -w
```

푸시 후 3분 안에 변경사항이 감지되고 배포가 시작됩니다! 🚀

