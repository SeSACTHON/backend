"""Auth Application.

Clean Architecture 기반 인증 서비스입니다.

Layers:
    - domain/: 순수 비즈니스 로직
    - application/: Use Cases (Commands/Queries)
    - infrastructure/: 외부 시스템 연결
    - presentation/: HTTP 인터페이스
    - setup/: 설정 및 의존성 주입
"""

__version__ = "2.0.0"
