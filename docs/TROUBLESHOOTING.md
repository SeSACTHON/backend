# Troubleshooting Guide - 이코에코(Eco²)

> 14-Node Microservices Architecture + Worker Local SQLite WAL 구축 과정에서 발생한 문제 및 해결 방안
>
> **업데이트 (2025-11-15)**  
> 본 문서에는 `k8s/atlantis/atlantis-deployment.yaml` 등 레거시 경로가 다수 언급됩니다.  
> 현재 Atlantis는 `charts/platform/atlantis` Helm Chart와 `argocd/apps/70-gitops-tools.yaml`을 통해 배포되므로, 동일 문제 발생 시 최신 절차(`docs/architecture/gitops/ATLANTIS_TERRAFORM_FLOW.md`)도 함께 참고하세요.

## 📋 목차

- [1. Terraform 관련 문제](#1-terraform-관련-문제)
- [2. IAM Policy 중복 문제](#2-iam-policy-중복-문제)
- [3. AWS 한도 관련 문제](#3-aws-한도-관련-문제)
- [4. 스크립트 실행 문제](#4-스크립트-실행-문제)
- [5. GitHub CLI 인증 문제](#5-github-cli-인증-문제)
- [6. CloudFront 관련 문제](#6-cloudfront-관련-문제)
- [7. VPC 삭제 지연 문제](#7-vpc-삭제-지연-문제)
- [8. ArgoCD 리디렉션 루프 문제](#8-argocd-리디렉션-루프-문제)
- [9. Prometheus 메모리 부족 문제](#9-prometheus-메모리-부족-문제)
- [10. Atlantis Pod CrashLoopBackOff 문제](#10-atlantis-pod-crashloopbackoff-문제)
- [11. Atlantis Pod에서 kubectl을 찾을 수 없는 문제](#11-atlantis-pod에서-kubectl을-찾을-수-없는-문제)
- [12. Atlantis Deployment 파일을 찾을 수 없는 문제](#12-atlantis-deployment-파일을-찾을-수-없는-문제)
- [13. Atlantis 실행 파일을 찾을 수 없는 문제](#13-atlantis-실행-파일을-찾을-수-없는-문제)
- [14. Atlantis ConfigMap YAML 파싱 에러](#14-atlantis-configmap-yaml-파싱-에러)
- [15. 베스트 프랙티스](#15-베스트-프랙티스)
- [16. 참고 문서](#16-참고-문서)
- [17. 지원](#17-지원)
- [18. GitOps 배포 문제 (2025-11-16 추가)](#18-gitops-배포-문제-2025-11-16-추가)
- [19. 베스트 프랙티스 (2025-11-16 업데이트)](#19-베스트-프랙티스-2025-11-16-업데이트)
- [20. Legacy Troubleshooting Archive (docs/troubleshooting/*)](#20-legacy-troubleshooting-archive-docstroubleshooting)

---

## 1. Terraform 관련 문제

### 1.1. Duplicate Resource Configuration

#### 문제
```
Error: Duplicate resource "aws_iam_policy" configuration
Error: Duplicate resource "aws_iam_role_policy_attachment" configuration
```

**원인**: 동일한 리소스가 여러 파일에 선언됨
- `terraform/iam.tf`와 `terraform/alb-controller-iam.tf`에 `aws_iam_policy.alb_controller` 중복

#### 해결
```bash
# iam.tf에서 중복 선언 제거
# alb-controller-iam.tf에만 유지
```

**적용 파일**:
- `terraform/iam.tf` (중복 제거)
- `terraform/alb-controller-iam.tf` (유지)

**커밋**: `feat: Remove duplicate IAM policy declarations`

---

### 1.2. Provider Configuration Not Present

#### 문제
```
Error: Provider configuration not present
To work with aws_acm_certificate.cdn its original provider configuration at 
provider["registry.terraform.io/hashicorp/aws"].us_east_1 is required
```

**원인**: CloudFront ACM 인증서는 `us-east-1` 리전에 있어야 하지만 provider 설정 누락

#### 해결
`terraform/main.tf`에 `us-east-1` provider 추가:

```hcl
# CloudFront requires ACM certificate in us-east-1
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
  
  default_tags {
    tags = {
      Project     = "SeSACTHON"
      ManagedBy   = "Terraform"
      Environment = var.environment
      Team        = "Backend"
    }
  }
}
```

**커밋**: `fix: Add us-east-1 provider for CloudFront ACM certificates`

---

### 1.3. Reference to Undeclared Resource

#### 문제
```
Error: Reference to undeclared resource
A managed resource "aws_iam_role" "ec2_ssm_role" has not been declared
```

**원인**: 잘못된 IAM role 참조
- `alb-controller-iam.tf`와 `s3.tf`에서 `aws_iam_role.ec2_ssm_role` 참조
- 실제 리소스 이름은 `aws_iam_role.k8s_node`

#### 해결
```hcl
# Before
role = aws_iam_role.ec2_ssm_role.name

# After
role = aws_iam_role.k8s_node.name
```

**적용 파일**:
- `terraform/alb-controller-iam.tf`
- `terraform/s3.tf`

**커밋**: `fix: Correct IAM role reference from ec2_ssm_role to k8s_node`

---

### 1.4. Missing Resource Instance Key

#### 문제
```
Error: Missing resource instance key
Because data.aws_route53_zone.main has "count" set, its attributes must be 
accessed on specific instances.
```

**원인**: `count` 기반 리소스를 인덱스 없이 참조

#### 해결
```hcl
# Before
zone_id = data.aws_route53_zone.main.zone_id

# After
zone_id = data.aws_route53_zone.main[0].zone_id
```

**적용 파일**: `terraform/cloudfront.tf`

**커밋**: `fix: Add index to count-based Route53 zone reference`

---

### 1.5. Invalid Attribute Combination (S3 Lifecycle)

#### 문제
```
Warning: Invalid Attribute Combination
No attribute specified when one (and only one) of [rule[0].filter,rule[0].prefix] is required
```

**원인**: S3 lifecycle rule에 `filter` 또는 `prefix` 필수

#### 해결
```hcl
resource "aws_s3_bucket_lifecycle_configuration" "images" {
  bucket = aws_s3_bucket.images.id

  rule {
    id     = "cleanup-old-images"
    status = "Enabled"

    filter {
      prefix = ""  # 모든 객체에 적용
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = 90
    }
  }
}
```

**적용 파일**: `terraform/s3.tf`

**커밋**: `fix: Add filter block to S3 lifecycle configuration`

---

### 1.6. No Configuration Files

#### 문제
```
Error: No configuration files
Apply requires configuration to be present.
```

**원인**: `auto-rebuild.sh`의 Step 2에서 terraform 디렉토리로 이동하지 않음

#### 해결
```bash
# Step 2 시작 시 명시적으로 디렉토리 이동
cd "$PROJECT_ROOT/terraform"

echo "🔧 Terraform 초기화 (재확인)..."
terraform init -migrate-state -upgrade
```

**적용 파일**: `scripts/cluster/auto-rebuild.sh`

**커밋**: `fix: Add missing cd to terraform directory in auto-rebuild.sh Step 2`

---

## 2. IAM Policy 중복 문제

### 2.1. EntityAlreadyExists - IAM Policy

#### 문제
```
Error: creating IAM Policy (prod-alb-controller-policy): EntityAlreadyExists
Error: creating IAM Policy (prod-s3-presigned-url-policy): EntityAlreadyExists
```

**원인**: 이전 배포의 IAM Policy가 Terraform state에 없지만 AWS에 남아있음

#### 해결
`scripts/maintenance/destroy-with-cleanup.sh`에 IAM Policy 강제 정리 추가:

```bash
# IAM Policy 강제 정리
echo "🔐 IAM Policy 강제 정리..."
POLICY_ARNS=$(aws iam list-policies --scope Local \
    --query "Policies[?contains(PolicyName, 'alb-controller') || contains(PolicyName, 'ecoeco') || contains(PolicyName, 's3-presigned-url')].Arn" \
    --output text)

if [ -n "$POLICY_ARNS" ]; then
    for policy_arn in $POLICY_ARNS; do
        # Role에서 detach
        ATTACHED_ROLES=$(aws iam list-entities-for-policy \
            --policy-arn "$policy_arn" \
            --entity-filter Role \
            --query 'PolicyRoles[*].RoleName' \
            --output text)
        
        for role in $ATTACHED_ROLES; do
            aws iam detach-role-policy --role-name "$role" --policy-arn "$policy_arn"
        done
        
        # Policy 삭제
        aws iam delete-policy --policy-arn "$policy_arn"
    done
fi
```

**커밋**: `feat: Enhance destroy-with-cleanup.sh with comprehensive AWS resource cleanup`

---

### 2.2. auto-rebuild.sh 통합

#### 문제
`auto-rebuild.sh`가 복잡한 정리 로직을 직접 구현하여 유지보수 어려움

#### 해결
`destroy-with-cleanup.sh`를 호출하도록 리팩토링:

```bash
# Step 1: Terraform Destroy (destroy-with-cleanup.sh 호출)
if [ -f "$PROJECT_ROOT/scripts/maintenance/destroy-with-cleanup.sh" ]; then
    echo "🔧 destroy-with-cleanup.sh 실행 중..."
    export AUTO_MODE=true
    bash "$PROJECT_ROOT/scripts/maintenance/destroy-with-cleanup.sh"
else
    # Fallback: 간단한 destroy
    terraform destroy -auto-approve
fi
```

**효과**:
- 200+ 줄 코드 제거
- 단일 정리 로직으로 통합
- IAM, S3, CloudFront, Route53, ACM 모두 자동 정리

**커밋**: `feat: Integrate destroy-with-cleanup.sh into auto-rebuild.sh + S3 Policy cleanup`

---

## 3. AWS 한도 관련 문제

### 3.1. VcpuLimitExceeded

#### 문제
```
Error: creating EC2 Instance: VcpuLimitExceeded
You have requested more vCPU capacity than your current vCPU limit of 16 allows
```

**원인**: 14-Node 아키텍처 필요 vCPU (26) > 계정 한도 (16)

**vCPU 계산**:
| 노드 타입 | 개수 | 인스턴스 | vCPU/노드 | 총 vCPU |
|----------|------|---------|-----------|---------|
| Master | 1 | t3a.large | 2 | 2 |
| API | 6 | t3a.medium | 2 | 12 |
| Worker | 2 | t3a.large | 2 | 4 |
| Infrastructure | 4 | t3a.medium | 2 | 8 |
| **합계** | **13** | | | **26** |

#### 해결 방법 1: vCPU 한도 증가 요청 (권장)

**자동 스크립트**:
```bash
./scripts/utilities/request-vcpu-increase.sh
```

**수동 요청**:
```bash
aws service-quotas request-service-quota-increase \
    --service-code ec2 \
    --quota-code L-1216C47A \
    --desired-value 32 \
    --region ap-northeast-2
```

**AWS Console**: Service Quotas → EC2 → "Running On-Demand Standard instances"

**승인 시간**: 15분-2시간 (일반적)

**한도 확인**:
```bash
aws service-quotas get-service-quota \
    --service-code ec2 \
    --quota-code L-1216C47A \
    --region ap-northeast-2 \
    --query 'Quota.Value'
```

#### 해결 방법 2: 멀티 리전 배포 (권장)

✅ **성능 유지** - 한도 증가 전까지 임시 운영

**전략**: Stateless 서비스를 도쿄 리전(ap-northeast-1)으로 분산

**필수 API 현황 (7개)**:
1. auth - 인증/인가
2. my - 마이페이지 (userinfo)
3. info - 재활용 정보 (recycle_info)
4. location - 위치/지도
5. character - 캐릭터/미션 (신규 추가 필요)
6. scan - 폐기물 스캔/분석 (waste)
7. chat - 챗봇 (chat_llm)

**서울 리전 (ap-northeast-2) - 14 vCPU**:
```
Master        (t3.large)  = 2 vCPU  ← Kubernetes 컨트롤 플레인
API-Auth      (t3.micro)  = 2 vCPU  ← 인증 (지연 민감)
API-My        (t3.micro)  = 2 vCPU  ← 마이페이지 (DB 직접 접근)
API-Info      (t3.micro)  = 2 vCPU  ← 재활용 정보 (DB 직접 접근)
PostgreSQL    (t3.medium) = 2 vCPU  ← Stateful DB
Redis         (t3.small)  = 2 vCPU  ← 캐시/세션
RabbitMQ      (t3.small)  = 2 vCPU  ← 메시지 큐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
합계:                     14 vCPU ✅ (여유 2 vCPU)
```

**도쿄 리전 (ap-northeast-1) - 14 vCPU**:
```
API-Location  (t3.micro)  = 2 vCPU  ← 위치 (외부 API 호출)
API-Character (t3.micro)  = 2 vCPU  ← 캐릭터 (사용 빈도 낮음, 신규)
API-Scan      (t3.small)  = 2 vCPU  ← 스캔 (AI Worker 연계)
API-Chat      (t3.small)  = 2 vCPU  ← 챗봇 (외부 LLM 호출)
Worker-Storage(t3.small)  = 2 vCPU  ← S3 업로드 (비동기)
Worker-AI     (t3.small)  = 2 vCPU  ← AI 처리 (비동기)
Monitoring    (t3.medium) = 2 vCPU  ← Prometheus/Grafana
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
합계:                     14 vCPU ✅
```

**설정 방법**:

1. **Terraform 모듈 업데이트** (`terraform/main.tf`):
```hcl
# 이름 변경 및 신규 추가
module "api_my" { ... }          # userinfo → my
module "api_info" { ... }        # recycle_info → info  
module "api_scan" { ... }        # waste → scan
module "api_chat" { ... }        # chat_llm → chat
module "api_character" { ... }   # 신규 추가 (t3.micro)

# 도쿄 리전 프로바이더 추가
provider "aws" {
  alias  = "tokyo"
  region = "ap-northeast-1"
}
```

2. **VPC Peering 자동 설정**:
   - 서울 ↔ 도쿄 리전 간 Private 통신
   - RabbitMQ, PostgreSQL 접근 가능
   - 데이터 전송 비용: ~$0.09/GB (예상 $0.45/월)

3. **Kubernetes 크로스 리전 설정**:
   - 도쿄 노드를 서울 Master에 조인
   - NodeSelector로 리전별 Pod 배치
   - 지연시간: 5-10ms (허용 가능)

**재배치 계획** (한도 증가 후):
```bash
# 1. 도쿄 리소스를 서울로 마이그레이션
./scripts/utilities/migrate-tokyo-to-seoul.sh

# 2. Terraform으로 자동 재배치
terraform apply -var="enable_multi_region=false"
```

**장점**:
- ✅ 성능 저하 없음
- ✅ 필수 API 7개 모두 사용 가능
- ✅ 한도 증가 후 쉬운 재배치
- ✅ API Character 추가 가능

**단점**:
- ⚠️ 약간의 추가 비용 (~$0.45/월)
- ⚠️ 네트워크 설정 복잡도 증가
- ⚠️ 리전 간 지연 5-10ms

**커밋**: `feat: Add multi-region deployment strategy for 14-node architecture`

---

#### 해결 방법 3: 인스턴스 타입 다운그레이드 (비권장)

⚠️ **성능 저하 심각** - 개발/테스트용으로만

`terraform.tfvars` 생성:
```hcl
master_instance_type = "t3.small"   # 2 vCPU (기존: medium)
api_instance_type = "t3.nano"       # 0.5 vCPU (기존: micro)
worker_instance_type = "t3.micro"   # 2 vCPU (기존: small)
infra_instance_type = "t3.nano"     # 0.5 vCPU (기존: micro/small)
```

**총 vCPU**: ~12 (한도 내)

❌ **문제점**:
- PostgreSQL, RabbitMQ 성능 저하
- API 응답 시간 증가
- Worker 처리 속도 감소

---

### 3.2. ResourceAlreadyExistsException

#### 문제
```
Error: Only one open service quota increase request is allowed per quota.
```

**원인**: 이미 진행 중인 한도 증가 요청이 있음

#### 확인
```bash
aws service-quotas list-requested-service-quota-change-history-by-quota \
    --service-code ec2 \
    --quota-code L-1216C47A \
    --region ap-northeast-2 \
    --query 'RequestedQuotas[?Status==`PENDING` || Status==`CASE_OPENED`]'
```

**Status**:
- `CASE_OPENED`: AWS가 검토 중 (좋은 신호!)
- `PENDING`: 대기 중
- `APPROVED`: 승인 완료
- `DENIED`: 거절 (드물음)

#### 해결
기존 요청이 처리될 때까지 대기 (5-10분마다 한도 확인)

---

## 4. 스크립트 실행 문제

### 4.1. InvalidKeyPair.Duplicate

#### 문제
```
Error: importing EC2 Key Pair (k8s-cluster-key): InvalidKeyPair.Duplicate
```

**원인**: 이전 Key Pair가 삭제되지 않음

#### 해결
`destroy-with-cleanup.sh`에 Key Pair 정리 추가:

```bash
KEY_NAME="k8s-cluster-key"
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    aws ec2 delete-key-pair --key-name "$KEY_NAME" --region "$AWS_REGION"
fi
```

---

### 4.2. BucketAlreadyOwnedByYou

#### 문제
```
Error: creating S3 Bucket (prod-sesacthon-images): BucketAlreadyOwnedByYou
```

**원인**: S3 버킷이 삭제되지 않고 남아있음

#### 해결
`destroy-with-cleanup.sh`에 S3 Bucket 정리 추가:

```bash
BUCKETS=$(aws s3api list-buckets \
    --query "Buckets[?starts_with(Name, 'prod-sesacthon')].Name" \
    --output text)

for bucket in $BUCKETS; do
    # 버킷 내용물 삭제
    aws s3 rm "s3://$bucket" --recursive
    # 버킷 삭제
    aws s3api delete-bucket --bucket "$bucket" --region "$AWS_REGION"
done
```

---

## 5. GitHub CLI 인증 문제

### 5.1. Missing Required Scope

#### 문제
```
error validating token: missing required scope 'read:org'
```

**원인**: GitHub Personal Access Token에 필요한 scope 누락

#### 해결 방법 1: 대화형 로그인 (권장)

```bash
gh auth login
# GitHub.com 선택
# HTTPS 선택
# Login with a web browser 선택
# 브라우저에서 코드 입력
```

#### 해결 방법 2: 새 PAT 생성

1. https://github.com/settings/tokens 접속
2. "Generate new token (classic)" 클릭
3. 필요한 scopes 선택:
   - ✅ `repo` (전체)
   - ✅ `read:org`
   - ✅ `write:packages`
4. 토큰 생성 후:
```bash
echo "<your-token>" | gh auth login --with-token
```

#### 해결 방법 3: GitHub Web UI (수동)

1. Repository → Settings → Secrets and variables → Actions
2. Secret 등록:
   - `GITHUB_USERNAME`: `mangowhoiscloud`
3. Variable 등록:
   - `VERSION`: `v0.6.0`

⚠️ **주의**: `GITHUB_TOKEN`은 GitHub Actions에서 자동으로 제공되므로 등록 불필요

---

## 6. CloudFront 관련 문제

### 6.1. CloudFront 생성 시간

#### 현상
```
aws_cloudfront_distribution.images: Still creating... [6m0s elapsed]
```

**원인**: CloudFront distribution 생성은 전세계 edge location에 배포되므로 시간 소요

**정상 범위**: 5-15분

**확인**:
```bash
aws cloudfront get-distribution --id <distribution-id> \
    --query 'Distribution.Status'
```

**Status**:
- `InProgress`: 배포 중 (정상)
- `Deployed`: 배포 완료

---

### 6.2. CloudFront 삭제 필요성

#### 문제
CloudFront가 남아있으면:
- S3 버킷 삭제 불가
- 비용 지속 발생 ($0.085/GB + 요청 비용)
- Route53 레코드 충돌

#### 해결
`destroy-with-cleanup.sh`에 CloudFront 정리 추가:

```bash
# 1. Distribution disable
CONFIG=$(aws cloudfront get-distribution-config --id "$dist_id" --output json)
ETAG=$(echo "$CONFIG" | jq -r '.ETag')
NEW_CONFIG=$(echo "$CONFIG" | jq '.DistributionConfig | .Enabled = false')

aws cloudfront update-distribution \
    --id "$dist_id" \
    --if-match "$ETAG" \
    --distribution-config "$NEW_CONFIG"

# 2. Disabled 상태 대기 (2분)
sleep 120

# 3. Distribution 삭제
FINAL_CONFIG=$(aws cloudfront get-distribution-config --id "$dist_id" --output json)
FINAL_ETAG=$(echo "$FINAL_CONFIG" | jq -r '.ETag')

aws cloudfront delete-distribution --id "$dist_id" --if-match "$FINAL_ETAG"
```

**소요 시간**: 5-10분

---

### 6.3. CloudFront 검색 로직 부족으로 인한 ACM Certificate 삭제 실패

#### 문제
```
🔐 ACM Certificate 정리 (us-east-1)...
⚠️  ACM Certificate 발견:
  - 도메인: images.growbin.app
    ARN: arn:aws:acm:us-east-1:...:certificate/...
    ⚠️  Certificate가 아직 사용 중입니다:
       - arn:aws:cloudfront::...:distribution/E1GGDPUBLRQG59
    ⏳ CloudFront 완전 삭제 대기 중 (최대 10분)...
       ⏳ 대기 중... (120초 경과)
       ... (계속 대기)
```

**원인**: CloudFront Distribution이 검색되지 않아 삭제되지 않음

**근본 원인**:
```bash
# 기존 검색 쿼리 (문제)
CF_DISTRIBUTIONS=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?contains(Origins.Items[].DomainName, 'sesacthon-images')].Id" \
    --output text)
```

- S3 버킷 이름(`sesacthon-images`)만 검색
- ACM Certificate를 사용하는 다른 Origin의 Distribution은 검색 안 됨
- 결과: CloudFront가 Enable 상태로 남아있음 → ACM Certificate 삭제 불가

---

#### 진단

**CloudFront Distribution 상태 확인**:
```bash
# Distribution ID 확인
aws cloudfront list-distributions \
    --query "DistributionList.Items[*].{Id:Id,Status:Status,Enabled:DistributionConfig.Enabled,Aliases:Aliases.Items}" \
    --output table

# 특정 Distribution 상세 확인
aws cloudfront get-distribution --id E1GGDPUBLRQG59 \
    --query 'Distribution.{Status:Status,Enabled:DistributionConfig.Enabled,DomainName:DomainName}' \
    --output json
```

**예상 결과 (문제 상황)**:
```json
{
    "Status": "Deployed",
    "Enabled": true,  // ⚠️ 여전히 활성화 상태
    "DomainName": "d3f4l2e8xigfr9.cloudfront.net"
}
```

---

#### 해결 방법 1: 스크립트 개선 (권장)

`destroy-with-cleanup.sh`의 CloudFront 검색 로직 개선:

```bash
# 5-1. CloudFront Distribution 확인 및 삭제
echo "🌐 CloudFront Distribution 확인..."

# 1. S3 버킷 기반 검색
CF_DISTRIBUTIONS_S3=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?contains(Origins.Items[].DomainName, 'sesacthon-images')].Id" \
    --output text 2>/dev/null || echo "")

# 2. ACM Certificate 기반 검색 (images. 도메인)
CF_DISTRIBUTIONS_ACM=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?contains(to_string(ViewerCertificate.ACMCertificateArn), 'images') || contains(to_string(Aliases.Items), 'images')].Id" \
    --output text 2>/dev/null || echo "")

# 3. 중복 제거하고 병합
CF_DISTRIBUTIONS=$(echo "$CF_DISTRIBUTIONS_S3 $CF_DISTRIBUTIONS_ACM" | tr ' ' '\n' | sort -u | tr '\n' ' ')

if [ -n "$CF_DISTRIBUTIONS" ]; then
    echo "⚠️  CloudFront Distribution 발견 (삭제 시 5-10분 소요):"
    for dist_id in $CF_DISTRIBUTIONS; do
        echo "  📋 Distribution ID: $dist_id"
        
        # Distribution Config 가져오기
        CONFIG=$(aws cloudfront get-distribution-config --id "$dist_id" --output json 2>/dev/null || echo "")
        
        if [ -n "$CONFIG" ] && [ "$CONFIG" != "" ]; then
            ETAG=$(echo "$CONFIG" | jq -r '.ETag' 2>/dev/null || echo "")
            IS_ENABLED=$(echo "$CONFIG" | jq -r '.DistributionConfig.Enabled' 2>/dev/null || echo "true")
            
            if [ "$IS_ENABLED" = "true" ]; then
                echo "  - Disabling Distribution: $dist_id"
                
                # Enabled를 false로 변경
                NEW_CONFIG=$(echo "$CONFIG" | jq '.DistributionConfig | .Enabled = false' 2>/dev/null)
                
                if [ -n "$NEW_CONFIG" ] && [ -n "$ETAG" ]; then
                    aws cloudfront update-distribution \
                        --id "$dist_id" \
                        --if-match "$ETAG" \
                        --distribution-config "$NEW_CONFIG" \
                        >/dev/null 2>&1 || true
                    
                    echo "  ⏳ Distribution Disabled 상태 대기 (2분)..."
                    sleep 120
                fi
            fi
            
            # 삭제
            echo "  - Deleting Distribution: $dist_id"
            FINAL_CONFIG=$(aws cloudfront get-distribution-config --id "$dist_id" --output json 2>/dev/null || echo "")
            FINAL_ETAG=$(echo "$FINAL_CONFIG" | jq -r '.ETag' 2>/dev/null || echo "")
            
            if [ -n "$FINAL_ETAG" ]; then
                aws cloudfront delete-distribution --id "$dist_id" --if-match "$FINAL_ETAG" 2>/dev/null || \
                    echo "    ⚠️  삭제 실패 (아직 배포 중이거나 사용 중)"
            fi
        fi
    done
else
    echo "  ✅ CloudFront Distribution 없음"
fi
```

**개선 포인트**:
- ✅ S3 버킷 이름 기반 검색
- ✅ ACM Certificate ARN 기반 검색 (새로 추가)
- ✅ Aliases(CNAME) 기반 검색 (새로 추가)
- ✅ 중복 제거 및 일괄 처리

---

#### 해결 방법 2: 수동 해결 (즉시 필요 시)

현재 스크립트를 중단(Ctrl+C)하고 수동으로 처리:

```bash
# 1. CloudFront Distribution 비활성화
DIST_ID="E1GGDPUBLRQG59"  # 실제 Distribution ID 입력

CONFIG=$(aws cloudfront get-distribution-config --id "$DIST_ID" --output json)
ETAG=$(echo "$CONFIG" | jq -r '.ETag')
NEW_CONFIG=$(echo "$CONFIG" | jq '.DistributionConfig | .Enabled = false')

aws cloudfront update-distribution \
    --id "$DIST_ID" \
    --if-match "$ETAG" \
    --distribution-config "$NEW_CONFIG"

# 2. Disabled 상태 대기 (2-5분)
echo "⏳ CloudFront Disabled 대기 중..."
sleep 180

# 3. CloudFront Distribution 삭제
FINAL_CONFIG=$(aws cloudfront get-distribution-config --id "$DIST_ID" --output json)
FINAL_ETAG=$(echo "$FINAL_CONFIG" | jq -r '.ETag')

aws cloudfront delete-distribution \
    --id "$DIST_ID" \
    --if-match "$FINAL_ETAG"

# 4. ACM Certificate 삭제 (CloudFront 삭제 완료 후 5분 대기)
echo "⏳ CloudFront 완전 삭제 대기 중..."
sleep 300

aws acm delete-certificate \
    --certificate-arn "arn:aws:acm:us-east-1:721622471953:certificate/b34e6013-babe-4495-88f6-77f4d9bdd39f" \
    --region us-east-1
```

---

#### 예방 방법

**배포 시 태그 추가**:
```hcl
# terraform/cloudfront.tf
resource "aws_cloudfront_distribution" "images" {
  # ... 기존 설정 ...
  
  tags = {
    Name        = "sesacthon-images-cdn"
    Project     = "SeSACTHON"
    ManagedBy   = "Terraform"
    Environment = var.environment
    # 삭제 스크립트 검색용
    SearchKey   = "sesacthon-cleanup"  # ← 추가
  }
}
```

**스크립트에서 태그 기반 검색**:
```bash
# 태그 기반 검색 (가장 확실함)
CF_DISTRIBUTIONS_TAG=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Tags.Items[?Key=='SearchKey' && Value=='sesacthon-cleanup']].Id" \
    --output text 2>/dev/null || echo "")
```

---

#### 디버깅 명령어

```bash
# 1. 모든 CloudFront Distribution 목록
aws cloudfront list-distributions \
    --query "DistributionList.Items[*].{Id:Id,DomainName:DomainName,Status:Status,Enabled:DistributionConfig.Enabled}" \
    --output table

# 2. ACM Certificate 사용 여부 확인
aws acm describe-certificate \
    --certificate-arn "arn:aws:acm:us-east-1:...:certificate/..." \
    --region us-east-1 \
    --query 'Certificate.{InUseBy:InUseBy,Status:Status}' \
    --output json

# 3. Distribution의 Origin 확인
aws cloudfront get-distribution --id E1GGDPUBLRQG59 \
    --query 'Distribution.DistributionConfig.Origins.Items[*].DomainName' \
    --output json

# 4. Distribution의 Certificate 확인
aws cloudfront get-distribution --id E1GGDPUBLRQG59 \
    --query 'Distribution.DistributionConfig.ViewerCertificate' \
    --output json
```

---

#### 관련 커밋

- `fix: Improve CloudFront detection logic to include ACM Certificate-based search`
- `fix: Add multiple search strategies for CloudFront Distribution cleanup`

---

## 7. VPC 삭제 지연 문제

### 7.1. VPC 삭제가 15분 이상 소요되는 문제

#### 현상
```
module.vpc.aws_vpc.main: Still destroying... [id=vpc-02562955fe60907d8, 15m30s elapsed]
aws_acm_certificate.cdn: Still destroying... [id=arn:aws:acm:..., 15m30s elapsed]
```

**원인**: AWS 리소스가 완전히 삭제되지 않은 상태에서 VPC 삭제 시도

#### 주요 원인 분석

##### 1. NAT Gateway 삭제 지연 (가장 큰 원인)

**문제**:
- NAT Gateway는 삭제 시 **3-5분** 소요
- 기존 스크립트는 30초만 대기 후 다음 단계로 진행
- NAT Gateway가 완전히 삭제되지 않으면 VPC 삭제 불가

**해결**:
```bash
# NAT Gateway 완전 삭제 대기 (최대 5분)
MAX_NAT_WAIT=300  # 5분
NAT_WAIT_COUNT=0

while [ $NAT_WAIT_COUNT -lt $MAX_NAT_WAIT ]; do
    REMAINING_NATS=$(aws ec2 describe-nat-gateways \
        --filter "Name=vpc-id,Values=$VPC_ID" "Name=state,Values=available,pending,deleting" \
        --region "$AWS_REGION" \
        --query 'NatGateways[*].NatGatewayId' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$REMAINING_NATS" ]; then
        echo "✅ 모든 NAT Gateway 삭제 완료 (${NAT_WAIT_COUNT}초 소요)"
        break
    fi
    
    if [ $((NAT_WAIT_COUNT % 30)) -eq 0 ]; then
        echo "⏳ 대기 중... (${NAT_WAIT_COUNT}초 경과)"
    fi
    
    sleep 5
    NAT_WAIT_COUNT=$((NAT_WAIT_COUNT + 5))
done
```

##### 2. ENI (Elastic Network Interface) 삭제 실패

**문제**:
- NAT Gateway와 연결된 ENI가 자동 삭제되지 않음
- 5초 대기 후 재시도하지만 여전히 실패 가능
- ENI가 VPC에 연결되어 있어 VPC 삭제 불가

**해결**:
```bash
# ENI는 NAT Gateway 삭제 후에 자동으로 해제되므로 여러 번 재시도
MAX_ENI_RETRY=3
ENI_RETRY_COUNT=0

while [ $ENI_RETRY_COUNT -lt $MAX_ENI_RETRY ]; do
    ENI_IDS=$(aws ec2 describe-network-interfaces \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --region "$AWS_REGION" \
        --query 'NetworkInterfaces[?Status==`available`].NetworkInterfaceId' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$ENI_IDS" ]; then
        echo "✅ 남은 ENI 없음"
        break
    fi
    
    echo "⚠️  남은 ENI 발견 (시도 $((ENI_RETRY_COUNT + 1))/$MAX_ENI_RETRY):"
    
    for eni in $ENI_IDS; do
        aws ec2 delete-network-interface --network-interface-id "$eni" --region "$AWS_REGION" 2>/dev/null || true
    done
    
    ENI_RETRY_COUNT=$((ENI_RETRY_COUNT + 1))
    
    if [ $ENI_RETRY_COUNT -lt $MAX_ENI_RETRY ]; then
        echo "⏳ 10초 후 재시도..."
        sleep 10
    fi
done
```

##### 3. ACM Certificate 삭제 지연

**문제**:
- CloudFront가 ACM Certificate를 사용 중이면 삭제 불가
- CloudFront disable 후 2분만 대기하는데, 실제로는 5-10분 소요
- Certificate가 삭제되지 않으면 Terraform destroy가 계속 대기

**해결**:
```bash
# CloudFront 사용 여부 확인
CERT_IN_USE=$(aws acm describe-certificate \
    --certificate-arn "$cert_arn" \
    --region us-east-1 \
    --query 'Certificate.InUseBy' \
    --output json 2>/dev/null || echo "[]")

IN_USE_COUNT=$(echo "$CERT_IN_USE" | jq '. | length' 2>/dev/null || echo "0")

if [ "$IN_USE_COUNT" -gt 0 ]; then
    echo "⚠️  Certificate가 아직 사용 중입니다:"
    
    # CloudFront 완전 삭제 대기 (최대 10분)
    MAX_CF_WAIT=600  # 10분
    CF_WAIT_COUNT=0
    
    while [ $CF_WAIT_COUNT -lt $MAX_CF_WAIT ]; do
        CURRENT_IN_USE=$(aws acm describe-certificate \
            --certificate-arn "$cert_arn" \
            --region us-east-1 \
            --query 'Certificate.InUseBy' \
            --output json 2>/dev/null || echo "[]")
        
        CURRENT_COUNT=$(echo "$CURRENT_IN_USE" | jq '. | length' 2>/dev/null || echo "0")
        
        if [ "$CURRENT_COUNT" -eq 0 ]; then
            echo "✅ Certificate 해제 완료 (${CF_WAIT_COUNT}초 소요)"
            break
        fi
        
        if [ $((CF_WAIT_COUNT % 30)) -eq 0 ]; then
            echo "⏳ 대기 중... (${CF_WAIT_COUNT}초 경과)"
        fi
        
        sleep 10
        CF_WAIT_COUNT=$((CF_WAIT_COUNT + 10))
    done
fi
```

---

### 7.2. 리소스 삭제 순서 최적화

#### 권장 순서

```
1. Kubernetes 리소스 삭제 (Ingress, Service, PVC)
   └─> ALB, Target Groups 자동 삭제
   
2. AWS 리소스 확인 및 삭제
   ├─> Load Balancer 삭제 (최대 60초 대기)
   ├─> Security Groups 삭제
   ├─> ENI 삭제 (재시도 3회)
   ├─> Target Groups 삭제
   ├─> CloudFront Distribution 삭제 (최대 10분 대기)
   ├─> Route53 레코드 삭제
   ├─> S3 Bucket 정리
   ├─> ACM Certificate 삭제 (CloudFront 대기 최대 10분)
   └─> IAM Policy 강제 정리

3. NAT Gateway 삭제 (최대 5분 대기) ⭐ 중요!
   └─> 완전 삭제 확인 후 다음 단계 진행

4. VPC Endpoints 삭제
   VPC Peering Connections 삭제
   Elastic IP 해제

5. Terraform destroy 실행
   └─> VPC 및 나머지 리소스 삭제
```

---

### 7.3. 수동 디버깅 명령어

#### VPC 삭제를 막는 리소스 확인

```bash
# 1. NAT Gateway 상태 확인
aws ec2 describe-nat-gateways \
    --filter "Name=vpc-id,Values=$VPC_ID" \
    --region ap-northeast-2 \
    --query 'NatGateways[*].[NatGatewayId,State]' \
    --output table

# 2. ENI 확인
aws ec2 describe-network-interfaces \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region ap-northeast-2 \
    --query 'NetworkInterfaces[*].[NetworkInterfaceId,Status,Description]' \
    --output table

# 3. Security Groups 확인
aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region ap-northeast-2 \
    --query 'SecurityGroups[*].[GroupId,GroupName]' \
    --output table

# 4. Subnets 확인
aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region ap-northeast-2 \
    --query 'Subnets[*].[SubnetId,AvailabilityZone,CidrBlock]' \
    --output table

# 5. Internet Gateway 확인
aws ec2 describe-internet-gateways \
    --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
    --region ap-northeast-2 \
    --query 'InternetGateways[*].[InternetGatewayId]' \
    --output table

# 6. VPC Endpoints 확인
aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region ap-northeast-2 \
    --query 'VpcEndpoints[*].[VpcEndpointId,ServiceName,State]' \
    --output table

# 7. ACM Certificate 사용 여부 확인
aws acm describe-certificate \
    --certificate-arn "$CERT_ARN" \
    --region us-east-1 \
    --query 'Certificate.InUseBy' \
    --output json
```

#### 수동 리소스 삭제

```bash
# NAT Gateway 강제 삭제
NAT_GW_ID="nat-xxxxx"
aws ec2 delete-nat-gateway --nat-gateway-id "$NAT_GW_ID" --region ap-northeast-2

# ENI 강제 삭제
ENI_ID="eni-xxxxx"
aws ec2 delete-network-interface --network-interface-id "$ENI_ID" --region ap-northeast-2

# VPC 직접 삭제 시도
VPC_ID="vpc-xxxxx"
aws ec2 delete-vpc --vpc-id "$VPC_ID" --region ap-northeast-2
```

---

### 7.4. 예상 소요 시간

| 단계 | 소요 시간 | 설명 |
|-----|----------|------|
| Kubernetes 리소스 정리 | 30초-1분 | Ingress, Service, PVC 삭제 |
| Load Balancer 삭제 | 1-2분 | ALB 완전 삭제 대기 |
| CloudFront 삭제 | 5-10분 | Distribution disable + 삭제 |
| ACM Certificate 대기 | 5-10분 | CloudFront 해제 대기 |
| **NAT Gateway 삭제** | **3-5분** | ⭐ 가장 시간 소요 |
| Terraform destroy | 2-3분 | 나머지 리소스 삭제 |
| **총 예상 시간** | **15-30분** | 정상 범위 |

---

### 7.5. 개선 결과

#### 기존 문제
- NAT Gateway: 30초만 대기 → 완전 삭제되지 않음
- ENI: 1회 재시도 → 삭제 실패
- ACM Certificate: 대기 없음 → Terraform이 계속 대기

#### 개선 후
- ✅ NAT Gateway: 최대 5분 대기 → 완전 삭제 확인
- ✅ ENI: 3회 재시도 (10초 간격) → 삭제 성공률 향상
- ✅ ACM Certificate: 최대 10분 대기 → CloudFront 해제 확인 후 삭제

**결과**: VPC 삭제 지연 문제 해결 및 안정적인 cleanup 가능

---

### 7.6. 관련 커밋

- `fix: Add comprehensive NAT Gateway deletion wait in destroy-with-cleanup.sh`
- `fix: Improve ENI deletion with retry mechanism`
- `fix: Add CloudFront deletion wait for ACM Certificate cleanup`

---

## 8. ArgoCD 리디렉션 루프 문제

### 문제
브라우저에서 `https://argocd.growbin.app` 접속 시 "리디렉션한 횟수가 너무 많습니다" 에러 발생.

### 원인
- Ingress가 포트 443을 사용하지만 `backend-protocol: HTTP`가 설정되지 않음
- ALB가 HTTPS로 연결 시도하지만 ArgoCD는 HTTP만 지원
- Health Check 실패로 Target Group이 unhealthy 상태

### 해결 (2025-11-16 업데이트)
1. **HTTPS → HTTP NAT 명시**  
   - 모든 ALB Ingress에 `alb.ingress.kubernetes.io/backend-protocol: HTTP` 추가  
   - 참고: [AWS Load Balancer Controller 공식 가이드](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.7/guide/ingress/annotations/#backend-protocol)
2. **ALB Listener 단일화**  
   - `alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS": 443}]'` 로 고정  
   - `alb.ingress.kubernetes.io/ssl-redirect` 제거 (중복 리다이렉션 방지)
3. **ArgoCD Service 정리**  
   - NodePort 서비스에서 443 포트를 제거하고 HTTP(80)만 노출  
   - ALB가 TLS 종료 → 백엔드 HTTP 전달 (AWS 베스트 프랙티스)
4. **Health Check 일원화**  
   - `/healthz`(ArgoCD)와 `/api/health`(Grafana) 등 실제 엔드포인트로 통일

**적용 파일**
- `k8s/ingress/domain-based-api-ingress.yaml`
- `k8s/ingress/infrastructure-ingress.yaml`
- `ansible/roles/argocd/tasks/main.yml`
- `ansible/playbooks/07-ingress-resources.yml`

> 💡 HTTPS→HTTP NAT 구성은 ALB에서 TLS를 종료하고, Target Group에는 HTTP만 전달하는 공식 권장 구성이므로 별도 프록시/재암호화가 필요 없다.

---

## 9. Prometheus 메모리 부족 문제

### 문제
Prometheus Pod가 `Pending` 상태로 스케줄링되지 않음.

### 원인
- Prometheus가 2Gi 메모리를 요청
- Monitoring 노드(t3.small, 2GB RAM)의 Allocatable 메모리가 부족
- 에러: `9 Insufficient memory`

### 해결
1. **옵션 1 (권장):** Prometheus 리소스 요청을 2Gi → 1.5Gi로 감소
2. **옵션 2:** Monitoring 노드 인스턴스 타입을 t3.medium(4GB RAM)으로 업그레이드
3. **옵션 3:** Prometheus를 다른 노드로 스케줄링

**자세한 내용:** [PROMETHEUS_MEMORY_INSUFFICIENT.md](./troubleshooting/PROMETHEUS_MEMORY_INSUFFICIENT.md)

---

## 10. Atlantis Pod CrashLoopBackOff 문제

### 문제
Atlantis Pod가 `CrashLoopBackOff` 상태로 계속 재시작됨.

### 원인
1. **포트 파싱 에러**: Atlantis가 환경 변수에서 포트를 파싱할 때 Service의 ClusterIP 형식을 포트로 인식
2. **권한 문제**: PersistentVolume에 대한 쓰기 권한 없음 (`fsGroup`, `runAsUser` 설정 누락)

### 해결
1. 포트 명시적 설정 (`--port=4141`)
2. SecurityContext 추가 (`fsGroup: 1000`, `runAsUser: 1000`, `runAsGroup: 1000`)

**자세한 내용:** [ATLANTIS_POD_CRASHLOOPBACKOFF.md](./troubleshooting/ATLANTIS_POD_CRASHLOOPBACKOFF.md)

---

## 11. Atlantis Pod에서 kubectl을 찾을 수 없는 문제

### 문제
Atlantis Pod에서 kubectl을 실행할 때 `executable file not found in $PATH` 에러 발생.

### 원인
Init Container에서 kubectl을 설치했지만, Main Container에서 올바른 경로로 마운트되지 않음.

### 해결
1. Init Container에서 `/shared/usr/local/bin/kubectl`에 복사
2. Main Container에서 `/shared/usr/local/bin`을 `/usr/local/bin`에 subPath로 마운트
3. PATH 환경 변수에 `/usr/local/bin` 추가

**자세한 내용:** [ATLANTIS_KUBECTL_NOT_FOUND.md](./troubleshooting/ATLANTIS_KUBECTL_NOT_FOUND.md)

---

## 12. Atlantis Deployment 파일을 찾을 수 없는 문제

### 문제
Master 노드에서 `kubectl apply -f k8s/atlantis/atlantis-deployment.yaml` 실행 시 파일을 찾을 수 없음.

### 원인
Master 노드에는 Git 저장소가 없음. Atlantis는 Ansible을 통해 배포되며, 파일은 로컬 개발 환경에만 존재.

### 해결
로컬에서 Ansible을 실행하여 재배포:
```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/09-atlantis.yml
```

**자세한 내용:** [ATLANTIS_DEPLOYMENT_FILE_NOT_FOUND.md](./troubleshooting/ATLANTIS_DEPLOYMENT_FILE_NOT_FOUND.md)

---

## 13. Atlantis 실행 파일을 찾을 수 없는 문제

### 문제
Atlantis Pod가 시작되지 않고 다음 에러 발생:
```
exec: "atlantis": executable file not found in $PATH: unknown
```

### 원인
`command: ["atlantis"]`로 지정했지만, 컨테이너 내부에서 `atlantis` 실행 파일을 찾을 수 없음. Atlantis 이미지는 이미 ENTRYPOINT가 설정되어 있어서 `command`를 지정할 필요가 없음.

### 해결
`command`를 제거하고 이미지의 기본 ENTRYPOINT를 사용:
```yaml
# 수정 전
command: ["atlantis"]
args:
  - server
  # ...

# 수정 후
# command는 제거 (이미지의 기본 ENTRYPOINT 사용)
args:
  - server
  # ...
```

**자세한 내용:** [ATLANTIS_EXECUTABLE_NOT_FOUND.md](./troubleshooting/ATLANTIS_EXECUTABLE_NOT_FOUND.md)

---

## 14. Atlantis ConfigMap YAML 파싱 에러

### 14.1. 증상
```
Error: initializing server: parsing /etc/atlantis/atlantis.yaml file: yaml: unmarshal errors:
  line 1: field version not found in type raw.GlobalCfg
  line 2: field automerge not found in type raw.GlobalCfg
  line 3: field delete_source_branch_on_merge not found in type raw.GlobalCfg
  line 4: field parallel_plan not found in type raw.GlobalCfg
  line 5: field parallel_apply not found in type raw.GlobalCfg
  line 7: field projects not found in type raw.GlobalCfg
```

Atlantis Pod가 `CrashLoopBackOff` 상태

### 14.2. 원인
**Atlantis Config 파일의 두 가지 타입 혼동**

1. **Repo-level Config** (`.atlantis.yaml` in repository)
   - `version`, `automerge`, `projects`, `workflows` 등을 직접 정의
   
2. **Server-side Repo Config** (`ATLANTIS_REPO_CONFIG` 환경변수)
   - `repos`와 `workflows` 두 섹션으로 구성

현재는 **Repo-level Config 형식**을 **Server-side Config**로 사용하려고 해서 파싱 에러 발생

### 14.3. 해결 방법

#### Master 노드에서 실행:
```bash
# 기존 ConfigMap 삭제
kubectl delete configmap atlantis-repo-config -n atlantis

# 올바른 형식으로 재생성
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: atlantis-repo-config
  namespace: atlantis
data:
  atlantis.yaml: |
    # Repositories Configuration
    repos:
    - id: github.com/SeSACTHON/*
      workflow: infrastructure-workflow
      allowed_overrides:
        - workflow
        - apply_requirements
      allow_custom_workflows: true
      delete_source_branch_on_merge: true
    
    # Workflows Configuration
    workflows:
      infrastructure-workflow:
        plan:
          steps:
            - run: echo "🔍 Terraform Plan 시작..."
            - init
            - plan
        apply:
          steps:
            - run: echo "🚀 Terraform Apply 시작..."
            - apply
            - run: echo "✅ Terraform Apply 완료"
EOF

# Pod 재시작
kubectl delete pod atlantis-0 -n atlantis
```

#### 또는 자동 스크립트:
```bash
./scripts/utilities/fix-atlantis-config.sh
```

### 14.4. 적용된 수정사항
- `ansible/playbooks/09-atlantis.yml`: Server-side Repo Config 생성 Task 추가
- `scripts/utilities/fix-atlantis-config.sh`: ConfigMap 수정 스크립트 생성

**자세한 내용:** [ATLANTIS_CONFIG_YAML_PARSE_ERROR.md](./troubleshooting/ATLANTIS_CONFIG_YAML_PARSE_ERROR.md)

---

## 15. 베스트 프랙티스

### 15.1. 재구축 전 체크리스트

```bash
# 1. vCPU 한도 확인
aws service-quotas get-service-quota \
    --service-code ec2 \
    --quota-code L-1216C47A \
    --region ap-northeast-2 \
    --query 'Quota.Value'
# 결과: 32.0 이상이어야 함

# 2. 이전 리소스 완전 정리
./scripts/maintenance/destroy-with-cleanup.sh

# 3. 환경 변수 설정
export GITHUB_TOKEN="<your-token>"
export GITHUB_USERNAME="<your-username>"
export VERSION="v0.6.0"

# 4. 재구축 실행
./scripts/cluster/auto-rebuild.sh
```

---

### 15.2. 디버깅 명령어 모음

```bash
# Terraform 상태 확인
terraform state list
terraform output -json

# AWS 리소스 확인
aws ec2 describe-instances --region ap-northeast-2
aws iam list-policies --scope Local
aws s3api list-buckets

# Kubernetes 상태 확인
kubectl get nodes -o wide
kubectl get pods -A
kubectl get svc -A

# GitHub 인증 상태
gh auth status

# 로그 확인
tail -f /var/log/cloud-init-output.log  # Master 노드에서
journalctl -u kubelet -f                 # Worker 노드에서
```

---

### 15.3. 문제 발생 시 대응 순서

1. **에러 메시지 확인**: 정확한 에러 내용 파악
2. **이 문서 검색**: 유사한 문제 해결 방법 확인
3. **AWS 상태 확인**: 리소스가 실제로 남아있는지 확인
4. **정리 스크립트 실행**: `destroy-with-cleanup.sh`
5. **한도 확인**: vCPU, IAM Policy 등
6. **재시도**: 정리 후 재구축

---

## 16. 참고 문서

- [AWS Service Quotas Documentation](https://docs.aws.amazon.com/servicequotas/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [GitHub CLI Authentication](https://cli.github.com/manual/gh_auth_login)
- [CloudFront Developer Guide](https://docs.aws.amazon.com/cloudfront/)

---

## 17. 지원

문제가 해결되지 않으면:
- GitHub Issues: https://github.com/mangowhoiscloud/backend/issues
- AWS Support: https://console.aws.amazon.com/support/
- Terraform Registry: https://discuss.hashicorp.com/

---

## 18. GitOps 배포 문제 (2025-11-16 추가)

### 18.1. Kustomize 상위 디렉토리 참조 오류

#### 문제
```
Error: file '../namespaces/domain-based.yaml' is not in or below 'k8s/namespaces'
```

**원인**: Kustomize는 보안상 상위 디렉토리 참조 불가

#### 해결
```bash
# 모든 Namespace 리소스는 k8s/namespaces 디렉터리 안에 존재해야 함
# (Wave 00: namespaces)
```

**커밋**: `c17defd`

---

### 18.2. ApplicationSet kustomize.images 문법 오류

#### 문제
```
ApplicationSet.argoproj.io "api-services" is invalid: 
spec.template.spec.source.kustomize.images[0]: Invalid value: "object"
```

**원인**: ApplicationSet에서 kustomize.images는 객체 형태 사용 불가

#### 해결
```yaml
# argocd/apps/80-apis-app-of-apps.yaml
# BEFORE (오류)
source:
  path: k8s/overlays/{{domain}}
  kustomize:
    images:
      - name: ghcr.io/sesacthon/{{domain}}-api
        newTag: latest

# AFTER (수정)
source:
  path: k8s/overlays/{{domain}}
  # kustomize.images 제거 - overlay의 patch-deployment.yaml에서 이미 latest 지정
```

**커밋**: `7f79d30`

---

### 18.3. CI Workflow YAML 파싱 오류

#### 문제
```
YAML parsing failed: could not find expected ':'
in ".github/workflows/ci-quality-gate.yml", line 186
```

**원인**: Python heredoc의 들여쓰기 문제

#### 해결
```yaml
# .github/workflows/ci-quality-gate.yml
# BEFORE (오류)
python <<'PY'
import json  # 들여쓰기 없음
...
PY

# AFTER (수정)
python3 <<'PYEOF'
  import json  # YAML 문법에 맞게 들여쓰기
  ...
PYEOF
```

**커밋**: `84b1c1d`

---

### 18.4. GHCR ImagePullBackOff (권한 문제)

#### 문제
```
Failed to pull image "ghcr.io/sesacthon/auth-api:latest": 403 Forbidden
```

**원인**: Secret의 GitHub token에 `read:packages` 권한 없음

#### 해결
```bash
# 1. read:packages 권한이 있는 토큰 생성
# GitHub Settings → Developer settings → Personal access tokens

# 2. 모든 namespace에 Secret 재생성
for ns in auth character chat info location my scan workers; do
  kubectl delete secret ghcr-secret -n $ns
  kubectl create secret docker-registry ghcr-secret \
    --docker-server=ghcr.io \
    --docker-username=<USERNAME> \
    --docker-password=<TOKEN_WITH_READ_PACKAGES> \
    --namespace=$ns
done

# 3. Pods 재생성
kubectl delete pod --all -n auth
```

**필수 권한**: `read:packages`, `write:packages` (빌드 시)

**커밋**: Secret 생성 (수동), `0f6663e` (imagePullSecrets 추가)

---

### 18.5. RabbitMQ Bitnami Debian 이미지 중단

#### 문제
```
bitnami/rabbitmq:4.1.3-debian-12-r1: not found
bitnami/rabbitmq:3.13.7-debian-12-r0: not found
```

**원인**: Bitnami의 Debian 기반 RabbitMQ 이미지가 2025-08-28부터 중단됨

#### 해결 방법

**Option A: Docker Official Image (임시)**
```yaml
# charts/data/databases/values.yaml
rabbitmq:
  image:
    registry: docker.io
    repository: rabbitmq
    tag: "3.13-management"
```

**주의**: Bitnami Chart의 init scripts가 Docker Official Image와 호환되지 않을 수 있음

**Option B: RabbitMQ Cluster Operator (권장)**
```yaml
# argocd/apps/50-data-operators.yaml에 추가
# RabbitMQ Operator 설치 후
# RabbitMQCluster CRD로 배포
```

**커밋**: `dd51c46`

**참고**: https://www.rabbitmq.com/kubernetes/operator/operator-overview.html

---

### 18.6. Ansible Playbook import_tasks 문법 충돌

#### 문제
```
ERROR: conflicting action statements: hosts, tasks
Origin: ansible/playbooks/07-alb-controller.yml:4:3
```

**원인**: `import_tasks`로 호출되는 playbook에 `hosts` 정의 불가

#### 해결
```yaml
# ansible/playbooks/07-alb-controller.yml
# BEFORE (오류)
---
- name: Task name
  hosts: masters  # ← import_tasks로 호출 시 불가
  tasks:
    - ...

# AFTER (수정)
---
- name: Task name
  # hosts 제거, tasks만 정의
  set_fact:
    ...
```

**커밋**: `7f79d30`

---

### 18.7. VPC 삭제 실패 (ALB/Target Groups 남음)

#### 문제
```
terraform destroy 실패
Error: VPC has dependencies and cannot be deleted
```

**원인**: Kubernetes ALB Controller가 생성한 ALB, Target Groups가 남아있음

#### 해결
```bash
# VPC cleanup 스크립트 사용
bash scripts/cleanup-vpc-resources.sh

# 수동 정리
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Project,Values=SeSACTHON" --query 'Vpcs[0].VpcId' --output text)

# Target Groups 삭제
aws elbv2 describe-target-groups --query "TargetGroups[?VpcId=='$VPC_ID'].TargetGroupArn" --output text | \
  xargs -I {} aws elbv2 delete-target-group --target-group-arn {}

# Load Balancers 삭제
aws elbv2 describe-load-balancers --query "LoadBalancers[?VpcId=='$VPC_ID'].LoadBalancerArn" --output text | \
  xargs -I {} aws elbv2 delete-load-balancer --load-balancer-arn {}

# 30초 대기 후 terraform destroy
sleep 30
terraform destroy -auto-approve
```

**스크립트**: `scripts/cleanup-vpc-resources.sh` 생성됨

---

### 18.8. scan-api CrashLoopBackOff (모듈 경로)

#### 문제
```
ERROR: Error loading ASGI app. Could not import module "main".
```

**원인**: Dockerfile의 uvicorn 경로가 잘못됨

#### 해결
```dockerfile
# services/scan/Dockerfile
# BEFORE
CMD ["uvicorn", "main:app", ...]

# AFTER  
CMD ["uvicorn", "app.main:app", ...]
```

**커밋**: `eb154a7`

---

### 18.9. ArgoCD Application 자동 Sync 안됨

#### 문제
Applications가 OutOfSync 상태로 남아있음

#### 원인
```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true  # 설정되어 있지만 delay 있음
```

#### 해결
```bash
# 수동 sync 트리거
kubectl patch application <app-name> -n argocd --type merge \
  -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"develop"}}}'

# 또는 Application 재생성 (root-app이 자동 재생성)
kubectl delete application <app-name> -n argocd
```

**시간이 지나면 자동으로 sync됨** (retryPolicy 설정)

---

### 18.10. ALB Controller VPC ID 하드코딩

#### 문제
```
ALB Controller CrashLoopBackOff
Error: unable to create controller
```

**원인**: ArgoCD Application에 이전 VPC ID 하드코딩됨

#### 해결
```yaml
# argocd/apps/20-alb-controller.yaml
# 현재 VPC ID로 수정 필요
parameters:
  - name: vpcId
    value: vpc-0cb5bbb41f25671f5  # 새 VPC ID
```

**개선안**: ConfigMap이나 External Secrets로 동적 주입 고려

**커밋**: `0645847`

---

### 18.11. ALB Controller egress 차단 (NetworkPolicy)

#### 문제
```
aws-load-balancer-controller-7cbcb46f48-xxxxx  CrashLoopBackOff
unable to create controller: Post "https://10.96.0.1:443/...": dial tcp 10.96.0.1:443: i/o timeout
```

- 외부 통신 (Kubernetes API, AWS API, IMDS 등)에 접근하지 못해 Operator가 기동 직후 종료
- ALB, TargetGroup, Listener 동기화가 모두 멈추면서 Wave 15~70 전체가 OutOfSync

#### 원인
- GitOps v0.7.3 (`5341203`)에서 배포된 `k8s/infrastructure/networkpolicies/domain-isolation.yaml`이 **모든 네임스페이스 egress를 TCP 80/443 + data namespace**로만 제한
- `kube-system` → API Server(10.96.0.1), DNS(UDP 53), AWS Public API(0.0.0.0/0:443) CIDR 이 허용되지 않아 Control Plane과 IRSA STS 호출이 모두 차단
- 동일한 템플릿이 business-logic namespace 전체에 반복 적용되면서 ALB Controller 뿐 아니라 ExternalDNS, Metrics Server까지 연쇄 CrashLoop

#### 해결
1. 문제 Policy 제거 (`git revert 5341203 -- k8s/infrastructure/networkpolicies/domain-isolation.yaml` 혹은 `kubectl delete`로 즉시 완화)
2. 전용 egress 허용 정책을 별도 파일로 재작성  
   - `workloads/network-policies/base/allow-dns.yaml` (UDP/TCP 53)  
   - `workloads/network-policies/base/default-deny-all.yaml` (기본 차단)  
   - `alb-controller-egress` 커스텀 정책:  
     ```yaml
     egress:
       - to:
           - ipBlock: { cidr: 10.96.0.1/32 }        # Kubernetes API
         ports:
           - protocol: TCP
             port: 443
       - to:
           - namespaceSelector:
               matchLabels:
                 kubernetes.io/metadata.name: kube-system
         ports:
           - protocol: UDP
             port: 53
           - protocol: TCP
             port: 53
       - to:
           - ipBlock: { cidr: 169.254.169.254/32 }  # Instance Metadata
           - ipBlock: { cidr: 0.0.0.0/0 }           # AWS API (STS 등)
         ports:
           - protocol: TCP
             port: 443
     ```
3. Wave 5/6 (Calico → NetworkPolicy)에서 위 정책 세트를 배포하도록 `clusters/{env}/apps/05-calico.yaml`, `06-network-policies.yaml` 순서를 고정
4. ALB Controller 재기동 (`kubectl rollout restart deployment/aws-load-balancer-controller -n kube-system`)

#### 사후 조치
- `5c4f5cc`에서 legacy `k8s/infrastructure/networkpolicies` 경로를 정리하고, 모든 정책을 `workloads/network-policies`로 통합
- `77d694c`에서 overlays 없이 base/환경별 평면 구조로 재정비하여 ArgoCD Diff, GitHub PR 리뷰가 가능하도록 함
- `docs/architecture/networking/NAMESPACE_NETWORKPOLICY_INGRESS.md`에 동일 사례를 표준 가이드로 연결하고, NetworkPolicy 변경 시 `kubectl logs` / `kubectl describe networkpolicy` 점검을 배포 체크리스트에 추가

---

## 19. 베스트 프랙티스 (2025-11-16 업데이트)

### 19.1. GitOps 배포

**권장:**
- ✅ Namespace는 ArgoCD namespaces에서만 관리 (Ansible 중복 제거)
- ✅ Cert-manager 제거, ACM 사용
- ✅ Kustomize 리소스는 같은 디렉토리나 하위에만
- ✅ ApplicationSet에서 kustomize.images 사용 금지
- ✅ CI YAML heredoc는 올바른 들여쓰기

### 19.2. GHCR 이미지 관리

**권장:**
- ✅ Token에 `read:packages`, `write:packages` 권한 필수
- ✅ imagePullSecrets를 base deployment에 정의
- ✅ Private packages 사용 시 모든 namespace에 Secret 생성
- ✅ CI에서 `secrets.GH_TOKEN` 사용 (GITHUB_TOKEN은 제한적)

### 19.3. Bitnami Charts

**주의:**
- ⚠️ Bitnami Debian 이미지 중단 (2025-08-28)
- ✅ Docker Official Image 또는 Operator 사용 권장
- ✅ Bitnami Chart와 Docker Official Image 호환성 확인 필요

---

**최종 업데이트**: 2025-11-16  
**버전**: v0.7.3  
**아키텍처**: 14-Node GitOps Production

## 20. Legacy Troubleshooting Archive (docs/troubleshooting/\*)

2025-11-11 `84dcb7fa` 등 문서 정리 커밋에서 삭제된 `docs/troubleshooting/*.md` 19건을 다시 이 문서에 통합했습니다. 기존 섹션과 내용이 겹치는 항목은 **버전/아키텍처 정보**만 표에 기록하고, 누락돼 있던 사례는 `20.1~20.10`에 전문을 요약해 복원했습니다.

| Legacy ID | 이슈 | 버전·아키텍처 | 현재 반영 |
|-----------|------|---------------|-----------|
| 01 | ALB Provider ID 누락 | GitOps v0.6.0 · 14-Node | 20.1 (복원) |
| 02 | auto-rebuild Ansible SSH 타임아웃 | GitOps v0.7.0 · 14-Node | 20.2 (복원) |
| 03 | ArgoCD 502 Bad Gateway | GitOps v0.6.0 · 14-Node | 20.3 (복원) |
| 04 | ArgoCD 리디렉션 루프 | GitOps v0.6.0 · 14-Node | 섹션 8 |
| 05 | Atlantis Config YAML 파싱 오류 | GitOps v0.6.0 · 13-Node | 섹션 14 |
| 06 | Atlantis Deployment 파일 없음 | GitOps v0.6.0 · 13-Node | 섹션 12 |
| 07 | Atlantis executable not found | GitOps v0.6.0 · 13-Node | 섹션 13 |
| 08 | Atlantis Pod에서 kubectl 미탑재 | GitOps v0.6.0 · 13-Node | 섹션 11 |
| 09 | Atlantis CrashLoopBackOff | GitOps v0.6.0 · 13-Node | 섹션 10 |
| 10 | CloudFront ACM Certificate stuck | GitOps v0.6.0 · 13-Node | 섹션 6.3 |
| 11 | deploy.sh SSH 키/Ingress Deprecated 옵션 | GitOps v0.6.0 · 14-Node | 20.4 (복원) |
| 12 | macOS TLS 인증서 오류 | GitOps v0.6.0 · Local Dev | 20.5 (복원) |
| 13 | Monitoring 노드 리소스 분석 | GitOps v0.6.0 · 14-Node | 20.6 (복원) |
| 14 | PostgreSQL FailedScheduling | GitOps v0.6.0 · 14-Node | 20.7 (복원) |
| 15 | Prometheus 메모리 부족 | GitOps v0.6.0 · 14-Node | 섹션 9 |
| 16 | Prometheus Pending (CPU 부족) | GitOps v0.6.0 · 14-Node | 20.8 (복원) |
| 17 | Route53 → ALB 라우팅 수정 | GitOps v0.6.0 · 14-Node | 20.9 (복원) |
| 18 | CloudFront/ACM/VPC 삭제 장애 | GitOps v0.6.0 · 14-Node | 20.10 (복원) |
| 19 | VPC 삭제 지연 (Security Group) | GitOps v0.6.0 · 13-Node | 섹션 7 |

### 20.1. ALB Provider ID 누락 (GitOps v0.6.0 · 14-Node)

- **증상**: ALB가 만들어졌지만 TargetGroup이 비어 있고 `503 Service Unavailable`.
- **원인**: Worker/Infra 노드 `spec.providerID`가 `aws:///ap-northeast-2a/`처럼 Instance ID 없이 비어 있어 AWS Load Balancer Controller가 노드를 식별하지 못함.
- **해결**:
  1. 긴급: 각 노드에서 `kubeadm-flags.env` 끝에 `--provider-id=aws:///AZ/i-xxxxxxxx`를 추가 후 `systemctl restart kubelet`.
  2. 영구: `ansible/playbooks/03-worker-join.yml`에 `ec2-metadata` 기반 providerID 주입 태스크 추가.
  3. 검증: `kubectl get nodes -o custom-columns='NAME:.metadata.name,PROVIDER:.spec.providerID'`.
- **참고**: `terraform/alb-controller-iam.tf`, `ansible/playbooks/03-worker-join.yml`.

### 20.2. auto-rebuild Ansible SSH 타임아웃 (GitOps v0.7.0 · 14-Node)

- **증상**: `ansible-playbook site.yml` 단계에서 `Timeout when waiting for <old-ip>:22`.
- **원인**: Terraform이 새 Public IP를 발급했으나 `auto-rebuild.sh`가 `ansible/inventory/hosts.ini`를 재생성하지 않아 구버전 IP(이전 클러스터)를 계속 사용.
- **해결**:
  - Terraform output을 진실원으로 사용:  
    `terraform output -raw ansible_inventory > ansible/inventory/hosts.ini`.
  - 스크립트 강화: apply 직후 inventory 재생성, 노드 개수 동적 계산, Phase3/4 라벨링·헬스체크 추가.
  - 실행 순서: inventory 재생성 → `ansible all -m ping` → `ansible-playbook site.yml`.

### 20.3. ArgoCD 502 Bad Gateway (GitOps v0.6.0 · 14-Node)

- **증상**: `https://growbin.app/argocd` 접근 시 502, TargetHealth `unhealthy`.
- **원인**: Ingress annotation이 `alb.ingress.kubernetes.io/backend-protocol: HTTPS`이고 Service Port가 443인 반면 ArgoCD 서버는 `server.insecure: true`로 HTTP 8080만 리슨.
- **해결**:
  1. `backend-protocol`을 HTTP로, backend Service Port를 80으로 수정.  
     `kubectl annotate ingress argocd-ingress alb.ingress.kubernetes.io/backend-protocol=HTTP --overwrite`
  2. `ansible/playbooks/07-ingress-resources.yml` 템플릿 업데이트.
  3. `aws elbv2 describe-target-health`로 Health 확인.

### 20.4. deploy.sh SSH 키·Ingress Deprecated 옵션 (GitOps v0.6.0 · 14-Node)

- **증상**: `deploy.sh`가 `~/.ssh/sesacthon.pem` 미존재로 중단, `kubernetes.io/ingress.class` warning 다수 발생.
- **해결**:
  - SSH: Terraform이 업로드한 `~/.ssh/id_rsa`를 기본 키로 사용하도록 스크립트 수정.
  - Ingress: annotation 대신 `spec.ingressClassName: alb` 사용.
  - `ansible/ansible.cfg`에 `deprecation_warnings = False`.
- **검증**: `kubectl get ingress -A -o jsonpath='{.items[*].spec.ingressClassName}'`.

### 20.5. macOS TLS 인증서 오류 (GitOps v0.6.0 · Local Dev)

- **증상**: macOS에서 Terraform/kubectl 실행 시 `x509: certificate signed by unknown authority`.
- **원인**: Go 런타임이 macOS Keychain 인증서를 인식하지 못하거나 프록시형 SSL 검사 도구가 중간자 인증서를 삽입.
- **해결 옵션**:
  - Terraform을 Docker 이미지에서 실행하여 리눅스 cacerts 사용.
  - 개발 환경에 한해 `SSL_CERT_FILE` 지정 또는 `GODEBUG=x509ignoreCN=0`.
  - Keychain에서 루트 인증서를 재신뢰.

### 20.6. Monitoring 노드 리소스 분석 (GitOps v0.6.0 · 14-Node)

- **증상**: Prometheus/Grafana/Alertmanager가 다른 노드에 스케줄링되어 Monitoring 전용 노드가 비게 됨.
- **원인**: Monitoring 노드에 `node-role.kubernetes.io/infrastructure=true:NoSchedule` taint가 있는데 Helm values에 toleration과 nodeSelector가 없었음.
- **해결**:
  - `kube-prometheus-stack` values에 공통 toleration/nodeSelector 추가(현재 dev/prod values에 반영).
  - 리소스 분석: t3.medium 기준 CPU 1780m 사용(89%), RAM 2.4Gi(65%)로 업스케일 불필요.

### 20.7. PostgreSQL FailedScheduling (GitOps v0.6.0 · 14-Node)

- **증상**: `postgres-0`가 `FailedScheduling: ... node(s) didn't match Pod's node selector`.
- **원인**: Storage 노드에 `workload=storage` 레이블이 누락되거나 잘못된 노드명을 사용해 Ansible 라벨링이 실패.
- **해결**:
  1. `kubectl get nodes -L workload`로 확인 후 `kubectl label nodes <node> workload=storage --overwrite`.
  2. 필요 시 `scripts/fix-node-labels.sh` 실행 또는 Ansible 레이블 단계 재실행.
  3. `kubectl rollout restart statefulset/postgres -n postgres`.

### 20.8. Prometheus Pending (CPU 부족) (GitOps v0.6.0 · 14-Node)

- **증상**: Prometheus StatefulSet이 Pending, 이벤트에 `1 Insufficient cpu`.
- **원인**: Monitoring 노드(t3.large, 2000m)가 이미 1130m를 사용 중인 상태에서 Prometheus가 1000m 요청 → 가용량 초과.
- **해결**:
  - CPU request를 500m로 낮춤(`kubectl patch prometheus ...` 또는 Helm values 수정).
  - 대안: Grafana를 다른 노드로 이동 또는 Monitoring 인스턴스를 t3.xlarge로 업그레이드.

### 20.9. Route53 → ALB 라우팅 수정 (GitOps v0.6.0 · 14-Node)

- **증상**: `growbin.app`, `argocd.growbin.app` 등이 Master Public IP를 직접 가리켜 TLS 종료·부하분산이 무력화.
- **해결**:
  - Terraform `aws_route53_record`를 ALB Alias로 교체하거나,
  - ALB Controller가 생성된 뒤 Ansible Playbook으로 Route53 레코드를 자동 업데이트.
- **예시**:
  ```hcl
  alias {
    name    = data.aws_lb.alb[0].dns_name
    zone_id = data.aws_lb.alb[0].zone_id
    evaluate_target_health = true
  }
  ```

### 20.10. CloudFront/ACM/VPC 삭제 장애 (GitOps v0.6.0 · 14-Node)

- **증상**: `force-destroy-all.sh` 실행 시 CloudFront Distribution을 감지하지 못해 ACM Certificate와 VPC 삭제가 20분 이상 지연.
- **원인**:
  - `aws cloudfront list-distributions` JMESPath가 복잡해 `E1GGDPUBLRQG59`를 찾지 못함.
  - CloudFront가 남아 있어 `arn:aws:acm:us-east-1:...` Certificate 삭제가 계속 pending.
- **해결**:
  1. `jq` 기반 단순 리스트로 Distribution ID를 검색하고 Disabled 상태 확인 후 명시적으로 삭제.
  2. Certificate `InUseBy`를 검사해 CloudFront 삭제 완료까지 대기.
  3. 필요 시 `scripts/utilities/manual-cleanup-cloudfront-acm.sh`로 수동 정리 후 Terraform destroy 재시도.

