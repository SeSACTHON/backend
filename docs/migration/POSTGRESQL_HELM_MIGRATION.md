# PostgreSQL Helm 마이그레이션 가이드

## 📋 변경 사항 요약

### 🔄 Zalando Postgres Operator → Bitnami PostgreSQL Helm Chart

기존의 Zalando Postgres Operator 대신 **Bitnami PostgreSQL Helm Chart**를 사용하도록 변경했습니다.

---

## ❌ 기존 문제점 (Zalando Operator)

### 1. **비밀번호 인증 실패 원인**

```
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "sesacthon"
```

**원인:**
- Zalando Operator는 사용자를 생성할 때 **자동으로 랜덤 비밀번호**를 생성
- Secret 이름: `sesacthon.postgres-cluster.credentials.postgresql.acid.zalan.do`
- 이 Secret은 `postgres` namespace에 생성됨
- `auth` namespace의 Job에서 **크로스 네임스페이스 Secret 참조 불가**
- AWS SSM의 postgres-password는 **superuser(postgres)의 비밀번호**이지 sesacthon 사용자의 비밀번호가 아님

### 2. **복잡성**
- Secret 동기화를 위해 Reflector 등 추가 도구 필요
- 사용자 비밀번호 관리가 복잡
- 초기화 스크립트 실행이 어려움

---

## ✅ Helm Chart 솔루션의 장점

### 1. **간단한 비밀번호 관리**

```yaml
auth:
  existingSecret: postgresql-secret
  username: sesacthon
  database: sesacthon
```

- AWS SSM Parameter Store의 비밀번호를 직접 사용
- External Secrets Operator가 `postgresql-secret`을 자동 생성
- **크로스 네임스페이스 문제 없음**

### 2. **초기화 스크립트 지원**

```yaml
primary:
  initdb:
    scripts:
      00-init-schemas.sql: |
        CREATE SCHEMA IF NOT EXISTS auth;
        GRANT ALL PRIVILEGES ON SCHEMA auth TO sesacthon;
```

- PostgreSQL 시작 시 자동으로 스키마 생성
- **별도의 Job 불필요** (하지만 Job도 계속 사용 가능)

### 3. **표준화된 구성**

- Redis와 동일한 방식 (Bitnami Helm Charts)
- 일관된 인프라 관리
- 커뮤니티에서 검증된 설정

---

## 🚀 배포 순서

### 1. **기존 Zalando Operator 리소스 제거** (선택적)

```bash
# 기존 PostgreSQL 클러스터 백업 (중요!)
kubectl -n postgres exec -it postgres-cluster-0 -- pg_dumpall -U postgres > backup.sql

# Zalando Operator 리소스 삭제
kubectl delete -k platform/cr/dev/
```

### 2. **ArgoCD로 새 PostgreSQL 배포**

```bash
# dev 환경
kubectl apply -f clusters/dev/apps/27-postgresql.yaml

# ArgoCD에서 자동으로 배포됨
# Service 이름: dev-postgresql.postgres.svc.cluster.local
```

### 3. **데이터베이스 URL 변경사항**

**변경 전 (Zalando):**
```
postgres-cluster.postgres.svc.cluster.local:5432
```

**변경 후 (Helm):**
```
dev-postgresql.postgres.svc.cluster.local:5432
```

### 4. **DB 초기화 방법**

#### 옵션 A: Helm의 initdb 사용 (권장)
- PostgreSQL Pod가 시작될 때 자동으로 스키마 생성
- `27-postgresql.yaml`의 `initdb.scripts` 섹션에 정의됨

#### 옵션 B: 기존 Job 계속 사용
- `db-bootstrap-job.yaml`은 그대로 사용 가능
- ArgoCD PostSync Hook으로 실행
- 스키마가 이미 존재하면 `CREATE SCHEMA IF NOT EXISTS` 덕분에 에러 없음

---

## 📁 생성된 파일

### Dev 환경
```
clusters/dev/apps/27-postgresql.yaml
```

### Prod 환경
```
clusters/prod/apps/27-postgresql.yaml
```

**차이점:**
- **Dev**: standalone (단일 인스턴스)
- **Prod**: replication (Primary + Read Replica 1개)

---

## 🔧 주요 설정

### Dev 환경

```yaml
architecture: standalone
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi
persistence:
  size: 20Gi
```

