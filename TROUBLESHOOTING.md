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
5. [RabbitMQ PVC 바인딩 실패](#5-rabbitmq-pvc-바인딩-실패)

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

## 📊 해결 요약

| 문제 | 원인 | 해결 | 커밋 |
|------|------|------|------|
| Terraform 디렉토리 오류 | 잘못된 working directory | `-chdir` 옵션 추가 | `9211bb5` |
| Namespace 생성 실패 | command 모듈에서 파이프 불가 | shell 모듈로 변경 | `bc728fd` |
| Prometheus retention 오류 | map 대신 string 필요 | 설정 형식 수정 | `b8d4f44` |
| Prometheus Pod 타이밍 | 리소스 생성 전 wait 실행 | 다단계 대기 로직 | `df7c3da` |
| RabbitMQ PVC 바인딩 실패 | StorageClass 없음 | EBS CSI Driver 설치 | `80a7f9c` |

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
**총 해결 문제**: 5개  
**총 커밋**: 5개  
**상태**: ✅ 모든 문제 해결 완료

