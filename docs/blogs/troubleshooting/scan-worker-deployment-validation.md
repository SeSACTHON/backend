# Scan Worker 배포 전 정합성 점검 보고서

> 작성일: 2026-01-07  
> 상태: Resolved

---

## 1. 개요

Scan Worker를 Clean Architecture로 마이그레이션한 후 배포 전 전체 정합성을 점검했습니다.

### 점검 범위

- Celery Task ↔ Queue 이름 일치 (1:1 매핑 정책)
- `apps/scan_worker` ↔ `apps/scan` 호출 정합성
- Kubernetes Manifest ↔ 코드 환경변수 정합성
- RabbitMQ 큐 존재 여부
- External Secret 설정 정합성

---

## 2. 큐 라우팅 정합성

### 2.1 Scan 내부 큐 (✅ 통과)

| Task | Queue | scan_worker | scan API | RabbitMQ |
|------|-------|:-----------:|:--------:|:--------:|
| `scan.vision` | `scan.vision` | ✅ | ✅ | ✅ |
| `scan.rule` | `scan.rule` | ✅ | ✅ | ✅ |
| `scan.answer` | `scan.answer` | ✅ | ✅ | ✅ |
| `scan.reward` | `scan.reward` | ✅ | ✅ | ✅ |

**검증 위치:**

- `apps/scan_worker/setup/celery.py`: `SCAN_TASK_ROUTES`
- `apps/scan/setup/celery_app.py`: `task_routes`
- `apps/scan_worker/presentation/tasks/*.py`: `@celery_app.task(name=..., queue=...)`

### 2.2 External 서비스 호출 (⚠️ 이슈 발견)

| Task | Queue | reward_step | Target Worker | RabbitMQ |
|------|-------|:-----------:|:-------------:|:--------:|
| `character.match` | `character.match` | ✅ | character_worker | ✅ |
| `character.save_ownership` | `character.save_ownership` | ✅ | character_worker | ✅ |
| `users.save_character` | `users.save_character` | ✅ | users_worker | ❌ **없음** |

**원인:** `users-worker`가 RabbitMQ에 연결되지 않아 큐가 생성되지 않음

---

## 3. 발견된 이슈

### 3.1 RabbitMQ 사용자명 불일치 (🔴 Critical)

**증상:**

```
consumer: Cannot connect to amqp://rabbitmq:**@eco2-rabbitmq...
```

**원인 분석:**

| 파일 | 설정된 사용자명 | 올바른 값 |
|------|:--------------:|:--------:|
| `dev/users-api-secrets.yaml` | `rabbitmq` | `admin` |
| `prod/users-api-secrets.yaml` | `rabbitmq` | `admin` |
| `dev/api-secrets.yaml` (auth) | `rabbitmq` | `admin` |

**수정:**

```yaml
# Before
CELERY_BROKER_URL: amqp://rabbitmq:{{ .rabbitmqPassword }}@...

# After
CELERY_BROKER_URL: amqp://admin:{{ .rabbitmqPassword }}@...
```

### 3.2 환경변수 Prefix 불일치 (🟡 Medium)

**증상:** scan_worker가 환경변수를 읽지 못함

**원인:**

```python
# config.py에서 SCAN_WORKER_ prefix 사용
model_config = SettingsConfigDict(
    env_prefix="SCAN_WORKER_",  # ❌ 문제
    ...
)
```

```yaml
# deployment.yaml에서 prefix 없이 주입
- name: CELERY_BROKER_URL  # SCAN_WORKER_CELERY_BROKER_URL가 아님
  valueFrom:
    secretKeyRef:
      name: scan-secret
      key: CELERY_BROKER_URL
```

**수정:**

```python
# env_prefix 제거
model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
)
```

---

## 4. Manifest-Code 정합성

### 4.1 Deployment (✅ 통과)

| 항목 | 값 | 상태 |
|------|-----|:----:|
| Celery app 경로 | `apps.scan_worker.setup.celery:celery_app` | ✅ |
| Queue 목록 | `scan.vision,scan.rule,scan.answer,scan.reward` | ✅ |
| Pool 타입 | `gevent` | ✅ |
| Concurrency | `100` | ✅ |

### 4.2 ConfigMap (✅ 통과)

| 키 | 값 | 용도 |
|-----|-----|------|
| `CHECKPOINT_TTL` | `3600` | 체크포인트 TTL (1시간) |
| `DEFAULT_MODEL` | `gpt-5.2` | 기본 LLM 모델 |
| `SUPPORTED_GPT_MODELS` | `gpt-5.2,...` | GPT 허용 목록 |
| `SUPPORTED_GEMINI_MODELS` | `gemini-3-pro-preview,...` | Gemini 허용 목록 |

### 4.3 ExternalSecret (✅ 통과)

| 키 | SSM 경로 | 상태 |
|-----|----------|:----:|
| `OPENAI_API_KEY` | `/sesacthon/dev/api/chat/openai-api-key` | ✅ |
| `GEMINI_API_KEY` | `/sesacthon/dev/api/scan/gemini-api-key` | ✅ |
| `CELERY_BROKER_URL` | (template) | ✅ |

---

## 5. 수정 사항 요약

| 파일 | 변경 내용 |
|------|----------|
| `workloads/secrets/external-secrets/dev/users-api-secrets.yaml` | `rabbitmq` → `admin` |
| `workloads/secrets/external-secrets/prod/users-api-secrets.yaml` | `rabbitmq` → `admin` |
| `workloads/secrets/external-secrets/dev/api-secrets.yaml` | `rabbitmq` → `admin` |
| `apps/scan_worker/setup/config.py` | `env_prefix` 제거 |

---

## 6. 배포 후 검증 절차

### 6.1 RabbitMQ 큐 확인

```bash
kubectl exec -n rabbitmq eco2-rabbitmq-server-0 -- \
  rabbitmqctl list_queues -p eco2 | grep -E "scan\.|users\."
```

**기대 결과:**

```
scan.vision       0
scan.rule         0
scan.answer       0
scan.reward       0
users.save_character  0
```

### 6.2 Workers 상태 확인

```bash
kubectl get pod -n scan | grep worker
kubectl get pod -n users | grep worker
```

### 6.3 Celery 연결 확인

```bash
kubectl exec -n scan deployment/scan-worker -- \
  celery -A apps.scan_worker.setup.celery:celery_app inspect ping
```

---

## 7. 교훈

### 7.1 일관된 네이밍의 중요성

- RabbitMQ 사용자명이 서비스마다 다르게 설정되어 있었음
- **대책:** ExternalSecret 템플릿 표준화 (공통 변수 추출)

### 7.2 환경변수 매핑 검증

- pydantic `env_prefix`와 Kubernetes env 주입 간 불일치
- **대책:** 배포 전 환경변수 매핑 테이블 검증 추가

### 7.3 큐 존재 검증

- 연결 실패로 인해 큐가 자동 생성되지 않음
- **대책:** startup probe에서 큐 생성 검증 추가 고려

---

## 8. 관련 문서

- [Scan Worker Migration Roadmap](../../plans/scan-worker-migration-roadmap.md)
- [Stateless Reducer Pattern](../../plans/scan-worker-stateless-reducer.md)
- [Clean Architecture Migration](../clean-architecture/07-scan-migration-roadmap.md)

