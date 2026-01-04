FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 공유 코드 복사
COPY domains/_shared /app/domains/_shared

# Location 앱 의존성 설치
COPY apps/location/requirements.txt /app/apps/location/
RUN pip install --no-cache-dir -r apps/location/requirements.txt

# Location 앱 소스 복사
COPY apps/location /app/apps/location

# Python 경로 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 포트 노출
EXPOSE 8000

# 서버 실행
CMD ["uvicorn", "apps.location.main:app", "--host", "0.0.0.0", "--port", "8000"]
