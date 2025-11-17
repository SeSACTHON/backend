# Helm · Platform(Kustomize) 환경 분리 계획

> 목적: `clusters/{env}` 수준에서 이미 분리된 GitOps 루트 구조를 따라, `platform/helm`(Helm ApplicationSet)과 `platform/crds`(Kustomize) 자원도 환경별(dev/prod)로 완전히 분리해 교차 오너십·Sync 충돌을 제거한다.

---

## 1. 배경 요약

- **클러스터 루트 분리**  
  `clusters/dev/root-app.yaml` · `clusters/prod/root-app.yaml`가 서로 다른 Git 리비전(`refactor/gitops-sync-wave` vs `main`)과 프로젝트(`project: dev` vs `prod`)를 사용하며 App-of-Apps 트리를 구축한다.

- **Helm ApplicationSet 현황(분리 이전)**  
  예: `platform/helm/grafana/app.yaml`, `platform/helm/postgres-operator/app.yaml`은 list generator 안에 dev/prod 엔트리를 한 번에 정의하고, `clusters/*/apps/*-*.yaml`에서 `directory.include: app.yaml`로 참조했다.

- **CRD(Kustomize) 현황**  
  `clusters/dev/apps/00-crds.yaml`, `clusters/prod/apps/00-crds.yaml` 모두 동일한 `platform/crds` Kustomization을 `Replace=true` 옵션과 함께 적용한다. 결과적으로 동일한 Cluster-scoped CRD를 두 환경 App이 동시에 소유하려 하면서 `object has been modified` · `SharedResourceWarning`이 발생한다.

---

## 2. 문제 정의

1. **환경 혼재 ApplicationSet**  
   - AppSet 한 개가 dev/prod 리소스를 동시에 생성하고, 두 Application이 동일 리소스(예: ClusterRole, CRD, Namespace)를 소유해 OutOfSync/Degraded 상태가 반복된다.
2. **CRD 오너십 불명확**  
   - 동일 Kustomize 번들을 각 환경 App이 적용하면서 Server-side diff가 충돌한다.
3. **릴리스/롤백 단위 불일치**  
   - dev는 `refactor/gitops-sync-wave`, prod는 `main`을 바라보지만, Helm/CRD 레이어는 동일 파일에 두 리비전을 동시에 정의해 코드 리뷰와 프로모션 경로가 혼재된다.

---

## 3. 목표 및 원칙

| 항목 | 목표 |
|------|------|
| Ownership | 하나의 리소스는 단 하나의 Argo Application에서만 생성/갱신 |
| Repo 구조 | `platform/helm/<component>/{base,dev,prod}` · `platform/crds/{base,overlays}` |
| Git Flow | dev는 `refactor/gitops-sync-wave`, prod는 `main`에서만 변경 |
| Sync Wave | 기존 Wave 정의 유지, 단 참조 경로만 환경별 디렉터리로 교체 |
| 마이그레이션 | Zero-downtime, AppSet 교체 전에 대상 App Pause → 새 구조 적용 후 Unpause |

---

## 4. 설계 방향

### 4.1 리포지토리 구조 변경안

| 현재 | 개선안 |
|------|--------|
| `platform/helm/<component>/app.yaml` 안에서 dev/prod 동시 정의 | `platform/helm/<component>/{base,dev,prod}/application.yaml` (base + env overlay) |
| `platform/crds/<component>/kustomization.yaml`를 dev/prod App이 동시 참조 | `platform/crds/<component>/{base,dev,prod}` (base + env overlay) |
| `clusters/{env}/apps/*` → `directory.include: app.yaml` | `clusters/{env}/apps/*` → `directory.path: platform/helm/<component>/<env>` |

### 4.2 Helm(AppSet) 분리 절차

1. **디렉터리 생성**
   ```
   platform/helm/<component>/
     ├── base/
     │     ├── application.yaml   # 공통 spec (chart, repo, syncPolicy 등)
     │     └── kustomization.yaml
     ├── dev/
     │     ├── application.yaml   # base를 직접 복사하거나 Kustomize overlay 사용
     │     └── kustomization.yaml (선택)
     └── prod/
           ├── application.yaml
           └── kustomization.yaml (선택)
   ```
   - Kustomize overlay를 쓰지 않을 경우, `dev/application.yaml`과 `prod/application.yaml`에서 base를 복사해 필요한 값만 수정한다.

2. **env별 Application 정의**
   - dev:
     - `project: dev`
     - `source.chart` + `helm.parameters/valuesObject`에 dev 설정만 포함
     - `targetRevision: refactor/gitops-sync-wave`
   - prod는 동일 구조에서 `project: prod`, `targetRevision: main`, prod 매개변수로만 차등.
   - 대부분의 컴포넌트는 base/overlay 패턴이 중복 감소와 리뷰 용이성 측면에서 더 안전하지만, 매우 단순한 차트라면 dev/prod에 공통 spec을 복사한 뒤 environment 값만 수정하는 방식도 허용한다.

3. **기존 AppSet 제거**
   - `platform/helm/<component>/app.yaml`(multi-env AppSet)을 삭제하거나 `archive/`로 이동.
   - `clusters/*/apps`에서 AppSet을 배포하던 ApplicationSet(`dev-data-operators`, `dev-alb-controller-appset` 등)은 `Application`으로 교체하거나, 새 env overlay를 직접 가리키도록 변경.

