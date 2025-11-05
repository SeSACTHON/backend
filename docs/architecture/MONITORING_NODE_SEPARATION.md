# Monitoring 노드 분리 (5-Node 클러스터)

> 날짜: 2025-11-04  
> 목적: Prometheus + Grafana를 전용 노드로 분리하여 독립적인 모니터링 환경 구축

---

## 🎯 변경 사항 요약

### Before (4 Nodes)

```
├─ Master (t3.large, 8GB)
│  └─ Control Plane
├─ Worker-1 (t3.medium, 4GB)
│  └─ Application Pods + Grafana + Prometheus ⚠️
├─ Worker-2 (t3.medium, 4GB)
│  └─ Celery Workers
└─ Storage (t3.large, 8GB)
   └─ RabbitMQ + PostgreSQL + Redis
```

**문제점**:
- ❌ Grafana/Prometheus가 Worker Node에서 Application과 리소스 경합
- ❌ Monitoring 부하가 Application에 영향
- ❌ 독립적인 확장 불가

---

### After (5 Nodes)

```
├─ Master (t3.large, 8GB)
│  └─ Control Plane
├─ Worker-1 (t3.medium, 4GB)
│  └─ Application Pods ✅
├─ Worker-2 (t3.medium, 4GB)
│  └─ Celery Workers ✅
├─ Storage (t3.large, 8GB)
│  └─ RabbitMQ + PostgreSQL + Redis ✅
└─ Monitoring (t3.medium, 4GB) ⭐ NEW
   └─ Prometheus + Grafana + Alertmanager ✅
```

**장점**:
- ✅ Monitoring 전용 노드로 격리
- ✅ Application과 Monitoring 리소스 완전 분리
- ✅ 독립적인 확장 가능
- ✅ 모니터링 성능 최적화

---

## 📊 클러스터 구성 비교

| 항목 | Before (4 Nodes) | After (5 Nodes) | 변화 |
|------|-----------------|----------------|------|
| **총 노드 수** | 4 | 5 | +1 |
| **총 vCPU** | 8 | 10 | +2 |
| **총 메모리** | 24GB | 28GB | +4GB |
| **월 비용** | $180 | $210 | +$30 |
| **Monitoring 격리** | ❌ | ✅ | ⭐ |

---

## 🔧 변경된 파일

### 1. Terraform: `terraform/main.tf`

**추가된 모듈**:
```hcl
# EC2 Instances - Monitoring (Prometheus + Grafana)
module "monitoring" {
  source = "./modules/ec2"
  
  instance_name         = "k8s-monitoring"
  instance_type         = "t3.medium"  # 4GB (Prometheus + Grafana)
  ami_id                = data.aws_ami.ubuntu.id
  subnet_id             = module.vpc.public_subnet_ids[1]  # Same AZ as Worker-1
  security_group_ids    = [module.security_groups.worker_sg_id]
  key_name              = aws_key_pair.k8s.key_name
  iam_instance_profile  = aws_iam_instance_profile.k8s.name
  
  root_volume_size = 60  # Prometheus TSDB + Grafana
  root_volume_type = "gp3"
  
  user_data = templatefile("${path.module}/user-data/common.sh", {
    hostname = "k8s-monitoring"
  })
  
  tags = {
    Role     = "worker"
    Workload = "monitoring"
  }
}
```

---

### 2. Terraform: `terraform/outputs.tf`

**추가된 Output**:
```hcl
output "monitoring_public_ip" {
  description = "Monitoring 노드 Public IP"
  value       = module.monitoring.public_ip
}

output "monitoring_private_ip" {
  description = "Monitoring 노드 Private IP"
  value       = module.monitoring.private_ip
}

output "cluster_info" {
  value = {
    monitoring_ip      = module.monitoring.public_ip
    total_nodes        = 5
    total_vcpu         = 10
    total_memory_gb    = 28
    estimated_cost_usd = 210
  }
}

output "node_roles" {
  value = {
    master     = "Control Plane (t3.large, 8GB)"
    worker_1   = "Application Pods (t3.medium, 4GB)"
    worker_2   = "Celery Workers (t3.medium, 4GB)"
    storage    = "RabbitMQ, PostgreSQL, Redis (t3.large, 8GB)"
    monitoring = "Prometheus + Grafana (t3.medium, 4GB)" ⭐
  }
}
```

---

### 3. Terraform: `terraform/templates/hosts.tpl`

**추가된 호스트 그룹**:
```ini
[monitoring]
k8s-monitoring ansible_host=${monitoring_public_ip} private_ip=${monitoring_private_ip} workload=monitoring instance_type=t3.medium

[k8s_cluster:children]
masters
workers
storage
monitoring  ⭐
```

---

### 4. Ansible: `ansible/playbooks/08-monitoring.yml`

**nodeSelector 추가**:
```yaml
- name: Prometheus + Grafana 설치 (Monitoring 노드 전용 배치)
  command: >
    helm install prometheus prometheus-community/kube-prometheus-stack
    --namespace monitoring
    --set prometheus.prometheusSpec.nodeSelector.workload=monitoring  ⭐
    --set grafana.nodeSelector.workload=monitoring  ⭐
    --set alertmanager.alertmanagerSpec.nodeSelector.workload=monitoring  ⭐
```

---

### 5. Ansible: `ansible/site.yml`

