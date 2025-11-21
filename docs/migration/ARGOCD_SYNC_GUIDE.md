# ArgoCD 동기화 흐름 및 파일 정리 가이드

## ✅ Commit & Push 시 예상 동작

### 1. **ArgoCD 자동 감지 (develop 브랜치)**

```yaml
# 대부분의 Application이 이 설정을 사용
syncPolicy:
  automated:
    prune: true      # 삭제된 리소스 자동 제거
    selfHeal: true   # 변경사항 자동 반영
```

**프로세스:**
```
1. git push origin develop
   ↓
2. ArgoCD가 변경사항 감지 (3분 내)
   ↓
3. 자동 동기화 시작
   ↓
4. 삭제된 리소스 정리 (prune: true)
   - 24-postgres-operator.yaml 삭제 감지
     → Zalando Postgres Operator 제거
   - 35-data-cr.yaml 삭제 감지
     → postgres-cluster CR 제거
   ↓
5. 새 리소스 생성
   - 27-postgresql.yaml 추가 감지
     → Bitnami PostgreSQL 배포
```

---

## 🔄 예상 동기화 순서

### Phase 1: 삭제 (Prune)
```
1. postgres-cluster CR 삭제
   - StatefulSet: postgres-cluster-0, postgres-cluster-1
   - Service: postgres-cluster
   - PVC: pgdata-postgres-cluster-0, pgdata-postgres-cluster-1

2. Postgres Operator 삭제
   - Deployment: postgres-operator
   - ServiceAccount, RBAC 등
```

### Phase 2: 생성 (Sync)
```
1. External Secret 업데이트
   - auth-secret: DATABASE_URL 변경 감지
   - 새로운 URL로 Secret 재생성

2. PostgreSQL Helm Chart 배포
   - Secret: postgresql-secret 생성 (External Secrets에서)
   - StatefulSet: dev-postgresql-0 생성
   - Service: dev-postgresql 생성
   - ConfigMap: dev-postgresql-configuration
   - initdb 스크립트 실행 (auth 스키마 생성)
```

### Phase 3: 후속 작업 (PostSync)
```
1. auth-db-bootstrap Job 재실행
   - 새 PostgreSQL에 연결
   - auth.users, auth.login_audits 테이블 생성
```

---

## 📁 파일 정리 권장사항

### 🗂️ 디렉토리 구조 정리

#### 현재 상태
```
backend/
├── clusters/
│   ├── dev/apps/
│   │   ├── 00-crds.yaml
│   │   ├── 02-namespaces.yaml
│   │   ├── 10-secrets-operator.yaml
│   │   ├── 11-secrets-cr.yaml
│   │   ├── 24-postgres-operator.yaml ❌ 삭제
│   │   ├── 27-postgresql.yaml ✅ 새로 추가
│   │   ├── 28-redis-operator.yaml
│   │   ├── 35-data-cr.yaml ❌ 삭제
│   │   └── ...
│   └── prod/apps/ (동일)
│
├── platform/
│   ├── cr/ (Custom Resources)
│   │   ├── base/
│   │   │   ├── redis-sentinel.yaml ✅ 유지
│   │   │   └── postgres-cluster.yaml ❌ 삭제
│   │   └── README.md
│   └── crds/ (Custom Resource Definitions)
│
├── workloads/
│   ├── apis/
│   ├── secrets/
│   └── namespaces/
│
└── docs/
    ├── migration/
    │   ├── POSTGRESQL_HELM_MIGRATION.md
    │   └── POSTGRESQL_CLEANUP_SUMMARY.md
    └── ...
```

---

## 🎯 정리 제안

### 옵션 1: **platform/cr 디렉토리 유지** (권장)

**이유:**
- 향후 Redis Sentinel 등 다른 CR 추가 가능
- 구조 일관성 유지

**정리 방안:**
```bash
# 이미 정리 완료
platform/cr/
├── README.md
├── base/
│   ├── kustomization.yaml (postgres 제거됨)
│   └── redis-sentinel.yaml (향후 사용 가능)
├── dev/
│   └── kustomization.yaml (비어있지만 유지)
└── prod/
    └── kustomization.yaml (비어있지만 유지)
```

**추가 정리 (선택적):**
```bash
# redis-sentinel.yaml도 현재 사용 안 함
# Bitnami Redis Helm Chart가 이미 Sentinel 포함
# 나중에 필요하면 추가
```

### 옵션 2: **platform/cr 디렉토리 최소화**

**선택사항 A: redis-sentinel.yaml도 삭제**
```bash
# Bitnami Redis가 이미 replication + sentinel 제공
git rm platform/cr/base/redis-sentinel.yaml
```

**선택사항 B: 빈 kustomization은 유지**
```bash
# 향후 확장성을 위해 구조 유지
# dev/prod kustomization.yaml은 그대로 두기
```

### 옵션 3: **platform/cr 디렉토리 완전 제거** (극단적)

```bash
# 만약 CR을 전혀 사용하지 않는다면
git rm -r platform/cr/
```

**⚠️ 주의:** 나중에 다른 Operator의 CR이 필요할 수 있음

---

## 📋 권장 파일 정리 체크리스트

### ✅ 이미 완료된 작업
- [x] Postgres Operator Application 삭제
- [x] Data CR Application 삭제
- [x] postgres-cluster CR 파일 삭제
- [x] Kustomization 업데이트
- [x] PostgreSQL Helm Application 추가
- [x] api-secrets.yaml 업데이트

### 🔍 추가 검토 필요

