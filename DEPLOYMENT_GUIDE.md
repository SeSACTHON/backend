# 🚀 배포 가이드

> **4-Node Kubernetes 클러스터 + ALB + S3**  
> **Instagram-style Architecture**

## 📋 사전 준비

### 필수 도구

```bash
# AWS CLI
aws --version

# Terraform
terraform --version  # >= 1.0

# Ansible
ansible --version  # >= 2.14

# SSH Key
ls ~/.ssh/sesacthon
```

### AWS 설정

```bash
# AWS 자격증명
aws configure
# Region: ap-northeast-2

# S3 Backend (Terraform State)
aws s3 mb s3://sesacthon-terraform-state --region ap-northeast-2

# DynamoDB (State Lock)
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-northeast-2

# Route53 Hosted Zone
# growbin.app 도메인의 Hosted Zone이 이미 있어야 함
```

---

## 🚀 자동 배포

### 방법 1: 완전 자동 (추천)

```bash
cd /Users/mango/workspace/SeSACTHON/backend

# 확인 없이 전체 자동 실행
./scripts/auto-rebuild.sh

# 소요 시간: 약 40-50분
# - Terraform destroy: 5분
# - Terraform apply: 5-10분
# - Ansible playbook: 30-40분
```

### 방법 2: 대화형

```bash
# 각 단계마다 확인
./scripts/rebuild-cluster.sh

# 프롬프트:
# - 인프라 삭제 확인
# - Ansible 실행 확인
```

---

## 📊 배포 결과

### 생성되는 리소스

```
AWS:
✅ VPC (10.0.0.0/16)
✅ 3 Public Subnets
✅ Security Groups (K8s + VXLAN)
✅ EC2 4대:
   - Master: t3.large (8GB)
   - Worker-1: t3.medium (4GB)
   - Worker-2: t3.medium (4GB)
   - Storage: t3.large (8GB)
✅ Elastic IP (Master)
✅ Route53 DNS
✅ ACM Certificate (*.growbin.app)
✅ S3 Bucket (이미지 저장)

Kubernetes:
✅ kubeadm cluster (1M + 3W)
✅ Calico VXLAN CNI
✅ AWS Load Balancer Controller
✅ cert-manager
✅ Prometheus + Grafana
✅ ArgoCD
✅ RabbitMQ (HA 3-node)
✅ Metrics Server

비용: $185/월
- EC2: $180/월
- S3: ~$5/월
```

---

## 🔍 배포 검증

### 1. 노드 확인

```bash
# Master 접속
./scripts/connect-ssh.sh master

# 노드 상태
kubectl get nodes

# 예상:
# k8s-master    Ready   control-plane
# k8s-worker-1  Ready   <none>
# k8s-worker-2  Ready   <none>
# k8s-storage   Ready   <none>
```

### 2. Pod 확인

```bash
kubectl get pods -A

# 모든 Pod Running 확인
```

### 3. Ingress 확인

```bash
kubectl get ingress -A

# ALB DNS 확인
kubectl get ingress main-ingress -n default -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

### 4. S3 확인

```bash
# Terraform output
cd terraform
terraform output s3_bucket_info

# 버킷 존재 확인
aws s3 ls | grep sesacthon-images
```

---

## 🌐 Route53 업데이트

### ALB Alias 레코드 생성

```bash
# 1. ALB DNS 가져오기
ALB_DNS=$(kubectl get ingress main-ingress -n default -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo "ALB DNS: $ALB_DNS"

# 2. Route53 레코드 업데이트 (수동)
# AWS Console → Route53 → growbin.app
# - Type: A Record (Alias)
# - Name: growbin.app
# - Alias target: $ALB_DNS
# - Alias hosted zone: [ALB Zone ID]

# 또는 AWS CLI:
aws route53 change-resource-record-sets \
  --hosted-zone-id <ZONE_ID> \
  --change-batch file://route53-change.json
```

---

## 🎯 접속 테스트

```bash
# 1. ArgoCD
https://growbin.app/argocd

# 2. Grafana
https://growbin.app/grafana

# 3. API (서비스 배포 후)
https://growbin.app/api/v1/auth/login
https://growbin.app/api/v1/waste/analyze
```

---

## 🔧 트러블슈팅

### 헬스체크

```bash
# 원격 헬스체크
./scripts/remote-health-check.sh master

# 점수 90% 이상이면 정상
```

### 로그 확인

```bash
# Calico
kubectl logs -n kube-system -l k8s-app=calico-node

# ALB Controller
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
```

---

## 📚 참고 문서

- [구축 체크리스트](docs/guides/setup-checklist.md)
- [IaC 빠른 시작](docs/guides/iac-quick-start.md)
- [최종 아키텍처](docs/architecture/final-k8s-architecture.md)

---

**작성일**: 2025-10-31  
**버전**: 2.0 (4-node, Path-based routing, S3)

