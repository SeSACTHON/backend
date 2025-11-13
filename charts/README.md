# Helm Chart 상태 및 사용 방침

**현재 상태**: ⚠️ 참고용 유지 (실제 배포는 Kustomize 사용)

---

## 📋 현재 배포 방식

### ✅ 실제 사용 중: Kustomize

```yaml
배포 도구: Kustomize + ArgoCD ApplicationSet
구조:
  k8s/
  ├── base/           # 공통 manifests
  └── overlays/       # API별 커스터마이징
      ├── auth/
      ├── my/
      ├── scan/
      └── ... (7개 API)

네임스페이스: api (단일 네임스페이스)
```

**참고**: `docs/architecture/08-GITOPS_TOOLING_DECISION.md`

---

## 📦 Helm Chart 상태

### charts/ecoeco-backend/

```yaml
상태: 참고용 유지
이유:
  - Helm → Kustomize 마이그레이션 완료 (2025-11-11)
  - 초기 구조 참고 자료
  - 롤백 시 참고 가능

실제 사용: ❌ 없음
ArgoCD 배포: Kustomize만 사용
```

---

## 🔧 최근 변경사항

### 2025-11-13: 네임스페이스 정리

**변경 파일**: `charts/ecoeco-backend/templates/namespaces.yaml`

```yaml
Before:
  - api ✅
  - workers ❌
  - data ❌
  - messaging ❌

After:
  - api ✅ (단일 네임스페이스)
  
제거 이유:
  - workers, data, messaging 실제 사용 안 함
  - Kustomize overlays는 모두 api 네임스페이스 사용
  - 문서와 실제 구조 일치
```

---

## 📚 관련 문서

- [GitOps 도구 선택](../../docs/architecture/08-GITOPS_TOOLING_DECISION.md) - Helm → Kustomize 전환 배경
- [네임스페이스 전략](../../docs/architecture/09-NAMESPACE_STRATEGY_ANALYSIS.md) - 현재 구조 vs 베스트 프랙티스
- [GitOps 파이프라인](../../docs/deployment/GITOPS_PIPELINE_KUSTOMIZE.md) - Kustomize 기반 배포

---

## ⚠️ 주의사항

```yaml
Helm Chart 삭제 금지:
  - 초기 구조 참고 자료
  - 트러블슈팅 시 비교 가능
  - 향후 하이브리드 배포 가능성

실제 배포:
  - Kustomize만 사용
  - ArgoCD ApplicationSet
  - Helm 사용 안 함
```

---

**작성일**: 2025-11-13  
**상태**: Helm Chart 유지 (참고용), Kustomize 사용 (실제 배포)

