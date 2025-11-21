# ✅ PostgreSQL Helm 마이그레이션 완료

## 🗑️ 삭제된 파일들

### Zalando Postgres Operator 관련
```
✅ clusters/dev/apps/24-postgres-operator.yaml
✅ clusters/prod/apps/24-postgres-operator.yaml
```

### Custom Resource (CR) 관련
```
✅ clusters/dev/apps/35-data-cr.yaml
✅ clusters/prod/apps/35-data-cr.yaml
✅ platform/cr/base/postgres-cluster.yaml
✅ platform/cr/dev/postgres-patch.yaml
✅ platform/cr/prod/postgres-patch.yaml
```

### 업데이트된 파일들
```
✅ platform/cr/base/kustomization.yaml
✅ platform/cr/dev/kustomization.yaml
✅ platform/cr/prod/kustomization.yaml
```

---

## 📦 추가된 파일들

### Bitnami PostgreSQL Helm Chart
```
✅ clusters/dev/apps/27-postgresql.yaml
✅ clusters/prod/apps/27-postgresql.yaml
```

### 설정 변경
```
✅ workloads/secrets/external-secrets/dev/api-secrets.yaml
   - 데이터베이스 이름: sesacthon → ecoeco
   - Service: postgres-cluster → dev-postgresql
```

### 마이그레이션 문서
```
✅ docs/migration/POSTGRESQL_HELM_MIGRATION.md
```

---

## 📂 platform/cr 디렉토리 구조

**변경 전:**
```
platform/cr/
├── base/
│   ├── kustomization.yaml
│   ├── postgres-cluster.yaml ❌ 삭제
│   └── redis-sentinel.yaml
├── dev/
│   ├── kustomization.yaml
│   └── postgres-patch.yaml ❌ 삭제
└── prod/
    ├── kustomization.yaml
    └── postgres-patch.yaml ❌ 삭제
```

**변경 후:**
```
platform/cr/
├── README.md
├── base/
│   ├── kustomization.yaml ✅ 업데이트
│   └── redis-sentinel.yaml
├── dev/
│   └── kustomization.yaml ✅ 업데이트
└── prod/
    └── kustomization.yaml ✅ 업데이트
```

**비고:**
- Redis Sentinel CR은 유지 (Redis Operator에서 사용)
- PostgreSQL 관련 CR만 제거
- 향후 다른 CR이 필요하면 추가 가능

---

## 🎯 변경 요약

### 1. **Operator 제거**
- ❌ Zalando Postgres Operator
- ✅ Bitnami PostgreSQL Helm Chart

### 2. **데이터베이스 이름 변경**
- ❌ sesacthon
- ✅ ecoeco

### 3. **Service 엔드포인트 변경**
```diff
- postgres-cluster.postgres.svc.cluster.local:5432/sesacthon?ssl=require
+ dev-postgresql.postgres.svc.cluster.local:5432/ecoeco
```

### 4. **관리 방식 변경**
- ❌ Custom Resource (CR) 기반
- ✅ Helm Values 기반

---

## 🚀 다음 단계

### 1. ArgoCD 동기화
```bash
# 27-postgresql Application 배포
# ArgoCD UI 또는 CLI로 Sync

# 예상 생성 리소스:
# - StatefulSet: dev-postgresql-0
# - Service: dev-postgresql
# - ConfigMap: dev-postgresql-configuration
# - Secret: postgresql-secret (External Secrets에서 자동 생성)
```

### 2. 기존 PostgreSQL 클러스터 제거
```bash
# ⚠️ 주의: 데이터 백업 후 진행!

# Zalando Operator CR 삭제 (ArgoCD에서 자동으로 제거됨)
# ArgoCD가 24-postgres-operator와 35-data-cr를 감지하고 리소스 정리

# 수동으로 확인 및 정리
kubectl -n postgres get postgresql
kubectl -n postgres get pods
kubectl -n data-system get pods  # Operator Pod 확인
```

### 3. 애플리케이션 재배포
```bash
# DB 초기화 Job 재실행
kubectl -n auth delete job auth-db-bootstrap

# ArgoCD가 자동으로 재생성 (PostSync Hook)
# 또는
kubectl -n auth apply -f workloads/apis/auth/base/db-bootstrap-job.yaml

# auth-api 재배포
kubectl -n auth rollout restart deployment auth-api
```

---

## ✅ 체크리스트

