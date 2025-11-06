# Pull Request: FastAPI Health Check Implementation

## 📋 개요
- **브랜치**: `feat/fastapi-health-checks` → `develop`
- **타입**: Feature
- **목적**: Kubernetes Liveness/Readiness Probe를 위한 Health Check 구현

## 🎯 변경 사항

### 1. Health Check 모듈

#### app/health.py (신규)

**클래스: HealthChecker**
```python
class HealthChecker:
    def add_readiness_check(self, name: str, check_func: Callable)
    async def check_liveness(self) -> Dict
    async def check_readiness(self) -> Dict
    def shutdown(self)
```

**함수: setup_health_checks()**
```python
def setup_health_checks(app: FastAPI, service_name: str) -> HealthChecker:
    # /health, /ready 엔드포인트 자동 추가
    # Graceful shutdown 지원
```

**공통 Check 함수**:
- `check_postgres()` - PostgreSQL 연결 확인
- `check_redis()` - Redis 연결 확인
- `check_rabbitmq()` - RabbitMQ 연결 확인
- `check_s3()` - S3 버킷 접근 확인

### 2. Waste API 예제

#### services/waste-api/main.py (신규)
```python
from fastapi import FastAPI
from app.health import setup_health_checks, check_postgres, check_redis, check_s3

app = FastAPI(title="Waste API")

# Health Check 설정
health_checker = setup_health_checks(app, service_name="waste-api")

# Readiness Checks 등록
@app.on_event("startup")
async def startup_event():
    health_checker.add_readiness_check("database", lambda: check_postgres(...))
    health_checker.add_readiness_check("cache", lambda: check_redis(...))
    health_checker.add_readiness_check("storage", lambda: check_s3(...))

# Business Logic
@app.get("/api/v1/waste/categories")
async def get_waste_categories():
    ...
```

### 3. Dockerfile

#### services/waste-api/Dockerfile (신규)
```dockerfile
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4. Requirements

#### services/waste-api/requirements.txt (신규)
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
asyncpg==0.29.0
aioredis==2.0.1
aio-pika==9.3.1
aioboto3==12.1.0
celery==5.3.4
```

## 🏥 Health Check 동작

### Liveness Probe
```
경로: /health
목적: 프로세스가 살아있는지 확인
실패 시: Pod 재시작
응답: {status, service, uptime_seconds}
```

### Readiness Probe
```
경로: /ready
목적: 트래픽 수신 준비 확인 (DB, Redis, S3)
실패 시: Service에서 제거 (트래픽 차단)
응답: {status, service, checks: {database, cache, storage}}
```

### Kubernetes 설정 (Helm Chart 연동)
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: http
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

## 🔧 사용 방법

### 1. 다른 API 서비스에 적용
```python
from app.health import setup_health_checks

app = FastAPI(title="Auth API")
health_checker = setup_health_checks(app, service_name="auth-api")

# Readiness checks 등록
health_checker.add_readiness_check("database", lambda: check_postgres(...))
```

### 2. 커스텀 Check 함수
```python
async def check_external_api() -> bool:
    try:
        response = await httpx.get("https://external-api.com/status")
        return response.status_code == 200
    except:
        return False

health_checker.add_readiness_check("external_api", check_external_api)
```

### 3. 로컬 테스트
```bash
# 서버 실행
cd services/waste-api
uvicorn main:app --reload

# Health check
curl http://localhost:8000/health
# {"status":"healthy","service":"waste-api","uptime_seconds":10}

# Readiness check
curl http://localhost:8000/ready
# {"status":"ready","service":"waste-api","checks":{"database":"ready","cache":"ready"}}
```

## ✅ 테스트 체크리스트

- [ ] `/health` 엔드포인트 응답 확인
- [ ] `/ready` 엔드포인트 응답 확인
- [ ] PostgreSQL 다운 시 readiness 실패 확인
- [ ] Redis 다운 시 readiness 실패 확인
- [ ] Graceful shutdown 동작 확인
- [ ] Kubernetes Probe 동작 확인

## 🔗 관련 PR

- ⬅️ Helm Charts 13-Node 템플릿 (Probe 설정 포함)
- ➡️ 다른 API 서비스 구현 (auth, userinfo 등)

## 📝 비고

- `waste-api`는 예제 구현 (실제 비즈니스 로직은 TODO)
- 나머지 5개 API도 동일한 패턴으로 구현 가능
- Readiness check는 의존성에 따라 선택적 등록

---

**리뷰어**: @team
**우선순위**: High
**호환성**: Kubernetes 1.22+, Python 3.11+

