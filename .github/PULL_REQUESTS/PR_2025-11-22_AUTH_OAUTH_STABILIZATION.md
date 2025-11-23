# PR: Auth OAuth 안정화 (2025-11-20 ~ 2025-11-23)

## Summary
- OAuth 콜백 흐름의 불안정(로그 미비, 쿠키 손실, 외부 HTTPS 차단, webhook 실패)을 정비했습니다.
- growbin.app 전역에서 공유 가능한 인증 쿠키 구조와 Route53 DNS 구성을 마련했습니다.

## Changes
1. **OAuth 로깅/정비**
   - Callback 핸들러에 상세 에러 로깅 추가 및 import 순서 정리.
   - RedirectResponse 객체를 재사용하여 `Set-Cookie` 헤더가 리다이렉트 이후에도 유지되도록 수정.
   - 쿠키 `domain`을 `.growbin.app` 으로 설정해 dev/prod 서브도메인에서 공통 사용 가능하도록 변경.
2. **네트워크/보안**
   - AWS ALB Controller에 HTTPS 백엔드 적용을 위해 `allow-external-https` NetworkPolicy 추가.
   - ArgoCD webhook secret을 ExternalSecret + SSM 기반으로 재구성하고 템플릿 문법 오류 수정.
   - Pre-commit(Black/Ruff + hooks) 도입으로 CI lint 안정화.
3. **DNS**
   - Route53에 `frontend.growbin.app`, `frontend.dev.growbin.app` CNAME(Vercel) 레코드 추가  
     (ChangeIds `/change/C0319266JT9MJ5X34A3B`, `/change/C0282994NN7HNNOV0O6V`).

## Testing
- `kubectl logs -n auth deployment/auth-api --since=5m | grep -v health`
- Google/Kakao OAuth 로그인 시나리오 수동 검증
- Route53 `aws route53 get-change <id>`로 DNS 전파 상태 확인

## Checklist
- [x] Pre-commit (black/ruff 등) 통과
- [x] Dev 클러스터 배포/검증
- [x] DNS 변경 반영 대기 (Route53)
- [ ] Prod 반영 (향후)

