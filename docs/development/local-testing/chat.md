# Chat API 로컬 테스트 가이드

## 한눈에 보기

- **기본 포트**: `8030`
- **Swagger**: `http://localhost:8030/api/v1/chat/docs`
- **세션 저장소**: Redis 7 (없으면 인메모리 fallback)
- **Auth 우회**: `CHAT_AUTH_DISABLED=true` (기본값 true)
- **OpenAI**: `OPENAI_API_KEY` 를 설정하면 GPT 응답 사용, 없으면 기본 답변

## 1. 사전 준비

```bash
cd /Users/mango/workspace/SeSACTHON/backend
source .venv/bin/activate
pip install -r domains/chat/requirements.txt
pytest domains/chat/tests
```

### 환경 변수

```bash
export CHAT_REDIS_URL=redis://localhost:6379/7
export CHAT_AUTH_DISABLED=true
# (선택) export OPENAI_API_KEY=<key>  # 없으면 기본 답변 + 이미지 파이프라인만 사용
```

Redis가 필요하면 간단하게 `docker run --name chat-redis -p 6379:6379 redis:7` 로 띄울 수 있습니다.

## 2. FastAPI 실행

```bash
uvicorn domains.chat.main:app --reload --port 8030
```

## 3. 기본 점검

```bash
curl -s http://localhost:8030/health | jq

curl -X POST http://localhost:8030/api/v1/chat/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"페트병 어떻게 버려?", "temperature":0.2}' | jq

curl -s http://localhost:8030/api/v1/chat/suggestions | jq
```

## 4. 이미지 + Scan 파이프라인 연동

- `image_url` 필드를 포함해 호출하면 Scan 파이프라인을 내부적으로 실행합니다.
- 이때 `OPENAI_API_KEY` 가 없어도 Scan 서비스에서 이미지를 처리할 수 있도록 별도로 띄워져 있어야 합니다.

## 5. Auth 토글

- 기본값 `CHAT_AUTH_DISABLED=true` 상태에서는 JWT 없이 `/api/v1/chat/*` 요청이 허용됩니다.
- 실제 사용자별 세션 history를 확인하려면 `CHAT_AUTH_DISABLED=false` 로 실행하고 Auth 스택에서 발급받은 `s_access` 쿠키를 첨부하세요.

## 6. Troubleshooting

| 증상 | 해결책 |
| --- | --- |
| Redis 연결 오류 | `CHAT_REDIS_URL` 을 확인하고 로컬 Redis 를 띄웁니다. 필요 시 `redis-cli ping` 으로 점검 |
| 응답이 항상 동일 | `OPENAI_API_KEY` 가 없으면 fallback 답변만 반환합니다. |
| 401 Unauthorized | Auth 우회 플래그를 true 로 돌리거나 실제 쿠키를 포함하세요. |

