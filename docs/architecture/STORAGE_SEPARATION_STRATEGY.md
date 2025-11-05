# Storage 노드 분리 전략 (수평 확장 대비)

> 날짜: 2025-11-04  
> 목적: Message Queue와 Storage를 분리하여 수평 확장 용이하게 구성

---

## 📊 현재 아키텍처 (문제점)

### 현재 구성 (4 Nodes)

```
Master (k8s-master)
  - Control Plane
  - Taint: NoSchedule

Worker-1 (k8s-worker-1)
  - workload=application
  - FastAPI, 기타 애플리케이션
  - t3.medium (2 vCPU, 4GB RAM, 40GB EBS)

Worker-2 (k8s-worker-2)
  - workload=async-workers
  - Celery Workers (AI, Batch, API, Schedule)
  - t3.medium (2 vCPU, 4GB RAM, 40GB EBS)

Storage (k8s-storage) ⚠️ 문제!
  - workload=storage
  - PostgreSQL (Database)
  - RabbitMQ (Message Queue)
  - Redis (Cache & State)
  - t3.large (2 vCPU, 8GB RAM, 100GB EBS)
```

### 문제점

1. **단일 장애점 (SPOF)**
   - Storage 노드 장애 시 Database, MQ, Cache 모두 중단
   - 데이터베이스와 메시지 큐가 같은 노드에 위치

2. **리소스 경합**
   - PostgreSQL (CPU/Memory 집약)
   - RabbitMQ (Network/Disk I/O 집약)
   - Redis (Memory 집약)
   - 모두 같은 노드에서 리소스 경쟁

3. **수평 확장 불가**
   - RabbitMQ 클러스터 확장 시 PostgreSQL/Redis도 영향
   - 각 서비스의 독립적 스케일링 불가
   - 노드 추가 시 모든 서비스 재배치 필요

4. **유지보수 어려움**
   - PostgreSQL 업그레이드 시 RabbitMQ/Redis 영향
   - 백업/복구 전략 복잡
   - 모니터링 및 알림 설정 복잡

---

## 🎯 개선된 아키텍처 (수평 확장 대비)

### 목표 구성 (6 Nodes)

```
Tier 1: Control Plane
├── Master (k8s-master)
│   - Control Plane Components
│   - Taint: NoSchedule

Tier 2: Application Layer
├── Worker-1 (k8s-worker-1)
│   - workload=application
│   - FastAPI, Web Applications
│   - t3.medium (2 vCPU, 4GB, 40GB)
│
└── Worker-2 (k8s-worker-2)
    - workload=async-workers
    - Celery Workers
    - t3.medium (2 vCPU, 4GB, 40GB)

Tier 3: Message Queue Layer (NEW)
└── MQ-1 (k8s-mq-1)
    - workload=message-queue
    - RabbitMQ (단일 또는 클러스터)
    - t3.medium (2 vCPU, 4GB, 40GB)

Tier 4: Persistence Layer
├── DB-1 (k8s-db-1)
│   - workload=database
│   - PostgreSQL (Primary)
│   - t3.large (2 vCPU, 8GB, 100GB)
│
└── Cache-1 (k8s-cache-1)
    - workload=cache
    - Redis (Master)
    - t3.medium (2 vCPU, 4GB, 20GB)
```

---

## 🔄 확장 시나리오

### Phase 1: 초기 구성 (6 Nodes)

**비용**: ~$150/month

```
Master x1 (t3.large)
Worker x2 (t3.medium x2)
MQ x1 (t3.medium)
DB x1 (t3.large)
Cache x1 (t3.medium)
```

**장점**:
- ✅ 서비스 분리 (단일 장애점 제거)
- ✅ 독립적 리소스 관리
- ✅ 명확한 역할 분리

---

### Phase 2: Message Queue 확장 (트래픽 증가 시)

**추가**: MQ-2, MQ-3 (RabbitMQ Cluster)

```
Tier 3: Message Queue Layer
├── MQ-1 (k8s-mq-1) - RabbitMQ Node 1
├── MQ-2 (k8s-mq-2) - RabbitMQ Node 2
└── MQ-3 (k8s-mq-3) - RabbitMQ Node 3
```

