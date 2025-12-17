# PostgreSQL & Redis CR 전환 계획

> **상태**: 📋 계획  
> **우선순위**: 중간  
> **선행 조건**: Observability Enhancement 완료 후

---

## 📋 개요

현재 StatefulSet으로 배포된 PostgreSQL과 Redis를 Kubernetes Operator CR(Custom Resource)로 전환하여 GitOps 관리를 강화합니다.

---

## 🎯 목표

1. **선언적 관리**: DB 설정을 YAML로 버전 관리
2. **자동화된 운영**: 백업, 페일오버, 스케일링 자동화
3. **일관된 GitOps**: 모든 인프라를 CR로 통일

---

## 📊 현재 상태

| 서비스 | 현재 방식 | CRD 상태 | 네임스페이스 |
|--------|----------|----------|-------------|
| PostgreSQL | StatefulSet | ✅ Zalando CRD 설치됨 | postgres |
| Redis | StatefulSet (Bitnami) | ❌ 미설치 | redis |

---

## 🔄 전환 계획

### Phase 1: PostgreSQL CR 전환

**Operator**: Zalando Postgres Operator (이미 CRD 설치됨)

```yaml
apiVersion: acid.zalan.do/v1
kind: postgresql
metadata:
  name: eco2-postgres
  namespace: postgres
spec:
  teamId: "eco2"
  volume:
    size: 50Gi
    storageClass: gp3
  numberOfInstances: 2  # Primary + Replica
  users:
    eco2_admin:
    - superuser
    - createdb
  databases:
    eco2_auth: eco2_admin
    eco2_character: eco2_admin
    eco2_chat: eco2_admin
    eco2_scan: eco2_admin
  postgresql:
    version: "15"
  resources:
    requests:
      cpu: 500m
      memory: 2Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: workload
          operator: In
          values: [database]
```

**전환 절차**:
1. 기존 데이터 pg_dump 백업
2. Zalando Operator 배포 확인
3. PostgreSQL CR 생성
4. 데이터 복원
5. 앱 연결 문자열 변경
6. 기존 StatefulSet 삭제

---

### Phase 2: Redis CR 전환

**Operator**: Spotahome Redis Operator

```yaml
# 1. CRD 추가 (workloads/crds/base/kustomization.yaml)
- https://raw.githubusercontent.com/spotahome/redis-operator/master/manifests/databases.spotahome.com_redisfailovers.yaml

# 2. Redis CR
apiVersion: databases.spotahome.com/v1
kind: RedisFailover
metadata:
  name: eco2-redis
  namespace: redis
spec:
  sentinel:
    replicas: 3
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
  redis:
    replicas: 2
    resources:
      requests:
        cpu: 200m
        memory: 512Mi
      limits:
        memory: 1Gi
    storage:
      persistentVolumeClaim:
        metadata:
          name: redis-data
        spec:
          accessModes: [ReadWriteOnce]
          storageClassName: gp3
          resources:
            requests:
              storage: 10Gi
```

**전환 절차**:
1. Redis Operator CRD 추가
2. Redis Operator 배포
3. 기존 Redis 데이터 RDB 백업
4. RedisFailover CR 생성
5. 데이터 복원
6. 앱 Sentinel 연결로 변경
7. 기존 StatefulSet 삭제

---

## ⚠️ 주의사항

1. **다운타임**: 전환 중 짧은 다운타임 발생 가능
2. **연결 문자열**: CR 전환 시 서비스 이름 변경될 수 있음
3. **Sentinel**: Redis CR은 Sentinel 기반 HA - 클라이언트 설정 변경 필요

---

## 📅 일정 (예상)

| 단계 | 작업 | 예상 소요 |
|------|------|----------|
| 1 | PostgreSQL CR 테스트 (dev) | 1일 |
| 2 | PostgreSQL CR 프로덕션 전환 | 1일 |
| 3 | Redis Operator 설치 | 0.5일 |
| 4 | Redis CR 테스트 (dev) | 1일 |
| 5 | Redis CR 프로덕션 전환 | 1일 |

---

## 🔗 참고 자료

- [Zalando Postgres Operator](https://github.com/zalando/postgres-operator)
- [Spotahome Redis Operator](https://github.com/spotahome/redis-operator)
- [CloudNativePG (대안)](https://cloudnative-pg.io/)
