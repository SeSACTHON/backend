## Scan API 테스트 가이드

- Base URL: `https://api.dev.growbin.app/api/v1/scan`
- Swagger: `https://api.dev.growbin.app/api/v1/scan/docs`
- 필요 권한: 현재 Public (v0.1). 추후 JWT 요구 가능.

### 1. 사전 준비
1. CDN에 접근 가능한 이미지 URL 확보 (예: Image API presigned → CDN URL).
2. Dev 환경 네트워크에서 `api.dev.growbin.app` 접근 가능해야 함.

### 2. 테스트 절차

#### 2.1 분류 요청
- Method: `POST /scan/classify`
- Body 예시:
```json
{
  "image_urls": [
    "https://images.dev.growbin.app/scan/2025/11/sample.png"
  ],
  "user_input": "이건 재활용이 가능한가요?"
}
```
- 기대 결과: HTTP 200, `status=completed`, `pipeline_result` 포함.
- 에러 케이스: `image_urls` 미입력 시 `status=failed`, `error=IMAGE_URL_REQUIRED`.

#### 2.2 분류 결과 조회
- `POST /scan/classify` 응답의 `task_id` 활용.
- Method: `GET /scan/task/{task_id}`
- 기대 결과: `status=completed`, 동일한 `pipeline_result`.
- 인메모리 저장이므로 Pod 재시작 후에는 404 가능.

#### 2.3 카테고리 조회
- Method: `GET /scan/categories`
- 기대 결과: YAML 기반 major category 목록 + `instructions` 배열.

#### 2.4 헬스/메트릭
- `GET /health`, `GET /ready`: 200 응답 확인.
- `GET /metrics/`: Prometheus scrape 가능 여부 확인.

### 3. 수동 확인 체크리스트
- [ ] `/scan/classify` 요청 1건 이상 성공.
- [ ] `/scan/task/{task_id}`로 방금 요청한 결과 조회.
- [ ] `/scan/categories` 응답에서 major category 목록 확인.
- [ ] `/health`, `/ready`, `/metrics` 모두 200.

### 4. Troubleshooting
- 404 `/openapi.json`: 앱 내부 `docs_url`/`openapi_url` 경로 불일치 → `FastAPI` 설정 확인.
- `Invalid or expired token`: 인증이 붙은 이후엔 JWT 필수.
- OpenAI 오류 (`invalid type for image_url`): CDN URL 전달 여부, `OPENAI_API_KEY` 주입 상태 확인 (`scan-secret`).

### 5. 향후 자동화
- k6 script로 이미지 URL 10건 반복 요청.
- Pytest integration: `tests/scan/test_classify.py` 추가 예정.

