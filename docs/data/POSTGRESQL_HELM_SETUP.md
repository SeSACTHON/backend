# PostgreSQL Helm 전환 가이드

## ✅ 완료된 작업

### 1. Kustomize 빌드 에러 해결
- `platform/cr/dev`, `platform/cr/prod` 디렉토리 제거
- `platform/cr/base/kustomization.yaml`에 `resources: []` 설정
- CI 파이프라인 통과 준비 완료

### 2. 새 PostgreSQL 설정
- **Bitnami PostgreSQL Helm Chart** 추가
- Dev: `clusters/dev/apps/27-postgresql.yaml` (standalone, 20Gi)
- Prod: `clusters/prod/apps/27-postgresql.yaml` (replication, 50Gi)
- 데이터베이스 이름: `ecoeco`
- 사용자: `sesacthon`

### 3. 기존 리소스 정리
- Zalando Postgres Operator 관련 파일 제거
- Custom Resource 정의 제거
- 마이그레이션 문서 제거 (필요 없음)

---

## 🚀 배포 절차

### 1. 기존 PostgreSQL 리소스 삭제

클러스터에서 실행:
```bash
# 스크립트 사용 (권장)
./scripts/cleanup-old-postgres.sh

# 또는 수동으로:
kubectl -n postgres delete postgresql postgres-cluster --ignore-not-found=true
kubectl -n postgres delete statefulset postgres-cluster --ignore-not-found=true
kubectl -n postgres delete pod -l cluster-name=postgres-cluster --grace-period=0 --force
kubectl -n postgres delete service postgres-cluster --ignore-not-found=true
kubectl -n postgres delete pvc pgdata-postgres-cluster-0  # 데이터 완전 삭제
```

### 2. 코드 푸시
```bash
git commit -m "refactor(infra): migrate PostgreSQL to Bitnami Helm Chart

- Remove Zalando Postgres Operator (24-postgres-operator.yaml)
- Remove Custom Resource applications (35-data-cr.yaml)
- Add Bitnami PostgreSQL Helm charts (27-postgresql.yaml)
- Update database name: sesacthon → ecoeco
- Clean up platform/cr directory structure
- Fix Kustomize build errors

BREAKING CHANGE: PostgreSQL service endpoint changed
- Old: postgres-cluster.postgres.svc.cluster.local
- New: dev-postgresql.postgres.svc.cluster.local
"

git push origin develop
```

### 3. ArgoCD 동기화 대기
```bash
# 3분 이내 ArgoCD가 변경사항 감지
# dev-postgresql Application이 자동으로 생성되고 배포됨

# Pod 생성 확인
kubectl -n postgres get pods -w
# 예상 결과: dev-postgresql-0   1/1   Running
```

### 4. 데이터베이스 확인
```bash
# 접속 테스트
kubectl -n postgres exec -it dev-postgresql-0 -- psql -U sesacthon -d ecoeco

# 스키마 확인
ecoeco=> \dn
# auth 스키마가 자동 생성되어 있어야 함
```

### 5. auth-api 재시작
```bash
# DATABASE_URL이 변경되었으므로 재시작 필요
kubectl -n auth rollout restart deployment auth-api

# 로그 확인
kubectl -n auth logs -f deployment/auth-api | grep -i database
```

---

## 📊 변경 요약

| 항목 | Before | After |
|------|--------|-------|
| **관리 방식** | Zalando Operator + CR | Bitnami Helm Chart |
| **Service** | postgres-cluster | dev-postgresql |
| **Database** | sesacthon | ecoeco |
| **초기화** | 별도 Job 필요 | initdb 자동 실행 |
| **비밀번호** | 자동 생성 (복잡) | AWS SSM 직접 사용 |

---

## 🔍 트러블슈팅

### Pod이 시작 안 됨
```bash
# Pod 상태 확인
kubectl -n postgres describe pod dev-postgresql-0

# PVC 권한 문제 확인
kubectl -n postgres get events --sort-by='.lastTimestamp'
```

### auth-api 연결 실패
```bash
# Secret 확인
kubectl -n auth get secret auth-secret -o yaml | grep DATABASE_URL

# 올바른 URL:
# postgresql+asyncpg://sesacthon:PASSWORD@dev-postgresql.postgres.svc.cluster.local:5432/ecoeco
```

---

## ✅ 체크리스트

- [ ] 기존 PostgreSQL 리소스 삭제
- [ ] git commit & push
- [ ] ArgoCD 동기화 확인
- [ ] dev-postgresql-0 Running 확인
- [ ] 데이터베이스 접속 테스트
- [ ] auth 스키마 존재 확인
- [ ] auth-api 재시작
- [ ] API 동작 테스트

