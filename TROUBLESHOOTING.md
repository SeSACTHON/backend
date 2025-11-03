# 🔧 Kubernetes 클러스터 구축 트러블슈팅

> **작성일**: 2025-11-02  
> **브랜치**: feat/2-iac-terraform-ansible  
> **상태**: 실제 구축 과정에서 발생한 문제와 해결 방법 기록

---

## 📋 목차

1. [Terraform 명령 디렉토리 컨텍스트 오류](#1-terraform-명령-디렉토리-컨텍스트-오류)
2. [RabbitMQ Namespace 생성 실패](#2-rabbitmq-namespace-생성-실패)
3. [Prometheus Retention 설정 오류](#3-prometheus-retention-설정-오류)
4. [Prometheus Pod 대기 타이밍 문제](#4-prometheus-pod-대기-타이밍-문제)
5. [RabbitMQ PVC 바인딩 실패 - StorageClass 없음](#5-rabbitmq-pvc-바인딩-실패---storageclass-없음)
6. [PVC Provisioning 실패 - IAM 권한 부족](#6-pvc-provisioning-실패---iam-권한-부족)
7. [VPC 삭제 장시간 대기 - Kubernetes 생성 리소스 미삭제](#7-vpc-삭제-장시간-대기---kubernetes-생성-리소스-미삭제)

---

## 1. Terraform 명령 디렉토리 컨텍스트 오류

### 🐛 문제

**에러 메시지**:
```
Backend initialization required, please run "terraform init"
Reason: Unsetting the previously set backend "s3"
Terraform initialized in an empty directory!
```

**발생 시점**: `rebuild-cluster.sh` 실행 시 Ansible inventory 생성 단계

### 🔍 원인

`provision.sh` 스크립트에서 `terraform output` 명령 실행 시:
- 현재 디렉토리가 terraform 디렉토리가 아님
- 잘못된 디렉토리에서 terraform 명령 실행
- Backend 초기화 오류 발생

### ✅ 해결

**커밋**: `9211bb5` - fix: Fix terraform command directory context in all scripts

**수정 파일**:
1. `scripts/provision.sh` (42번째 줄)
2. `scripts/rebuild-cluster.sh` (106-108번째 줄)
3. `scripts/quick-rebuild.sh`
4. `scripts/destroy.sh`

**변경 내용**:

```bash
# Before
terraform output -raw ansible_inventory > "$ANSIBLE_DIR/inventory/hosts.ini"

# After (방법 1: -chdir 옵션)
terraform -chdir="$TERRAFORM_DIR" output -raw ansible_inventory > "$ANSIBLE_DIR/inventory/hosts.ini"

# After (방법 2: 명시적 cd + 디버그)
cd "$TERRAFORM_DIR"
echo "📍 현재 디렉토리: $(pwd)"
terraform output -raw ansible_inventory > "$ANSIBLE_DIR/inventory/hosts.ini"
```

**교훈**:
- Terraform 명령은 항상 terraform 디렉토리에서 실행
- `-chdir` 옵션 사용 또는 명시적 `cd` 필요
- 디버그 메시지로 현재 디렉토리 확인

---

## 2. RabbitMQ Namespace 생성 실패

### 🐛 문제

**에러 메시지**:
```
error: unknown shorthand flag: 'f' in -f
See 'kubectl create namespace --help' for usage.
```

**발생 시점**: RabbitMQ 설치 중 namespace 생성

### 🔍 원인

Ansible `command` 모듈에서 파이프(`|`) 처리 불가:
```yaml
# 잘못된 방법
- name: RabbitMQ namespace 생성
  command: kubectl create namespace messaging --dry-run=client -o yaml | kubectl apply -f -
```

Ansible `command` 모듈은 파이프를 문자열로 처리하여 `|`를 인자로 전달함

### ✅ 해결

**커밋**: `bc728fd` - fix: Change command to shell for kubectl pipe in RabbitMQ namespace creation

**변경 내용**:
```yaml
# After
- name: RabbitMQ namespace 생성
  shell: kubectl create namespace {{ rabbitmq_namespace }} --dry-run=client -o yaml | kubectl apply -f -
```

**적용 파일**:
- `ansible/roles/rabbitmq/tasks/main.yml`
- `ansible/playbooks/08-monitoring.yml`

**교훈**:
- 파이프(`|`), 리다이렉션(`>`), 환경변수(`$VAR`) 사용 시 → `shell` 모듈
- 단순 명령어만 실행 시 → `command` 모듈

---

## 3. Prometheus Retention 설정 오류

### 🐛 문제

**에러 메시지**:
```
coalesce.go:301: warning: destination for kube-prometheus-stack.prometheus.prometheusSpec.retention is a table. Ignoring non-table value (10d)

Error: spec.retention: Invalid value: "map[size:80% time:7d]": 
spec.retention in body should match '^(0|(([0-9]+)y)?(([0-9]+)w)?(([0-9]+)d)?(([0-9]+)h)?(([0-9]+)m)?(([0-9]+)s)?(([0-9]+)ms)?)$'
```

**발생 시점**: Prometheus Helm Chart 설치

### 🔍 원인

잘못된 설정:
```yaml
--set prometheus.prometheusSpec.retention.time=7d
--set prometheus.prometheusSpec.retention.size=80%
```

Prometheus는 `retention`을 **단순 문자열**로 기대하는데, `.time`과 `.size`로 나눠서 설정하면 **map 객체**로 인식됨

### ✅ 해결

**커밋**: `b8d4f44` - fix: Correct Prometheus retention configuration format

**변경 내용**:
```yaml
# Before (잘못됨)
--set prometheus.prometheusSpec.retention.time=7d
--set prometheus.prometheusSpec.retention.size=80%

# After (올바름)
--set prometheus.prometheusSpec.retention=7d
--set prometheus.prometheusSpec.retentionSize=40GB
```

**파일**: `ansible/playbooks/08-monitoring.yml`

**설명**:
- `retention`: 시간 기반 보관 기간 (문자열: `7d`, `30d`, `1y`)
- `retentionSize`: 용량 기반 보관 제한 (절대값: `40GB`, `100GB`)
- 50GB PVC의 80% = 40GB로 계산하여 설정

**교훈**:
- Helm Chart values는 공식 문서 확인 필수
- 백분율(%)은 지원하지 않을 수 있음 → 절대값 사용
- map vs string 타입 주의

---

## 4. Prometheus Pod 대기 타이밍 문제

### 🐛 문제

**에러 메시지**:
```
error: no matching resources found
```

**발생 시점**: Prometheus 설치 직후 Pod 대기 단계

### 🔍 원인

1. `helm install` 명령이 완료되어도 **Pod가 즉시 생성되지 않음**
2. Prometheus Operator가 먼저 설치되고 CRD 생성
3. CRD 기반으로 Prometheus StatefulSet 생성
4. StatefulSet이 Pod 생성
5. `kubectl wait` 실행 시 아직 Pod가 없음

**타임라인**:
```
0s   → Helm install 시작
10s  → Operator Pod 생성
20s  → CRD 생성
40s  → Prometheus StatefulSet 생성
60s  → Prometheus Pod 생성 시작 ← kubectl wait 실행 (너무 빠름!)
120s → Prometheus Pod Ready
```

### ✅ 해결

**커밋**: `df7c3da` - fix: Add robust waiting logic for Prometheus deployment

**변경 내용**:
```yaml
# 다단계 대기 로직 추가

1. Operator 및 CRD 생성 대기 (60초)
   - sleep 60

2. StatefulSet 생성 확인 (최대 300초)
   - for loop로 statefulset 존재 여부 확인
   - 10초마다 체크, 최대 30회

3. Pod Ready 대기
   - kubectl wait (실패해도 계속 진행)
   - ignore_errors: yes

4. 모든 Pods 상태 확인
   - kubectl get pods -n monitoring
   - 설치 결과 검증
```

**파일**: `ansible/playbooks/08-monitoring.yml`

**교훈**:
- Operator 패턴에서는 리소스 생성에 시간이 걸림
- 충분한 대기 시간 확보 필요
- `ignore_errors`로 graceful handling
- 최종 상태 확인으로 실제 결과 검증

---

## 5. RabbitMQ PVC 바인딩 실패

### 🐛 문제

**에러 메시지**:
```
Warning  FailedScheduling  
0/4 nodes are available: pod has unbound immediate PersistentVolumeClaims.
```

**Pod 상태**:
```
Name:           rabbitmq-0
Status:         Pending
Node:           <none>
Node-Selectors: workload=storage

Events:
  pod has unbound immediate PersistentVolumeClaims
```

**발생 시점**: RabbitMQ StatefulSet 생성 후

### 🔍 원인 분석

**Self-Managed Kubernetes의 특징**:
- EKS는 기본 StorageClass (gp2) 제공 ✅
- Self-Managed는 **StorageClass가 없음** ❌

**RabbitMQ 요구사항**:
```yaml
persistence:
  enabled: true
  size: 20Gi
  storageClass: gp3  # ← 이 StorageClass가 없음!
```

**PVC가 생성되지만 바인딩 안 됨**:
```bash
kubectl get pvc -n messaging
# NAME              STATUS    VOLUME   CAPACITY
# data-rabbitmq-0   Pending   -        -
```

### ✅ 해결

**커밋**: `80a7f9c` - feat: Add AWS EBS CSI Driver and gp3 StorageClass

**새 파일**: `ansible/playbooks/05-1-ebs-csi-driver.yml`

**설치 내용**:

#### 1. AWS EBS CSI Driver 설치
```yaml
kubectl apply -k "github.com/kubernetes-sigs/aws-ebs-csi-driver/deploy/kubernetes/overlays/stable/?ref=release-1.28"
```

**역할**:
- AWS EBS 볼륨을 동적으로 프로비저닝
- PVC 요청 → EBS 볼륨 자동 생성 → Pod에 연결

#### 2. gp3 StorageClass 생성
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
parameters:
  type: gp3           # 최신 세대 (gp2보다 20% 저렴)
  encrypted: "true"   # 암호화 활성화
  iops: "3000"        # 기본 IOPS
  throughput: "125"   # 125 MiB/s
volumeBindingMode: WaitForFirstConsumer  # Pod 스케줄링 후 볼륨 생성
allowVolumeExpansion: true               # 볼륨 확장 가능
reclaimPolicy: Delete                    # PVC 삭제 시 볼륨도 삭제
```

#### 3. 설치 순서 변경

**Before**:
```
1. Add-ons
2. ALB Controller
3. ArgoCD
4. Monitoring → PVC 필요 (실패!)
5. RabbitMQ → PVC 필요 (실패!)
```

**After**:
```
1. Add-ons
2. EBS CSI Driver ⭐ (먼저 설치)
3. gp3 StorageClass ⭐ (먼저 생성)
4. ALB Controller
5. ArgoCD
6. Monitoring → PVC 생성 성공! ✅
7. RabbitMQ → PVC 생성 성공! ✅
```

### 📊 PVC 생성 과정

**설치 후 프로세스**:
```
1. RabbitMQ StatefulSet 생성
   └─> PVC 요청 (20Gi, storageClass: gp3)

2. EBS CSI Driver가 PVC 감지
   └─> AWS API 호출 → EBS 볼륨 생성

3. EBS 볼륨 생성 완료
   └─> PVC 상태: Pending → Bound

4. PVC 바인딩 완료
   └─> RabbitMQ Pod 스케줄링 시작

5. Pod가 노드에 배치
   └─> EBS 볼륨 마운트

6. Pod Running!
```

**생성되는 PVC**:
```
Prometheus:
  - prometheus-prometheus-kube-prometheus-prometheus-db-0
  - 50Gi, gp3

RabbitMQ (HA 3-node):
  - data-rabbitmq-0  (20Gi, gp3)
  - data-rabbitmq-1  (20Gi, gp3)
  - data-rabbitmq-2  (20Gi, gp3)
```

**총 EBS 볼륨**: 4개, 110GB

### 💡 핵심 교훈

#### Self-Managed vs EKS 차이점

| 항목 | EKS | Self-Managed |
|------|-----|--------------|
| **기본 StorageClass** | ✅ gp2 제공 | ❌ 없음 |
| **CSI Driver** | ✅ 자동 설치 | ❌ 수동 설치 필요 |
| **PVC 자동 프로비저닝** | ✅ 즉시 가능 | ❌ CSI Driver 후 가능 |

#### 필수 체크리스트

Self-Managed Kubernetes에서 StatefulSet 사용 시:

- [ ] CSI Driver 설치 (AWS EBS, NFS 등)
- [ ] StorageClass 생성
- [ ] 기본 StorageClass 지정
- [ ] PVC 생성 테스트
- [ ] StatefulSet 배포

**순서 엄수**: CSI Driver → StorageClass → StatefulSet

### 🔧 검증 명령어

```bash
# StorageClass 확인
kubectl get storageclass

# PVC 상태 확인
kubectl get pvc -A

# EBS 볼륨 상세 정보
kubectl describe pvc data-rabbitmq-0 -n messaging

# CSI Driver Pod 상태
kubectl get pods -n kube-system | grep ebs-csi
```

---

## 6. PVC Provisioning 실패 - IAM 권한 부족

### 🐛 문제

**에러 메시지**:
```
Warning  ProvisioningFailed  
failed to provision volume with StorageClass "gp3": 
rpc error: code = Internal desc = Could not create volume "pvc-xxx": 
could not create volume in EC2: UnauthorizedOperation: 
You are not authorized to perform this operation. 
User: arn:aws:sts::721622471953:assumed-role/prod-k8s-ec2-ssm-role/i-xxx 
is not authorized to perform: ec2:CreateVolume on resource: arn:aws:ec2:ap-northeast-2:721622471953:volume/* 
because no identity-based policy allows the ec2:CreateVolume action.
```

**PVC 상태**:
```bash
kubectl get pvc -A
# NAMESPACE    NAME                 STATUS    
# messaging    data-rabbitmq-0      Pending (20Gi, gp3)
# monitoring   prometheus-xxx-0     Pending (50Gi, gp3)
```

**발생 시점**: Terraform apply 후 RabbitMQ, Prometheus 설치 시

### 🔍 원인 분석

**IAM Role에 EBS 권한 없음**:

현재 IAM Role (`prod-k8s-ec2-ssm-role`):
```json
{
  "Policies": [
    "AmazonSSMManagedInstanceCore",      // ✅ SSM 권한만
    "CloudWatchAgentServerPolicy"        // ✅ CloudWatch 권한만
  ]
}
```

**EBS CSI Driver의 동작**:
1. PVC 생성 요청 감지
2. EC2 인스턴스의 IAM Role 사용
3. AWS API 호출: `ec2:CreateVolume`
4. ❌ **UnauthorizedOperation** - 권한 없음!

**EBS CSI Driver가 필요한 권한**:
- `ec2:CreateVolume` ⭐ (볼륨 생성)
- `ec2:DeleteVolume` (볼륨 삭제)
- `ec2:AttachVolume` (Pod에 연결)
- `ec2:DetachVolume` (Pod에서 분리)
- `ec2:DescribeVolumes` (볼륨 정보)
- `ec2:CreateTags` (태그 생성)
- 기타 EBS 관련 권한

### ✅ 해결

**커밋**: `6b48c4d` - fix: Add EBS CSI Driver IAM permissions for dynamic volume provisioning

**파일**: `terraform/iam.tf`

**추가된 IAM Policy**:
```hcl
resource "aws_iam_role_policy" "ebs_csi_driver" {
  name = "${var.environment}-k8s-ebs-csi-driver-policy"
  role = aws_iam_role.ec2_ssm_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateVolume",           # PVC 생성
          "ec2:DeleteVolume",           # PVC 삭제
          "ec2:AttachVolume",           # Pod 마운트
          "ec2:DetachVolume",           # Pod 언마운트
          "ec2:DescribeVolumes",        # 볼륨 조회
          "ec2:DescribeVolumeStatus",   # 상태 확인
          "ec2:DescribeVolumeAttribute",# 속성 확인
          "ec2:CreateSnapshot",         # 스냅샷 생성
          "ec2:DeleteSnapshot",         # 스냅샷 삭제
          "ec2:DescribeSnapshots",      # 스냅샷 조회
          "ec2:DescribeSnapshotAttribute",
          "ec2:ModifyVolume",           # 볼륨 확장
          "ec2:DescribeVolumesModifications",
          "ec2:CreateTags",             # 태그 추가
          "ec2:DescribeTags",           # 태그 조회
          "ec2:DescribeInstances"       # 인스턴스 정보
        ]
        Resource = "*"
      }
    ]
  })
}
```

**적용 명령**:
```bash
cd /Users/mango/workspace/SeSACTHON/backend/terraform
terraform apply -auto-approve
```

### 📊 적용 후 과정

**Timeline**:
```
T+0s   : terraform apply 완료
T+30s  : IAM 권한 AWS 서비스 전파
T+60s  : EC2 Instance Metadata 갱신
T+90s  : EBS CSI Controller가 새 credentials 획득
T+120s : PVC 재시도 → 성공! → Bound ✅
```

**확인 방법**:
```bash
# 1. IAM 권한 확인 (Master 노드)
aws sts get-caller-identity

# 2. EBS 권한 테스트
aws ec2 describe-volumes --region ap-northeast-2 --max-results 1

# 3. PVC 상태 실시간 확인
kubectl get pvc -A -w

# 4. EBS CSI Controller 로그 확인
kubectl logs -n kube-system -l app=ebs-csi-controller --tail=50
```

**빠른 적용**:
```bash
# EBS CSI Controller 재시작 (즉시 새 credentials 적용)
kubectl rollout restart deployment ebs-csi-controller -n kube-system
```

### 💡 핵심 교훈

#### Self-Managed Kubernetes의 IAM 관리

**EKS**:
- ✅ IRSA (IAM Roles for Service Accounts) 사용
- ✅ Pod별 세분화된 권한
- ✅ EBS CSI Driver에 자동 권한 부여

**Self-Managed**:
- ❌ IRSA 없음 (직접 구현 필요)
- ❌ 모든 Pod가 EC2 Instance IAM Role 공유
- ❌ EBS CSI Driver 권한 직접 추가 필요 ⭐

#### IAM 권한 설계 원칙

**최소 권한 원칙**:
```
❌ Administrator Access (너무 광범위)
✅ 필요한 ec2:* 권한만 명시적 부여
✅ Resource: "*" (EBS의 경우 불가피)
```

**필수 CSI Driver 권한**:
- EBS CSI Driver → ec2:CreateVolume 등
- EFS CSI Driver → elasticfilesystem:CreateFileSystem 등
- FSx CSI Driver → fsx:CreateFileSystem 등

#### 실전 체크리스트

Self-Managed K8s에서 CSI Driver 사용 전:

- [ ] CSI Driver 설치
- [ ] StorageClass 생성
- [ ] **IAM 권한 확인** ⭐ (중요!)
- [ ] 테스트 PVC 생성
- [ ] PVC Events 확인
- [ ] 실제 StatefulSet 배포

**순서**: CSI Driver → IAM 권한 → StorageClass → 테스트 → 프로덕션

### 🔧 검증 명령어

```bash
# IAM 권한 전파 확인 (Master 노드)
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/prod-k8s-ec2-ssm-role | jq .Expiration

# EBS 권한 테스트
aws ec2 describe-volumes --region ap-northeast-2 --max-results 1

# PVC 생성 성공 확인
kubectl get pvc -A

# EBS 볼륨 실제 생성 확인 (AWS CLI)
aws ec2 describe-volumes \
  --filters "Name=tag:kubernetes.io/created-for/pvc/name,Values=data-rabbitmq-0" \
  --region ap-northeast-2

# PVC → PV → EBS 볼륨 매핑 확인
kubectl get pv
```

---

## 7. VPC 삭제 장시간 대기 - Kubernetes 생성 리소스 미삭제

### 🐛 문제

**증상**:
```
module.vpc.aws_vpc.main: Still destroying... [id=vpc-004d44bcda91cd06b, 6m10s elapsed]
```

**발생 시점**: `terraform destroy` 실행 중 VPC 삭제 단계에서 6분 이상 대기

### 🔍 원인

**Kubernetes가 동적으로 생성한 AWS 리소스**들이 VPC에 남아있어 삭제 불가:

1. **EBS 볼륨 (EBS CSI Driver가 생성)**
   - Prometheus PVC: 50GB × 3개
   - RabbitMQ PVC: 20GB × 3개
   - 총 6개, 210GB

2. **보안 그룹 (ALB Controller가 생성)**
   - `k8s-growbinalb-*` (Load Balancer용)
   - `k8s-traffic-sesacthon-*` (Backend용)

**왜 Terraform이 삭제하지 못하나?**
- Terraform State에 없는 리소스 (Kubernetes가 생성)
- Terraform은 자신이 생성하지 않은 리소스를 자동 삭제하지 않음
- VPC는 종속 리소스가 모두 삭제되어야 삭제 가능

### ✅ 해결

**즉시 해결 (이미 terraform destroy 실행 중인 경우)**:

```bash
# 1. Kubernetes가 생성한 EBS 볼륨 확인 및 삭제
aws ec2 describe-volumes \
  --filters "Name=tag:kubernetes.io/created-for/pvc/name,Values=*" \
  --region ap-northeast-2 \
  --query 'Volumes[*].[VolumeId,State,Size,Tags[?Key==`kubernetes.io/created-for/pvc/name`].Value|[0]]' \
  --output table

# 볼륨 ID 복사 후 삭제
aws ec2 delete-volume --volume-id vol-xxxxx --region ap-northeast-2
aws ec2 delete-volume --volume-id vol-yyyyy --region ap-northeast-2
# ... (모든 볼륨 삭제)

# 2. Kubernetes가 생성한 보안 그룹 확인 및 삭제
aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=vpc-004d44bcda91cd06b" \
  --region ap-northeast-2 \
  --query 'SecurityGroups[?GroupName!=`default`].[GroupId,GroupName,Description]' \
  --output table

# 보안 그룹 ID 복사 후 삭제
aws ec2 delete-security-group --group-id sg-xxxxx --region ap-northeast-2
aws ec2 delete-security-group --group-id sg-yyyyy --region ap-northeast-2

# 3. terraform destroy 재시도 또는 대기
terraform destroy -auto-approve
```

**올바른 삭제 순서 (향후)**:

```bash
# 1단계: Kubernetes 리소스 먼저 삭제
echo "🧹 Kubernetes 리소스 정리..."

# Ingress 삭제 (ALB 및 보안 그룹 제거)
kubectl delete ingress --all -A

# PVC 삭제 (EBS 볼륨 제거)
kubectl delete pvc --all -A

# Helm Release 삭제
helm uninstall kube-prometheus-stack -n monitoring
helm uninstall rabbitmq -n messaging

# 2단계: AWS 리소스 정리 대기 (중요!)
echo "⏳ AWS 리소스 정리 대기 중..."
sleep 60

# 3단계: 수동 생성 리소스 확인
echo "🔍 남은 리소스 확인..."
aws ec2 describe-volumes \
  --filters "Name=tag:kubernetes.io/created-for/pvc/name,Values=*" \
  --region ap-northeast-2 \
  --query 'Volumes[*].VolumeId' \
  --output text

# 4단계: Terraform 인프라 삭제
echo "🗑️  Terraform 인프라 삭제..."
cd terraform
terraform destroy -auto-approve
```

### 💡 자동화 스크립트

**파일**: `scripts/destroy-with-cleanup.sh` (새로 생성 권장)

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

echo "🧹 Kubernetes 리소스 정리 중..."

# Ingress 삭제 (ALB 제거)
kubectl delete ingress --all -A || true

# PVC 삭제 (EBS 볼륨 제거)
kubectl delete pvc --all -A || true

# Monitoring 삭제
helm uninstall kube-prometheus-stack -n monitoring || true

# RabbitMQ 삭제
helm uninstall rabbitmq -n messaging || true

echo "⏳ AWS 리소스 정리 대기 (60초)..."
sleep 60

echo "🔍 남은 Kubernetes 생성 리소스 확인..."

# EBS 볼륨 강제 삭제
VOLUMES=$(aws ec2 describe-volumes \
  --filters "Name=tag:kubernetes.io/created-for/pvc/name,Values=*" \
  --region ap-northeast-2 \
  --query 'Volumes[*].VolumeId' \
  --output text)

if [ -n "$VOLUMES" ]; then
  echo "⚠️  남은 EBS 볼륨 발견, 삭제 중..."
  for vol in $VOLUMES; do
    echo "  - 삭제: $vol"
    aws ec2 delete-volume --volume-id $vol --region ap-northeast-2 || true
  done
fi

# 보안 그룹 강제 삭제 (k8s-* 패턴)
SG_IDS=$(aws ec2 describe-security-groups \
  --filters "Name=tag:kubernetes.io/cluster/prod-sesacthon,Values=*" \
  --region ap-northeast-2 \
  --query 'SecurityGroups[*].GroupId' \
  --output text)

if [ -n "$SG_IDS" ]; then
  echo "⚠️  남은 보안 그룹 발견, 삭제 중..."
  for sg in $SG_IDS; do
    echo "  - 삭제: $sg"
    aws ec2 delete-security-group --group-id $sg --region ap-northeast-2 || true
  done
fi

echo "🗑️  Terraform 인프라 삭제..."
cd "$TERRAFORM_DIR"
terraform destroy -auto-approve

echo "✅ 완전 삭제 완료!"
```

### 📊 삭제 프로세스

**잘못된 방법 (현재 문제)**:
```
1. terraform destroy 실행
   └─> VPC 삭제 시도
       └─> ❌ 실패 (EBS 볼륨, 보안 그룹 남아있음)
           └─> 무한 대기...
```

**올바른 방법**:
```
1. Kubernetes 리소스 삭제
   ├─> Ingress 삭제 (ALB, 보안 그룹 제거)
   ├─> PVC 삭제 (EBS 볼륨 제거)
   └─> Helm Release 삭제

2. AWS 리소스 정리 대기 (60초)
   └─> AWS API 비동기 처리 완료 대기

3. 잔여 리소스 확인 및 수동 삭제
   ├─> aws ec2 describe-volumes
   └─> aws ec2 delete-volume

4. terraform destroy 실행
   └─> ✅ 성공 (종속 리소스 없음)
```

### 🔍 리소스 확인 명령어

```bash
# 1. VPC에 연결된 모든 ENI 확인
aws ec2 describe-network-interfaces \
  --filters "Name=vpc-id,Values=vpc-xxxxx" \
  --region ap-northeast-2

# 2. VPC에 연결된 보안 그룹 확인
aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=vpc-xxxxx" \
  --region ap-northeast-2

# 3. Kubernetes가 생성한 EBS 볼륨 확인
aws ec2 describe-volumes \
  --filters "Name=tag-key,Values=kubernetes.io/created-for/pvc/name" \
  --region ap-northeast-2

# 4. VPC에 연결된 로드밸런서 확인
aws elbv2 describe-load-balancers \
  --region ap-northeast-2 \
  --query 'LoadBalancers[?VpcId==`vpc-xxxxx`]'

# 5. NAT Gateway 확인
aws ec2 describe-nat-gateways \
  --filter "Name=vpc-id,Values=vpc-xxxxx" \
  --region ap-northeast-2
```

### 💡 핵심 교훈

#### Kubernetes와 Terraform의 리소스 관리 차이

**Terraform 관리 리소스**:
- VPC, Subnet, IGW, Route Table
- EC2 Instance
- IAM Role/Policy
- Security Groups (Terraform으로 생성한 것만)

**Kubernetes 관리 리소스** (Terraform State 밖):
- EBS 볼륨 (PVC → EBS CSI Driver → CreateVolume)
- 보안 그룹 (Ingress → ALB Controller → CreateSecurityGroup)
- Load Balancer (Ingress → ALB Controller → CreateLoadBalancer)
- ENI (Service type=LoadBalancer)

#### Self-Managed K8s 삭제 체크리스트

삭제 전 필수 확인:

- [ ] 모든 Ingress 삭제 (`kubectl delete ingress --all -A`)
- [ ] 모든 PVC 삭제 (`kubectl delete pvc --all -A`)
- [ ] 모든 Service type=LoadBalancer 삭제
- [ ] Helm Release 삭제
- [ ] 60초 대기 (AWS 리소스 정리)
- [ ] 잔여 리소스 확인 (`aws ec2 describe-volumes`, etc.)
- [ ] Terraform destroy 실행

**순서 엄수**: Kubernetes → 대기 → 확인 → Terraform

### 🎯 예방 방법

#### 1. 삭제 스크립트 사용

```bash
# destroy.sh 대신 destroy-with-cleanup.sh 사용
./scripts/destroy-with-cleanup.sh
```

#### 2. CI/CD Pipeline에 추가

```yaml
# .github/workflows/destroy.yml
- name: Clean Kubernetes Resources
  run: |
    kubectl delete ingress --all -A
    kubectl delete pvc --all -A
    helm uninstall --all -A
    sleep 60

- name: Terraform Destroy
  run: terraform destroy -auto-approve
```

#### 3. Terraform Lifecycle 관리

```hcl
# 향후 개선: Terraform으로 Helm Release 관리
resource "helm_release" "rabbitmq" {
  # ...
  
  # Terraform destroy 시 자동 삭제
  lifecycle {
    prevent_destroy = false
  }
}
```

---

## 📊 해결 요약

| 문제 | 원인 | 해결 | 커밋 |
|------|------|------|------|
| Terraform 디렉토리 오류 | 잘못된 working directory | `-chdir` 옵션 추가 | `9211bb5` |
| Namespace 생성 실패 | command 모듈에서 파이프 불가 | shell 모듈로 변경 | `bc728fd` |
| Prometheus retention 오류 | map 대신 string 필요 | 설정 형식 수정 | `b8d4f44` |
| Prometheus Pod 타이밍 | 리소스 생성 전 wait 실행 | 다단계 대기 로직 | `df7c3da` |
| RabbitMQ PVC 바인딩 실패 | StorageClass 없음 | EBS CSI Driver 설치 | `80a7f9c` |
| PVC Provisioning 실패 | IAM 권한 부족 | EBS CSI 권한 추가 | `6b48c4d` |
| **VPC 삭제 장시간 대기** | **Kubernetes 생성 리소스 미삭제** | **수동 리소스 정리 후 destroy** | **수동 해결** |

---

## 🎯 모범 사례

### 1. **스크립트 작성**
- 현재 디렉토리 항상 확인 (`pwd`)
- 명시적 경로 사용 (`-chdir` 또는 `cd`)
- 에러 핸들링 (`set -e`, exit codes)

### 2. **Ansible Playbook**
- 파이프/리다이렉션 → `shell` 모듈
- 단순 명령 → `command` 모듈
- 멱등성 확보 (`--dry-run`, `changed_when`)

### 3. **Operator 패턴**
- 충분한 대기 시간 (60초+)
- 리소스 생성 확인 후 다음 단계
- `ignore_errors` + 최종 상태 확인

### 4. **Self-Managed K8s**
- StorageClass 먼저 준비
- CSI Driver 설치 확인
- PVC 테스트 후 StatefulSet 배포

---

## 📚 참고 자료

- [AWS EBS CSI Driver](https://github.com/kubernetes-sigs/aws-ebs-csi-driver)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [Ansible Command vs Shell](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/command_module.html)
- [Kubernetes StorageClass](https://kubernetes.io/docs/concepts/storage/storage-classes/)

---

**마지막 업데이트**: 2025-11-02  
**총 해결 문제**: 7개  
**총 커밋**: 6개 (1개 수동 해결)  
**상태**: ✅ 모든 문제 해결 완료

---

## ⚡ 빠른 참조

### 문제별 핵심 포인트

1. **Terraform**: `-chdir` 옵션 사용 또는 명시적 `cd`
2. **Ansible**: 파이프 사용 시 `shell` 모듈 필수
3. **Prometheus**: `retention`은 문자열, `retentionSize`는 절대값
4. **Operator 패턴**: 충분한 대기 시간 + 다단계 검증
5. **StorageClass**: Self-Managed는 CSI Driver 수동 설치 필수
6. **IAM 권한**: EBS CSI Driver에 ec2:CreateVolume 등 권한 추가
7. **VPC 삭제**: Kubernetes 리소스 먼저 삭제 → 대기 → Terraform destroy