- [x] Zalando Postgres Operator Application 삭제
- [x] Data CR Application 삭제
- [x] postgres-cluster CR 파일 삭제
- [x] Kustomization 파일 업데이트
- [x] Bitnami PostgreSQL Helm Application 생성
- [x] api-secrets.yaml 업데이트 (DB 이름, Service 변경)
- [x] 마이그레이션 문서 작성
- [ ] ArgoCD에서 새 PostgreSQL 배포
- [ ] DB 초기화 확인
- [ ] 애플리케이션 연결 테스트

---

## 🔍 검증 방법

### PostgreSQL 접속 테스트
```bash
# Pod 확인
kubectl -n postgres get pods
# dev-postgresql-0 Running 확인

# 데이터베이스 접속
kubectl -n postgres exec -it dev-postgresql-0 -- psql -U sesacthon -d ecoeco

# 스키마 확인
ecoeco=> \dn
         List of schemas
  Name  |    Owner
--------+-------------
 auth   | sesacthon
 public | pg_database_owner
(2 rows)

# 테이블 확인 (auth.users가 있어야 함)
ecoeco=> \dt auth.*
```

### 애플리케이션 연결 확인
```bash
# auth-api 로그 확인
kubectl -n auth logs -f deployment/auth-api | grep -i "database\|connection"

# 예상 출력:
# INFO:     Connected to database
# INFO:     Database pool initialized
```

---

## 📊 최종 아키텍처

### Dev 환경
```
┌─────────────────────────────────────────┐
│ ArgoCD Application: 27-postgresql       │
├─────────────────────────────────────────┤
│ Source: Bitnami Helm Chart              │
│ Chart: postgresql:16.2.1                │
│ Architecture: standalone                │
│                                         │
│ ┌─────────────────────────────────┐   │
│ │ StatefulSet: dev-postgresql     │   │
│ │  - dev-postgresql-0             │   │
│ │    * CPU: 500m / 2000m          │   │
│ │    * Memory: 1Gi / 4Gi          │   │
│ │    * Storage: 20Gi (gp3)        │   │
│ │                                 │   │
│ │ Database: ecoeco                │   │
│ │ User: sesacthon                 │   │
│ │ Schema: auth, public            │   │
│ └─────────────────────────────────┘   │
│                                         │
│ Service:                                │
│   dev-postgresql.postgres.svc:5432     │
└─────────────────────────────────────────┘
```

### Prod 환경
```
┌─────────────────────────────────────────┐
│ ArgoCD Application: 27-postgresql       │
├─────────────────────────────────────────┤
│ Architecture: replication               │
│                                         │
│ Primary:                                │
│ ┌─────────────────────────────────┐   │
│ │ prod-postgresql-0               │   │
│ │  * CPU: 1000m / 4000m           │   │
│ │  * Memory: 2Gi / 8Gi            │   │
│ │  * Storage: 50Gi (gp3)          │   │
│ └─────────────────────────────────┘   │
│                                         │
│ Read Replica:                           │
│ ┌─────────────────────────────────┐   │
│ │ prod-postgresql-1               │   │
│ │  * CPU: 1000m / 4000m           │   │
│ │  * Memory: 2Gi / 8Gi            │   │
│ │  * Storage: 50Gi (gp3)          │   │
│ └─────────────────────────────────┘   │
│                                         │
│ Services:                               │
│   prod-postgresql.postgres.svc:5432    │
│   prod-postgresql-read.postgres.svc    │
└─────────────────────────────────────────┘
```

---

## 💡 장점 요약

| 항목 | Before (Zalando) | After (Bitnami) |
|------|------------------|-----------------|
| **설정 복잡도** | ⚠️ 높음 | ✅ 낮음 |
| **비밀번호 관리** | ⚠️ 자동 생성 (복잡) | ✅ External Secret 직접 사용 |
| **초기화** | ⚠️ 별도 Job 필수 | ✅ initdb 내장 |
| **크로스 네임스페이스** | ❌ 문제 있음 | ✅ 문제 없음 |
| **Redis와 일관성** | ❌ 다른 방식 | ✅ 동일한 방식 |
| **커뮤니티 지원** | ⚠️ 좁음 | ✅ 넓음 |
| **운영 난이도** | ⚠️ 높음 | ✅ 낮음 |

---

이제 **PostgreSQL은 Helm으로 관리하고, CR 방식은 사용하지 않습니다!** ✨

