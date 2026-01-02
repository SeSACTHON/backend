"""Auth Infrastructure Layer.

외부 시스템(DB, Redis, OAuth, gRPC, Messaging)과의 연결을 담당합니다.

Components:
    - common/adapters/: 저장소 기술과 무관한 공통 어댑터
    - persistence_postgres/: PostgreSQL 연결, ORM 매핑, 어댑터
    - persistence_redis/: Redis 연결 및 어댑터
    - grpc/: gRPC 클라이언트 및 어댑터
    - messaging/: RabbitMQ 이벤트 발행 어댑터
    - oauth/: OAuth 프로바이더 구현
    - security/: JWT 토큰 처리
    - exceptions/: 인프라 예외
"""