**RabbitMQ 클러스터 구성**:
```yaml
spec:
  replicas: 3
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: workload
            operator: In
            values:
            - message-queue
    podAntiAffinity:
      # 각 RabbitMQ Pod를 다른 노드에 배치
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app.kubernetes.io/name: rabbitmq
        topologyKey: kubernetes.io/hostname
```

**장점**:
- ✅ 고가용성 (HA)
- ✅ 메시지 처리량 3배 증가
- ✅ 노드 장애 시 자동 페일오버

---

### Phase 3: Database 확장 (Read Replica)

**추가**: DB-2 (Read Replica)

```
Tier 4: Persistence Layer
├── DB-1 (k8s-db-1) - PostgreSQL Primary (Write)
├── DB-2 (k8s-db-2) - PostgreSQL Replica (Read)
└── Cache-1 (k8s-cache-1) - Redis
```

**PostgreSQL Replication**:
```yaml
# DB-1 (Primary)
spec:
  replicas: 1
  affinity:
    nodeAffinity:
      nodeSelectorTerms:
      - matchExpressions:
        - key: workload
          operator: In
          values:
          - database
        - key: db-role
          operator: In
          values:
          - primary

# DB-2 (Replica)
spec:
  replicas: 1
  affinity:
    nodeAffinity:
      nodeSelectorTerms:
      - matchExpressions:
        - key: workload
          operator: In
          values:
          - database
        - key: db-role
          operator: In
          values:
          - replica
```

**장점**:
- ✅ Read 성능 향상
- ✅ Primary 부하 분산
- ✅ 백업 데이터 실시간 유지

---

### Phase 4: Redis Cluster 확장

**추가**: Cache-2, Cache-3 (Redis Cluster)

```
Tier 4: Persistence Layer
├── DB-1, DB-2 (PostgreSQL)
├── Cache-1 (Redis Master 1)
├── Cache-2 (Redis Master 2)
└── Cache-3 (Redis Master 3)
```

**Redis Cluster**:
```yaml
spec:
  replicas: 3
  affinity:
    nodeAffinity:
      nodeSelectorTerms:
      - matchExpressions:
        - key: workload
          operator: In
          values:
          - cache
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app: redis
        topologyKey: kubernetes.io/hostname
```

**장점**:
- ✅ 캐시 용량 증가
- ✅ 고가용성
- ✅ 자동 샤딩

---

## 📋 Terraform 변경 (새 노드 추가)

### terraform/main.tf

```hcl
# Message Queue Node
module "mq_node" {
  source = "./modules/ec2"
  
  name               = "${var.environment}-k8s-mq-1"
  instance_type      = "t3.medium"
  ami_id             = data.aws_ami.ubuntu.id
  subnet_id          = module.vpc.public_subnet_ids[0]
  security_group_ids = [module.vpc.worker_security_group_id]
  iam_instance_profile = module.iam.instance_profile_name
  key_name           = aws_key_pair.k8s_key.key_name
  root_volume_size   = 40
  
  tags = {
    Name        = "${var.environment}-k8s-mq-1"
    Environment = var.environment
    Terraform   = "true"
    Workload    = "message-queue"
    Tier        = "tier-3-mq"
  }
}

# Database Node (renamed from storage)
module "db_node" {
  source = "./modules/ec2"
  
  name               = "${var.environment}-k8s-db-1"
  instance_type      = "t3.large"
  ami_id             = data.aws_ami.ubuntu.id
  subnet_id          = module.vpc.public_subnet_ids[1]
  security_group_ids = [module.vpc.worker_security_group_id]
  iam_instance_profile = module.iam.instance_profile_name
  key_name           = aws_key_pair.k8s_key.key_name
  root_volume_size   = 100
  
  tags = {
    Name        = "${var.environment}-k8s-db-1"
    Environment = var.environment
    Terraform   = "true"
    Workload    = "database"
    Tier        = "tier-4-db"
  }
}

# Cache Node (NEW)
module "cache_node" {
  source = "./modules/ec2"
  
  name               = "${var.environment}-k8s-cache-1"
  instance_type      = "t3.medium"
  ami_id             = data.aws_ami.ubuntu.id
  subnet_id          = module.vpc.public_subnet_ids[2]
  security_group_ids = [module.vpc.worker_security_group_id]
  iam_instance_profile = module.iam.instance_profile_name
  key_name           = aws_key_pair.k8s_key.key_name
  root_volume_size   = 20
  
  tags = {
    Name        = "${var.environment}-k8s-cache-1"
    Environment = var.environment
    Terraform   = "true"
    Workload    = "cache"
    Tier        = "tier-4-cache"
  }
}
```

