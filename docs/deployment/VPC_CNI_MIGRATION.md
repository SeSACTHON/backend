# AWS VPC CNI 전환 가이드

## 📋 개요

이 문서는 Kubernetes 클러스터의 CNI 플러그인을 **Calico**에서 **AWS VPC CNI**로 전환하는 과정을 설명합니다.

## 🎯 전환 이유

### Calico의 문제점
- **Pod IP가 VPC CIDR 밖에 할당됨** (`192.168.0.0/16`)
- ALB가 Pod IP로 직접 통신 불가 (`target-type: ip` 사용 불가)
- `target-type: instance`로 우회 시 NodePort 필요 및 추가 홉 발생
- AWS 네이티브 통합 부족

### AWS VPC CNI의 장점
- **Pod IP가 VPC CIDR 내에서 할당됨** (`10.0.x.x`)
- ALB가 Pod에 직접 통신 가능 (`target-type: ip`)
- AWS Security Group을 Pod에 직접 적용 가능
- AWS 네이티브 통합 (ELB, NLB, ALB 등)
- 성능 향상 (Overlay 네트워크 오버헤드 없음)

---

## 🏗️ 아키텍처 변경

### Before (Calico)
```
VPC CIDR: 10.0.0.0/16
Pod CIDR: 192.168.0.0/16 (Overlay)

ALB → Worker Node (NodePort) → Pod
    (10.0.x.x)     (31xxx)    (192.168.x.x)
```

### After (AWS VPC CNI)
```
VPC CIDR: 10.0.0.0/16
Pod CIDR: 10.0.x.x (VPC 내)

ALB → Pod
    (10.0.x.x)
```

---

## 🚀 전환 프로세스

### 1. 자동 전환 (권장)

```bash
cd scripts
./switch-to-vpc-cni.sh
```

이 스크립트는 자동으로:
1. 현재 클러스터 설정 백업
2. 클러스터 완전 삭제
3. VPC CNI로 재구축
4. Pod IP 범위 검증

**소요 시간:** 15-20분

### 2. 수동 전환

#### Step 1: 백업
```bash
mkdir -p backup/pre-vpc-cni
ssh -i ~/.ssh/sesacthon ubuntu@52.79.238.50 "kubectl get nodes -o wide" > backup/pre-vpc-cni/nodes.txt
ssh -i ~/.ssh/sesacthon ubuntu@52.79.238.50 "kubectl get pods -A -o wide" > backup/pre-vpc-cni/pods.txt
ssh -i ~/.ssh/sesacthon ubuntu@52.79.238.50 "kubectl get ingress -A" > backup/pre-vpc-cni/ingress.txt
```

#### Step 2: 설정 변경
`ansible/inventory/group_vars/all.yml` 수정:
```yaml
# 네트워크 (AWS VPC CNI 사용)
cni_plugin: "vpc-cni"  # calico → vpc-cni로 변경
service_cidr: "10.96.0.0/12"
```

#### Step 3: 클러스터 삭제 및 재구축
```bash
cd scripts
./cleanup.sh
./build-cluster.sh
```

#### Step 4: Pod IP 검증
```bash
ssh -i ~/.ssh/sesacthon ubuntu@52.79.238.50 "kubectl get pods -A -o wide"
```

Pod IP가 VPC CIDR (`10.0.x.x`) 내에 있는지 확인합니다.

---

## ✅ 검증 체크리스트

### 1. CNI 설치 확인
```bash
ssh -i ~/.ssh/sesacthon ubuntu@52.79.238.50 "kubectl get daemonset -n kube-system aws-node"
```

예상 출력:
```
NAME       DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR
aws-node   4         4         4       4            4           <none>
```

### 2. Pod IP 범위 확인
```bash
# VPC CIDR 확인
cd terraform
terraform output vpc_cidr

# Pod IP 확인
ssh -i ~/.ssh/sesacthon ubuntu@52.79.238.50 "kubectl get pods -A -o wide | grep -v NAMESPACE | awk '{print \$7}' | head -20"
```

**모든 Pod IP가 VPC CIDR 내에 있어야 합니다.**

### 3. ALB 상태 확인
```bash
ssh -i ~/.ssh/sesacthon ubuntu@52.79.238.50 "kubectl get ingress -A"
```

ALB ADDRESS가 할당되었는지 확인 (3-5분 소요).

### 4. ALB Target Health 확인
AWS Console → EC2 → Target Groups → `k8s-...` 선택 → Targets 탭

**Status: healthy** 확인

### 5. 브라우저 테스트
```bash
curl -Lk https://growbin.app/
```

---

## 🔧 Troubleshooting

### Pod IP가 VPC 밖에 할당됨

**증상:**
```bash
kubectl get pods -A -o wide
# Pod IP: 192.168.x.x (VPC CIDR: 10.0.0.0/16)
```

**원인:** AWS VPC CNI가 제대로 설치되지 않음

**해결:**
```bash
# aws-node DaemonSet 확인
kubectl get daemonset aws-node -n kube-system

# 재설치
kubectl delete -f https://raw.githubusercontent.com/aws/amazon-vpc-cni-k8s/release-1.16/config/master/aws-k8s-cni.yaml
kubectl apply -f https://raw.githubusercontent.com/aws/amazon-vpc-cni-k8s/release-1.16/config/master/aws-k8s-cni.yaml

# 모든 Pod 재시작
kubectl delete pods --all -A
```

### ALB Target Unhealthy

**증상:** ALB Target Group의 Targets가 `unhealthy`

**원인:**
1. Security Group 규칙 누락
2. Health Check 경로 오류
3. Pod가 정상 동작하지 않음

**해결:**
```bash
# 1. Security Group 확인
# Worker Node SG에 ALB SG로부터 모든 트래픽 허용 필요

# 2. Target Group Health Check 확인
# AWS Console → EC2 → Target Groups → Health checks 탭

# 3. Pod 상태 확인
kubectl get pods -A
kubectl describe pod <pod-name> -n <namespace>
```

### ALB가 생성되지 않음

**증상:** Ingress ADDRESS가 비어 있음

**원인:**
1. IAM 권한 부족
2. ALB Controller Pod 오류

**해결:**
```bash
# ALB Controller 로그 확인
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller

# IAM 권한 확인
aws iam get-policy-version \
  --policy-arn arn:aws:iam::721622471953:policy/prod-alb-controller-policy \
  --version-id v1
```

---

## 📚 참고 자료

- [AWS VPC CNI 공식 문서](https://github.com/aws/amazon-vpc-cni-k8s)
- [AWS VPC CNI vs Calico 비교](https://docs.aws.amazon.com/eks/latest/userguide/pod-networking.html)
- [ALB Ingress Controller 가이드](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)

---

## 🎯 다음 단계

VPC CNI 전환이 완료되면:
1. ✅ ALB `target-type: ip` 사용 가능
2. ✅ Pod에 직접 Security Group 적용 가능
3. ✅ AWS 네이티브 네트워킹 최적화
4. ✅ 서비스 배포 (ArgoCD GitOps)

