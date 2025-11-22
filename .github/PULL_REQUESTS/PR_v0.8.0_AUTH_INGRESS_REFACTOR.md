# Pull Request: v0.8.0 - Auth Service 개발 및 클러스터 환경 배포

## 📋 변경 사항

### 1. Ingress 구조 리팩토링 (2025-11-21 ~ 2025-11-22)

#### 디렉터리 구조 개편
- **Before**: `workloads/ingress/{base,dev,prod}` 통합 구조
- **After**: `workloads/ingress/{auth,argocd,grafana}/{base,dev,prod}` 서비스별 분리

#### ArgoCD Application 관리 방식 변경
- `clusters/*/apps/70-ingresses.yaml` ApplicationSet으로 전환
- 각 서비스(`auth`, `argocd`, `grafana`)가 독립적인 네임스페이스에서 Ingress 관리
- sync-wave: 70 (Secrets 이후, API 배포 이후)

### 2. ALB 통합 및 라우팅 설정

#### ACM Certificate 설정
- ACM ARN을 각 Ingress base에 하드코딩 (v0.9.0에서 SSM 자동화 예정)
- Certificate: `arn:aws:acm:ap-northeast-2:721622471953:certificate/4afcd696-4cc9-4e98-90d4-bfc1161316d2`

#### Host 기반 라우팅 구성
- **Auth API**: `api.dev.growbin.app` → `/api/v1/auth` prefix
- **ArgoCD**: `argocd.dev.growbin.app` → `/` 
- **Grafana**: `grafana.dev.growbin.app` → `/` (현재 503, v0.9.0에서 활성화 예정)

#### Backend 프로토콜 수정
- ArgoCD Ingress: `backend-protocol: HTTPS` → `HTTP`
- 이유: ArgoCD 서버가 `--insecure` 모드로 8080/HTTP 노출

### 3. aws-load-balancer-controller 호환성 수정

#### 문제 상황
```
prefix path shouldn't contain wildcards: /api/v1/auth/*
prefix path shouldn't contain wildcards: /*
```

#### 해결 방법
- dev/prod patch 파일에서 wildcard(`/*`, `/api/v1/auth/*`) 제거
- Kustomize `pathType: Prefix` 사용 시 경로 끝에 `*` 불필요
- ALB Listener Rule이 정상 생성되어 Forward action 구성 완료

### 4. Kustomize 구조 개선

#### patches 전환
- `patchesStrategicMerge` → `patches` 사용
- 각 overlay에서 host/path/backend 명시적 정의

#### 로컬 빌드 검증
```bash
kustomize build workloads/ingress/auth/dev
kustomize build workloads/ingress/argocd/dev
kustomize build workloads/ingress/grafana/dev
```

## 🔍 커밋 히스토리

```
a953fd5  2025-11-22 11:52:01  fix(ingress): remove wildcard from alb prefix paths
6d1d1ef  2025-11-22 11:28:15  fix(ingress): add path backends for alb rules  
40cbf10  2025-11-22 06:49:29  fix(ingress): use HTTP backend for argocd ALB
ce47f89  2025-11-22 06:15:31  refactor(ingress): 도메인별 base/overlay 구조로 재구성
a9c877f  2025-11-22 06:11:01  refactor(ingress): manage ingress apps via applicationset
```

## ✅ 테스트 결과

### 1. Kustomize 빌드 검증
```bash
# Auth Ingress
kustomize build workloads/ingress/auth/dev
✓ host: api.dev.growbin.app
✓ path: /api/v1/auth
✓ backend: auth-api:8000

# ArgoCD Ingress  
kustomize build workloads/ingress/argocd/dev
✓ host: argocd.dev.growbin.app
✓ path: /
✓ backend: argocd-server:443 (protocol: HTTP)

# Grafana Ingress
kustomize build workloads/ingress/grafana/dev
✓ host: grafana.dev.growbin.app
✓ path: /
✓ backend: grafana:80
```

### 2. ALB 리스너 룰 확인
```bash
aws elbv2 describe-rules --listener-arn $LISTENER_ARN --region ap-northeast-2
```

**결과**:
- **Priority 1**: `api.dev.growbin.app` + `/api/v1/auth` → TargetGroup `k8s-auth-authapi-b86698b1f3` ✅
- **Priority 2**: `argocd.dev.growbin.app` + `/*` → TargetGroup `k8s-argocd-argocdse-c1679bb6f2` ✅
- **Priority 3**: `grafana.dev.growbin.app` + `/*` → `fixed-response 503` (예정)
- **Default**: `fixed-response 404`

### 3. aws-load-balancer-controller 로그
```bash
kubectl logs -n kube-system deployment/dev-aws-load-balancer-controller --tail=200
```

**결과**:
- ✅ `successfully built model`
- ✅ `successfully deployed model`
- ✅ `created listener rule` (Priority 1, 2)
- ✅ `created targetGroup` (auth, argocd)
- ✅ `registered targets` (13 instances each)
- ❌ 더 이상 wildcard 관련 에러 없음

