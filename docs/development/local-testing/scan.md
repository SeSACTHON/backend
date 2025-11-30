# Scan API 로컬 테스트 가이드

## 한눈에 보기

- **기본 포트**: `8003`
- **Swagger**: `http://localhost:8003/api/v1/scan/docs`
- **필수 키**: `OPENAI_API_KEY`
- **Auth 우회**: `SCAN_AUTH_DISABLED=true` (기본값 true)

## 1. 사전 준비

```bash
cd /Users/mango/workspace/SeSACTHON/backend
source .venv/bin/activate
pip install -r domains/scan/requirements.txt
pytest domains/scan/tests
```

### 필수 환경 변수

```bash
export OPENAI_API_KEY=<your-openai-key>
export SCAN_AUTH_DISABLED=true          # JWT 검증 비활성화
export SCAN_REWARD_FEATURE_ENABLED=false  # (선택) Character 보상 API 호출 비활성화
```

> OpenAI Vision API를 호출하므로 유효한 API Key가 없으면 애플리케이션이 즉시 종료됩니다.

## 2. FastAPI 개발 서버 실행

```bash
uvicorn domains.scan.main:app --reload --port 8003
```

- 이미지 URL은 CDN 등 외부에서 접근 가능한 주소여야 합니다.
- 분류 결과/보상 내역은 인메모리로 저장되므로 프로세스를 재시작하면 초기화됩니다.

## 3. 기본 점검

```bash
curl -s http://localhost:8003/health | jq
curl -s http://localhost:8003/api/v1/scan/categories | jq '.[:2]'

curl -X POST http://localhost:8003/api/v1/scan/classify \
  -H 'Content-Type: application/json' \
  -d '{"image_url":"https://images.dev.growbin.app/samples/pet.png","user_input":"이거 어떻게 버려?"}'
```

## 4. Auth 토글 및 Character 연동

- `SCAN_AUTH_DISABLED=true` 인 경우 `s_access` 쿠키 없이도 `/scan/classify` 요청이 허용됩니다.
- 실 사용자 ID 기반 리워드 적립 흐름을 테스트하려면:
  1. `SCAN_AUTH_DISABLED=false`
  2. Auth 스택을 실행 후 실제 쿠키를 획득
  3. Character API가 접근 가능한 환경(예: docker-compose.my-local + Postgres)에서 `SCAN_REWARD_FEATURE_ENABLED=true`

## 5. Troubleshooting

| 증상 | 해결 방법 |
| --- | --- |
| `OPENAI_API_KEY not set` | 키를 환경 변수로 주입하거나 `.env` 파일에 저장 후 `python-dotenv` 로드 |
| `Character reward API call failed` | Character API를 띄우지 않은 상태이므로 `SCAN_REWARD_FEATURE_ENABLED=false` 로 비활성화 |
| `/scan/classify` 401 | JWT 검증이 켜진 상태입니다. 로컬 테스트라면 `SCAN_AUTH_DISABLED=true` 로 설정하세요. |

