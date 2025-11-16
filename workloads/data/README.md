# Data Layer Custom Resources

Operator가 관리하는 데이터 계층 인스턴스 정의 (Wave 35).

## 디렉터리

- `postgres/`: Zalando Postgres Operator CR (`acid.zalan.do/v1` postgresql)
- `redis/`: Spotahome Redis Operator CR (`databases.spotahome.com/v1` RedisFailover)

## 배포 순서

1. **Wave 25**: Operator 설치 (`platform/helm/postgres-operator`, `redis-operator`)
2. **Wave 35**: 이 디렉터리의 CR 배포
3. Operator가 CR을 reconcile하여 StatefulSet/PVC/Service 자동 생성

## 환경별 차이

| 항목 | dev | prod |
|------|-----|------|
| Postgres replicas | 1 | 1 |
| Postgres volume | 20Gi | 100Gi |
| Redis replicas | 1 | 1 |
| Redis volume | 10Gi | 50Gi |
| Backup | 비활성 | 활성 (S3) |

## 참고

- Operator 스펙: `docs/architecture/operator/OPERATOR_SOURCE_SPEC.md`
- Secret 주입: `docs/architecture/gitops/TERRAFORM_SECRET_INJECTION.md`

