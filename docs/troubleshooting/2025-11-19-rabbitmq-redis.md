# 2025-11-19 RabbitMQ / Redis 운영 이슈 정리

## 개요
- **대상 환경**: `dev` Argo CD Application (`dev-rabbitmq-operator`, `dev-data-crs`, `dev-rbac-storage`)
- **문제 요약**
  1. RabbitMQ Cluster Operator: `kustomize build config/installation` 실패
  2. Redis Cluster: PVC `redis-cluster-redis-cluster-0`가 `ExternalProvisioning` 상태로 대기
  3. CRD 이중 적용 우려: 운영자 질문 대응 (CRD 분리 전략 문서화)

---

## 1. RabbitMQ Cluster Operator Sync Error

### 증상
- Argo CD `dev-rabbitmq-operator` 앱에서 `ComparisonError: kustomization file not found` 및
  ```
  invalid Kustomization: json: cannot unmarshal string into Go struct field Kustomization.patches of type types.Patch
  ```

### 원인
- 공식 리포(`rabbitmq/cluster-operator` v1.11.0)의 `config/installation`은 **Kustomize v5** 스키마(`patches`)를 사용.
- Argo CD 기본 Kustomize(v4)로 빌드하면서 새로운 스키마를 이해하지 못해 실패.
- 해당 패키지가 `../crd/`를 포함해 읽어오면서, CRD를 중복 적용할 위험이 있다는 질문도 함께 제기됨.

### 조치
1. `clusters/{dev,prod}/apps/32-rabbitmq-operator.yaml`
   ```yaml
   spec.source.kustomize.version: v5.3.0
   ```
   으로 빌드 버전 고정.
2. 기존 패치 유지:
   ```yaml
   - op: remove
     path: /
   ```
   → upstream `crd` 리소스를 제거하여 `platform/crds/*`에서만 CRD를 관리.

### 결과
- Argo CD가 Kustomize v5로 빌드하면서 오류 제거.
- CRD는 여전히 `dev-crds` 애플리케이션을 통해 단일 경로로 관리되어 충돌 없음.

---

## 2. Redis PVC External Provisioning Pending

### 증상
- `redis-cluster-redis-cluster-0` PVC 이벤트:
  ```
  Waiting for a volume to be created either by the external provisioner 'ebs.csi.aws.com'...
  ```
- StatefulSet `redis-cluster` 파드가 PVC 바인딩 실패로 Pending.

### 원인
- 기본 StorageClass 정의(`workloads/rbac-storage/base/storage-class.yaml`)가 **legacy in-tree provisioner**(`kubernetes.io/aws-ebs`)를 가리킴.
- 클러스터는 이미 EBS CSI 드라이버(`ebs.csi.aws.com`)를 사용하고 있어, PVC Owner가 일치하지 않아 프로비저닝이 진행되지 않음.

### 조치
```yaml
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
  csi.storage.k8s.io/fstype: ext4
```
- StorageClass를 CSI 드라이버로 전환 후 `argocd app sync dev-rbac-storage`.
- 필요 시 기존 PVC 삭제 → 새 클래스 기반으로 재생성.

### 결과
- 신규 PVC는 즉시 Bound, Redis StatefulSet이 진행됨.

---

## 3. CRD 분리 전략 FAQ

| 항목 | Postgres Operator | Redis Operator | RabbitMQ Operator |
| --- | --- | --- | --- |
| 배포 방식 | Helm (`skipCrds: true`) | Kustomize (`config/default`) | Kustomize (`config/installation`) |
| CRD 관리 | `platform/crds/*` App | 동일 | 동일 |
| 중복 방지 방법 | Helm values (`skipCrds`) | (필요 시) Kustomize patch로 CRD 제거 | 이미 patch 적용 |

- RabbitMQ는 Helm Chart를 제공하지 않아 `helm.skipCrds` 옵션을 쓸 수 없음 → 패치로 CRD 제거.
- Redis도 같은 패턴을 적용할 수 있으며, 버전 업 시 patch 유지 필요.
- 모든 데이터 계층 Operator는 “Operator와 CRD를 분리 관리”한다는 전략을 공유.

---

## 후속 체크리스트
- [ ] `dev-rbac-storage` Sync 후 Redis PVC 상태 확인
- [ ] `dev-rabbitmq-operator`/`prod-rabbitmq-operator` Sync 결과 확인
- [ ] CRD 업데이트 필요 시 `platform/crds/base` 버전 업과 패치 목록 동기화


