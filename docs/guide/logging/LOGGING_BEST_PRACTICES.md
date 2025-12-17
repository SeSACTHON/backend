# Logging Best Practices: 빅테크 & CNCF 벤더 사례

> **Version**: 1.0.0  
> **Last Updated**: 2025-12-17  
> **References**: Google SRE, Netflix, Uber, CNCF OpenTelemetry, Elastic

---

## 목차

1. [빅테크 사례 분석](#빅테크-사례-분석)
2. [CNCF 표준](#cncf-표준)
3. [Elastic Common Schema (ECS)](#elastic-common-schema-ecs)
4. [Kubernetes 로깅 패턴](#kubernetes-로깅-패턴)
5. [구현 권장사항](#구현-권장사항)

---

## 빅테크 사례 분석

### Google SRE

| 원칙 | 설명 |
|------|------|
| **Structured Logging** | JSON 포맷으로 파싱/검색 용이성 확보 |
| **Centralized Management** | 모든 서비스 로그를 단일 플랫폼에 집중 |
| **Contextual Enrichment** | request_id, user_id, service_name 등 메타데이터 포함 |
| **Log Level Consistency** | 전체 시스템에서 동일한 레벨 기준 적용 |
| **Sensitive Data Protection** | PII, 자격증명 로깅 금지 |
| **Distributed Tracing Integration** | 로그-트레이스 연동으로 디버깅 효율화 |

### Netflix

**규모**: 하루 페타바이트 단위 로그 처리

```
┌─────────────────────────────────────────────────────────────┐
│                      Netflix Logging Architecture           │
├─────────────────────────────────────────────────────────────┤
│  Services → Request Interceptors → Kafka → ClickHouse      │
│                                                             │
│  특징:                                                       │
│  - HTTP/gRPC 인터셉터로 자동 트레이스 발행                    │
│  - Kafka를 버퍼로 사용 (실시간 스트리밍)                       │
│  - ClickHouse로 고성능 분석 쿼리                              │
└─────────────────────────────────────────────────────────────┘
```

**핵심 포인트:**
- 애플리케이션 코드 변경 최소화 (인터셉터 패턴)
- Kafka를 통한 비동기 처리로 성능 영향 최소화
- 분석용 DB (ClickHouse) 분리로 쿼리 성능 확보

### Uber

**규모**: 하루 8.4억 트레이스, 2,100억 스팬 처리

```
┌─────────────────────────────────────────────────────────────┐
│                      Uber Logging Architecture              │
├─────────────────────────────────────────────────────────────┤
│  Services → Jaeger SDK → Kafka → Elasticsearch              │
│                                                             │
│  특징:                                                       │
│  - Jaeger 개발 (CNCF 기증)                                   │
│  - Adaptive Sampling (<1%)으로 볼륨 관리                     │
│  - ELK Stack으로 중앙 집중화                                 │
│  - Prometheus로 실시간 메트릭                                │
└─────────────────────────────────────────────────────────────┘
```

**핵심 포인트:**
- 샘플링으로 비용/성능 최적화 (통계적 유의성 유지)
- 트레이싱과 로깅 통합
- 실시간 메트릭과 로그 상관관계 분석

---

## CNCF 표준

### OpenTelemetry Logging (2024 GA)

OpenTelemetry는 2024년 로깅 스펙이 GA(General Availability)가 되어 프로덕션 사용 준비 완료.

**3대 신호 통합:**
```
┌─────────────────────────────────────────────────────────────┐
│                    OpenTelemetry Signals                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Traces ←────────────────→ Metrics                        │
│      ↑                          ↑                          │
│      │      trace_id 연동       │                          │
│      └──────────→ Logs ←────────┘                          │
│                                                             │
│   모든 신호가 trace_id로 상관관계 분석 가능                   │
└─────────────────────────────────────────────────────────────┘
```

### OpenTelemetry + Python 통합 패턴

```python
# OpenTelemetry 권장 패턴: Logging Bridge
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

# 1. Logger Provider 설정
logger_provider = LoggerProvider()
set_logger_provider(logger_provider)

# 2. 표준 logging 모듈에 핸들러 추가
handler = LoggingHandler(logger_provider=logger_provider)
logging.getLogger().addHandler(handler)

# 3. 기존 logging 코드 그대로 사용
logger = logging.getLogger(__name__)
logger.info("Message")  # 자동으로 trace_id 포함
```

**장점:**
- 기존 코드 변경 최소화
- 표준 `logging` 모듈 그대로 사용
- trace_id 자동 주입

### Elastic Common Schema (ECS) 통합

OpenTelemetry와 Elastic Common Schema가 2023년 병합되어 통합 표준 제공.

---

## Elastic Common Schema (ECS)

### Core Fields (필수)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `@timestamp` | date | 이벤트 발생 시간 (ISO 8601) | `2025-12-17T09:30:00.000Z` |
| `message` | text | 로그 메시지 | `User login successful` |
| `log.level` | keyword | 로그 레벨 | `info`, `error` |
| `ecs.version` | keyword | ECS 버전 | `8.11.0` |

### Service Fields (서비스 식별)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `service.name` | keyword | 서비스명 | `auth-api` |
| `service.version` | keyword | 서비스 버전 | `0.7.3` |
| `service.environment` | keyword | 환경 | `dev`, `prod` |
| `service.node.name` | keyword | 인스턴스/Pod명 | `auth-api-7d8f9` |

### Trace Fields (분산 추적)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `trace.id` | keyword | 분산 트레이스 ID | `4bf92f3577b34da6...` |
| `span.id` | keyword | 스팬 ID | `00f067aa0ba902b7` |
| `transaction.id` | keyword | 트랜잭션 ID | `abc123` |

### HTTP Fields (API 요청)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `http.request.method` | keyword | HTTP 메서드 | `POST` |
| `url.path` | keyword | 요청 경로 | `/api/v1/auth/login` |
| `http.response.status_code` | long | 응답 코드 | `200` |
| `event.duration` | long | 처리 시간 (나노초) | `145000000` |

### User Fields (사용자)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `user.id` | keyword | 사용자 ID | `user-123` |
| `user.name` | keyword | 사용자명 | `john_doe` |
| `client.ip` | ip | 클라이언트 IP | `192.168.1.1` |

### Error Fields (에러)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `error.type` | keyword | 에러 타입 | `ValidationError` |
| `error.message` | text | 에러 메시지 | `Invalid email format` |
| `error.stack_trace` | text | 스택 트레이스 | `Traceback...` |

### ECS 로그 예시

```json
{
  "@timestamp": "2025-12-17T09:30:00.000Z",
  "message": "User login successful",
  "log.level": "info",
  "ecs.version": "8.11.0",
  "service.name": "auth-api",
  "service.version": "0.7.3",
  "service.environment": "dev",
  "trace.id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span.id": "00f067aa0ba902b7",
  "http.request.method": "POST",
  "url.path": "/api/v1/auth/kakao/callback",
  "http.response.status_code": 200,
  "event.duration": 145000000,
  "user.id": "user-123",
  "client.ip": "192.168.1.1",
  "labels": {
    "provider": "kakao"
  }
}
```

---

## Kubernetes 로깅 패턴

### 핵심 원칙

| 원칙 | 설명 | 이유 |
|------|------|------|
| **stdout/stderr 출력** | 파일 대신 표준 출력 사용 | kubelet 자동 수집, 컨테이너 런타임 통합 |
| **JSON 포맷** | 구조화된 로그 | 파싱/인덱싱/검색 용이 |
| **Node-level Agent** | DaemonSet으로 수집 | Sidecar 대비 리소스 효율적 |
| **중앙 집중화** | Pod 독립적 저장 | Pod 종료 시 로그 보존 |

### 권장 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Node                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│  │ Pod A   │  │ Pod B   │  │ Pod C   │                     │
│  │ stdout→ │  │ stdout→ │  │ stdout→ │                     │
│  └────┬────┘  └────┬────┘  └────┬────┘                     │
│       │            │            │                           │
│       ▼            ▼            ▼                           │
│  ┌─────────────────────────────────────┐                   │
│  │     /var/log/containers/*.log       │                   │
│  └─────────────────┬───────────────────┘                   │
│                    │                                        │
│                    ▼                                        │
│  ┌─────────────────────────────────────┐                   │
│  │     Fluent Bit (DaemonSet)          │  ← Node Agent     │
│  │     - Tail input                    │                   │
│  │     - K8s metadata enrichment       │                   │
│  │     - ES output                     │                   │
│  └─────────────────┬───────────────────┘                   │
│                    │                                        │
└────────────────────┼────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Elasticsearch                            │
│                    (Central Storage)                        │
└─────────────────────────────────────────────────────────────┘
```

### Sidecar vs Node Agent

| 방식 | 장점 | 단점 | 권장 |
|------|------|------|------|
| **Node Agent (DaemonSet)** | 리소스 효율적, 관리 단순 | 커스터마이징 제한 | ✅ 권장 |
| **Sidecar** | 서비스별 커스텀 가능 | 리소스 오버헤드, 복잡성 | 특수 케이스만 |

---

## 구현 권장사항

### 1. 로깅 라이브러리 선택

**Python (FastAPI)**

| 옵션 | 설명 | 권장도 |
|------|------|--------|
| **표준 logging + OTel** | 코드 변경 최소, OTel 자동 연동 | ⭐⭐⭐ 최우선 |
| **structlog** | 강력한 구조화, 추가 의존성 | ⭐⭐ 대안 |
| **loguru** | 간편함, OTel 통합 수동 | ⭐ 소규모 |

**권장: 표준 logging + OpenTelemetry Logging Bridge**

```python
# 최소 변경으로 구조화 로깅 + 트레이스 연동
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "@timestamp": self.formatTime(record),
            "message": record.getMessage(),
            "log.level": record.levelname.lower(),
            "log.logger": record.name,
            "service.name": "auth-api",
        }
        # OTel context 자동 포함 (OTel Handler 사용 시)
        return json.dumps(log_obj)
```

### 2. 로그 포맷 표준화

**ECS 기반 최소 필드셋:**

```json
{
  "@timestamp": "ISO8601",
  "message": "string",
  "log.level": "info|warn|error",
  "service.name": "string",
  "service.version": "string",
  "trace.id": "string (optional)",
  "span.id": "string (optional)"
}
```

### 3. 로그 레벨 정책

| Level | Production | Staging | Development |
|-------|------------|---------|-------------|
| DEBUG | ❌ | ✅ | ✅ |
| INFO | ✅ | ✅ | ✅ |
| WARNING | ✅ | ✅ | ✅ |
| ERROR | ✅ | ✅ | ✅ |

### 4. 민감 정보 처리

**절대 로깅 금지:**
- 비밀번호, 토큰, API 키
- 개인식별정보 (PII)
- 금융 정보

**마스킹 필수:**
```python
# 토큰: 앞 10자만 표시
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6..."
masked = token[:10] + "..." if len(token) > 10 else "***"

# 이메일: 앞 3자 + 도메인
email = "john@example.com"
masked = email[:3] + "***@" + email.split("@")[1]
```

### 5. 성능 최적화

| 기법 | 설명 | 효과 |
|------|------|------|
| **Async I/O** | 로그 쓰기 비동기 처리 | 요청 처리 블로킹 방지 |
| **Level Gating** | 레벨 체크 후 로깅 | 불필요한 연산 방지 |
| **Sampling** | 고빈도 이벤트 샘플링 | 볼륨/비용 절감 |
| **Buffering** | Fluent Bit 버퍼 설정 | 네트워크 효율화 |

---

## ECO2 적용 권장안

### Phase 1: 최소 변경 (권장)

1. **JSON Formatter 적용**
   - 표준 `logging` 모듈 유지
   - JSONFormatter로 포맷만 변경
   - ECS 필드 기반

2. **OpenTelemetry 연동**
   - 이미 설치된 OTel 활용
   - Logging Bridge로 trace_id 자동 주입

3. **환경 변수 제어**
   ```yaml
   env:
   - name: LOG_LEVEL
     value: "INFO"
   - name: LOG_FORMAT
     value: "json"
   ```

### Phase 2: 고도화 (선택)

1. **도메인별 로그 이벤트 정의**
2. **Kibana 대시보드 구성**
3. **Alert 규칙 설정**

---

## 참고 자료

- [Google Cloud Logging Best Practices](https://cloud.google.com/logging/docs/best-practices)
- [OpenTelemetry Logging Specification](https://opentelemetry.io/docs/specs/otel/logs/)
- [Elastic Common Schema Reference](https://www.elastic.co/guide/en/ecs/current/ecs-reference.html)
- [Netflix Logging Architecture](https://clickhouse.com/blog/netflix-petabyte-scale-logging)
- [Uber Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Kubernetes Logging Architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/)