**노드 레이블 추가**:
```yaml
- name: Label monitoring (Prometheus + Grafana)
  command: kubectl label nodes k8s-monitoring workload=monitoring instance-type=t3.medium role=monitoring --overwrite
  register: label_monitoring
  failed_when: label_monitoring.rc != 0

- name: Verify monitoring node label
  command: kubectl get nodes k8s-monitoring -L workload --no-headers
  register: verify_monitoring_label
  failed_when: "'monitoring' not in verify_monitoring_label.stdout"
  changed_when: false
```

---

## 🚀 배포 방법

### Step 1: Terraform 실행

```bash
cd terraform
terraform init
terraform apply
```

**출력 예시**:
```
monitoring_public_ip  = "52.79.xxx.xxx"
monitoring_private_ip = "10.0.2.xxx"
total_nodes           = 5
total_memory_gb       = 28
estimated_cost_usd    = 210
```

---

### Step 2: Ansible Inventory 생성

```bash
cd ../ansible
terraform output -raw ansible_inventory > inventory/hosts
```

**생성된 Inventory**:
```ini
[monitoring]
k8s-monitoring ansible_host=52.79.xxx.xxx private_ip=10.0.2.xxx workload=monitoring instance_type=t3.medium

[k8s_cluster:children]
masters
workers
storage
monitoring
```

---

### Step 3: Ansible Playbook 실행

```bash
ansible-playbook site.yml
```

**자동 실행 순서**:
1. ✅ Monitoring 노드 join
2. ✅ `workload=monitoring` 레이블 적용
3. ✅ Prometheus + Grafana 설치 (nodeSelector 적용)
4. ✅ Pod가 `k8s-monitoring` 노드에 배치됨

---

## 📊 배치 확인

### 노드 확인

```bash
kubectl get nodes -L workload
```

**출력**:
```
NAME             STATUS   ROLES           WORKLOAD
k8s-master       Ready    control-plane   <none>
k8s-worker-1     Ready    <none>          application
k8s-worker-2     Ready    <none>          async-workers
k8s-storage      Ready    <none>          storage
k8s-monitoring   Ready    <none>          monitoring  ⭐
```

---

### Monitoring Pod 배치 확인

```bash
kubectl get pods -n monitoring -o wide
```

**출력**:
```
NAME                                  NODE            WORKLOAD
prometheus-prometheus-0               k8s-monitoring  monitoring ✅
prometheus-grafana-xxx                k8s-monitoring  monitoring ✅
alertmanager-prometheus-kube-0        k8s-monitoring  monitoring ✅
```

---

## 🔍 리소스 사용량

### Monitoring 노드 리소스

| 컴포넌트 | CPU 요청 | Memory 요청 | Storage |
|---------|----------|------------|---------|
| Prometheus | 1000m | 2Gi | 50Gi (PVC) |
| Grafana | 500m | 512Mi | - |
| Alertmanager | 250m | 256Mi | - |
| **합계** | **1750m** | **~2.8Gi** | **50Gi** |

**t3.medium 스펙**:
- vCPU: 2 (2000m)
- Memory: 4GB
- 리소스 사용률: **CPU 87%, Memory 70%** ✅

---

## 💰 비용 분석

### 노드별 비용

| 노드 | 타입 | 월 비용 |
|------|------|---------|
| Master | t3.large | $60 |
| Worker-1 | t3.medium | $42 |
| Worker-2 | t3.medium | $42 |
| Storage | t3.large | $60 |
| **Monitoring** | **t3.medium** | **$42** ⭐ |
| **합계** | | **$246** |

**추가 비용**: +$42/month (Monitoring 노드)

---

## ✅ 장점

### 1. **리소스 격리**
- ✅ Application Pod와 Monitoring 완전 분리
- ✅ 서로 간섭 없음

### 2. **성능 최적화**
- ✅ Prometheus TSDB 전용 리소스
- ✅ Grafana 대시보드 성능 향상

### 3. **독립적 확장**
- ✅ Monitoring 부하 증가 시 노드만 Scale Up
- ✅ Application 리소스에 영향 없음

### 4. **관리 용이성**
- ✅ Monitoring Pod를 한 노드에서 관리
- ✅ 문제 발생 시 노드 단위 격리 가능

---

## 🎯 향후 확장

### Scale Up (수직 확장)

**Monitoring 노드만 Scale Up**:
```hcl
# terraform/main.tf
module "monitoring" {
  instance_type = "t3.large"  # 4GB → 8GB
}
```

**비용 증가**: +$18/month

---

### Scale Out (수평 확장)

**Prometheus 고가용성 (HA)**:
```yaml
# ansible/playbooks/08-monitoring.yml
--set prometheus.prometheusSpec.replicas=2
```

**필요 조건**: Monitoring 노드 2개 필요

---

## 📄 관련 문서

- [Pod 배치 및 응답 경로](./POD_PLACEMENT_AND_RESPONSE_FLOW.md)
- [Storage 노드 분리 전략](./STORAGE_SEPARATION_STRATEGY.md)
- [네트워크 라우팅 구조](./NETWORK_ROUTING_STRUCTURE.md)

---

**작성일**: 2025-11-04  
**버전**: 1.0.0  
**결론**: Monitoring 전용 노드로 분리하여 Application과 Monitoring의 리소스 격리 및 독립적 확장 달성!

