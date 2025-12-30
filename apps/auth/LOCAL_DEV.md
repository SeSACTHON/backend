# Auth API 로컬 개발 가이드

## 🧪 테스트 방법

### 방법 1: pytest 단위 테스트 (가장 빠름)

```bash
cd /Users/mango/workspace/SeSACTHON/backend

# 의존성 설치
pip install -r apps/auth/requirements.txt

# 단위 테스트 실행
pytest apps/auth/tests/unit/ -v

# 커버리지 포함
pytest apps/auth/tests/unit/ -v --cov=apps/auth --cov-report=term-missing
```

### 방법 2: Docker Compose (통합 테스트)

```bash
cd apps/auth

# .env.local 파일 생성 (OAuth 키 설정)
cat > .env.local << 'EOF'
AUTH_GOOGLE_CLIENT_ID=your-google-client-id
AUTH_GOOGLE_CLIENT_SECRET=your-google-client-secret
AUTH_GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
AUTH_KAKAO_CLIENT_ID=your-kakao-client-id
AUTH_KAKAO_REDIRECT_URI=http://localhost:8000/api/v1/auth/kakao/callback
AUTH_NAVER_CLIENT_ID=your-naver-client-id
AUTH_NAVER_CLIENT_SECRET=your-naver-client-secret
AUTH_NAVER_REDIRECT_URI=http://localhost:8000/api/v1/auth/naver/callback
EOF

# 실행
docker-compose -f docker-compose.local.yml up --build

# 백그라운드 실행
docker-compose -f docker-compose.local.yml up --build -d

# 로그 확인
docker-compose -f docker-compose.local.yml logs -f auth

# 종료
docker-compose -f docker-compose.local.yml down
```

### 방법 3: uvicorn 직접 실행 (Hot Reload)

```bash
cd /Users/mango/workspace/SeSACTHON/backend

# PostgreSQL, Redis 먼저 실행 (Docker)
docker run -d --name auth-postgres -p 5433:5432 \
  -e POSTGRES_USER=sesacthon \
  -e POSTGRES_PASSWORD=sesacthon \
  -e POSTGRES_DB=sesacthon \
  postgres:16

docker run -d --name auth-redis -p 6380:6379 redis:7

# 환경변수 설정
export AUTH_DATABASE_URL="postgresql+asyncpg://sesacthon:sesacthon@localhost:5433/sesacthon"
export AUTH_REDIS_BLACKLIST_URL="redis://localhost:6380/0"
export AUTH_REDIS_OAUTH_STATE_URL="redis://localhost:6380/3"
export AUTH_JWT_SECRET_KEY="local-test-secret"
export PYTHONPATH="${PWD}"

# uvicorn 실행
uvicorn apps.auth.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔍 API 테스트

### Health Check
```bash
curl http://localhost:8000/health
```

### OAuth 인증 URL 생성
```bash
# Google
curl "http://localhost:8000/api/v1/auth/google/authorize?frontend_origin=http://localhost:3000"

# Kakao
curl "http://localhost:8000/api/v1/auth/kakao/authorize?frontend_origin=http://localhost:3000"

# Naver
curl "http://localhost:8000/api/v1/auth/naver/authorize?frontend_origin=http://localhost:3000"
```

### X-Frontend-Origin 헤더 테스트
```bash
curl -H "X-Frontend-Origin: http://localhost:3000" \
  "http://localhost:8000/api/v1/auth/google/authorize"
```

### OpenAPI 문서
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🐛 트러블슈팅

### PostgreSQL 연결 실패
```bash
# 컨테이너 상태 확인
docker ps -a | grep postgres

# 로그 확인
docker logs auth-postgres
```

### Redis 연결 실패
```bash
# Redis CLI로 테스트
docker exec -it auth-redis redis-cli ping
```

### OAuth 콜백 오류
- redirect_uri가 OAuth 제공자 콘솔에 등록되어 있는지 확인
- HTTPS가 필요한 경우 ngrok 등 터널링 사용

---

## 📁 환경변수 참조

| 환경변수 | 설명 | 기본값 |
|---------|------|--------|
| `AUTH_DATABASE_URL` | PostgreSQL 연결 URL | - |
| `AUTH_REDIS_BLACKLIST_URL` | 토큰 블랙리스트용 Redis | redis://localhost:6379/0 |
| `AUTH_REDIS_OAUTH_STATE_URL` | OAuth 상태용 Redis | redis://localhost:6379/3 |
| `AUTH_JWT_SECRET_KEY` | JWT 서명 키 | - |
| `AUTH_GOOGLE_CLIENT_ID` | Google OAuth Client ID | - |
| `AUTH_GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | - |
| `AUTH_KAKAO_CLIENT_ID` | Kakao OAuth REST API 키 | - |
| `AUTH_NAVER_CLIENT_ID` | Naver OAuth Client ID | - |
| `AUTH_NAVER_CLIENT_SECRET` | Naver OAuth Client Secret | - |
