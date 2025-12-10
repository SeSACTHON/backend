FROM python:3.11-slim

WORKDIR /app

RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 의존성 설치
COPY domains/location/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY domains/_shared /app/domains/_shared
COPY domains/location /app/domains/location

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

CMD ["opentelemetry-instrument", "uvicorn", "domains.location.main:app", "--host", "0.0.0.0", "--port", "8000"]
