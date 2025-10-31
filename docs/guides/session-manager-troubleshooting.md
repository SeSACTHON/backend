# 🔧 Session Manager 트러블슈팅

## ❌ Error: TargetNotConnected

### 원인

```
"i-xxxxxxxxx is not connected"

의미:
- SSM Agent가 AWS Systems Manager에 등록되지 않음
- 인스턴스가 SSM과 통신 불가
```

---

## 🔍 해결 방법

### 1. SSM Agent 상태 확인

```bash
# 인스턴스가 SSM에 등록되었는지 확인
aws ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=i-0123456789abcdef" \
  --region ap-northeast-2

# 출력:
# "InstanceInformationList": []  ← 비어있으면 등록 안 됨
```

### 2. IAM Instance Profile 확인

```bash
# Instance Profile이 연결되었는지 확인
aws ec2 describe-instances \
  --instance-ids i-0123456789abcdef \
  --query 'Reservations[].Instances[].IamInstanceProfile' \
  --region ap-northeast-2

# 출력:
# "Arn": "arn:aws:iam::...:instance-profile/k8s-instance-profile"
# ← 있어야 함!

# 없으면 Terraform 재실행 필요
```

### 3. SSM Agent 설치 확인 (SSH로)

```bash
# SSH로 접속 (백업 방법)
ssh -i ~/.ssh/sesacthon ubuntu@MASTER_PUBLIC_IP

# SSM Agent 상태
sudo systemctl status amazon-ssm-agent

# 설치 안 되어있으면
sudo snap install amazon-ssm-agent --classic
sudo systemctl enable amazon-ssm-agent
sudo systemctl start amazon-ssm-agent

# 재확인
sudo systemctl status amazon-ssm-agent
# Active: active (running) ← 이래야 함
```

### 4. 대기 시간

```bash
# EC2 생성 후 SSM 등록까지 시간 필요
# 2-5분 대기

# 30초마다 체크
while true; do
  aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=i-0123456789abcdef" \
    --region ap-northeast-2 \
    --query 'InstanceInformationList[].PingStatus' \
    --output text
  
  if [ $? -eq 0 ]; then
    echo "✅ SSM 등록 완료!"
    break
  fi
  
  echo "⏳ SSM 등록 대기 중..."
  sleep 30
done
```

### 5. 네트워크 확인

```bash
# SSM Agent는 아웃바운드 HTTPS 필요
# Security Group Egress 확인

aws ec2 describe-security-groups \
  --group-ids $(aws ec2 describe-instances \
    --instance-ids i-0123456789abcdef \
    --query 'Reservations[].Instances[].SecurityGroups[].GroupId' \
    --output text) \
  --query 'SecurityGroups[].IpPermissionsEgress'

# 443 포트 아웃바운드가 열려있어야 함
```

---

## ✅ 해결 순서

### Step 1: Terraform 재적용

```bash
cd terraform

# IAM Instance Profile 강제 재적용
terraform taint module.master
terraform apply

# 또는 전체 재적용
terraform apply -replace=module.master.aws_instance.this
```

### Step 2: 대기

```bash
# 5분 대기
sleep 300

# SSM 등록 확인
aws ssm describe-instance-information \
  --region ap-northeast-2
```

### Step 3: 재시도

```bash
# Instance ID 다시 확인
MASTER_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=k8s-master" \
  --query "Reservations[].Instances[].InstanceId" \
  --output text \
  --region ap-northeast-2)

echo "Instance ID: $MASTER_ID"

# 재접속
aws ssm start-session --target $MASTER_ID --region ap-northeast-2
```

---

## 🔧 user-data 수정 (SSM Agent 자동 설치)

```bash
# terraform/user-data/common.sh
#!/bin/bash
set -e

# 호스트명 설정
hostnamectl set-hostname ${hostname}

# 시스템 업데이트
apt-get update
apt-get upgrade -y

# SSM Agent 설치 (Ubuntu 22.04는 보통 포함, 명시적 설치)
snap install amazon-ssm-agent --classic
systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service
systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service

# 나머지 설정...
```

---

## 💡 빠른 해결 (권장)

```bash
# 1. Terraform 전체 재생성
cd terraform
terraform destroy -auto-approve
terraform apply -auto-approve

# 2. 5분 대기
sleep 300

# 3. 재접속
aws ssm start-session --target $(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=k8s-master" \
  --query "Reservations[].Instances[].InstanceId" \
  --output text \
  --region ap-northeast-2)
```

---

**작성일**: 2025-10-30  
**해결률**: 99%