### 4. 실제 접속 테스트

#### Auth API
```
URL: https://api.dev.growbin.app/api/v1/auth/docs
결과: ✅ FastAPI Swagger UI 정상 접근
```

#### Google OAuth 로그인
```
Redirect URI: https://api.dev.growbin.app/api/v1/auth/google/callback
결과: ✅ 로그인 성공, JWT 토큰 발급 확인
```

#### PostgreSQL 사용자 저장 확인
```bash
kubectl port-forward -n postgres svc/dev-postgresql 5432:5432
PGPASSWORD=$POSTGRES_PASSWORD psql -h 127.0.0.1 -U postgres -d ecoeco \
  -c "SELECT provider, email, nickname, last_login_at FROM auth.users ORDER BY created_at DESC LIMIT 10;"
```
**결과**: ✅ Google OAuth 사용자 정보 정상 저장

### 5. ArgoCD 상태
```bash
kubectl get applications -n argocd
```

**결과**:
- `dev-ingress-auth`: ✅ Synced / Healthy
- `dev-ingress-argocd`: ✅ Synced / Healthy  
- `dev-ingress-grafana`: ✅ Synced / Healthy

## 🔧 Infrastructure

### ALB 정보
```
LoadBalancer ARN: 
  arn:aws:elasticloadbalancing:ap-northeast-2:721622471953:loadbalancer/app/k8s-ecoecomain-e65d380332/a4812c1c788008bc

Listener ARN (HTTPS:443):
  arn:aws:elasticloadbalancing:ap-northeast-2:721622471953:listener/app/k8s-ecoecomain-e65d380332/a4812c1c788008bc/f7cb060c03c05edc

DNS:
  k8s-ecoecomain-e65d380332-1407559621.ap-northeast-2.elb.amazonaws.com
```

### TargetGroup
- **auth-api**: `k8s-auth-authapi-b86698b1f3` (port 32309)
- **argocd-server**: `k8s-argocd-argocdse-c1679bb6f2` (port 30826)

### Route53 (ExternalDNS 자동 생성)
- `api.dev.growbin.app` → ALB CNAME ✅
- `argocd.dev.growbin.app` → ALB CNAME ✅
- `grafana.dev.growbin.app` → ALB CNAME ✅

## 📝 Known Issues & Next Steps

### v0.9.0 예정 사항

1. **ACM ARN 자동화**
   - 현재: Ingress base에 하드코딩
   - 개선: External Secrets + Kustomize `replacements`로 SSM 기반 자동 주입
   - 관련 파일: `workloads/secrets/external-secrets/{dev,prod}/ingress-acm-secret.yaml`

2. **Grafana Ingress 활성화**
   - 현재: ALB Rule Priority 3이 `fixed-response 503`
   - 원인: Grafana TargetGroup 미생성
   - 조치: Grafana Service/Deployment 상태 확인 후 Ingress 재동기화

3. **Prod 환경 배포**
   - dev 환경 검증 완료 후 `workloads/ingress/*/prod` 적용
   - Google OAuth Redirect URI에 `https://api.growbin.app/api/v1/auth/google/callback` 추가

## 📚 참고 문서

- [AWS Load Balancer Controller Annotations](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.4/guide/ingress/annotations/)
- [Kustomize Replacements](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/replacements/)
- [External Secrets Operator](https://external-secrets.io/latest/)

## ✅ 체크리스트

- [x] 코드 리뷰 완료 (자체 점검)
- [x] 로컬 Kustomize 빌드 테스트
- [x] ArgoCD Application 동기화 확인
- [x] ALB Listener Rule 생성 확인
- [x] aws-load-balancer-controller 로그 점검
- [x] Auth API Swagger 접근 테스트
- [x] Google OAuth 로그인 테스트
- [x] PostgreSQL 사용자 저장 확인
- [x] DNS 레코드 자동 생성 확인
- [ ] Grafana Ingress 활성화 (v0.9.0)
- [ ] ACM ARN 자동화 (v0.9.0)
- [ ] Prod 환경 배포 (v0.9.0)

## 🎯 Release Notes

### v0.8.0 - Auth Service 개발 및 클러스터 환경 배포

**주요 변경사항**:
- ✨ Auth Service Google OAuth 로그인 기능 구현
- ♻️ Ingress 구조를 서비스별 base/overlay로 리팩토링
- 🐛 ALB Listener Rule wildcard 이슈 해결
- 🔧 ArgoCD ApplicationSet 기반 Ingress 배포 자동화
- 🚀 dev 환경 ALB 통합 라우팅 구성 완료

**Breaking Changes**: 없음

**Endpoints**:
- Auth API: `https://api.dev.growbin.app/api/v1/auth/docs`
- ArgoCD UI: `https://argocd.dev.growbin.app`
- Grafana: `https://grafana.dev.growbin.app` (v0.9.0 예정)

