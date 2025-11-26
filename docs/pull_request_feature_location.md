# 🚀 Pull Request · v0.8.4 Chat/Scan 멀티모달 파이프라인 개편

## 📋 변경 사항
- Vision/RAG/Answer 파이프라인을 `domains/_shared/waste_pipeline` 모듈로 통합
- 파이프라인 리소스(JSON/YAML/프롬프트)를 `data/waste_pipeline` 경로로 이동
- Chat/Scan Dockerfile에 `_shared` 모듈·데이터 복사를 추가해 컨테이너에서도 Vision 파이프라인 사용 가능
- Image 도메인 Secret을 SSM→일반 Secret 방식으로 단순화하고, Ingress/Kustomize 구조를 Info → Image로 교체
- 저장소 전체에 pre-commit 포맷(black/ruff/yaml formatter 등) 일괄 적용

## 🔍 관련 이슈
- Chat/Scan 이미지 첨부 시 Vision 파이프라인 재사용 필요
- CDN presigned URL을 프론트가 바로 사용할 수 있도록 Image API 구성 단순화
- 포맷 상태가 뒤죽박죽이었던 레포 정리 요구

## 🔧 상세 내용

### 1. 파이프라인 모듈화
- `domains/_shared/waste_pipeline/{vision,rag,answer,pipeline}.py` 로직을 추가하고, Chat/Scan 서비스는 `from domains._shared.waste_pipeline import ...` 형태로 재사용
- `domains/_shared/schemas/waste.py`로 결과 스키마(`WasteClassificationResult`)를 공통화
- Chat/Scan 서비스 로직은 동일하지만 의존 모듈 경로만 변경됨

### 2. 데이터 레이어 이관
- `data/waste_pipeline` 디렉터리에 YAML/JSON/프롬프트/결과 디렉터리를 구성
- `utils.py`는 프로젝트 루트를 기준으로 `data/waste_pipeline` 경로를 계산하여 로딩
- Dockerfile에서 `domains/_shared` 와 `data/waste_pipeline`을 함께 복사하도록 변경 → 컨테이너에서도 즉시 사용 가능

### 3. Image 도메인 구조 개편
- `domains/image/` 에 API/Dockerfile/Config/Service를 정식 도메인 구조로 추가 (기존 info -> image 리네임 반영)
- `workloads/domains/image/**`, `workloads/ingress/image/**`, `workloads/secrets/external-secrets/*/image-api-secrets.yaml` 등을 새 구조에 맞게 생성
- Secret은 다른 도메인과 동일하게 YAML에 직접 값을 기술(SSM ExternalSecret 제거) → ArgoCD가 즉시 인식 가능

### 4. Repo 포맷 일괄 적용
- `pre-commit run --all-files` 실행으로 black/ruff/yaml/EOF/whitespace 등 포맷을 저장소 전체에 맞춤
- ansible/terraform/workloads/scripts 등 모든 서브디렉터리 포맷이 정리되어 이후 diff 가시성이 향상됨

## 🧪 테스트
- `pre-commit run --all-files`
- `docker build` (chat/scan/image) – Vision 리소스 복사 확인
- 로컬 presign API(`domains/image/docker-compose.image-local.yml`)로 CDN URL 발급 후 Vision 호출 스모크 테스트

## 🚀 배포 영향
- Chat/Scan: 새 이미지를 빌드 후 dev/prod ArgoCD Sync 필요 (`IMAGE_CDN_DOMAIN` 값은 변경 없음)
- Image: Secret 방식이 바뀌었으므로 기존 ExternalSecret 삭제 후 `kubectl apply -k workloads/secrets/external-secrets/{dev,prod}` 재적용
- 대규모 포맷 적용으로 모든 매니페스트가 업데이트되므로, ArgoCD Sync 시 대량의 “OutOfSync”가 표시될 수 있음. 순차적으로 Sync 하면 됨

## ⚠️ Breaking Changes
- 없음 (API 응답/스키마는 변경되지 않고 내부 모듈 경로만 이동). 단, Chat/Scan 이미지는 반드시 재빌드해야 Vision 파이프라인을 찾을 수 있음

## ✅ 체크리스트
- [x] Chat/Scan Dockerfile에 `_shared` 모듈/데이터 복사 추가
- [x] Image Secret/Ingress/Kustomize/Deployment dev/prod 동작 확인
- [x] pre-commit 포맷 전체 적용
- [x] GitHub 브랜치 `feature/chat-service` push 완료
- [ ] ArgoCD dev 환경에서 Chat/Scan/Image Sync (CDN presign/ Vision 라운드 트립 확인)
- [ ] API 스모크 테스트 (health, /api/v1/images, 이미지 첨부 대화)

## 📌 참고
- Shared 파이프라인 경로: `domains/_shared/waste_pipeline/`
- 데이터 파일: `data/waste_pipeline/` (JSON/YAML/프롬프트)
- Image presign API: `POST /api/v1/images/{channel}` → `cdn_url` 값을 Chat/Scan 요청에 연결하면 Vision 파이프라인이 프리사인드 URL을 그대로 사용함

