# apps/scan/Dockerfile
# Clean Architecture Scan API (독립적, 도메인 의존성 없음)

FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements 먼저 복사 (캐시 활용)
COPY apps/scan/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 앱 코드만 복사 (완전 독립)
COPY apps/scan /app/scan

# 환경 변수
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 포트
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 실행
CMD ["uvicorn", "scan.main:app", "--host", "0.0.0.0", "--port", "8000"]
