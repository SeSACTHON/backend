# Auth Relay (Temporarily Disabled)

> ⚠️ **현재 비활성화됨**: 코드 분리 작업 중

## 상태

- **코드**: `apps/auth/workers/` → `apps/auth_relay/`로 이동 예정
- **ArgoCD**: dev/prod ApplicationSet에서 주석 처리됨
- **CI**: `ci-auth-relay.yml` 비활성화됨

## 설명

Redis Outbox에서 실패한 블랙리스트 이벤트를 RabbitMQ로 재발행하는 워커입니다.

```
auth-api (logout)
    │
    ├── 1차 시도: RabbitMQ 직접 발행 (성공률 ~99%)
    │
    └── 실패 시: Redis Outbox에 적재 (LPUSH)
            │
            └── Relay Worker
                    │
                    └── RPOP → RabbitMQ 재발행
```

## 재활성화 방법

1. `apps/auth_relay/` 생성 및 코드 이동
2. `ci-auth-relay.yml` 활성화
3. ArgoCD ApplicationSet에서 주석 해제