#### 1. **redis-sentinel.yaml 사용 여부 확인**
```bash
# Bitnami Redis가 이미 Sentinel 포함하는지 확인
kubectl -n redis get all

# 만약 redis-sentinel CR을 사용하지 않는다면 삭제 고려
```

#### 2. **문서 정리**
```bash
# 마이그레이션 문서 위치 확인
docs/migration/
├── POSTGRESQL_HELM_MIGRATION.md
└── POSTGRESQL_CLEANUP_SUMMARY.md

# 옵션: 기존 PostgreSQL 관련 문서도 정리
docs/data/database-architecture.md  # 업데이트 필요?
docs/infrastructure/06-redis-configuration.md
```

#### 3. **Terraform 파일 확인**
```bash
# PostgreSQL 비밀번호 SSM Parameter는 그대로 사용
terraform/ssm-parameters.tf  # ✅ 변경 불필요

# Ansible 파일 (사용 안 함)
ansible/roles/postgresql/  # 이미 사용 안 함
```

#### 4. **워크트리 확인**
```bash
# feature-auth 브랜치 워크트리도 동기화 필요
worktrees/feature-auth/domain/auth/
```

---

## 🚀 Git 커밋 권장사항

### 커밋 메시지
```bash
git add -A
git commit -m "refactor(infra): migrate PostgreSQL from Zalando Operator to Bitnami Helm Chart

- Remove Zalando Postgres Operator (24-postgres-operator.yaml)
- Remove Custom Resource applications (35-data-cr.yaml)
- Remove postgres-cluster CR definitions
- Add Bitnami PostgreSQL Helm charts (27-postgresql.yaml)
- Update database URL (postgres-cluster → dev-postgresql)
- Change database name (sesacthon → ecoeco)
- Clean up platform/cr directory
- Add migration documentation

BREAKING CHANGE: PostgreSQL service endpoint changed
- Old: postgres-cluster.postgres.svc.cluster.local
- New: dev-postgresql.postgres.svc.cluster.local

Closes #XXX
"
```

### 푸시 전 확인사항
```bash
# 1. 변경사항 최종 확인
git diff --stat

# 2. 새 파일 확인
git status

# 3. 푸시
git push origin develop
```

---

## ⚠️ 배포 후 모니터링

### 1. **ArgoCD UI 확인**
```
1. https://argocd.yourdomain.com
2. dev-postgresql Application 상태 확인
3. Sync 진행 상황 모니터링
```

### 2. **리소스 확인**
```bash
# PostgreSQL Pod 확인
kubectl -n postgres get pods -w

# 예상 출력:
# NAME                READY   STATUS    RESTARTS   AGE
# dev-postgresql-0    1/1     Running   0          2m

# Service 확인
kubectl -n postgres get svc

# 예상 출력:
# NAME              TYPE        CLUSTER-IP      PORT(S)
# dev-postgresql    ClusterIP   10.100.xxx.xxx  5432/TCP

# PVC 확인
kubectl -n postgres get pvc

# Secret 확인
kubectl -n postgres get secret postgresql-secret
```

### 3. **데이터베이스 접속 테스트**
```bash
kubectl -n postgres exec -it dev-postgresql-0 -- psql -U sesacthon -d ecoeco -c "\dn"
```

### 4. **auth-api 재시작**
```bash
# DATABASE_URL이 변경되었으므로
kubectl -n auth rollout restart deployment auth-api

# 로그 확인
kubectl -n auth logs -f deployment/auth-api | grep -i database
```

---

## 📊 정리 우선순위

| 우선순위 | 작업 | 상태 | 비고 |
|---------|------|------|------|
| 🔴 높음 | Postgres Operator/CR 제거 | ✅ 완료 | 필수 |
| 🔴 높음 | PostgreSQL Helm 추가 | ✅ 완료 | 필수 |
| 🔴 높음 | api-secrets 업데이트 | ✅ 완료 | 필수 |
| 🟡 중간 | redis-sentinel.yaml 검토 | ⏳ 대기 | 사용 여부 확인 |
| 🟡 중간 | 문서 업데이트 | ✅ 완료 | 마이그레이션 가이드 |
| 🟢 낮음 | platform/cr 구조 재검토 | ⏳ 선택 | 향후 확장성 고려 |
| 🟢 낮음 | 기존 문서 정리 | ⏳ 선택 | 점진적 개선 |

---

## 💡 권장 접근법

### **단계적 정리 (Recommended)**

**Phase 1: 긴급 (지금 커밋/푸시)**
```bash
✅ Postgres Operator → Helm 마이그레이션
✅ 마이그레이션 문서 추가
```

**Phase 2: 배포 후 확인 (1일 이내)**
```bash
⏳ PostgreSQL 정상 동작 확인
⏳ auth-api 연결 테스트
⏳ 기존 Postgres Operator 리소스 완전 제거 확인
```

**Phase 3: 추가 정리 (1주일 이내)**
```bash
⏳ redis-sentinel.yaml 사용 여부 확인 후 정리
⏳ platform/cr 구조 최종 결정
⏳ 관련 문서 업데이트
```

---

## ✅ 결론

**현재 상태로 커밋/푸시해도 안전합니다!**

```yaml
syncPolicy:
  automated:
    prune: true      # ✅ 삭제된 리소스 자동 제거
    selfHeal: true   # ✅ 새 리소스 자동 배포
```

**ArgoCD가 자동으로:**
1. ❌ Postgres Operator 제거
2. ❌ postgres-cluster CR 제거
3. ✅ Bitnami PostgreSQL 배포
4. ✅ auth-secret 업데이트

**준비 완료! 🚀**

