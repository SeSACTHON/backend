# Platform Helm Charts (벤더 스택)

이 디렉터리는 외부 Helm chart를 ArgoCD Multi-Source 패턴 없이(단일 `source`) 배포하기 위한 환경별 Application 오버레이(`dev`, `prod`)를 보관한다. ApplicationSet은 제거했고, 각 환경은 독립 `Application`으로 등록되며 Helm 값은 env overlay(`patch-application.yaml`)에 직접 선언한다.

## Overlay 패턴 예시

```yaml
spec:
  project: dev
  source:
    repoURL: https://prometheus-community.github.io/helm-charts
    chart: kube-prometheus-stack
    targetRevision: 56.21.1
    helm:
      releaseName: kube-prometheus-stack
      valuesObject:
        alertmanager:
          alertmanagerSpec:
            replicas: 1
```

## 디렉터리 구조

각 컴포넌트는 아래 규칙을 따른다:

```
platform/helm/<component>/
├─ base/
│  ├─ application.yaml         # 공통 스펙
│  └─ kustomization.yaml       # base 참조
├─ dev/
│  ├─ kustomization.yaml       # base + patch
│  └─ patch-application.yaml   # Dev 환경 설정(Helm valuesObject 등)
└─ prod/
   ├─ kustomization.yaml
   └─ patch-application.yaml
```

- `base/application.yaml`: chart repo·버전·Sync 옵션 등 공통 정의
- `patch-application.yaml`: 환경별 차이(project, targetRevision, Helm valuesObject 등)를 선언

## 주의사항

1. **Secret 참조**: Helm valuesObject에 민감 정보를 직접 넣지 말고 `existingSecret` 또는 `valueFrom`으로 ExternalSecrets 출력을 참조한다.
2. **CRD 선행**: `platform/crds/` 경로의 CRD를 Wave -1에서 먼저 적용해야 Operator Helm이 정상 동작한다.
3. **Sync Wave**: `application.yaml` 메타데이터의 `argocd.argoproj.io/sync-wave` 어노테이션이 `ARGOCD_SYNC_WAVE_PLAN.md`와 일치해야 한다.

---

> 새 Helm 컴포넌트를 추가할 때는 위 구조를 따르고, `OPERATOR_SOURCE_SPEC.md`에 소스와 버전을 먼저 기록한 뒤 env별 overlay(`kustomization.yaml`, `patch-application.yaml`)를 생성한다.