4. **Argo App-of-Apps 갱신**
   - 예: `clusters/dev/apps/21-grafana.yaml`의 `path`를 `platform/helm/grafana/dev`로 교체.
   - Prod도 동일하게 `platform/helm/grafana/prod`.

5. **마이그레이션**
   - 대상 App을 `argocd app set <name> --sync-policy none` 등으로 일시 정지 → 새 Application 생성 → 상태 확인 후 기존 App 제거.

### 4.3 CRD(Kustomize) 분리 절차

1. **Base/Overlay 구조화**
```
platform/crds/
  ├── alb-controller/
  │    ├── base/kustomization.yaml
  │    ├── dev/kustomization.yaml
  │    └── prod/kustomization.yaml
  ├── external-secrets/
  │    └── (동일 패턴)
  └── ...
```
   - base에는 현재 `platform/crds/*/kustomization.yaml`에서 remote bundle을 참조하는 부분을 그대로 둔다.
   - overlay는 base를 `resources`로 include 하며, env별 추가 패치(예: label, namespace annotation)나 버전 pinning(다른 tag) 필요 시 `patchesStrategicMerge`로 분리한다.

2. **환경별 Application 정의**
   - `clusters/dev/apps/00-crds.yaml` → `path: platform/crds/<component>/dev` (또는 dev 전체를 묶은 aggregator)
   - `clusters/prod/apps/00-crds.yaml` → `path: platform/crds/<component>/prod`
   - Dev/Prod 구성이 다른 remote tag를 바라봐야 하면 env 디렉터리에서 `patchesStrategicMerge`나 `components:`로 개별 리소스를 재정의한다.

3. **소유권 규칙**
   - 동일 CRD가 dev/prod 양쪽에 필요하더라도, 물리적으로 하나의 클러스터에서만 설치·관리한다는 원칙을 세우고 나머지 env 디렉터리에서는 `resources:` 목록에서 제외한다.  
     예: 공용 클러스터라면 dev 디렉터리만 CRD를 적용하고 prod 디렉터리는 비워 두거나 `dependsOn` 없이 skip.

4. **검증**
   - `kubectl kustomize platform/crds/<component>/dev | kubeconform`로 lint → dev cluster에만 `kubectl apply --server-side --dry-run=client` 확인.  
   - Prod도 동일하게 분리 검증 후 배포.

### 4.4 Sync Wave 및 Project 영향

- Sync wave 값(`argocd.argoproj.io/sync-wave`)은 기존 manifest에서 그대로 유지한다.
- App 이름 규칙: `dev-<component>` · `prod-<component>`를 유지해 모니터링 템플릿 변경이 불필요하도록 한다.
- AppSet을 Application으로 바꾸면 Argo Projects의 `sourceRepos` · `destinations` 설정을 수정해야 할 수 있으므로, `argocd proj edit` 시나리오를 문서화한다.

---

## 5. 단계별 실행 계획

| 단계 | 작업 | 산출물 |
|------|------|--------|
| 0 | 본 문서 확정 및 리뷰 | 승인된 설계서 |
| 1 | Skeleton 디렉터리 생성 (`platform/helm/<component>/{base,dev,prod}`, `platform/crds/<component>/{base,dev,prod}`) | 빈 overlay + README |
| 2 | Helm App 마이그레이션 (우선순위: cluster-scoped 리소스를 만드는 컴포넌트) | env별 Application manifest |
| 3 | CRD overlay 구성 및 dev/prod Application 경로 수정 | `clusters/*/apps/00-crds.yaml` 업데이트 |
| 4 | Argo 테스트 & 문서화 (Sync 상태 스크린샷, runbook) | `docs/troubleshooting/...` 업데이트 |
| 5 | 잔여 AppSet/Deprecated 파일 정리 | legacy 디렉터리 삭제 또는 `archive/` 이동 |

---

## 6. 리스크 및 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| App 이름/UID 변경으로 Argo가 리소스를 재생성 | 잠시 동안 리소스 재배포 | 동일 `metadata.name`을 유지하고 `Application` spec만 교체, 필요 시 `argocd app set ... --replace` 사용 |
| CRD를 한쪽에서만 관리할 때 다른 환경이 의존 | Prod 기능 영향 | overlay 설계 시 “환경 공유 리소스” 목록을 먼저 정의하고, 실제로 어디에서 apply할지 합의 |
| Git 리비전 차이로 overlay간 Drift | Hotfix 지연 | dev/prod overlay 각각에서 버전 관리, prod 변경 시 cherry-pick 전략 명시 |

---

## 7. 후속 문서 및 작업

- `docs/deployment/HELM_PLATFORM_STACK_GUIDE.md`에 본 구조 반영 (새 디렉터리 트리, 운영 절차).
- `docs/troubleshooting/argocd-applicationset-patterns.md`에 “환경 분리 패턴” 항목 추가.
- Actual 작업 순서와 체크리스트는 `docs/checklists/SYNC_WAVE_PENDING_ITEMS.md`에 항목을 신설해 추적.

---

> 이 문서는 Helm/CRD 환경 분리 작업의 기준선이며, 구현 완료 후 변경 내역과 검증 결과(Argo UI 캡처, `kubectl get application`)를 본 문서 하단에 링크 형태로 축적한다.


