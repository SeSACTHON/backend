# Character API 로컬 테스트 가이드

## 한눈에 보기

- **기본 포트**: `8004`
- **Swagger**: `http://localhost:8004/api/v1/character/docs`
- **스토리지**: 기본 SQLite (`character.db`), 필요 시 Postgres
- **Auth 우회**: `CHARACTER_AUTH_DISABLED=true` (기본값 true)

## 1. 사전 준비

```bash
cd /Users/mango/workspace/SeSACTHON/backend
source .venv/bin/activate
pip install -r domains/character/requirements.txt
pytest domains/character/tests
```

### 주요 환경 변수

```bash
export CHARACTER_DATABASE_URL=sqlite+aiosqlite:///./character.db  # 기본값
export CHARACTER_AUTH_DISABLED=true
```

필요하다면 Postgres URL(예: `postgresql+asyncpg://sesacthon:sesacthon@localhost:5435/ecoeco`)로 바꿀 수 있습니다.

## 2. FastAPI 개발 서버 실행

```bash
uvicorn domains.character.main:app --reload --port 8004
```

> 최초 실행 시 SQLite 파일이 자동으로 생성됩니다.

## 3. 샘플 데이터 주입 (선택)

캐릭터 카탈로그/리워드 매핑을 미리 넣고 싶다면 Job을 실행하세요.

```bash
python -m domains.character.jobs.import_character_catalog \
  --database-url ${CHARACTER_DATABASE_URL}
```

## 4. 기본 점검

```bash
curl -s http://localhost:8004/health | jq
curl -s http://localhost:8004/api/v1/character/rewards | head
```

## 5. Auth 토글

- `CHARACTER_AUTH_DISABLED=true` 이면 JWT 없이 `/api/v1/character/*` 호출이 가능합니다.
- 실제 쿠키를 검증하려면 Auth 스택 실행 후 `CHARACTER_AUTH_DISABLED=false` 로 재실행하세요.

## 6. Troubleshooting

| 증상 | 해결 방법 |
| --- | --- |
| `sqlite3.OperationalError: no such table` | Job이 실행되기 전에 API를 호출했습니다. 위 import job을 먼저 실행하거나 SQLite 파일을 삭제 후 다시 띄웁니다. |
| `/api/v1/internal/characters/rewards` 401 | Auth 우회가 꺼져 있습니다. 로컬 테스트라면 `CHARACTER_AUTH_DISABLED=true` 로 설정하세요. |

