# My API 로컬 테스트 가이드

## 한눈에 보기

- **기본 포트**: `8002` (docker compose 기준)
- **Swagger**: `http://localhost:8002/api/v1/my/docs`
- **Auth 우회**: `MY_AUTH_DISABLED=true` (기본값 true)
- **필수 백엔드**: Postgres 16, (초기 캐릭터 데이터용) Character Bootstrap Job

## 1. 사전 준비

```bash
cd /Users/mango/workspace/SeSACTHON/backend
source .venv/bin/activate
pip install -r domains/my/requirements.txt
pytest domains/my/tests
```

### 필수 환경 변수

- `MY_DATABASE_URL` (예: `postgresql+asyncpg://sesacthon:sesacthon@localhost:5435/ecoeco`)
- `MY_JWT_SECRET_KEY`
- (캐릭터 히스토리 연동 시) `CHARACTER_DATABASE_URL`
- `MY_AUTH_DISABLED=true` 로 설정하면 JWT 없이도 API 호출 가능

## 2. FastAPI 개발 서버 (uvicorn)

```bash
export MY_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/my
export MY_JWT_SECRET_KEY=local-secret
export CHARACTER_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/my
export MY_AUTH_DISABLED=true

uvicorn domains.my.main:app --reload --port 8002
```

> 로컬 Postgres가 없다면 아래 docker compose 스택을 활용하세요.

## 3. docker compose 스택

```bash
cd /Users/mango/workspace/SeSACTHON/backend/domains/my
MY_AUTH_DISABLED=true docker compose -f docker-compose.my-local.yml up --build
```

- `db` (Postgres 5435), `character-bootstrap`, `api` 컨테이너가 순차 실행됩니다.
- 종료: `docker compose -f docker-compose.my-local.yml down -v`

## 4. Auth 연동 토글

- 기본적으로 `MY_AUTH_DISABLED=true` 로 실행되며, JWT 없이 `/api/v1/users/*` 엔드포인트를 호출할 수 있습니다.
- 실제 쿠키 검증을 하려면:
  1. `domains/auth/docker-compose.auth-local.yml` 로 Auth 스택을 띄우고
  2. `MY_AUTH_DISABLED=false` 로 재실행합니다.

## 5. 빠른 점검 명령

```bash
curl -s http://localhost:8002/health | jq
curl -s http://localhost:8002/ready | jq
curl -s http://localhost:8002/api/v1/metrics | jq
```

## 6. Troubleshooting

| 증상 | 해결 방법 |
| --- | --- |
| `asyncpg.exceptions.InvalidCatalogNameError` | `MY_DATABASE_URL` 이 가리키는 DB가 없으므로 Postgres 내부에서 데이터베이스를 생성합니다. |
| `/api/v1/users/...` 401 | `MY_AUTH_DISABLED` 가 `false` 인데 쿠키가 없는 상태입니다. Auth 스택에서 로그인 후 재시도하거나 우회 플래그를 `true` 로 설정하세요. |

