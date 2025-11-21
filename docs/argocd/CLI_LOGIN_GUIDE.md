# ArgoCD CLI 로그인 및 Rollout 가이드

## 🔐 ArgoCD CLI 로그인 방법

### 1. ArgoCD CLI 설치

```bash
# macOS
brew install argocd

# Linux
curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x /usr/local/bin/argocd

# 설치 확인
argocd version
```

---

## 🚀 로그인 방법 (4가지)

### **방법 1: Port-Forward로 로그인 (가장 간단, 추천)**

```bash
# 1. Port-forward 시작
kubectl port-forward svc/argocd-server -n argocd 8080:443 &

# 2. 초기 admin 비밀번호 가져오기
kubectl -n argocd get secret argocd-initial-admin-secret \
    -o jsonpath="{.data.password}" | base64 -d

# 3. 로그인
argocd login localhost:8080 \
    --username admin \
    --password <위에서_복사한_비밀번호> \
    --insecure

# 4. 로그인 확인
argocd account get-user-info
```

### **방법 2: 도메인으로 직접 로그인**

```bash
# Username/Password
argocd login argocd.growbin.app \
    --username admin \
    --password <비밀번호> \
    --insecure

# 또는 입력 프롬프트
argocd login argocd.growbin.app --insecure
```

### **방법 3: SSO 로그인**

```bash
argocd login argocd.growbin.app --sso --insecure
# 브라우저가 자동으로 열림
```

### **방법 4: Token 사용**

```bash
# UI에서 Token 생성: Settings > Accounts > Generate Token
argocd login argocd.growbin.app \
    --auth-token <your-token> \
    --insecure
```

---

## 🔄 전체 Rollout (sync-wave 순서)

### **자동 스크립트 사용**

```bash
# 로그인 + 전체 동기화
./scripts/argocd-login-and-sync.sh dev
```

### **수동 명령어**

#### 1. 전체 Applications 한번에
```bash
# 모든 dev Applications 동기화
argocd app sync -l env=dev --prune

# 완료 대기
argocd app wait -l env=dev --health
```

#### 2. sync-wave 순서대로 (순차)
```bash
# 0번: CRDs
argocd app sync dev-crds --prune
argocd app wait dev-crds --health

# 2번: Namespaces
argocd app sync dev-namespaces --prune
argocd app wait dev-namespaces --health

# 10번: Secrets Operator
argocd app sync dev-secrets-operator --prune
argocd app wait dev-secrets-operator --health

# 11번: Secrets CR
argocd app sync dev-secrets-cr --prune
argocd app wait dev-secrets-cr --health

# 27번: PostgreSQL
argocd app sync dev-postgresql --prune --retry-limit 3
argocd app wait dev-postgresql --health --timeout 300

# 28번: Redis
argocd app sync dev-redis --prune
argocd app wait dev-redis --health

# 60번: APIs
argocd app sync dev-apis-appset --prune
argocd app wait dev-apis-appset --health

# 70번: Ingress
argocd app sync dev-ingress --prune
argocd app wait dev-ingress --health
```

#### 3. 특정 Application만
```bash
# PostgreSQL만 동기화
argocd app sync dev-postgresql --prune --retry-limit 3

# Hard Refresh 후 동기화
argocd app get dev-postgresql --hard-refresh
argocd app sync dev-postgresql --prune
```

---

## 📊 상태 확인

### Applications 목록
```bash
# 전체
argocd app list

# dev 환경만
argocd app list --selector env=dev

# 특정 Application
argocd app get dev-postgresql
```

### 실시간 로그
```bash
# Sync 로그
argocd app logs dev-postgresql --follow

# Events
argocd app events dev-postgresql
```

### Diff 확인
```bash
# 현재와 Git의 차이
argocd app diff dev-postgresql
```

---

## 🛠️ 유용한 명령어

### History
```bash
# 배포 히스토리
argocd app history dev-postgresql

# 이전 버전으로 롤백
argocd app rollback dev-postgresql <revision>
```

### Sync 옵션
```bash
# Prune (삭제된 리소스 제거)
argocd app sync dev-postgresql --prune

# Force (강제 동기화)
argocd app sync dev-postgresql --force

# Dry-run (미리보기)
argocd app sync dev-postgresql --dry-run

# Replace (기존 리소스 교체)
argocd app sync dev-postgresql --replace

# 특정 리소스만
argocd app sync dev-postgresql --resource Deployment:dev-postgresql
```

### 자동 동기화 설정
```bash
# 활성화
argocd app set dev-postgresql \
    --sync-policy automated \
    --auto-prune \
    --self-heal

# 비활성화
argocd app unset dev-postgresql --sync-policy
```

---

## 🎯 PostgreSQL 배포 시나리오

### 시나리오 1: 로그인 후 PostgreSQL만 빠르게
```bash
# 1. Port-forward + 로그인
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
ARGOCD_PWD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
argocd login localhost:8080 --username admin --password $ARGOCD_PWD --insecure

# 2. PostgreSQL 동기화
argocd app sync dev-postgresql --prune --retry-limit 3

# 3. 상태 확인
argocd app get dev-postgresql
kubectl -n postgres get pods -w
```

### 시나리오 2: 전체 Applications 순차 동기화
```bash
# 1. 로그인 (위와 동일)

# 2. 전체 동기화
for wave in crds namespaces rbac-storage network-policies secrets-operator secrets-cr alb-controller external-dns monitoring-operator grafana postgresql redis apis-appset ingress; do
    echo "🔄 Syncing: dev-$wave"
    argocd app sync dev-$wave --prune
    argocd app wait dev-$wave --health
done
```

### 시나리오 3: Hard Refresh 후 전체 동기화
```bash
# 1. 모든 Applications Hard Refresh
argocd app list --selector env=dev -o name | xargs -I {} argocd app get {} --hard-refresh

# 2. 전체 동기화
argocd app sync -l env=dev --prune

# 3. 완료 대기
argocd app wait -l env=dev --health
```

---

## 🔑 비밀번호 변경 (권장)

```bash
# 초기 admin 비밀번호는 변경하는 것이 좋습니다
argocd account update-password
```

---

## 💡 Tips

### Context 저장
```bash
# 현재 로그인 정보는 ~/.argocd/config에 저장됨
cat ~/.argocd/config

# 여러 환경 전환
argocd context
argocd context <context-name>
```

### 자동 완성
```bash
# Bash
source <(argocd completion bash)

# Zsh
source <(argocd completion zsh)
```

---

## ✅ 빠른 참조

```bash
# 로그인
argocd login localhost:8080 --username admin --password <pwd> --insecure

# 전체 동기화
argocd app sync -l env=dev --prune

# 상태 확인
argocd app list --selector env=dev

# PostgreSQL만
argocd app sync dev-postgresql --prune
argocd app get dev-postgresql

# 로그 확인
argocd app logs dev-postgresql --follow
```

---

## 🚨 로그인 실패 시

### 문제: "dial tcp: lookup argocd.growbin.app: no such host"
```bash
# Port-forward 사용
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
argocd login localhost:8080 --insecure
```

### 문제: "x509: certificate signed by unknown authority"
```bash
# --insecure 플래그 추가
argocd login <server> --insecure
```

### 문제: "context deadline exceeded"
```bash
# 타임아웃 증가
argocd login <server> --grpc-web
```

---

**가장 간단한 방법:**
```bash
./scripts/argocd-login-and-sync.sh dev
```

로그인부터 전체 동기화까지 자동! 🚀

