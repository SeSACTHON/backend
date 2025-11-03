#!/bin/bash
# Kubernetes 클러스터 상태 점검 스크립트 (원격)
# Master 노드에 SSH로 접속하여 클러스터 상태 확인
# 로컬 환경을 깨끗하게 유지하기 위해 원격 점검

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Kubernetes 클러스터 상태 점검 (원격)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Terraform에서 Master IP 가져오기
cd "$TERRAFORM_DIR"
MASTER_IP=$(terraform output -raw master_public_ip 2>/dev/null || echo "")

if [ -z "$MASTER_IP" ]; then
    echo "❌ Master IP를 가져올 수 없습니다."
    echo "   Terraform output을 확인하세요: terraform output master_public_ip"
    exit 1
fi

# SSH 키 경로 확인
SSH_KEY="${HOME}/.ssh/sesacthon"
if [ ! -f "$SSH_KEY" ]; then
    SSH_KEY="${HOME}/.ssh/id_rsa"
    if [ ! -f "$SSH_KEY" ]; then
        echo "❌ SSH 키를 찾을 수 없습니다."
        echo "   $HOME/.ssh/sesacthon 또는 $HOME/.ssh/id_rsa 필요"
        exit 1
    fi
fi

echo "📋 Master 노드: $MASTER_IP"
echo "🔑 SSH 키: $SSH_KEY"
echo ""
echo "🔌 Master 노드에 연결 중..."
echo ""

# Master 노드에서 전체 점검 실행
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@$MASTER_IP 'bash -s' << 'REMOTE_CHECK'
set -e

ERRORS=0
WARNINGS=0

# kubectl 연결 확인
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ Kubernetes 클러스터에 연결할 수 없습니다."
    exit 1
fi

# 1. 노드 상태 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣ 노드 상태"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

