"""Auth Domain Layer.

순수 비즈니스 로직을 담당하는 레이어입니다.
외부 프레임워크나 라이브러리에 의존하지 않습니다.

Components:
    - entities/: 도메인 엔티티 (User, UserSocialAccount, LoginAudit)
    - value_objects/: 값 객체 (UserId, Email, TokenPayload)
    - enums/: 열거형 (OAuthProvider, TokenType)
    - ports/: 인터페이스 (UserIdGenerator)
    - services/: 도메인 서비스 (UserService)
    - exceptions/: 도메인 예외
"""
