# Kibana 대시보드

> 베스트 프랙티스: Elastic 공식 가이드라인, Google SRE Golden Signals, CNCF OpenTelemetry

## 설계 원칙

### 1. Google SRE Golden Signals

모든 운영 대시보드는 4가지 Golden Signals를 우선 표시:

| Signal | 설명 | ECO2 구현 |
|--------|------|-----------|
| **Latency** | 응답 시간 | (메트릭 기반 별도 구현) |
| **Traffic** | 요청량 | 서비스별 로그 볼륨 |
| **Errors** | 에러율 | ERROR 레벨 추이 |
| **Saturation** | 리소스 포화 | (메트릭 기반 별도 구현) |

### 2. Elastic 공식 명명 규칙

```
[<Logs | Metrics> <PACKAGE>] <Name>
```

| 대시보드 | ID | 설명 |
|----------|-----|------|
| `[Logs ECO2] Overview` | `logs-eco2-overview` | Golden Signals 개요 |
| `[Logs ECO2] Developer Debug` | `logs-eco2-debug` | 개발자 디버깅 |
| `[Logs ECO2] Business Metrics` | `logs-eco2-business` | 비즈니스 지표 |

### 3. 네비게이션

- **Links Panel**: 모든 대시보드에 Markdown 기반 네비게이션 포함
- **Controls Filter**: 서비스/레벨별 필터링
- **Drilldown**: 에러 → Trace ID 상세 연결

## 대시보드 파일

### 1. `sre-operations.ndjson` - [Logs ECO2] Overview

운영팀을 위한 Golden Signals 기반 대시보드

**패널 구성:**
- Navigation Links (Markdown)
- Service/Level Filter (Controls)
- Service Health Grid (Tag Cloud)
- Traffic Volume (Line Chart) - Golden Signal: Traffic
- Error Trend (Line Chart) - Golden Signal: Errors
- Recent Errors (Table)

**기본 설정:**
- 시간 범위: 24시간
- 자동 새로고침: 5분

### 2. `developer-debug.ndjson` - [Logs ECO2] Developer Debug

개발자를 위한 디버깅 대시보드

**패널 구성:**
- Navigation Links (Markdown)
- Multi-field Filters (Service, Level, Error Type)
- Errors by Type (Pie Chart)
- Errors by Service (Horizontal Bar)
- Error Details with trace.id (Table)
- Trace Correlation Search

**기본 설정:**
- 시간 범위: 6시간
- 자동 새로고침: 1분

### 3. `business-metrics.ndjson` - [Logs ECO2] Business Metrics

비즈니스 메트릭 대시보드

**패널 구성:**
- Navigation Links (Markdown)
- Total Logins (Metric)
- Rewards Granted (Metric)
- Rewards by Character (Pie Chart)
- Daily Active Logins by Provider (Line Chart)
- Feature Usage: Chat, Image, Location (Stacked Bar)

**기본 설정:**
- 시간 범위: 7일
- 자동 새로고침: 비활성화 (리포트용)

## 사용법

### Import

```bash
# Kibana Dev Tools에서 import
POST kbn:/api/saved_objects/_import?overwrite=true
# 파일 업로드: sre-operations.ndjson

# 또는 curl 사용
curl -X POST "https://kibana.example.com/api/saved_objects/_import?overwrite=true" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: multipart/form-data" \
  --form file=@sre-operations.ndjson
```

### Export (업데이트 시)

```bash
# 특정 대시보드 export
curl -X POST "https://kibana.example.com/api/saved_objects/_export" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -d '{
    "objects": [{"type": "dashboard", "id": "logs-eco2-overview"}],
    "includeReferencesDeep": true
  }' > sre-operations.ndjson
```

## Data View

모든 대시보드는 단일 Data View 사용:

| ID | 패턴 | 설명 |
|----|------|------|
| `logs-eco2-app-dataview` | `logs-app-*` | 앱 로그 |

## 필수 로그 필드 (ECS 기반)

대시보드 쿼리에 사용되는 필드:

| 필드 | 타입 | 용도 |
|------|------|------|
| `@timestamp` | date | 시계열 분석 |
| `log.level` | keyword | 필터, 에러율 |
| `service.name` | keyword | 그룹핑, 필터 |
| `message` | text | 검색, 비즈니스 이벤트 |
| `trace.id` | keyword | 분산 추적 연결 |
| `labels.*` | object | 비즈니스 컨텍스트 |

### 비즈니스 이벤트 메시지 (쿼리용)

```
# 인증
"OAuth login successful"
"Session refreshed"
"User logged out"

# 보상
"Reward evaluation completed" + labels.received: true

# 기능
"Chat message received"
"Upload finalized"
"Location search completed"
```

## 참조

- [Elastic Dashboard Guidelines](https://www.elastic.co/docs/extend/integrations/dashboard-guidelines)
- [Google SRE - Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)
- [CNCF OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/)
- [베스트 프랙티스 문서](../../docs/guide/observability/DASHBOARD_BEST_PRACTICES.md)
