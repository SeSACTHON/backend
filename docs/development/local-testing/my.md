# My API 로컬 테스트 가이드

## 한눈에 보기

- **기본 포트**: `8000`(Auth), `8002`(My)
- **Swagger**: `http://localhost:8002/api/v1/user/docs`
- **Auth 우회**: `MY_AUTH_DISABLED=true` (기본값 true)
- **필수 백엔드**: Postgres 16 + Redis 7 (두 서비스가 공유), Auth DB Bootstrap, My DB Bootstrap, Character Catalog Job

## 0. `.env.my-local` 작성

새 통합 compose 스택은 Auth/My/Character가 모두 같은 Postgres·Redis를 사용합니다.  
다음 파일을 `domains/my/.env.my-local` 로 저장한 뒤 필요 시 값을 바꾸세요.

```bash
cat > domains/my/.env.my-local <<'EOF'
# Database / Redis
AUTH_DATABASE_URL=postgresql+asyncpg://sesacthon:sesacthon@db:5432/ecoeco
MY_DATABASE_URL=postgresql+asyncpg://sesacthon:sesacthon@db:5432/ecoeco
CHARACTER_DATABASE_URL=postgresql+asyncpg://sesacthon:sesacthon@db:5432/ecoeco
AUTH_REDIS_BLACKLIST_URL=redis://redis:6379/0
AUTH_REDIS_OAUTH_STATE_URL=redis://redis:6379/3
AUTH_SCHEMA_RESET_ENABLED=true
MY_SCHEMA_RESET_ENABLED=true

# JWT / Cookie
AUTH_JWT_SECRET_KEY=local-auth-secret
AUTH_JWT_ISSUER=sesacthon-auth
AUTH_JWT_AUDIENCE=sesacthon-clients
AUTH_COOKIE_DOMAIN=localhost
AUTH_FRONTEND_URL=http://localhost:5173
MY_JWT_SECRET_KEY=local-auth-secret
MY_AUTH_DISABLED=false
AUTH_CHARACTER_ONBOARDING_ENABLED=false

# OAuth (임시 값, 실제 테스트 시 교체)
AUTH_CHARACTER_API_BASE_URL=http://host.docker.internal:8004
AUTH_CHARACTER_API_TOKEN=local-character-token
AUTH_KAKAO_CLIENT_ID=<YOUR_KAKAO_CLIENT_ID>
AUTH_KAKAO_REDIRECT_URI=http://localhost:8000/api/v1/auth/kakao/callback
AUTH_GOOGLE_CLIENT_ID=<YOUR_GOOGLE_CLIENT_ID>
AUTH_GOOGLE_CLIENT_SECRET=<YOUR_GOOGLE_CLIENT_SECRET>
AUTH_GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
AUTH_NAVER_CLIENT_ID=<YOUR_NAVER_CLIENT_ID>
AUTH_NAVER_CLIENT_SECRET=<YOUR_NAVER_CLIENT_SECRET>
AUTH_NAVER_REDIRECT_URI=http://localhost:8000/api/v1/auth/naver/callback
EOF
```

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

## 3. docker compose 스택 (Auth + My 통합)

```bash
cd /Users/mango/workspace/SeSACTHON/backend/domains/my
docker-compose --env-file .env.my-local -f docker-compose.my-local.yml up --build
```

- 기동 순서: `db` → `redis` → `auth-bootstrap` → `my-bootstrap`/`character-bootstrap` → `auth` → `my-api`
- `auth` 는 `http://localhost:8000`, `my-api` 는 `http://localhost:8002`
- 종료: `docker-compose --env-file .env.my-local -f docker-compose.my-local.yml down -v`

> 기존처럼 별도의 Auth compose 를 띄울 필요가 없습니다.  
> 통합 스택이 Postgres/Redis 및 부트스트랩 잡을 모두 실행합니다.

## 4. Auth 연동 토글

- 통합 compose 를 그대로 쓰면 Auth API가 항상 같이 떠 있으므로, `MY_AUTH_DISABLED=false` 로 재시작하면 쿠키 검증 흐름을 재현할 수 있습니다.
- JWT를 우회하고 싶다면 `.env.my-local` 의 `MY_AUTH_DISABLED=true` 유지 후 재기동하세요.

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
| `/api/v1/user/...` 401 | `MY_AUTH_DISABLED` 가 `false` 인데 쿠키가 없는 상태입니다. Auth 스택에서 로그인 후 재시도하거나 우회 플래그를 `true` 로 설정하세요. |

