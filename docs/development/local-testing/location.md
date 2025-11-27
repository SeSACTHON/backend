# Location API 로컬 테스트 가이드

## 한눈에 보기

- **기본 포트**: `8010` (docker compose 기본 노출)
- **Swagger**: `http://localhost:8010/api/v1/location/docs`
- **백엔드**: Postgres 16 + Redis 7 + 정규화 데이터 import 잡
- **Auth 우회**: `LOCATION_AUTH_DISABLED=true` (기본값 true)

## 1. 사전 준비

```bash
cd /Users/mango/workspace/SeSACTHON/backend
source .venv/bin/activate
pip install -r domains/location/requirements.txt
pytest domains/location/tests
```

## 2. docker compose 로 전체 스택 실행

```bash
cd /Users/mango/workspace/SeSACTHON/backend/domains/location
LOCATION_AUTH_DISABLED=true docker compose -f docker-compose.location-local.yml up --build
```

- 구성 요소: `db`(Postgres 5434), `redis`(6381), `normalized-import` (CSV 주입), `api`
- 종료 시 `docker compose -f docker-compose.location-local.yml down -v`

## 3. 환경 변수 요약

| 이름 | 설명 |
| ---- | ---- |
| `LOCATION_DATABASE_URL` | Postgres 접속 URL |
| `LOCATION_REDIS_URL` | 캐시/세션 Redis URL |
| `LOCATION_AUTH_DISABLED` | JWT 우회 여부 (default true) |

## 4. FastAPI 수동 실행이 필요한 경우

DB/Redis를 이미 갖고 있다면 아래처럼 직접 실행할 수 있습니다.

```bash
export LOCATION_DATABASE_URL=postgresql+asyncpg://location:location@localhost:5434/location
export LOCATION_REDIS_URL=redis://localhost:6381/5
export LOCATION_AUTH_DISABLED=true

uvicorn domains.location.main:app --reload --port 8010
```

## 5. 기본 점검

```bash
curl -s http://localhost:8010/health | jq
curl -s "http://localhost:8010/api/v1/location/search?query=강남" | jq '.results[:3]'
curl -s http://localhost:8010/api/v1/location/metrics | jq
```

## 6. Auth 토글

- 기본값은 `true` 이므로 JWT 없이도 `/api/v1/location/*` 호출이 가능합니다.
- 실제 세션 검증이 필요하면 `LOCATION_AUTH_DISABLED=false` 로 바꾸고 Auth 스택에서 발급받은 `s_access` 쿠키를 사용하세요.

## 7. Troubleshooting

| 증상 | 해결 방법 |
| --- | --- |
| `normalized-import` 컨테이너가 실패 | CSV 경로가 변경되지 않았는지 확인 후 `docker compose ... up normalized-import` 로 재시도 |
| Redis 연결 실패 | 포트 충돌 시 `IMAGE_REDIS_URL` 처럼 별도의 DB index로 변경 |
| 401 Unauthorized | `LOCATION_AUTH_DISABLED` 가 false 이고 쿠키가 없습니다. 필요에 따라 true 로 돌리세요. |