### terraform/outputs.tf

```hcl
output "mq_public_ip" {
  value = module.mq_node.public_ip
}

output "mq_private_ip" {
  value = module.mq_node.private_ip
}

output "db_public_ip" {
  value = module.db_node.public_ip
}

output "db_private_ip" {
  value = module.db_node.private_ip
}

output "cache_public_ip" {
  value = module.cache_node.public_ip
}

output "cache_private_ip" {
  value = module.cache_node.private_ip
}
```

---

## 📝 Ansible 변경 (노드 레이블링)

### ansible/inventory/hosts.ini

```ini
[masters]
master ansible_host=<MASTER_IP> ansible_user=ubuntu

[workers]
worker-1 ansible_host=<WORKER1_IP> ansible_user=ubuntu
worker-2 ansible_host=<WORKER2_IP> ansible_user=ubuntu

[message_queue]
mq-1 ansible_host=<MQ1_IP> ansible_user=ubuntu

[database]
db-1 ansible_host=<DB1_IP> ansible_user=ubuntu

[cache]
cache-1 ansible_host=<CACHE1_IP> ansible_user=ubuntu

[k8s_cluster:children]
masters
workers
message_queue
database
cache
```

### ansible/site.yml

```yaml
- name: 노드 레이블 지정
  hosts: masters
  become: yes
  become_user: "{{ kubectl_user }}"
  tasks:
    - name: Label worker-1 (Application)
      command: kubectl label nodes k8s-worker-1 workload=application tier=tier-2-app --overwrite
    
    - name: Label worker-2 (Async Workers)
      command: kubectl label nodes k8s-worker-2 workload=async-workers tier=tier-2-workers --overwrite
    
    - name: Label mq-1 (Message Queue)
      command: kubectl label nodes k8s-mq-1 workload=message-queue tier=tier-3-mq --overwrite
    
    - name: Label db-1 (Database)
      command: kubectl label nodes k8s-db-1 workload=database tier=tier-4-db --overwrite
    
    - name: Label cache-1 (Cache)
      command: kubectl label nodes k8s-cache-1 workload=cache tier=tier-4-cache --overwrite
    
    - name: Verify all labels
      command: kubectl get nodes -L workload,tier
      register: node_labels
      changed_when: false
    
    - name: Display node labels
      debug:
        msg: "{{ node_labels.stdout_lines }}"
```

---

## 🔧 서비스별 배치 전략

### RabbitMQ (Message Queue)

```yaml
# ansible/roles/rabbitmq/tasks/main.yml
spec:
  replicas: 1  # 초기에는 1개
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: workload
            operator: In
            values:
            - message-queue  # 변경!
```

**확장 시** (Phase 2):
```yaml
spec:
  replicas: 3  # 3개로 확장
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: workload
            operator: In
            values:
            - message-queue
    podAntiAffinity:
      # 각 Pod를 다른 노드에 배치
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app.kubernetes.io/name: rabbitmq
        topologyKey: kubernetes.io/hostname
```

---

### PostgreSQL (Database)

```yaml
# ansible/roles/postgresql/tasks/main.yml
spec:
  nodeSelector:
    workload: database  # 변경!
  containers:
  - name: postgres
    resources:
      requests:
        cpu: 1000m    # 증가 (독립 노드)
        memory: 4Gi   # 증가
      limits:
        cpu: 2000m
        memory: 6Gi
```

**확장 시** (Phase 3 - Read Replica):
- Patroni 또는 Stolon 사용
- Primary-Replica 구성
- 자동 페일오버

---

### Redis (Cache)

```yaml
# ansible/roles/redis/tasks/main.yml
spec:
  replicas: 1
  template:
    spec:
      nodeSelector:
        workload: cache  # 변경!
      containers:
      - name: redis
        resources:
          requests:
            cpu: 500m     # 증가
            memory: 2Gi   # 증가
          limits:
            cpu: 1000m
            memory: 4Gi
```

**확장 시** (Phase 4 - Redis Cluster):
- Redis Cluster 모드
- 3 Master + 3 Replica
- 자동 샤딩 및 페일오버

---

## 💰 비용 분석

### 현재 구성 (4 Nodes)