NODES=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
READY_NODES=$(kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready " || echo "0")
EXPECTED_NODES=4  # Master, Worker-1, Worker-2, Storage

echo "📊 노드 상태: $READY_NODES / $NODES Ready (예상: $EXPECTED_NODES)"
kubectl get nodes -o wide
echo ""

if [ "$NODES" -ne "$EXPECTED_NODES" ]; then
    echo "❌ 노드 개수 불일치 (예상: $EXPECTED_NODES, 실제: $NODES)"
    ((ERRORS++))
elif [ "$READY_NODES" -ne "$EXPECTED_NODES" ]; then
    echo "⚠️  일부 노드가 Ready 상태가 아닙니다"
    ((WARNINGS++))
else
    echo "✅ 모든 노드 Ready"
fi

# 노드 레이블 확인
echo ""
echo "📋 노드 레이블 확인:"
STORAGE_LABEL=$(kubectl get nodes k8s-storage --show-labels --no-headers 2>/dev/null | grep -o "workload=storage" || echo "")
if [ -n "$STORAGE_LABEL" ]; then
    echo "  ✅ k8s-storage: workload=storage"
else
    echo "  ❌ k8s-storage: workload=storage 레이블 없음"
    ((ERRORS++))
fi
echo ""

# 2. 시스템 Pod 상태
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣ 시스템 Pod 상태 (kube-system)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

NOT_READY_PODS=$(kubectl get pods -n kube-system --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')

if [ "$NOT_READY_PODS" -gt 0 ]; then
    echo "⚠️  비정상 Pod: $NOT_READY_PODS개"
    kubectl get pods -n kube-system --field-selector=status.phase!=Running
    ((WARNINGS++))
else
    echo "✅ 모든 시스템 Pod 실행 중"
fi

# EBS CSI Driver 확인
EBS_CSI=$(kubectl get pods -n kube-system | grep ebs-csi | grep -c "Running" || echo "0")
if [ "$EBS_CSI" -ge 2 ]; then
    echo "✅ EBS CSI Driver: $EBS_CSI개 Pod 실행 중"
else
    echo "❌ EBS CSI Driver: Pod 부족 또는 미실행"
    ((ERRORS++))
fi
echo ""

# 3. StorageClass 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣ StorageClass 확인"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

GP3_SC=$(kubectl get storageclass gp3 2>/dev/null || echo "")
if [ -n "$GP3_SC" ]; then
    echo "✅ gp3 StorageClass 존재"
    kubectl get storageclass gp3
else
    echo "❌ gp3 StorageClass 없음"
    ((ERRORS++))
fi
echo ""

# 4. Helm Release 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣ Helm Release 상태"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

       EXPECTED_RELEASES=(
           "kube-prometheus-stack:monitoring"
           "rabbitmq:messaging"
           "argocd:argocd"
           "aws-load-balancer-controller:kube-system"
       )

for release_info in "${EXPECTED_RELEASES[@]}"; do
    IFS=':' read -r release_name namespace <<< "$release_info"
    RELEASE_STATUS=$(helm status "$release_name" -n "$namespace" 2>/dev/null | grep "STATUS:" | awk '{print $2}' || echo "not_found")
    
    if [ "$RELEASE_STATUS" == "deployed" ]; then
        echo "  ✅ $release_name ($namespace): deployed"
    elif [ "$RELEASE_STATUS" == "not_found" ]; then
        echo "  ❌ $release_name ($namespace): 설치되지 않음"
        ((ERRORS++))
    else
        echo "  ⚠️  $release_name ($namespace): $RELEASE_STATUS"
        ((WARNINGS++))
    fi
done
echo ""

# 5. 애플리케이션 Pod 상태
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣ 애플리케이션 Pod 상태"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

       # RabbitMQ (Operator 관리 - 단일 Pod)
       RABBITMQ_PODS=$(kubectl get pods -n messaging -l rabbitmq.com/cluster=rabbitmq --no-headers 2>/dev/null | grep -c "Running" || echo "0")
       RABBITMQ_EXPECTED=1
       if [ "$RABBITMQ_PODS" -eq "$RABBITMQ_EXPECTED" ]; then
           echo "✅ RabbitMQ: $RABBITMQ_PODS/$RABBITMQ_EXPECTED Pod 실행 중 (Operator 관리)"
       else
           echo "⚠️  RabbitMQ: $RABBITMQ_PODS/$RABBITMQ_EXPECTED Pod (예상: $RABBITMQ_EXPECTED, Operator 관리)"
           kubectl get pods -n messaging -l rabbitmq.com/cluster=rabbitmq 2>/dev/null || kubectl get pods -n messaging
           ((WARNINGS++))
       fi

# Redis
REDIS_PODS=$(kubectl get pods -n default -l app=redis --no-headers 2>/dev/null | grep -c "Running" || echo "0")
if [ "$REDIS_PODS" -ge 1 ]; then
    echo "✅ Redis: $REDIS_PODS Pod 실행 중"
else
    echo "⚠️  Redis: Pod 실행 중 아님"
    kubectl get pods -n default -l app=redis 2>/dev/null || true
    ((WARNINGS++))
fi

# Prometheus
PROM_PODS=$(kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus --no-headers 2>/dev/null | grep -c "Running" || echo "0")
if [ "$PROM_PODS" -ge 1 ]; then
    echo "✅ Prometheus: $PROM_PODS Pod 실행 중"
else
    echo "⚠️  Prometheus: Pod 실행 중 아님"
    ((WARNINGS++))
fi

# ArgoCD
ARGOCD_PODS=$(kubectl get pods -n argocd --no-headers 2>/dev/null | grep -c "Running" || echo "0")
if [ "$ARGOCD_PODS" -ge 1 ]; then
    echo "✅ ArgoCD: $ARGOCD_PODS Pod 실행 중"
else
    echo "⚠️  ArgoCD: Pod 실행 중 아님"
    ((WARNINGS++))
fi
echo ""

# 6. PVC 상태
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6️⃣ PVC 상태"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

BOUND_PVC=$(kubectl get pvc -A --no-headers 2>/dev/null | grep -c "Bound" || echo "0")
PENDING_PVC=$(kubectl get pvc -A --no-headers 2>/dev/null | grep -c "Pending" || echo "0")

if [ "$PENDING_PVC" -gt 0 ]; then
    echo "⚠️  Pending PVC: $PENDING_PVC개"
    kubectl get pvc -A | grep Pending
    ((WARNINGS++))
fi

if [ "$BOUND_PVC" -gt 0 ]; then
    echo "✅ Bound PVC: $BOUND_PVC개"
fi
echo ""

# 7. Service 및 Ingress
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7️⃣ Service 및 Ingress"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# LoadBalancer Service
LB_SVCS=$(kubectl get svc -A -o json 2>/dev/null | jq -r '.items[] | select(.spec.type=="LoadBalancer") | "\(.metadata.namespace)/\(.metadata.name)"' 2>/dev/null || echo "")
if [ -n "$LB_SVCS" ]; then
    echo "📋 LoadBalancer Service:"
    echo "$LB_SVCS" | while read svc; do
        echo "  - $svc"
    done
else
    echo "ℹ️  LoadBalancer Service 없음 (정상 - Ingress 사용)"
fi

# Ingress
INGRESS_COUNT=$(kubectl get ingress -A --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [ "$INGRESS_COUNT" -gt 0 ]; then
    echo "✅ Ingress: $INGRESS_COUNT개"
    kubectl get ingress -A
else
    echo "ℹ️  Ingress 없음 (아직 생성되지 않음)"
fi
echo ""

# 8. etcd 상태
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8️⃣ etcd 상태"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ETCD_HEALTH=$(sudo ETCDCTL_API=3 etcdctl endpoint health --endpoints=https://127.0.0.1:2379 --cacert=/etc/etcd/pki/ca.crt --cert=/etc/etcd/pki/apiserver-etcd-client.crt --key=/etc/etcd/pki/apiserver-etcd-client.key 2>/dev/null || echo "error")
if echo "$ETCD_HEALTH" | grep -q "is healthy"; then
    echo "✅ etcd: healthy"
else
    echo "⚠️  etcd: 상태 확인 불가 또는 비정상"
    ((WARNINGS++))
fi
echo ""

# 9. 요약
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 점검 요약"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" 2>/dev/null | base64 -d || echo "N/A")
ARGOCD_HOSTNAME=$(kubectl get svc argocd-server -n argocd -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "N/A")

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo "✅ 클러스터 상태 양호!"
    echo ""
    echo "📋 주요 정보:"
    echo "  - 노드: $READY_NODES/$NODES Ready"
    echo "  - Helm Release: 모두 deployed"
    echo "  - 시스템 Pod: 정상"
    echo ""
    echo "🔗 접속 정보:"
    echo "  - ArgoCD: https://${ARGOCD_HOSTNAME}:8080"
    echo "    Username: admin"
    echo "    Password: $ARGOCD_PASSWORD"
    echo ""
    exit 0
elif [ "$ERRORS" -eq 0 ]; then
    echo "⚠️  경고 $WARNINGS개 (치명적 오류 없음)"
    echo ""
    echo "💡 권장 사항:"
    echo "   - 위의 경고 항목 확인"
    echo "   - Pod 로그 확인: kubectl logs <pod-name> -n <namespace>"
    exit 0
else
    echo "❌ 오류 $ERRORS개, 경고 $WARNINGS개"
    echo ""
    echo "💡 다음 단계:"
    echo "   1. 오류 항목 확인"
    echo "   2. Pod 이벤트 확인: kubectl describe pod <pod-name> -n <namespace>"
    echo "   3. 로그 확인: kubectl logs <pod-name> -n <namespace>"
    exit 1
fi

REMOTE_CHECK

# SSH 실행 결과 확인
EXIT_CODE=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 원격 점검 완료"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 클러스터 점검이 성공적으로 완료되었습니다."
else
    echo "⚠️  일부 문제가 발견되었습니다. 위의 결과를 확인하세요."
fi

exit $EXIT_CODE
