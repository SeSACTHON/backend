# Kibana 대시보드 베스트 프랙티스

> 참조: Elastic 공식 가이드라인, Google SRE, CNCF OpenTelemetry (2024-2025)

## 1. 설계 원칙

### 1.1 Google SRE Golden Signals

모든 운영 대시보드는 **4가지 Golden Signals**를 우선적으로 표시합니다:

| Signal | 설명 | ECO2 구현 |
|--------|------|-----------|
| **Latency** | 요청 처리 시간 | 로그 기반 응답 시간 (P95, P99) |
| **Traffic** | 시스템 부하 | 분당 요청 수, 서비스별 로그 볼륨 |
| **Errors** | 에러 비율 | ERROR 레벨 로그 / 전체 로그 |
| **Saturation** | 리소스 포화도 | Pod 메트릭 (별도 메트릭 대시보드) |

### 1.2 대시보드 복잡도 관리

```
✅ 권장:
- 대시보드당 4-6개 시각화
- 관련 콘텐츠는 Links Panel로 연결
- 마진 사용으로 가독성 확보

❌ 피하기:
- 10개 이상 시각화 (과밀)
- 동일 대시보드에 모든 정보 집약
```

## 2. 명명 규칙 (Elastic 공식)

### 2.1 대시보드

```
[<Logs | Metrics> <PACKAGE>] <Name>
```

예시:
- `[Logs ECO2] Overview` - 전체 로그 개요
- `[Logs ECO2] Service Health` - 서비스 상태
- `[Logs ECO2] Business Metrics` - 비즈니스 지표

### 2.2 시각화

패키지명 제외, 기능만 표시:

```
✅ Error Rate by Service
✅ Request Volume
❌ [Logs ECO2] Error Rate by Service (중복)
```

### 2.3 Data View

안정적인 커스텀 ID 사용:

```
✅ logs-eco2-app-dataview
❌ logs-app-* (자동 생성 ID 의존)
```

## 3. 네비게이션

### 3.1 Links Panel

대시보드 간 이동을 위한 Links 패널 필수:

```json
{
  "type": "links",
  "panelsJSON": [
    {"label": "Overview", "dashboard": "logs-eco2-overview"},
    {"label": "Service Health", "dashboard": "logs-eco2-service-health"},
    {"label": "Business", "dashboard": "logs-eco2-business"}
  ]
}
```

### 3.2 Drilldown

상세 정보로 이동하는 Drilldown 설정:

- 에러 클릭 → Trace ID로 필터링된 상세 뷰
- 서비스 클릭 → 해당 서비스 전용 대시보드

### 3.3 Controls Filter

서비스/환경별 필터링:

```json
{
  "type": "input_control_vis",
  "controls": [
    {"field": "service.name", "label": "Service"},
    {"field": "service.environment", "label": "Environment"}
  ]
}
```

## 4. 로깅 연계 (CNCF/OTel)

### 4.1 필수 필드 (ECS 기반)

| 필드 | 용도 | 대시보드 활용 |
|------|------|---------------|
| `@timestamp` | 시계열 분석 | 모든 시각화의 X축 |
| `log.level` | 심각도 필터 | 에러율 계산, 필터 |
| `service.name` | 서비스 식별 | 그룹핑, 필터 |
| `trace.id` | 분산 추적 | Drilldown 연결 |
| `labels.*` | 비즈니스 컨텍스트 | 커스텀 메트릭 |

### 4.2 로그 메시지 표준화

대시보드 쿼리 용이성을 위한 일관된 메시지:

```python
# ✅ 권장: 검색 가능한 구조화된 메시지
logger.info("OAuth login successful", extra={"user_id": user_id, "provider": provider})

# ❌ 피하기: 가변적인 메시지
logger.info(f"User {user_id} logged in via {provider}")
```

## 5. 성능 고려사항

### 5.1 쿼리 최적화

```
✅ 권장:
- 시간 범위 제한 (기본 24h)
- 집계 사용 (terms, date_histogram)
- 필요한 필드만 select

❌ 피하기:
- 전체 기간 스캔
- 와일드카드 쿼리 남용
- 불필요한 필드 포함
```

### 5.2 새로고침 간격

| 대시보드 유형 | 권장 간격 |
|--------------|----------|
| 실시간 모니터링 | 30초 |
| 일반 운영 | 5분 |
| 비즈니스 리포트 | 수동 |

## 6. ECO2 대시보드 구조

```
[Logs ECO2] Overview (Landing)
    ├── Links Panel (네비게이션)
    ├── Golden Signals Summary
    └── Service Health Grid

[Logs ECO2] Service Health
    ├── Error Rate by Service
    ├── Request Volume Trend
    └── Top Errors Table

[Logs ECO2] Developer Debug
    ├── Trace Search
    ├── Recent Errors
    └── Debug Log Stream

[Logs ECO2] Business Metrics
    ├── Daily Active Users
    ├── Feature Usage
    └── Reward Grants
```

## 참조

- [Elastic Dashboard Guidelines](https://www.elastic.co/docs/extend/integrations/dashboard-guidelines)
- [Google SRE Book - Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)
- [CNCF OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/)
- [Elastic Common Schema](https://www.elastic.co/guide/en/ecs/current/index.html)
