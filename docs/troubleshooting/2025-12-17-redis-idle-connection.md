# Redis Idle Connection 문제 해결

> **날짜**: 2025-12-17  
> **영향 서비스**: auth-api, chat-api, image-api  
> **심각도**: Medium  
> **상태**: ✅ 해결됨

---

## 📋 증상

### 에러 메시지

```
ERROR: Exception in ASGI application
redis.exceptions.ConnectionError: Connection closed by server.
```

### 발생 조건

- 서비스가 일정 시간(30초~1분) 유휴 상태 후 첫 번째 요청
- OAuth 콜백, 채팅 메시지 전송 등 Redis 조회가 필요한 엔드포인트

### 영향

- 간헐적 500 에러 발생
- 사용자 로그인 실패
- 재시도 시 정상 동작 (자동 재연결)

---

## 🔍 원인 분석

### Redis 서버 측 설정

Redis는 기본적으로 **idle connection timeout**을 설정할 수 있습니다:

```
# redis.conf
timeout 0  # 0 = 무제한 (기본값)
```

그러나 **네트워크 레벨**에서 idle connection을 끊는 경우가 있습니다:

1. **Kubernetes NetworkPolicy**: 일정 시간 유휴 연결 종료
2. **AWS NAT Gateway**: 350초 idle timeout
3. **Load Balancer**: idle timeout 설정

### 클라이언트 측 문제

`redis.asyncio` 클라이언트는 기본적으로 **connection pool**을 사용하며, pool 내 연결이 서버에서 끊어진 것을 감지하지 못합니다.

```python
# 문제 코드
redis_client = Redis.from_url(url, decode_responses=True)
# ❌ health_check_interval 미설정 → 끊어진 연결 재사용
```

---

## ✅ 해결 방법

### health_check_interval 설정

`redis.asyncio.Redis.from_url()`에 `health_check_interval` 파라미터를 추가:

```python
# domains/auth/core/redis.py
from redis.asyncio import Redis

HEALTH_CHECK_INTERVAL = 30  # 30초마다 연결 상태 확인


def _build_client(url: str) -> Redis:
    return Redis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        health_check_interval=HEALTH_CHECK_INTERVAL,  # ✅ 핵심
    )
```

### 동작 원리

`health_check_interval=30` 설정 시:

1. 마지막 명령 실행 후 30초가 지난 연결에 대해
2. 실제 명령 실행 전 `PING` 명령으로 연결 상태 확인
3. 연결이 끊어졌으면 자동으로 재연결

### 적용 대상 서비스

| 서비스 | 파일 | 적용 |
|--------|------|------|
| auth-api | `domains/auth/core/redis.py` | ✅ |
| chat-api | `domains/chat/core/redis.py` | ✅ |
| image-api | `domains/image/core/redis.py` | ✅ |

---

## 📝 변경 사항

### Before

```python
def _build_client(url: str) -> Redis:
    return Redis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
    )
```

### After

```python
HEALTH_CHECK_INTERVAL = 30


def _build_client(url: str) -> Redis:
    return Redis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        health_check_interval=HEALTH_CHECK_INTERVAL,
    )
```

---

## 🔗 관련 이슈

- **PR**: #155 (Observability Enhancement)
- **Kibana 로그**: `service.name: "auth-api" AND "Connection closed by server"`

---

## 📚 참고 자료

- [redis-py health_check_interval](https://redis-py.readthedocs.io/en/stable/connections.html#redis.Redis.from_url)
- [AWS NAT Gateway timeout](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-troubleshooting.html)
- [Kubernetes NetworkPolicy idle timeout](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

---

## 🧪 검증 방법

```bash
# 1. 서비스 배포 후 1분 대기
# 2. API 호출
curl https://api.dev.growbin.app/api/v1/auth/kakao

# 3. 에러 없이 응답 확인
# 4. Kibana에서 "Connection closed by server" 로그 없음 확인
```
