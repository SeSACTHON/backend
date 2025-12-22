# Kafka Cluster Separation Plan

> 용도별 Kafka 클러스터 분리 계획 (Logs, CDC, Events/Outbox)

## 1. 개요 (Overview)

본 문서는 Full Event-Driven Architecture (Phase 4) 달성 시 Kafka를 용도별로 분리하여 운영하는 계획을 정의합니다. 단일 노드의 한계를 극복하고, 워크로드별 최적화된 설정을 적용합니다.

### 1.1 분리 목적

| 목적 | 설명 |
|------|------|
| **장애 격리** | 로그 폭발이 CDC/Events에 영향 주지 않음 |
| **워크로드 최적화** | 용도별 최적 설정 (보존 기간, 파티션 수 등) |
| **SLA 차등화** | CDC: 99.99%, Logs: 99.9% |
| **독립적 확장** | 필요한 클러스터만 스케일 아웃 |

---

## 2. 진화 단계

### 2.1 Phase 2-3: 단일 Kafka (현재 계획)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    단일 Kafka (t3.medium, 4GB)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      k8s-kafka (단일 노드)                           │    │
│  │                                                                      │    │
│  │  Topics:                                                            │    │
│  │  ├─ cdc.auth.*, cdc.scan.*, cdc.character.*  (CDC)                 │    │
│  │  ├─ events.scan.*, events.character.*        (Domain Events)       │    │
│  │  └─ (로그는 EFK 직접 연결 권장)                                     │    │
│  │                                                                      │    │
│  │  Components:                                                        │    │
│  │  ├─ Kafka Broker (KRaft)                                           │    │
│  │  ├─ Debezium Connect                                               │    │
│  │  └─ Schema Registry                                                │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  비용: ~$30/월                                                               │
│  한계: SPOF, 리소스 경합                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Phase 4: Kafka Cluster 분리 (목표)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Kafka Cluster 분리 (3개 클러스터)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  🟢 kafka-cdc (CDC 전용)                                             │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  노드: 3 × t3.small (2GB)                                           │   │
│  │  용도: Debezium CDC (WAL 기반 변경 감지)                            │   │
│  │  Topics:                                                             │   │
│  │  ├─ cdc.auth.users                                                  │   │
│  │  ├─ cdc.scan.scan_tasks                                             │   │
│  │  ├─ cdc.character.ownerships                                        │   │
│  │  └─ cdc.my.user_characters                                          │   │
│  │                                                                      │   │
│  │  설정:                                                               │   │
│  │  ├─ Retention: 7일                                                  │   │
│  │  ├─ Replication Factor: 3                                           │   │
│  │  ├─ Partitions: 테이블당 3                                          │   │
│  │  └─ Cleanup Policy: delete                                          │   │
│  │                                                                      │   │
│  │  SLA: 99.99% (비즈니스 핵심)                                        │   │
│  │  비용: ~$45/월                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  🟣 kafka-events (Domain Events 전용)                                │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  노드: 3 × t3.small (2GB)                                           │   │
│  │  용도: Outbox 기반 도메인 이벤트                                    │   │
│  │  Topics:                                                             │   │
│  │  ├─ events.scan.classified                                          │   │
│  │  ├─ events.scan.answered                                            │   │
│  │  ├─ events.scan.rewarded                                            │   │
│  │  ├─ events.character.granted                                        │   │
│  │  └─ events.my.profile_updated                                       │   │
│  │                                                                      │   │
│  │  설정:                                                               │   │
│  │  ├─ Retention: 30일 (Event Sourcing)                                │   │
│  │  ├─ Replication Factor: 3                                           │   │
│  │  ├─ Partitions: 이벤트 타입당 6                                     │   │
│  │  └─ Cleanup Policy: compact (중요 이벤트)                           │   │
│  │                                                                      │   │
│  │  SLA: 99.95% (재생 가능)                                            │   │
│  │  비용: ~$45/월                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  🟡 kafka-logs (Logs 전용) - Optional                                │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  노드: 2 × t3.small (2GB) 또는 단일 노드                            │   │
│  │  용도: 애플리케이션/인프라 로그 버퍼                                │   │
│  │  Topics:                                                             │   │
│  │  ├─ logs.app.api                                                    │   │
│  │  ├─ logs.app.worker                                                 │   │
│  │  └─ logs.infra.system                                               │   │
│  │                                                                      │   │
│  │  설정:                                                               │   │
│  │  ├─ Retention: 1일 (버퍼 용도)                                      │   │
│  │  ├─ Replication Factor: 1~2 (손실 허용)                             │   │
│  │  ├─ Partitions: 12 (높은 처리량)                                    │   │
│  │  └─ Cleanup Policy: delete                                          │   │
│  │                                                                      │   │
│  │  SLA: 99.9% (손실 허용)                                             │   │
│  │  비용: ~$30/월                                                       │   │
│  │                                                                      │   │
│  │  ※ 대안: EFK 직접 연결 유지 (Kafka 미사용)                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  총 비용: ~$90-120/월 (분리 시)                                             │
│  vs 단일: ~$30/월                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 클러스터별 상세 설계

