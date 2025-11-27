# My API

유저 프로필 및 리워드 정보를 제공하는 FastAPI 마이크로서비스입니다. 소셜 로그인(Auth 서비스)에서 확보한 `provider`, `provider_user_id`, `email`, `username`, `name`, `profile_image_url` 데이터를 기반으로 사용자의 기본 정보를 읽고 업데이트합니다.

## 주요 기능

- `/health`, `/ready` 헬스 체크
- `/api/v1/users/{user_id}` 프로필 조회/수정/삭제
- `/api/v1/metrics` 서비스 메트릭 반환
- (내부) `UserRepository`/`MyService` 레이어를 통한 Postgres 접근

## 기술 스택

- Python 3.11, FastAPI, Pydantic v2
- SQLAlchemy 2.x + asyncpg
- ExternalSecret 기반 환경 변수 주입

## 환경 변수

| 이름 | 설명 |
| --- | --- |
| `MY_DATABASE_URL` | `postgresql+asyncpg://` 형식의 접속 URL |
| `MY_JWT_SECRET_KEY` | JWT 서명 키 (다른 서비스 검증용) |
| `MY_METRICS_CACHE_TTL_SECONDS` | 메트릭 캐시 TTL (초) |
| `MY_ACCESS_COOKIE_NAME` | 액세스 토큰 쿠키 이름 (기본값 `s_access`) |

> Dev/Prod 클러스터에서는 ExternalSecret(`my-secret`)이 위 변수들을 생성합니다.

## 로컬 실행 방법

```bash
cd domains/my
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
UVICORN_CMD="uvicorn domains.my.main:app --reload --port 8000"
MY_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/my" \
MY_JWT_SECRET_KEY="local-secret" \
$UVICORN_CMD
```

## API 문서

- Swagger UI: `http://localhost:8000/api/v1/my/docs`
- ReDoc: `http://localhost:8000/api/v1/my/redoc`
- OpenAPI JSON: `http://localhost:8000/api/v1/my/openapi.json`

## 테스트

```bash
cd domains/my
pytest
```

CI(GitHub Actions `ci-services.yml`)에서 `black`, `ruff`, `pytest`, Docker 이미지 빌드가 자동으로 실행됩니다. 수동 실행 시:

```bash
gh workflow run ci-services.yml -f target_services=my
```
