# 이코에코 서비스 아키텍처

> **작성일**: 2025-12-19  
> **버전**: develop (Observability Enhancement)

---

## 전체 서비스 아키텍처

```mermaid
flowchart TB
    subgraph External["🌐 External"]
        User["👤 User/Client"]
        Route53["Route 53"]
        ALB["AWS ALB"]
    end

    subgraph K8s["☸️ Kubernetes Cluster"]
        
        subgraph Ingress["Ingress Layer (istio-system)"]
            IG["Istio Gateway<br/>(Envoy)"]
            EF["EnvoyFilter<br/>(Cookie→Header)"]
        end
        
        subgraph AuthZ["AuthN/AuthZ Layer"]
            ExtAuthz["ext-authz v1.2.0<br/>(Go gRPC)"]
        end
        
        subgraph Services["Business Logic Layer"]
            Auth["auth-api"]
            My["my-api"]
            Scan["scan-api"]
            Character["character-api"]
            Location["location-api"]
            Image["image-api"]
            Chat["chat-api"]
        end
        
        subgraph Data["Data Layer"]
            Redis[("Redis")]
            PostgreSQL[("PostgreSQL")]
        end
        
        subgraph Observability["📊 Observability Stack"]
            subgraph Tracing["Distributed Tracing"]
                Jaeger["Jaeger<br/>(Collector + UI)"]
            end
            
            subgraph Logging["Central Logging (EFK)"]
                FluentBit["Fluent Bit<br/>(DaemonSet)"]
                ES["Elasticsearch<br/>(ECK)"]
                Kibana["Kibana"]
            end
            
            subgraph Metrics["Metrics"]
                Prometheus["Prometheus"]
                Grafana["Grafana"]
            end
        end
    end

    %% External Flow
    User -->|HTTPS| Route53
    Route53 --> ALB
    ALB --> IG

    %% Request Flow
    IG --> EF
    EF -->|gRPC| ExtAuthz
    ExtAuthz -->|Blacklist| Redis
    
    EF --> Auth & My & Scan & Character & Location & Image & Chat

    %% Data Access
    Auth & My & Scan & Character & Location & Image & Chat --> PostgreSQL
    Auth --> Redis

    %% Observability - Tracing
    IG -.->|Zipkin| Jaeger
    ExtAuthz -.->|OTLP| Jaeger
    Auth & Scan & Chat -.->|OTLP| Jaeger

    %% Observability - Logging
    IG & ExtAuthz & Auth & Scan -.->|stdout| FluentBit
    FluentBit -.->|HTTP| ES
    ES -.-> Kibana

    %% Observability - Metrics
    Prometheus -.->|Scrape| IG & ExtAuthz & Auth & Scan

    classDef external fill:#e1f5fe
    classDef ingress fill:#fff3e0
    classDef auth fill:#fce4ec
    classDef service fill:#e8f5e9
    classDef data fill:#f3e5f5
    classDef obs fill:#fffde7
```

---

## Observability 상세 아키텍처

```mermaid
flowchart LR
    subgraph Sources["📥 Data Sources"]
        subgraph Apps["Applications"]
            PyAPI["Python APIs<br/>(OTEL SDK)"]
            GoAPI["ext-authz<br/>(OTEL SDK)"]
        end
        
        subgraph Infra["Infrastructure"]
            Istio["Istio Sidecar<br/>(Envoy)"]
            System["System Pods<br/>(calico, argocd)"]
        end
    end

    subgraph Tracing["🔍 Distributed Tracing"]
        JaegerCol["Jaeger Collector<br/>:4317 OTLP<br/>:9411 Zipkin"]
        JaegerUI["Jaeger UI<br/>:16686"]
    end

    subgraph Logging["📝 Central Logging"]
        FB["Fluent Bit<br/>(DaemonSet x16)"]
        ESCluster["Elasticsearch<br/>(ECK 8.11)"]
        KibanaUI["Kibana<br/>:5601"]
    end

    subgraph Metrics["📊 Metrics"]
        Prom["Prometheus"]
        Graf["Grafana"]
    end

    %% Tracing Flow
    PyAPI -->|OTLP gRPC :4317| JaegerCol
    GoAPI -->|OTLP gRPC :4317| JaegerCol
    Istio -->|Zipkin :9411| JaegerCol
    JaegerCol --> JaegerUI

    %% Logging Flow
    Apps & Infra -->|stdout/stderr| FB
    FB -->|HTTP :9200| ESCluster
    ESCluster --> KibanaUI

    %% Metrics Flow
    Apps & Istio -->|/metrics| Prom
    Prom --> Graf

    %% Cross-linking
    JaegerUI -.->|trace.id| KibanaUI
```

---

