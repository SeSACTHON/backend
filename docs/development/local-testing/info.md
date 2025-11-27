# Info API 로컬 테스트 가이드

## 한눈에 보기

- **기본 포트**: `8040`
- **Swagger**: `http://localhost:8040/api/v1/info/docs`
- **의존성**: 없음 (인메모리 목 데이터)
- **Auth**: Public. 토큰 검증 없이 호출 가능

## 1. 사전 준비

```bash
cd /Users/mango/workspace/SeSACTHON/backend
source .venv/bin/activate
# 이미 다른 도메인을 위해 FastAPI 의존성을 설치했다면 생략 가능
pip install fastapi==0.109.0 uvicorn==0.27.0 pydantic==2.5.3
pytest domains/info/tests
```

## 2. FastAPI 실행

```bash
uvicorn domains.info.main:app --reload --port 8040
```

## 3. 기본 점검

```bash
curl -s http://localhost:8040/health | jq
curl -s http://localhost:8040/api/v1/info/categories | jq
curl -s http://localhost:8040/api/v1/info/items/1 | jq
curl -X POST http://localhost:8040/api/v1/info/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"페트병"}' | jq
```

## 4. 개발 메모

- 모든 응답은 `domains/info/services/info.py` 에 정의된 목 데이터입니다.
- 별도 DB가 없으므로 다른 서비스와의 연결에 영향을 주지 않습니다.

## 5. Troubleshooting

| 증상 | 해결책 |
| --- | --- |
| `FastAPI application instance not found` | `domains/info/tests/test_app.py` 에서 sys.path 를 추가했으므로 루트에서 실행했는지 확인하세요. |
| 404 | Router prefix가 `/api/v1/info` 이므로 엔드포인트 경로를 정확히 사용합니다. |