| Node | Type | vCPU | RAM | Storage | Cost/Month |
|------|------|------|-----|---------|------------|
| Master | t3.large | 2 | 8GB | 80GB | $40 |
| Worker-1 | t3.medium | 2 | 4GB | 40GB | $25 |
| Worker-2 | t3.medium | 2 | 4GB | 40GB | $25 |
| Storage | t3.large | 2 | 8GB | 100GB | $45 |
| **Total** | | **8** | **24GB** | **260GB** | **$135** |

### 제안 구성 (6 Nodes)

| Node | Type | vCPU | RAM | Storage | Cost/Month |
|------|------|------|-----|---------|------------|
| Master | t3.large | 2 | 8GB | 80GB | $40 |
| Worker-1 | t3.medium | 2 | 4GB | 40GB | $25 |
| Worker-2 | t3.medium | 2 | 4GB | 40GB | $25 |
| MQ-1 | t3.medium | 2 | 4GB | 40GB | $25 |
| DB-1 | t3.large | 2 | 8GB | 100GB | $45 |
| Cache-1 | t3.medium | 2 | 4GB | 20GB | $20 |
| **Total** | | **12** | **32GB** | **320GB** | **$180** |

**추가 비용**: +$45/month (+33%)
**장점**: 고가용성, 수평 확장 가능, 명확한 역할 분리

---

## 🎯 마이그레이션 전략

### Phase 1: 즉시 적용 (6 Nodes)

**단계**:
1. Terraform으로 MQ-1, DB-1, Cache-1 노드 생성
2. Ansible로 Kubernetes 클러스터에 Join
3. 노드 레이블 적용
4. RabbitMQ → MQ-1로 마이그레이션
5. PostgreSQL → DB-1로 마이그레이션
6. Redis → Cache-1로 마이그레이션
7. 기존 Storage 노드 제거

**예상 시간**: 1-2시간

---

### Phase 2: 점진적 확장 (필요 시)

**RabbitMQ 확장** (트래픽 > 1000 msg/sec):
- MQ-2, MQ-3 노드 추가
- RabbitMQ replicas: 1 → 3

**PostgreSQL 확장** (Read 부하 높음):
- DB-2 노드 추가 (Read Replica)
- Connection Pool 설정 (Primary/Replica 분리)

**Redis 확장** (캐시 Hit Rate < 80%):
- Cache-2, Cache-3 노드 추가
- Redis Cluster 모드 전환

---

## 📊 모니터링 전략

### Node 레벨

```yaml
# Prometheus Node Exporter
nodeSelector:
  # 모든 노드에 배포
  kubernetes.io/os: linux

tolerations:
- operator: Exists
```

### Service 레벨

```yaml
# RabbitMQ ServiceMonitor
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: rabbitmq
  namespaceSelector:
    matchNames:
    - messaging

# PostgreSQL Exporter
spec:
  selector:
    matchLabels:
      app: postgres
  namespaceSelector:
    matchNames:
    - default

# Redis Exporter
spec:
  selector:
    matchLabels:
      app: redis
  namespaceSelector:
    matchNames:
    - default
```

### Grafana Dashboard

- **Node 대시보드**: CPU, Memory, Disk, Network (노드별)
- **RabbitMQ 대시보드**: Queue Depth, Msg Rate, Connection
- **PostgreSQL 대시보드**: QPS, Connection, Replication Lag
- **Redis 대시보드**: Hit Rate, Memory Usage, Evictions

---

## ✅ 권장 사항

### 즉시 적용 (Phase 1)

**이유**:
1. **단일 장애점 제거**: Storage 노드 장애 시 전체 시스템 중단 방지
2. **독립적 확장 가능**: 각 서비스를 필요에 따라 독립적으로 스케일
3. **명확한 역할 분리**: 디버깅, 모니터링, 유지보수 용이
4. **미래 대비**: 트래픽 증가 시 빠른 대응 가능

**비용**: +$45/month (33% 증가)
**가치**: 고가용성, 확장성, 유지보수성 대폭 향상

### 점진적 확장 (Phase 2-4)

**RabbitMQ** → 트래픽 > 1000 msg/sec 시  
**PostgreSQL** → Read 부하 > 70% 시  
**Redis** → Cache Hit Rate < 80% 시  

---

**작성일**: 2025-11-04  
**버전**: 1.0.0

