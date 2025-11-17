# RabbitMQ Cluster (RabbitmqCluster)

- **Operator**: `rabbitmq/cluster-operator` (`rabbitmq.com/v1beta1`)
- **Wave**: 35 (Operator는 Wave 25 `platform/helm/rabbitmq-operator`)
- **Namespace**: `rabbitmq`

## 구조

```
rabbitmq/
├── base/
│   ├── kustomization.yaml
│   └── rabbitmq-cluster.yaml   # 공통 스펙 (secretBackend, scheduling 등)
├── dev/
│   ├── kustomization.yaml
│   └── rabbitmq-cluster.yaml   # replicas/storage/resources 패치
└── prod/
    ├── kustomization.yaml
    └── rabbitmq-cluster.yaml   # 고가용성 패치
```

## 값 요약

| 항목 | dev | prod |
|------|-----|------|
| Replicas | 1 | 3 |
| Storage | 20Gi gp3 | 50Gi gp3 |
| Requests | 0.5 CPU / 1Gi | 2 CPU / 4Gi |
| Limits | 1 CPU / 2Gi | 4 CPU / 8Gi |

## Secret 연동

`spec.secretBackend.externalSecret.name: rabbitmq-default-user`로
ExternalSecret(`workloads/secrets/external-secrets/*/data-secrets.yaml`)
에서 동기화된 관리자 계정을 사용합니다.