### 3.1 CDC Cluster (kafka-cdc)

#### 목적
- PostgreSQL WAL 변경사항을 실시간 스트림으로 변환
- 도메인 간 데이터 동기화 기반

#### 토픽 설계

```yaml
# Topic Naming Convention: cdc.<schema>.<table>
topics:
  cdc.auth.users:
    partitions: 3
    replication_factor: 3
    retention_ms: 604800000  # 7일
    cleanup_policy: delete
    
  cdc.scan.scan_tasks:
    partitions: 6           # 높은 처리량
    replication_factor: 3
    retention_ms: 604800000
    
  cdc.character.character_ownerships:
    partitions: 3
    replication_factor: 3
    retention_ms: 604800000
    
  cdc.my.user_characters:
    partitions: 3
    replication_factor: 3
    retention_ms: 604800000
```

#### Debezium Connector 설정

```json
{
  "name": "eco2-postgresql-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgresql.database.svc.cluster.local",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "${secrets:debezium-password}",
    "database.dbname": "ecoeco",
    "database.server.name": "eco2",
    "table.include.list": "auth.users,scan.scan_tasks,character.character_ownerships",
    "plugin.name": "pgoutput",
    "slot.name": "eco2_slot",
    "publication.name": "eco2_publication",
    "topic.prefix": "cdc",
    "key.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "key.converter.schema.registry.url": "http://schema-registry:8081",
    "value.converter.schema.registry.url": "http://schema-registry:8081"
  }
}
```

### 3.2 Events Cluster (kafka-events)

#### 목적
- Outbox 패턴 기반 도메인 이벤트 발행
- Event Sourcing 지원
- 다중 Consumer 구독

#### 토픽 설계

```yaml
# Topic Naming Convention: events.<domain>.<event_type>
topics:
  # Scan 도메인
  events.scan.requested:
    partitions: 6
    replication_factor: 3
    retention_ms: 2592000000  # 30일
    cleanup_policy: compact
    
  events.scan.classified:
    partitions: 6
    replication_factor: 3
    retention_ms: 2592000000
    
  events.scan.answered:
    partitions: 6
    replication_factor: 3
    retention_ms: 2592000000
    
  events.scan.rewarded:
    partitions: 3
    replication_factor: 3
    retention_ms: 2592000000
    
  # Character 도메인
  events.character.granted:
    partitions: 3
    replication_factor: 3
    retention_ms: 2592000000
    cleanup_policy: compact
    
  # My 도메인
  events.my.profile_updated:
    partitions: 3
    replication_factor: 3
    retention_ms: 2592000000
```

#### Outbox Connector 설정

