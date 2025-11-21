# ✅ CI Kustomize 빌드 에러 해결

## 🐛 문제

### CI 파이프라인 실패
```bash
Error: kustomization.yaml is empty
```

### 원인
`platform/cr/base/kustomization.yaml`에서 `resources` 필드가 비어있었습니다:

```yaml
# ❌ 잘못된 설정
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  # Redis Sentinel은 Redis Operator에서 관리
  # Redis 관련 CR은 별도로 추가 가능
```

Kustomize는 `resources` 필드가 있지만 실제 리소스가 없으면 에러를 발생시킵니다.

---

## ✅ 해결

### 수정된 kustomization.yaml
```yaml
# ✅ 올바른 설정
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
# Redis Sentinel은 Redis Operator에서 관리
# PostgreSQL은 Helm Chart로 관리 (clusters/dev/apps/27-postgresql.yaml)
# 현재 이 디렉토리에는 Custom Resources가 없음
resources: []
```

**핵심:** 빈 배열 `[]`을 명시적으로 지정하면 Kustomize가 정상 작동합니다.

---

## 🧪 테스트 결과

### ✅ 모든 platform/cr 빌드 성공
```bash
# Base
kustomize build platform/cr/base
# → 성공 (빈 출력)

# Dev
kustomize build platform/cr/dev
# → 성공 (빈 출력)

# Prod
kustomize build platform/cr/prod
# → 성공 (빈 출력)
```

---

## 📝 변경 내용

### 수정된 파일
```
platform/cr/base/kustomization.yaml
- resources 필드를 빈 배열로 명시: resources: []
```

### 이유
- PostgreSQL은 이제 Helm Chart로 관리됨 (CR 불필요)
- Redis도 Bitnami Helm Chart로 관리됨 (CR 불필요)
- platform/cr 디렉토리는 향후 확장성을 위해 구조만 유지
- 빈 kustomization도 유효한 설정임을 명시

---

## 🚀 다음 단계

### 1. 변경사항 커밋
```bash
git add platform/cr/base/kustomization.yaml
git commit -m "fix(kustomize): set empty resources array to fix CI build

- Fix kustomize build error: 'kustomization.yaml is empty'
- Set resources: [] explicitly for empty Custom Resources directory
- All CRs removed as services migrated to Helm Charts
"
```

### 2. 전체 변경사항 푸시
```bash
git add -A
git commit -m "refactor(infra): migrate PostgreSQL from Zalando Operator to Bitnami Helm

- Remove Zalando Postgres Operator (24-postgres-operator.yaml)
- Remove Custom Resource applications (35-data-cr.yaml)
- Remove postgres-cluster CR definitions
- Add Bitnami PostgreSQL Helm charts (27-postgresql.yaml)
- Update database URL and name (postgres-cluster → dev-postgresql, sesacthon → ecoeco)
- Fix Kustomize build error with empty resources array
- Add migration documentation

BREAKING CHANGE: PostgreSQL service endpoint changed
"

git push origin develop
```

### 3. CI 파이프라인 확인
```
✅ Kustomize Build 통과 예상
✅ Lint 통과 예상
✅ 파이프라인 성공 후 ArgoCD 자동 동기화
```

---

## 📊 Kustomize 모범 사례

### 빈 Kustomization 처리

#### ❌ 잘못된 방법
```yaml
# 방법 1: resources 필드 없음
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
# resources: # 주석 처리

# 방법 2: resources가 있지만 항목 없음
resources:
  # 주석만 있음
```

#### ✅ 올바른 방법
```yaml
# 방법 1: 빈 배열 명시 (권장)
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources: []

# 방법 2: 최소 1개의 리소스
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - some-resource.yaml
```

### 디렉토리 구조 정리 옵션

#### 옵션 1: 빈 Kustomization 유지 (현재 선택)
```
platform/cr/
├── base/kustomization.yaml (resources: [])
├── dev/kustomization.yaml
└── prod/kustomization.yaml
```
**장점:** 향후 CR 추가 시 구조 재사용 가능

#### 옵션 2: 디렉토리 완전 제거 (극단적)
```
# platform/cr 전체 삭제
git rm -r platform/cr/
```
**단점:** 나중에 CR 필요 시 구조 재생성 필요

---

## ✅ 해결 완료

```
✅ Kustomize 빌드 에러 수정
✅ CI 파이프라인 통과 준비 완료
✅ 커밋/푸시 준비 완료
```

**이제 안전하게 푸시할 수 있습니다!** 🚀