## Trace Context 전파 흐름

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant IG as Istio Gateway
    participant EA as ext-authz
    participant Sidecar as App Sidecar
    participant App as Python API
    participant Jaeger
    participant ES as Elasticsearch

    rect rgb(255, 245, 238)
        Note over IG: trace.id 생성 (%TRACE_ID%)
        Client->>IG: HTTP Request
        IG->>Jaeger: span (Zipkin)
        IG->>ES: access log (trace.id)
    end

    rect rgb(255, 240, 245)
        Note over EA: trace context 추출 (CheckRequest)
        IG->>EA: gRPC + B3 headers
        EA->>EA: Authorization.Check span
        EA->>Jaeger: span (OTLP)
        EA->>ES: auth log (trace.id)
        EA-->>IG: OK + x-user-id
    end

    rect rgb(240, 255, 240)
        Note over App: OTEL SDK B3 propagator
        IG->>Sidecar: HTTP + B3 headers
        Sidecar->>Jaeger: span (Zipkin)
        Sidecar->>App: HTTP + B3 headers
        App->>Jaeger: span (OTLP)
        App->>ES: app log (trace.id)
        App-->>Client: Response
    end
```

---

## 컴포넌트별 Observability 지원

### Span 전송 현황 (Jaeger)

| 서비스 | Istio Sidecar | OTEL SDK | Jaeger 등록 |
|--------|:---:|:---:|:---:|
| istio-ingressgateway | ✅ Zipkin | - | ✅ |
| **ext-authz** | ✅ Zipkin | ✅ OTLP | ✅ |
| auth-api | ✅ Zipkin | ✅ OTLP | ✅ |
| scan-api | ✅ Zipkin | ✅ OTLP | ✅ |
| chat-api | ✅ Zipkin | ✅ OTLP | ✅ |
| character-api | ✅ Zipkin | ✅ OTLP | ✅ |
| location-api | ✅ Zipkin | ✅ OTLP | ✅ |
| image-api | ✅ Zipkin | ✅ OTLP | ✅ |
| my-api | ✅ Zipkin | ✅ OTLP | ✅ |

### 로그 수집 현황 (EFK)

| 소스 | trace.id | service.name | ECS 호환 |
|------|:---:|:---:|:---:|
| Python APIs | ✅ OTEL 자동 | ✅ App 코드 | ✅ |
| ext-authz | ✅ 수동 추출 | ✅ App 코드 | ✅ |
| istio-proxy | ✅ EnvoyFilter | ✅ Lua 생성 | ✅ |
| 시스템 로그 | ❌ | ✅ Lua 생성 | ✅ |

---

## 서비스 포트 매핑

```mermaid
flowchart LR
    subgraph External["External Ports"]
        E443["443 HTTPS"]
    end

    subgraph Gateway["Istio Gateway"]
        G80["80 HTTP"]
        G15090["15090 Envoy Admin"]
    end

    subgraph Jaeger["Jaeger Collector"]
        J4317["4317 OTLP gRPC"]
        J9411["9411 Zipkin"]
        J16686["16686 UI"]
    end

    subgraph ES["Elasticsearch"]
        ES9200["9200 HTTP"]
    end

    subgraph Kibana["Kibana"]
        K5601["5601 UI"]
    end

    subgraph APIs["Backend APIs"]
        API8000["8000 HTTP"]
        API9090["9090 Metrics"]
    end

    subgraph ExtAuthz["ext-authz"]
        EA50051["50051 gRPC"]
        EA9090["9090 Metrics"]
    end

    E443 --> G80
    G80 -->|routing| API8000
    G80 -->|ext-authz| EA50051
    
    API8000 -.->|traces| J4317
    EA50051 -.->|traces| J4317
    G80 -.->|traces| J9411
```

---

## 핵심 설정 요약

### Istio Tracing 설정

```yaml
# meshConfig
defaultConfig:
  tracing:
    sampling: 100
    zipkin:
      address: jaeger-collector-clusterip:9411
enableTracing: true
```

### OTEL SDK 환경변수 (Python)

```yaml
OTEL_SERVICE_NAME: auth-api
OTEL_TRACES_EXPORTER: otlp
OTEL_EXPORTER_OTLP_ENDPOINT: http://jaeger-collector:4317
OTEL_PROPAGATORS: b3,tracecontext,baggage
```

### OTEL SDK 환경변수 (Go ext-authz)

```yaml
OTEL_ENABLED: "true"
OTEL_EXPORTER_OTLP_ENDPOINT: jaeger-collector:4317
OTEL_SAMPLING_RATE: "1.0"
```

### Fluent Bit → Elasticsearch

```ini
[OUTPUT]
    Name            es
    Host            eco2-logs-es-http.logging
    Port            9200
    Logstash_Format On
    Logstash_Prefix logs
    Replace_Dots    Off  # ECS dot notation
```

### Index Template (ECS)

```json
{
  "mappings": {
    "subobjects": false,
    "properties": {
      "trace.id": { "type": "keyword" },
      "span.id": { "type": "keyword" },
      "service.name": { "type": "keyword" }
    }
  }
}
```

---

## 실측 데이터 (2025-12-19)

| 메트릭 | 값 |
|--------|-----|
| Jaeger 서비스 수 | 17개 |
| trace.id 커버리지 | 7.16% (125K / 1.7M) |
| Fluent Bit 노드 | 16개 (DaemonSet) |
| ES 인덱스 | logs-YYYY.MM.DD |
| 일일 로그 볼륨 | ~50MB |

---

## 관련 문서

- [네트워크 토폴로지](./network-topology.md)
- [Observability 블로그 시리즈](../blogs/observability/)
- [Log-Trace Correlation](../blogs/observability/12-log-trace-correlation.md)