### Prod 환경

```yaml
architecture: replication
primary:
  resources:
    requests:
      cpu: 1000m
      memory: 2Gi
    limits:
      cpu: 4000m
      memory: 8Gi
  persistence:
    size: 50Gi

readReplicas:
  replicaCount: 1
  resources: (동일)
```

---

## 🧪 테스트 방법

### 1. PostgreSQL 접속 확인

```bash
# Pod 이름 확인
kubectl -n postgres get pods

# 접속 테스트
kubectl -n postgres exec -it dev-postgresql-0 -- psql -U sesacthon -d sesacthon

# 스키마 확인
\dn
# auth 스키마가 있어야 함

# 권한 확인
\du
# sesacthon 사용자가 있어야 함
```

### 2. auth-db-bootstrap Job 실행

```bash
# Job 재실행
kubectl -n auth delete job auth-db-bootstrap
kubectl -n auth apply -f workloads/apis/auth/base/db-bootstrap-job.yaml

# 로그 확인
kubectl -n auth logs -f job/auth-db-bootstrap
```

**예상 출력:**
```
🔗 Connecting to database: dev-postgresql.postgres.svc.cluster.local:5432/sesacthon
📦 Creating 'auth' schema if not exists...
📦 Creating database tables...
✅ Database tables created successfully!
```

### 3. 애플리케이션에서 연결 확인

```bash
# auth-api Pod 재시작
kubectl -n auth rollout restart deployment auth-api

# 로그 확인
kubectl -n auth logs -f deployment/auth-api
```

---

## 🔐 비밀번호 관리

### AWS SSM Parameter Store

```
/sesacthon/dev/data/postgres-password  → sesacthon 사용자 비밀번호
/sesacthon/prod/data/postgres-password → sesacthon 사용자 비밀번호
```

### Kubernetes Secret (자동 생성)

```yaml
# workloads/secrets/external-secrets/dev/data-secrets.yaml
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgresql-credentials
  namespace: postgres
spec:
  data:
    - secretKey: dbPassword
      remoteRef:
        key: /sesacthon/dev/data/postgres-password
  target:
    name: postgresql-secret
    template:
      data:
        username: sesacthon
        password: "{{ .dbPassword }}"
        postgres-password: "{{ .dbPassword }}"  # postgres superuser도 동일
```

---

## 📊 비교표

| 항목 | Zalando Operator | Bitnami Helm Chart |
|------|------------------|-------------------|
| **설치 방법** | Custom Resource | Helm Values |
| **비밀번호 관리** | 자동 생성 (복잡) | existingSecret (간단) |
| **초기화 스크립트** | 별도 Job 필요 | initdb 내장 |
| **크로스 네임스페이스** | 문제 있음 | 문제 없음 |
| **HA 지원** | 우수 | 양호 (replication) |
| **커뮤니티** | 좁음 | 넓음 |
| **러닝 커브** | 높음 | 낮음 |

---

## ⚠️ 주의사항

### 1. 기존 데이터 백업

```bash
# 반드시 마이그레이션 전에 백업!
kubectl -n postgres exec -it postgres-cluster-0 -- \
  pg_dumpall -U postgres > backup-$(date +%Y%m%d).sql
```

### 2. Service 이름 변경

- 모든 연결 문자열에서 서비스 이름 업데이트 필요
- `api-secrets.yaml`에서 이미 업데이트됨

### 3. Downtime

- 새로운 PostgreSQL 클러스터 생성 → 데이터 복구 → 애플리케이션 재배포
- 약 10-30분 소요 예상

---

## 🎯 다음 단계

1. ✅ PostgreSQL Helm Application 생성 완료
2. ✅ api-secrets.yaml 업데이트 완료
3. ⏳ ArgoCD에서 배포 확인
4. ⏳ DB 초기화 테스트
5. ⏳ 애플리케이션 연결 테스트

---

## 🔗 참고 링크

- [Bitnami PostgreSQL Helm Chart](https://github.com/bitnami/charts/tree/main/bitnami/postgresql)
- [PostgreSQL 초기화 스크립트](https://github.com/bitnami/containers/tree/main/bitnami/postgresql#initializing-a-new-instance)
- [Zalando Postgres Operator 문서](https://postgres-operator.readthedocs.io/)

