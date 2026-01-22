# Event Router 데이터 무결성 개선 리포트

**작성일**: 2026-01-22
**수정일**: 2026-01-23
**대상 코드**: `apps/event_router/`, `apps/sse_gateway/`
**작업 브랜치**: `fix/event-router-data-integrity`
**PR**: [#484](https://github.com/eco2-team/backend/pull/484)

---

## 1. Executive Summary

Event Router는 Redis Streams → Pub/Sub 기반의 실시간 이벤트 분배 시스템이다. 전반적으로 잘 설계되어 있으나, **process_event 실패 시 ACK 처리**에 치명적인 버그가 있어 데이터 유실 위험이 존재했다. 이 리포트는 발견된 버그와 개선 사항, 그리고 구현 결과를 정리한다.

---

## 2. Bugs (수정 완료)

### 2.1 [P0 Critical] Consumer ACK 정책 버그 ✅ Fixed

**위치**: `consumer.py:202-233`

| 항목 | 내용 |
|------|------|
| **증상** | `process_event` 실패 시에도 `XACK` 실행 → 메시지 PEL에서 제거 |
| **영향** | 실패한 메시지 영구 유실, Reclaimer 재처리 불가 |
| **원인** | 예외 처리 후 `continue` 없이 ACK 코드 도달 |

**수정 내용**:
```python
# Before: 실패해도 ACK 실행
try:
    await self._processor.process_event(event, stream_name=stream_name)
except Exception as e:
    logger.error(...)
# ACK - 항상 실행됨!
await self._redis.xack(...)

# After: 성공한 경우만 ACK
try:
    success = await self._processor.process_event(event, stream_name=stream_name)
    if not success:
        logger.warning("process_event_pubsub_failed", ...)
        continue  # ACK 스킵
except Exception as e:
    logger.error("process_event_error", ...)
    continue  # ACK 스킵

# 성공한 경우만 ACK
await self._redis.xack(...)
```

**커밋**: `97cfae88` fix(event-router): ACK policy 수정으로 데이터 유실 방지

---

### 2.2 [P1] Reclaimer ACK 정책 버그 ✅ Fixed

**위치**: `reclaimer.py:203-244`

| 항목 | 내용 |
|------|------|
| **증상** | Consumer와 동일한 버그 - 실패해도 ACK |
| **영향** | Reclaimer 재처리 시에도 메시지 유실 가능 |
| **원인** | 예외 처리 후 ACK 스킵 로직 누락 |

**수정 내용**: Consumer와 동일한 패턴 적용 - 성공 시에만 ACK

---

### 2.3 [P1] Reclaimer stream_id/stream_name 미주입 ✅ Fixed

**위치**: `reclaimer.py:197-204`

| 항목 | 내용 |
|------|------|
| **증상** | Reclaimer가 stream_id 주입 없이 이벤트 처리 |
| **영향** | SSE Gateway 중복 필터링 우회, 클라이언트 중복 수신 |
| **원인** | Consumer에만 있던 로직이 Reclaimer에 누락 |

**수정 내용**:
```python
# Before
event = self._parse_event(data)
await self._processor.process_event(event)  # stream_name 없음

# After
event = self._parse_event(data)
event["stream_id"] = msg_id  # 추가: Redis Stream ID 주입
await self._processor.process_event(event, stream_name=stream_key)  # stream_name 전달
```

---

### 2.4 [P1] Reclaimer 단일 도메인만 지원 ✅ Fixed

**위치**: `reclaimer.py:45-68`, `main.py:141-150`

| 항목 | 내용 |
|------|------|
| **증상** | Reclaimer가 `scan:events`만 처리 |
| **영향** | `chat:events` Pending 메시지 재할당 불가 |
| **원인** | 단일 `stream_prefix` 파라미터만 지원 |

**수정 내용**:
```python
# Before
self._stream_prefix = stream_prefix  # "scan:events" 고정
self._shard_count = shard_count

# After
self._stream_configs = stream_configs or [("scan:events", 4)]
# 예: [("scan:events", 4), ("chat:events", 4)]
```

---

## 3. Plans (개선 완료)

### 3.1 [P2] SSE id 필드 추가 ✅ Implemented

**위치**: `stream.py:61, 77, 111, 130`

| 항목 | 내용 |
|------|------|
| **목적** | SSE 표준 준수 (Last-Event-ID 지원) |
| **구현** | 모든 이벤트에 `id: stream_id` 필드 추가 |

**수정 내용**:
```python
yield {
    "event": stage,
    "data": json.dumps(event),
    "id": stream_id,  # SSE 표준 id 필드 추가
}
```

---

### 3.2 [추가] Reclaimer 도메인별 병렬 처리 ✅ Implemented

**위치**: `reclaimer.py:105-129`

| 항목 | 내용 |
|------|------|
| **목적** | 도메인별 독립적 처리로 지연 격리 |
| **구현** | `asyncio.gather`로 도메인별 병렬 처리 |

**코드 리뷰에서 발견**: 초기 구현이 순차 처리였으나, 성능 이슈로 병렬 처리로 변경

```python
async def _reclaim_pending(self) -> None:
    # 도메인별 병렬 처리
    tasks = [
        self._reclaim_domain(prefix, shard_count)
        for prefix, shard_count in self._stream_configs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

**커밋**: `cab79127` fix(reclaimer): 도메인 병렬 처리 및 메트릭 라벨 개선

---

### 3.3 [추가] Metrics 라벨 개선 ✅ Implemented

**위치**: `metrics.py:200-213`

| 항목 | 내용 |
|------|------|
| **목적** | 도메인/샤드별 쿼리 용이성 |
| **구현** | `shard` → `domain` + `shard` 라벨 분리 |

**수정 내용**:
```python
# Before
EVENT_ROUTER_RECLAIM_MESSAGES = Counter(
    ...,
    labelnames=["shard"],  # shard="scan:0"
)

# After
EVENT_ROUTER_RECLAIM_MESSAGES = Counter(
    ...,
    labelnames=["domain", "shard"],  # domain="scan", shard="0"
)
```

---

## 4. Plans (미적용 - Phase 2)

### 4.1 [P2] SSE 엔드포인트 인증

**위치**: `stream.py:146-149`

| 항목 | 내용 |
|------|------|
| **현황** | `job_id` 쿼리 파라미터만 검증 |
| **위험** | job_id 노출 시 타 사용자 채팅 탈취 가능 |
| **권장안** | JWT 토큰 검증 + 권한 확인 |

```python
# 권장 구현
@router.get("/{service}/{job_id}/events")
async def stream_events_restful(
    request: Request,
    service: str,
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    if not await verify_job_ownership(user.id, job_id, service):
        raise HTTPException(403, "Access denied")
```

**상태**: 별도 PR 필요 (API 변경 포함)

---

### 4.2 [P2] xgroup_create 운영 문서화

**위치**: `consumer.py:86-91`

| 항목 | 내용 |
|------|------|
| **현황** | `id="0"`으로 Stream 처음부터 읽기 |
| **위험** | `published_ttl` 만료 후 재배포 시 중복 처리 가능 |
| **권장안** | 운영 문서에 재배포 가이드 추가 |

**상태**: 운영 문서 작성 필요

---

### 4.3 [P3] Multi-shard 공정성 모니터링

**위치**: `consumer.py:147-153`

| 항목 | 내용 |
|------|------|
| **현황** | 단일 XREADGROUP으로 모든 shard 읽기 |
| **위험** | 특정 shard에 메시지 몰림 시 다른 shard 지연 |
| **권장안** | `EVENT_ROUTER_XREADGROUP_BATCH_SIZE` 메트릭 모니터링 |

**상태**: 메트릭 존재, 대시보드 연동 권장

---

## 5. 이미 양호한 구현

| 항목 | 위치 | 설명 |
|------|------|------|
| stream_id 주입 (Consumer) | `consumer.py:187` | ✅ Redis Stream ID를 이벤트에 주입 |
| stream_id 기반 중복 필터링 | `broadcast_manager.py:182-190` | ✅ SSE에서 단조 증가 ID로 중복 방지 |
| Token/Stage seq 분리 | `broadcast_manager.py:102-107` | ✅ `last_token_seq`와 `last_stream_id` 분리 |
| Token v2 복구 | `broadcast_manager.py:995-1094` | ✅ Token Stream + State 기반 복구 |
| Lua Script 멱등성 | `processor.py:63-99` | ✅ `router:published:{job_id}:{seq}` 마킹 |
| Pub/Sub 재시도 | `processor.py:284-319` | ✅ 3회 exponential backoff |

---

## 6. Race Condition 분석

### 6.1 동시 요청 안전성

**Lua Script 원자적 실행** (`processor.py:63-99`):

```lua
-- 1. 멱등성: 이미 처리했으면 스킵
if redis.call('EXISTS', publish_key) == 1 then
    return 0  -- router:published:{job_id}:{seq}
end

-- 2. State 조건부 갱신 (더 큰 seq만)
if new_seq <= cur_seq then
    should_update_state = false
end

-- 3. 처리 마킹 (항상)
redis.call('SETEX', publish_key, published_ttl, '1')
```

**동시 요청 시나리오**:

| Pod | 순서 | seq | State 갱신 | Pub/Sub |
|-----|------|-----|-----------|---------|
| B | 먼저 | 2 | ✅ seq=2 | ✅ 발행 |
| A | 나중 | 1 | ❌ seq≤cur | ✅ 발행 |

**결론**: State는 최신 seq 유지, 모든 이벤트 Pub/Sub 발행, 중복 처리 방지됨

---

## 7. 구현 결과 요약

### 완료 항목

| 우선순위 | 항목 | 커밋 |
|---------|------|------|
| P0 | Consumer ACK 정책 수정 | `97cfae88` |
| P1 | Reclaimer ACK 정책 수정 | `97cfae88` |
| P1 | Reclaimer stream_id/stream_name 주입 | `97cfae88` |
| P1 | Reclaimer 멀티 도메인 지원 | `97cfae88` |
| P2 | SSE id 필드 추가 | `97cfae88` |
| - | Reclaimer 도메인 병렬 처리 | `cab79127` |
| - | Metrics domain+shard 라벨 | `cab79127` |
| - | Black 포맷팅 | `a5c39565` |

### 미완료 항목 (Phase 2)

| 우선순위 | 항목 | 사유 |
|---------|------|------|
| P2 | SSE 엔드포인트 인증 | API 변경 필요, 별도 PR |
| P2 | xgroup_create 운영 문서 | 문서 작업 별도 진행 |
| P3 | Multi-shard 공정성 | 모니터링 후 필요 시 개선 |

---

## 8. 변경 파일 목록

```
apps/event_router/core/consumer.py   | ACK 정책 수정
apps/event_router/core/reclaimer.py  | stream_id 주입, 멀티 도메인, 병렬 처리
apps/event_router/main.py            | Reclaimer stream_configs 초기화
apps/event_router/metrics.py         | domain+shard 라벨
apps/sse_gateway/api/v1/stream.py    | SSE id 필드 추가
```

---

## Appendix: 테스트 체크리스트

- [ ] Consumer 처리 실패 시 PEL 유지 확인 (`XPENDING`)
- [ ] Reclaimer가 stream_id 포함하여 재처리 확인
- [ ] 멀티 도메인 (scan/chat) 병렬 처리 확인
- [ ] SSE Last-Event-ID 재연결 테스트
- [ ] Grafana 메트릭 쿼리 확인 (`domain="scan", shard="0"`)
