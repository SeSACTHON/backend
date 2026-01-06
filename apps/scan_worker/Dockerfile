# apps/scan_worker/Dockerfile
# Scan Worker - Clean Architecture (독립적, 도메인 의존성 없음)

FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements 먼저 복사 (캐시 활용)
COPY apps/scan_worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Worker 코드만 복사 (완전 독립)
COPY apps/scan_worker /app/scan_worker

# 환경 변수
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Celery Worker 실행
CMD ["celery", "-A", "scan_worker.setup.celery:celery_app", "worker", \
     "--pool=gevent", "--concurrency=100", \
     "-Q", "scan.vision,scan.rule,scan.answer,scan.reward", \
     "--loglevel=INFO"]
