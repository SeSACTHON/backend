# Dev Environment Cluster Apps

Dev 환경 ArgoCD App-of-Apps 구조.

## 진입점

`clusters/dev/root-app.yaml`: 이 Application을 ArgoCD에 등록하면 `apps/*.yaml`을 재귀로 Sync한다.

```bash
kubectl apply -f clusters/dev/root-app.yaml
argocd app sync dev-root
```

## Wave 순서

| 파일 | Wave | 내용 |
|------|------|------|
| `00-crds.yaml` | -1 | Platform CRDs (ALB, Prometheus, Postgres, ESO) |
| `05-namespaces.yaml` | 0 | Namespaces (workloads/namespaces/overlays/dev) |
| `10-network-policies.yaml` | 5 | NetworkPolicy (L3/L4 격리) |
| `60-apis-appset.yaml` | 60 | 7개 API ApplicationSet |
| `70-ingress.yaml` | 70 | ALB Ingress (Path routing) |

## 누락된 Wave (TODO)

- Wave 10: Platform (ExternalSecrets, cert-manager)
- Wave 15: ALB Controller
- Wave 20: Monitoring Operator
- Wave 25: Data Operators
- Wave 35: Data Clusters (postgres/redis CR)
- Wave 58: Secrets (ExternalSecret CRs)

위 Application들은 `platform/helm/*/app.yaml`을 참조하거나 별도로 생성해야 한다.

## 참고

- `docs/architecture/gitops/ARGOCD_SYNC_WAVE_PLAN.md`
- `docs/architecture/gitops/ARGOCD_HELM_KUSTOMIZE_STRUCTURE.md`

