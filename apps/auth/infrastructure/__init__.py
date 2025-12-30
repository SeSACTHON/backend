"""Auth Infrastructure Layer.

외부 시스템(DB, Redis, OAuth)과의 연결을 담당합니다.

Components:
    - adapters/: Gateway 구현체
    - persistence_postgres/: PostgreSQL 연결 및 ORM 매핑
    - persistence_redis/: Redis 연결 및 저장소
    - security/: JWT 토큰 처리
    - oauth/: OAuth 프로바이더 구현
    - exceptions/: 인프라 예외
"""
