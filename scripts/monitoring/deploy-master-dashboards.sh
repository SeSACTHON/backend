#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 마스터 노드 모니터링 대시보드 배포 스크립트
# 용도: Grafana 대시보드 ConfigMap 배포/삭제/상태확인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARDS_DIR="$SCRIPT_DIR/../../workloads/monitoring/dashboards"
NAMESPACE="prometheus"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  apply     대시보드 ConfigMap 배포 (기본값)"
    echo "  delete    대시보드 ConfigMap 삭제"
    echo "  status    대시보드 ConfigMap 상태 확인"
    echo "  restart   Grafana Pod 재시작 (대시보드 새로고침)"
    echo "  help      도움말 표시"
    echo ""
    echo "Examples:"
    echo "  $0 apply    # 대시보드 배포"
    echo "  $0 status   # 상태 확인"
    echo "  $0 restart  # Grafana 재시작"
}

check_prerequisites() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl이 설치되어 있지 않습니다.${NC}"
        exit 1
    fi

    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ Kubernetes 클러스터에 연결할 수 없습니다.${NC}"
        exit 1
    fi
}

apply_dashboards() {
    print_header "📊 마스터 노드 대시보드 배포"

    echo -e "${YELLOW}📁 대시보드 디렉토리: $DASHBOARDS_DIR${NC}"
    echo ""

    # 개별 파일 적용 (의도별로 출력)
    echo -e "${GREEN}1️⃣  리소스 모니터링 대시보드 배포...${NC}"
    kubectl apply -f "$DASHBOARDS_DIR/master-node-resources.yaml"

    echo -e "${GREEN}2️⃣  Control Plane 대시보드 배포...${NC}"
    kubectl apply -f "$DASHBOARDS_DIR/master-control-plane.yaml"

    echo -e "${GREEN}3️⃣  다운그레이드 결정 대시보드 배포...${NC}"
    kubectl apply -f "$DASHBOARDS_DIR/master-downgrade-decision.yaml"

    echo ""
    echo -e "${GREEN}✅ 모든 대시보드가 성공적으로 배포되었습니다!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Grafana에서 확인:${NC}"
    echo "   - 🖥️ Master Node - Resources"
    echo "   - ⚙️ Master Node - Control Plane"
    echo "   - 📉 Master Node - Downgrade Decision"
}

delete_dashboards() {
    print_header "🗑️  마스터 노드 대시보드 삭제"

    kubectl delete configmap \
        grafana-dashboard-master-resources \
        grafana-dashboard-master-control-plane \
        grafana-dashboard-master-downgrade \
        -n "$NAMESPACE" --ignore-not-found

    echo -e "${GREEN}✅ 대시보드가 삭제되었습니다.${NC}"
}

show_status() {
    print_header "📋 대시보드 ConfigMap 상태"

    echo -e "${YELLOW}Namespace: $NAMESPACE${NC}"
    echo ""

    kubectl get configmap -n "$NAMESPACE" \
        -l grafana_dashboard=1 \
        -o custom-columns=\
'NAME:.metadata.name,CREATED:.metadata.creationTimestamp,LABELS:.metadata.labels.monitoring'

    echo ""
    echo -e "${BLUE}📊 대시보드 목록:${NC}"
    kubectl get configmap -n "$NAMESPACE" \
        -l grafana_dashboard=1 \
        -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
}

restart_grafana() {
    print_header "🔄 Grafana Pod 재시작"

    echo -e "${YELLOW}Grafana Deployment 재시작 중...${NC}"
    kubectl rollout restart deployment -n "$NAMESPACE" -l app.kubernetes.io/name=grafana 2>/dev/null || \
    kubectl rollout restart deployment -n "$NAMESPACE" -l app=grafana 2>/dev/null || \
    echo -e "${YELLOW}⚠️ Grafana Deployment를 찾을 수 없습니다. 수동으로 확인해주세요.${NC}"

    echo ""
    echo -e "${GREEN}✅ Grafana 재시작이 요청되었습니다.${NC}"
    echo -e "${YELLOW}💡 롤아웃 상태 확인: kubectl rollout status deployment -n $NAMESPACE -l app.kubernetes.io/name=grafana${NC}"
}

# Main
check_prerequisites

COMMAND=${1:-apply}

case $COMMAND in
    apply)
        apply_dashboards
        ;;
    delete)
        delete_dashboards
        ;;
    status)
        show_status
        ;;
    restart)
        restart_grafana
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo -e "${RED}❌ 알 수 없는 명령: $COMMAND${NC}"
        usage
        exit 1
        ;;
esac
