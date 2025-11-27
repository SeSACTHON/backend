# Image API 로컬 테스트 가이드

## 한눈에 보기

- **기본 포트**: `8020`
- **Swagger**: `http://localhost:8020/api/v1/image/docs`
- **백엔드**: Redis 7 + AWS S3 (실제 버킷 또는 LocalStack)
- **Auth 우회**: `IMAGE_AUTH_DISABLED=true` (기본값 true)

## 1. 사전 준비

```bash
cd /Users/mango/workspace/SeSACTHON/backend
source .venv/bin/activate
pip install -r domains/image/requirements.txt
pytest domains/image/tests
```

### 필수 환경 변수

```bash
export IMAGE_AUTH_DISABLED=true
export IMAGE_AWS_REGION=ap-northeast-2
export IMAGE_S3_BUCKET=dev-sesacthon-dev-images
export IMAGE_CDN_DOMAIN=https://images.dev.growbin.app
export IMAGE_REDIS_URL=redis://localhost:6386/6
export AWS_ACCESS_KEY_ID=<aws-access-key>
export AWS_SECRET_ACCESS_KEY=<aws-secret>
# (세션 토큰 사용 시) export AWS_SESSION_TOKEN=<session-token>
```

## 2. docker compose 실행

```bash
cd /Users/mango/workspace/SeSACTHON/backend/domains/image
IMAGE_AUTH_DISABLED=true docker compose -f docker-compose.image-local.yml up --build
```

- `redis`(포트 6386)와 `api` 컨테이너가 실행됩니다.
- 종료: `docker compose -f docker-compose.image-local.yml down -v`

## 3. FastAPI 단독 실행

Redis를 별도로 띄워둔 경우:

```bash
uvicorn domains.image.main:app --reload --port 8020
```

## 4. 기본 점검

```bash
curl -s http://localhost:8020/health | jq
curl -s http://localhost:8020/api/v1/image/metrics | jq

# 업로드 세션 만들기
curl -X POST http://localhost:8020/api/v1/image/upload/init \
  -H 'Content-Type: application/json' \
  -d '{"target":"chat","mime_type":"image/png"}'
```

## 5. Auth 토글

- `IMAGE_AUTH_DISABLED=true` 이면 쿠키 없이 Presigned URL 발급이 가능합니다.
- 실제 사용자 쿠키와 연동하려면 `IMAGE_AUTH_DISABLED=false` 로 재실행하고 Auth 스택을 띄운 뒤 `s_access` 쿠키를 포함해 호출하세요.

## 6. Troubleshooting

| 증상 | 해결책 |
| --- | --- |
| `botocore.exceptions.NoCredentialsError` | AWS 자격증명이 누락되었습니다. export 또는 `aws configure` 로 주입하세요. |
| Presigned URL이 사라짐 | `IMAGE_UPLOAD_STATE_TTL` 값을 늘리거나 Redis TTL 상태를 확인합니다. |
| 401 Unauthorized | Auth 우회 플래그를 true 로 돌리거나 실제 쿠키를 첨부합니다. |