```json
{
  "name": "eco2-outbox-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "transforms": "outbox",
    "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
    "transforms.outbox.table.expand.json.payload": "true",
    "transforms.outbox.route.topic.replacement": "events.${routedByValue}",
    "table.include.list": "scan.outbox,character.outbox,my.outbox",
    "tombstones.on.delete": "false"
  }
}
```

### 3.3 Logs Cluster (kafka-logs) - Optional

#### 목적
- 로그 버퍼링 (Fluent Bit → Kafka → Logstash)
- 로그 폭발 시 버퍼 역할

#### 대안 비교

| 방식 | 장점 | 단점 |
|------|------|------|
| **EFK 직접** | 단순, 비용 절감 | 버퍼 없음, 폭발 시 유실 |
| **Kafka 경유** | 버퍼링, 재처리 | 추가 비용, 복잡도 |

#### 권장
- **Phase 4 초기**: EFK 직접 연결 유지
- **로그 볼륨 증가 시**: kafka-logs 추가

---

## 4. 인프라 구성

### 4.1 Kubernetes 리소스

```yaml
# Namespace
apiVersion: v1
kind: Namespace
metadata:
  name: kafka-cdc
---
apiVersion: v1
kind: Namespace
metadata:
  name: kafka-events
---
# Node Labels
# kubectl label node <node> infra-type=kafka-cdc
# kubectl label node <node> infra-type=kafka-events
```

### 4.2 Strimzi Operator 기반 클러스터

```yaml
# kafka-cdc-cluster.yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: kafka-cdc
  namespace: kafka-cdc
spec:
  kafka:
    version: 3.6.0
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      default.replication.factor: 3
      min.insync.replicas: 2
      log.retention.hours: 168  # 7일
    storage:
      type: jbod
      volumes:
        - id: 0
          type: persistent-claim
          size: 50Gi
          class: gp3
    template:
      pod:
        affinity:
          nodeAffinity:
            requiredDuringSchedulingIgnoredDuringExecution:
              nodeSelectorTerms:
                - matchExpressions:
                    - key: infra-type
                      operator: In
                      values:
                        - kafka-cdc
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 10Gi
      class: gp3
  entityOperator:
    topicOperator: {}
    userOperator: {}
---
# kafka-events-cluster.yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: kafka-events
  namespace: kafka-events
spec:
  kafka:
    version: 3.6.0
    replicas: 3
    config:
      log.retention.hours: 720  # 30일
      log.cleanup.policy: compact,delete
    # ... (유사한 설정)
```

---

## 5. 네트워크 토폴로지

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Kafka Cluster 네트워크                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                                                            │
│  │  API Pods   │                                                            │
│  │  (scan,my)  │                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                    │
│         │ Outbox INSERT                                                     │
│         ▼                                                                    │
│  ┌─────────────┐       ┌─────────────────────────────────────────────┐      │
│  │ PostgreSQL  │──WAL──│           Debezium Connect                  │      │
│  │             │       │  ├─ cdc-connector → kafka-cdc              │      │
│  │  + Outbox   │       │  └─ outbox-connector → kafka-events        │      │
│  └─────────────┘       └─────────────────────────────────────────────┘      │
│                                │                    │                        │
│                                ▼                    ▼                        │
│                        ┌─────────────┐      ┌─────────────┐                 │
│                        │ kafka-cdc   │      │kafka-events │                 │
│                        │ (3 brokers) │      │ (3 brokers) │                 │
│                        └──────┬──────┘      └──────┬──────┘                 │
│                               │                    │                         │
│         ┌─────────────────────┼────────────────────┤                        │
│         ▼                     ▼                    ▼                         │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                 │
│  │ my-service  │      │ Analytics   │      │  Webhook    │                 │
│  │ (CQRS Sync) │      │  Consumer   │      │  Consumer   │                 │
│  └─────────────┘      └─────────────┘      └─────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 비용 분석

### 6.1 Phase별 비용

