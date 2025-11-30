## Scan API Spec (MVP)

- service: `domains/scan`
- namespace: `scan`
- ingress path: `/api/v1/scan/`
- swagger: `https://api.dev.growbin.app/api/v1/scan/docs`
- openapi json: `https://api.dev.growbin.app/api/v1/scan/openapi.json`
- repo link: `domains/scan`

### 1. Responsibility
- 이미지 URL 기반 폐기물 분류 (GPT Vision 호출)
- 분류 결과 저장 (`_TASK_STORE` 인메모리, 추후 Redis/DB)
- 카테고리 목록 제공 (`item_class_list.yaml` 기반)
- 서비스 상태/메트릭 노출

### 2. Endpoints

| Method | Path | Description | Auth |
| --- | --- | --- | --- |
| GET | `/health`, `/ready` | 헬스체크 | Public |
| GET | `/metrics/` | 서비스 지표 | Public |
| POST | `/scan/classify` | 단일 이미지 URL + 유저 메시지 입력, 즉시 분류 | Public |
| GET | `/scan/task/{task_id}` | 분류 결과 조회 | Public |
| GET | `/scan/categories` | 지원 카테고리 목록 | Public |

#### 2.1 POST /scan/classify
- Body: `ClassificationRequest`
```json
{
  "image_url": "https://images.dev.growbin.app/scan/2025/11/...png",
  "user_input": "이게 종이컵인가요?"
}
```
- Response: `ClassificationResponse`
```json
{
  "task_id": "uuid",
  "status": "completed",
  "message": "classification completed",
  "pipeline_result": { ...WasteClassificationResult... }
}
```
- image_url 필수. 없는 경우 `IMAGE_URL_REQUIRED` 오류.

#### 2.2 GET /scan/task/{task_id}
- 메모리 저장소 `_TASK_STORE`에서 조회.
- 없다면 404.
- 추후 Redis/DB로 교체 예정.

#### 2.3 GET /scan/categories
- `domains/_shared/waste_pipeline/data/item_class_list.yaml` 기반.
- major category + instructions 배열 반환.
- 캐시: `ScanService._category_cache`.

### 3. Dependencies
- `domains._shared.waste_pipeline` (OpenAI Vision 호출)
- OpenAI API Key (ExternalSecret `scan-secret`)
- S3 presigned 업로드 결과에서 전달된 CDN URL
- 추후 ai_jobs Queue

### 4. Environment Variables
- via ConfigMap: `LOG_LEVEL`, `ENVIRONMENT`
- via Secret: `OPENAI_API_KEY`
- DB/Redis host envs (`POSTGRES_HOST`, `REDIS_HOST`) 고정 값

### 5. Limitations
- `_TASK_STORE` 인메모리 → Pod 재시작 시 데이터 소실
- 인증 없음 (v0.1)
- 이미지 URL만 받음 (Presigned 업로드 + CDN까지 외부에서 처리)
- AI 파이프라인은 동기 호출 (celery/worker 없음)

### 6. Ingress/Deployment
- Service: `scan-api` (NodePort 8000)
- Ingress: `scan-ingress` (dev/prod 패치 추가됨)
- CI: `ci-services.yml`에서 `scan` 서비스 포함

### 7. TODO
- 결과 저장소를 Redis/DB로 치환
- 인증 (JWT) 적용
- AI 큐 통합 (SQS/Redis Stream)
- presigned 채널과 직접 연동 (현재는 문서 기준)

