#!/bin/bash
# Observability 검증 스크립트
# Metrics, Logs, Traces 수집 상태 확인

set -e

echo "=========================================="
echo "Eco² Observability 검증"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check functions
check_pod() {
    local namespace=$1
    local pod_pattern=$2
    local name=$3

    echo -n "Checking $name... "
    if kubectl get pods -n "$namespace" | grep -q "$pod_pattern"; then
        local status=$(kubectl get pods -n "$namespace" | grep "$pod_pattern" | awk '{print $3}' | head -1)
        if [[ "$status" == "Running" ]]; then
            echo -e "${GREEN}✓ Running${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠ $status${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ Not found${NC}"
        return 1
    fi
}

check_service() {
    local namespace=$1
    local service=$2
    local name=$3

    echo -n "Checking $name Service... "
    if kubectl get svc -n "$namespace" "$service" &>/dev/null; then
        echo -e "${GREEN}✓ Exists${NC}"
        return 0
    else
        echo -e "${RED}✗ Not found${NC}"
        return 1
    fi
}

check_endpoint() {
    local namespace=$1
    local deployment=$2
    local endpoint=$3
    local name=$4

    echo -n "Checking $name endpoint... "
    if kubectl exec -n "$namespace" deployment/"$deployment" -- \
        curl -s -f "http://localhost:8000$endpoint" &>/dev/null; then
        echo -e "${GREEN}✓ Accessible${NC}"
        return 0
    else
        echo -e "${RED}✗ Not accessible${NC}"
        return 1
    fi
}

# ==========================================
# 1. Metrics (Prometheus)
# ==========================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Metrics (Prometheus)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_pod "prometheus" "prometheus-server" "Prometheus Server"
check_service "prometheus" "kube-prometheus-stack-prometheus" "Prometheus"

echo ""
echo "Checking Prometheus targets..."
if kubectl get servicemonitor -A &>/dev/null; then
    echo -e "${GREEN}✓ ServiceMonitor CRDs available${NC}"
    kubectl get servicemonitor -A --no-headers | wc -l | xargs echo "  ServiceMonitors:"
else
    echo -e "${YELLOW}⚠ ServiceMonitor CRDs not found${NC}"
fi

echo ""
echo "Checking application metrics endpoints..."
check_endpoint "scan" "scan-api" "/metrics" "scan-api /metrics"
check_endpoint "sse" "sse-gateway" "/metrics" "sse-gateway /metrics"
check_endpoint "event-router" "event-router" "/metrics" "event-router /metrics"

echo ""

# ==========================================
# 2. Logs (EFK)
# ==========================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Logs (EFK Stack)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_pod "logging" "elasticsearch" "Elasticsearch"
check_pod "logging" "kibana" "Kibana"
check_pod "logging" "fluent-bit" "Fluent Bit"

check_service "logging" "elasticsearch" "Elasticsearch"
check_service "logging" "kibana" "Kibana"

echo ""
echo "Checking application logs format..."
if kubectl logs -n scan deployment/scan-api --tail=1 2>/dev/null | jq -e '.ecs.version' &>/dev/null; then
    echo -e "${GREEN}✓ ECS JSON format detected${NC}"
else
    echo -e "${YELLOW}⚠ ECS JSON format not detected (may be plain text)${NC}"
fi

echo ""
echo "Checking trace.id in logs..."
if kubectl logs -n scan deployment/scan-api --tail=10 2>/dev/null | jq -e 'select(.trace.id != null)' &>/dev/null; then
    echo -e "${GREEN}✓ trace.id found in logs${NC}"
else
    echo -e "${YELLOW}⚠ trace.id not found (OpenTelemetry may not be configured)${NC}"
fi

echo ""

# ==========================================
# 3. Traces (Jaeger)
# ==========================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Traces (Jaeger)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_pod "istio-system" "jaeger-collector" "Jaeger Collector"
check_pod "istio-system" "jaeger-query" "Jaeger Query"

check_service "istio-system" "jaeger-collector" "Jaeger Collector"
check_service "istio-system" "jaeger-query" "Jaeger Query"

echo ""
echo "Checking OpenTelemetry configuration..."
if kubectl logs -n scan deployment/scan-api 2>/dev/null | grep -q "OpenTelemetry tracing configured"; then
    echo -e "${GREEN}✓ OpenTelemetry configured in scan-api${NC}"
else
    echo -e "${YELLOW}⚠ OpenTelemetry not configured in scan-api${NC}"
fi

echo ""
echo "Checking Jaeger Collector connectivity..."
if kubectl exec -n scan deployment/scan-api -- \
    timeout 2 bash -c "echo > /dev/tcp/jaeger-collector.istio-system.svc.cluster.local/4317" 2>/dev/null; then
    echo -e "${GREEN}✓ Can connect to Jaeger Collector${NC}"
else
    echo -e "${RED}✗ Cannot connect to Jaeger Collector${NC}"
fi

echo ""

# ==========================================
# 4. Integration Check
# ==========================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Integration Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "Checking Prometheus ServiceMonitor for scan-api..."
if kubectl get servicemonitor -n scan scan-api &>/dev/null; then
    echo -e "${GREEN}✓ ServiceMonitor exists${NC}"
else
    echo -e "${YELLOW}⚠ ServiceMonitor not found${NC}"
fi

echo ""
echo "Checking Fluent Bit configuration..."
if kubectl get configmap -n logging fluent-bit-config &>/dev/null; then
    echo -e "${GREEN}✓ Fluent Bit ConfigMap exists${NC}"
else
    echo -e "${YELLOW}⚠ Fluent Bit ConfigMap not found${NC}"
fi

echo ""

# ==========================================
# Summary
# ==========================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Access URLs:"
echo "  • Grafana:    https://grafana.dev.growbin.app"
echo "  • Kibana:     https://kibana.dev.growbin.app"
echo "  • Jaeger UI:  https://jaeger.dev.growbin.app"
echo ""
echo "Port Forward (local access):"
echo "  • Prometheus: kubectl port-forward -n prometheus svc/kube-prometheus-stack-prometheus 9090:9090"
echo "  • Kibana:     kubectl port-forward -n logging svc/kibana 5601:5601"
echo "  • Jaeger:     kubectl port-forward -n istio-system svc/jaeger-query 16686:16686"
echo ""