| Phase | 구성 | 월 비용 |
|-------|------|--------|
| Phase 2-3 | 단일 Kafka (t3.medium) | ~$30 |
| Phase 4 (최소) | CDC + Events (6 × t3.small) | ~$90 |
| Phase 4 (전체) | + Logs (2 × t3.small) | ~$120 |

### 6.2 비용 최적화 옵션

1. **Spot Instance 활용**: Events/Logs 클러스터에 적용 (50% 절감)
2. **Reserved Instance**: CDC 클러스터에 적용 (30% 절감)
3. **로그 클러스터 제외**: EFK 직접 연결 유지 ($30 절감)

---

## 7. 마이그레이션 계획

### 7.1 단계별 전환

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 1: kafka-events 클러스터 추가                                          │
│  ├─ 기존 단일 Kafka를 kafka-cdc로 전환                                      │
│  ├─ kafka-events 신규 구축                                                  │
│  └─ Outbox Connector 마이그레이션                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  Step 2: Consumer 마이그레이션                                               │
│  ├─ my-service: kafka-events 구독                                          │
│  ├─ Analytics: kafka-events 구독                                           │
│  └─ 기존 단일 Kafka Consumer 제거                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  Step 3: (Optional) kafka-logs 추가                                         │
│  ├─ 로그 볼륨 모니터링                                                      │
│  └─ 필요 시 Fluent Bit → Kafka → Logstash 전환                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 모니터링

### 8.1 클러스터별 대시보드

```yaml
# Grafana Dashboard 구성
dashboards:
  kafka-cdc-overview:
    - Broker Health (Up/Down)
    - Replication Lag
    - Under-replicated Partitions
    - Debezium Connector Status
    
  kafka-events-overview:
    - Consumer Group Lag
    - Messages In/Out Rate
    - Partition Distribution
    
  kafka-logs-overview:
    - Buffer Utilization
    - Drop Rate
    - Logstash Consumer Lag
```

### 8.2 Alert 규칙

```yaml
alerts:
  - name: KafkaCDCUnderReplicated
    expr: kafka_cluster_partition_underreplicated{cluster="kafka-cdc"} > 0
    severity: critical
    
  - name: KafkaEventsConsumerLag
    expr: kafka_consumergroup_lag{cluster="kafka-events"} > 10000
    severity: warning
    
  - name: KafkaLogsDropRate
    expr: rate(kafka_log_drops_total[5m]) > 100
    severity: info
```

---

## 9. 참고 문서

### 프로젝트 내 문서

- [SCAN_PIPELINE_EVOLUTION_PLAN.md](./SCAN_PIPELINE_EVOLUTION_PLAN.md) - Pipeline 진화 계획
- [CDC_ARCHITECTURE_PLAN.md](./CDC_ARCHITECTURE_PLAN.md) - CDC 아키텍처
- [ASYNC_OBSERVABILITY_ARCHITECTURE.md](./ASYNC_OBSERVABILITY_ARCHITECTURE.md) - 비동기 관측 아키텍처

### Foundations (이론적 기초)

| 주제 | 링크 | Kafka 클러스터 연관 |
|------|------|-------------------|
| **Transactional Outbox** | [블로그](https://rooftopsnow.tistory.com/56) | kafka-events: Outbox 이벤트 발행 |
| **Debezium Outbox Event Router** | [블로그](https://rooftopsnow.tistory.com/57) | kafka-cdc: CDC 커넥터 설정 |
| **The Log (Jay Kreps)** | [블로그](https://rooftopsnow.tistory.com/48) | Kafka 설계 원칙, Log 중심 아키텍처 |
| **CQRS** | [블로그](https://rooftopsnow.tistory.com/51) | kafka-events: Read Model 동기화 |
| **Life Beyond Distributed Transactions** | [블로그](https://rooftopsnow.tistory.com/53) | 클러스터 분리 이론적 근거 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2024-12-19 | 1.0 | 초안 작성 |

