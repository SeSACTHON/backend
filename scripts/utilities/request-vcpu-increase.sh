#!/bin/bash
# AWS vCPU 한도 증가 요청 스크립트
# 13-Node 아키텍처를 위해 16 vCPU → 32 vCPU로 증가

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 AWS vCPU 한도 증가 요청"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# AWS Region 설정
AWS_REGION=${AWS_REGION:-ap-northeast-2}

echo "📋 요청 정보:"
echo "   Service: EC2"
echo "   Quota: Running On-Demand Standard instances"
echo "   Current: 16 vCPU"
echo "   Requested: 32 vCPU"
echo "   Region: $AWS_REGION"
echo ""

# 현재 한도 확인
echo "🔍 현재 vCPU 한도 확인 중..."
CURRENT_QUOTA=$(aws service-quotas get-service-quota \
    --service-code ec2 \
    --quota-code L-1216C47A \
    --region "$AWS_REGION" \
    --query 'Quota.Value' \
    --output text 2>/dev/null || echo "unknown")

if [ "$CURRENT_QUOTA" != "unknown" ]; then
    echo "   현재 한도: $CURRENT_QUOTA vCPU"
    echo ""
    
    # 이미 충분한 경우 확인
    if [ "$(echo "$CURRENT_QUOTA >= 32" | bc -l 2>/dev/null || echo "0")" -eq 1 ]; then
        echo "✅ 현재 vCPU 한도가 이미 32 이상입니다!"
        echo "   추가 요청이 필요하지 않습니다."
        echo ""
        exit 0
    fi
else
    echo "   ⚠️  현재 한도를 확인할 수 없습니다."
    echo ""
fi

# 진행 중인 요청 확인
echo "🔍 진행 중인 요청 확인 중..."
PENDING_REQUESTS=$(aws service-quotas list-requested-service-quota-change-requests-by-status \
    --status PENDING \
    --region "$AWS_REGION" \
    --query 'RequestedQuotas[?QuotaCode==`L-1216C47A`].[Id,DesiredValue,Status]' \
    --output text 2>/dev/null || echo "")

if [ -n "$PENDING_REQUESTS" ]; then
    echo "⚠️  이미 진행 중인 요청이 있습니다:"
    echo "$PENDING_REQUESTS" | while read request_id desired_value status; do
        echo "   - Request ID: $request_id"
        echo "   - Desired Value: $desired_value"
        echo "   - Status: $status"
    done
    echo ""
    echo "기존 요청이 처리될 때까지 대기하세요."
    echo ""
    exit 0
fi

echo "   진행 중인 요청 없음"
echo ""

# 한도 증가 요청
echo "📤 vCPU 한도 증가 요청 중..."
echo ""

REQUEST_ID=$(aws service-quotas request-service-quota-increase \
    --service-code ec2 \
    --quota-code L-1216C47A \
    --desired-value 32 \
    --region "$AWS_REGION" \
    --query 'RequestedQuota.Id' \
    --output text 2>/dev/null)

if [ -n "$REQUEST_ID" ]; then
    echo "✅ vCPU 한도 증가 요청 완료!"
    echo ""
    echo "📋 요청 정보:"
    echo "   Request ID: $REQUEST_ID"
    echo "   Desired Value: 32 vCPU"
    echo "   Region: $AWS_REGION"
    echo ""
    echo "📧 AWS가 요청을 검토 중입니다."
    echo "   - 일반적으로 15분-2시간 소요"
    echo "   - 긴급한 경우 1-2시간 내 승인"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 요청 상태 확인 명령어:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "# 특정 요청 확인"
    echo "aws service-quotas get-requested-service-quota-change \\"
    echo "    --request-id $REQUEST_ID \\"
    echo "    --region $AWS_REGION"
    echo ""
    echo "# 모든 대기 중인 요청 확인"
    echo "aws service-quotas list-requested-service-quota-change-requests-by-status \\"
    echo "    --status PENDING \\"
    echo "    --region $AWS_REGION"
    echo ""
    echo "# 현재 한도 재확인"
    echo "aws service-quotas get-service-quota \\"
    echo "    --service-code ec2 \\"
    echo "    --quota-code L-1216C47A \\"
    echo "    --region $AWS_REGION \\"
    echo "    --query 'Quota.Value'"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 승인 후 실행 명령어:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "cd /Users/mango/workspace/SeSACTHON/backend"
    echo "export GITHUB_TOKEN=\"<your-token>\""
    echo "export GITHUB_USERNAME=\"<your-username>\""
    echo "export VERSION=\"v0.6.0\""
    echo "./scripts/cluster/auto-rebuild.sh"
    echo ""
else
    echo "❌ vCPU 한도 증가 요청 실패!"
    echo ""
    echo "💡 해결 방법:"
    echo "   1. AWS CLI 권한 확인 (service-quotas:RequestServiceQuotaIncrease)"
    echo "   2. AWS Console에서 수동 요청:"
    echo "      https://console.aws.amazon.com/servicequotas/home"
    echo ""
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

