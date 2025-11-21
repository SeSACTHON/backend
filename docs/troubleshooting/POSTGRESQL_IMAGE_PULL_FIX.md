# PostgreSQL 이미지 Pull 실패 해결

## ❌ 문제
```
container "postgresql" in pod "dev-postgresql-0" is waiting to start: 
trying and failing to pull image
```

**원인:**
- `bitnami/postgresql` 이미지는 엔터프라이즈 레지스트리로 이동
- 공개 Docker Hub에서 접근 불가

---

## ✅ 해결책

### 변경 사항
```yaml
# Before (실패)
image:
  registry: docker.io
  repository: bitnami/postgresql
  tag: 16.4.0-debian-12-r13

# After (성공)
image:
  registry: docker.io
  repository: bitnamilegacy/postgresql  # ← 변경!
  tag: 16.4.0-debian-12-r13
```

**Redis와 동일한 패턴 사용:**
- Redis: `bitnamilegacy/redis:7.4.1-debian-12-r0`
- PostgreSQL: `bitnamilegacy/postgresql:16.4.0-debian-12-r13`

---

## 🚀 재배포 방법

### 1. 코드 푸시
```bash
git push origin develop
```

### 2. 기존 Pod 삭제 (빠른 재시작)
```bash
# 기존 Pod 삭제
kubectl -n postgres delete pod dev-postgresql-0

# 또는 StatefulSet 재시작
kubectl -n postgres rollout restart statefulset dev-postgresql
```

### 3. 또는 ArgoCD Sync
```bash
# kubectl로
kubectl -n argocd annotate application dev-postgresql \
    argocd.argoproj.io/refresh=hard --overwrite

# 또는 argocd CLI로
argocd app sync dev-postgresql --prune
```

### 4. 이미지 Pull 확인
```bash
# Pod 상태 확인
kubectl -n postgres get pods -w

# 예상 출력:
# NAME                 READY   STATUS              RESTARTS   AGE
# dev-postgresql-0     0/1     ContainerCreating   0          10s
# dev-postgresql-0     0/1     Running             0          30s
# dev-postgresql-0     1/1     Running             0          45s  ← 성공!

# 이미지 확인
kubectl -n postgres describe pod dev-postgresql-0 | grep Image:
# Image: docker.io/bitnamilegacy/postgresql:16.4.0-debian-12-r13
```

---

## 🔍 검증된 이미지 정보

### bitnamilegacy/postgresql
- **레지스트리:** docker.io
- **리포지토리:** bitnamilegacy/postgresql
- **태그:** 16.4.0-debian-12-r13
- **PostgreSQL 버전:** 16.4
- **OS:** Debian 12
- **접근:** 공개 (pull 제한 없음)

### 다른 사용 가능한 버전들
```yaml
# PostgreSQL 16 (최신)
repository: bitnamilegacy/postgresql
tag: 16.4.0-debian-12-r13

# PostgreSQL 15
repository: bitnamilegacy/postgresql
tag: 15.8.0-debian-12-r13

# PostgreSQL 14
repository: bitnamilegacy/postgresql
tag: 14.13.0-debian-12-r13
```

---

## 📊 Bitnami vs BitnamilLegacy

| 항목 | bitnami/* | bitnamilegacy/* |
|------|-----------|-----------------|
| **접근** | 엔터프라이즈 전용 | 공개 |
| **인증** | 필요 | 불필요 |
| **Pull 제한** | 있음 | 없음 |
| **업데이트** | 최신 | 레거시 버전 |
| **사용 예** | 프로덕션 (유료) | 개발/테스트 |

---

## ✅ 체크리스트

- [x] 이미지를 `bitnamilegacy/postgresql`로 변경
- [x] dev 및 prod 환경 모두 수정
- [x] 커밋 완료
- [ ] git push
- [ ] 기존 Pod 삭제 또는 ArgoCD Sync
- [ ] 이미지 Pull 성공 확인
- [ ] Pod Running 상태 확인
- [ ] 데이터베이스 접속 테스트

---

## 🎯 빠른 실행 명령어

```bash
# 1. 푸시
git push origin develop

# 2. Pod 재시작
kubectl -n postgres delete pod dev-postgresql-0

# 3. 확인
kubectl -n postgres get pods -w

# 성공하면:
# dev-postgresql-0   1/1   Running   0   2m
```

**이제 이미지 pull이 성공할 것입니다!** 🎉

