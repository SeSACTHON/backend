# Clean Architecture #11: Character 도메인 마이그레이션

> Character 도메인에 Clean Architecture를 적용하고, 로컬 인메모리 캐시 레이어를 통합한 과정을 기록합니다.

---

## 1. 마이그레이션 배경

### 1.1 기존 구조 (domains/character)

```
domains/character/
├── api/v1/endpoints/
│   ├── catalog.py          # HTTP 엔드포인트
│   └── internal_reward.py
├── services/
│   ├── character_service.py  # ~400줄, 조회 + 캐시 + 매칭
│   └── reward_evaluator.py
├── repositories/
│   └── character_repository.py
├── models/
│   └── character.py
└── rpc/
    └── character_servicer.py  # gRPC
```

**문제점**:

| 문제 | 설명 |
|------|------|
| 책임 혼재 | `character_service.py`가 조회, 캐시, 매칭을 모두 담당 |
| Redis 의존 | 캐시가 Redis에 결합 → Redis 장애 시 전체 장애 |
| 테스트 어려움 | 인프라 구현체에 직접 의존 → Mock 불가 |

### 1.2 마이그레이션 목표

| 목표 | 방법 |
|------|------|
| 계층 분리 | Domain, Application, Infrastructure, Presentation |
| 의존성 역전 | Port/Adapter 패턴으로 외부 의존성 추상화 |
| Redis 제거 | 로컬 인메모리 캐시로 전환 |
| 테스트 용이성 | Port 기반 Mock 주입 가능 |

---

## 2. 최종 폴더 구조

```
apps/character/
├── domain/
│   ├── entities/
│   │   ├── character.py           # Character 엔티티
│   │   └── character_ownership.py # 소유권 엔티티
│   └── enums/
│       └── character.py           # CharacterStatus 등
├── application/
│   ├── catalog/
│   │   ├── dto/catalog.py              # CatalogItem, CatalogResult
│   │   ├── ports/catalog_reader.py     # CatalogReader Port
│   │   ├── services/catalog_service.py # 순수 로직 (DTO 변환)
│   │   └── queries/get_catalog.py      # GetCatalogQuery
│   └── reward/
│       ├── dto/reward.py                  # RewardRequest, RewardResult
│       ├── ports/
│       │   ├── character_matcher.py       # CharacterMatcher Port
│       │   └── ownership_checker.py       # OwnershipChecker Port
│       ├── services/reward_policy_service.py  # 순수 로직 (정책)
│       └── commands/evaluate_reward.py    # EvaluateRewardCommand
├── infrastructure/
│   ├── cache/
│   │   ├── character_cache.py         # Thread-safe 싱글톤 캐시
│   │   ├── cache_consumer.py          # MQ Consumer (실시간 동기화)
│   │   └── local_cached_catalog_reader.py # 캐시 Decorator
│   ├── persistence_postgres/
│   │   ├── character_reader_sqla.py   # CatalogReader + CharacterMatcher 구현
│   │   └── ownership_checker_sqla.py  # OwnershipChecker 구현
│   └── persistence_redis/
│       └── cached_catalog_reader.py   # (레거시, 미사용)
├── presentation/
│   ├── http/
│   │   └── controllers/
│   │       ├── catalog.py             # GET /catalog
│   │       └── reward.py              # POST /internal/characters/rewards
│   └── grpc/
│       └── servicers/character_servicer.py
├── setup/
│   ├── config.py
│   ├── database.py
│   └── dependencies.py           # DI 설정
├── main.py                       # FastAPI 앱 + Lifespan
└── tests/
```

---

## 3. 계층별 설계

### 3.1 Domain Layer

도메인 계층은 **외부 의존성 없이** 순수 비즈니스 로직만 포함합니다.

```python
# domain/entities/character.py
@dataclass
class Character:
    """캐릭터 엔티티 - 수집 가능한 캐릭터의 정적 정의."""
    
    id: UUID
    code: str
    name: str
    type_label: str
    dialog: str
    description: str | None = None
    match_label: str | None = None  # 분류 결과와 매칭에 사용
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Character):
            return False
        return self.id == other.id
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| `@dataclass` 사용 | Entity는 상태 변경 가능, `frozen=False` |
| `match_label` 필드 | 분류 결과 → 캐릭터 매칭의 비즈니스 규칙을 도메인에 표현 |
| `__hash__`, `__eq__` | ID 기반 동등성으로 Entity 정체성 보장 |

### 3.2 Application Layer

Application 계층은 **Use Case를 오케스트레이션**합니다. Port를 통해 Infrastructure에 의존하지 않습니다.

#### 계층 구성 원칙

```
┌─────────────────────────────────────────────────────────────────────┐
│  Application Layer                                                   │
│                                                                      │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐    │
│  │     DTO        │    │    Service     │    │  Query/Command │    │
│  │  (데이터 전달)  │◄───│  (순수 로직)   │◄───│ (오케스트레이션)│    │
│  └────────────────┘    └────────────────┘    └───────┬────────┘    │
│                                                       │             │
│  ┌────────────────────────────────────────────────────┴───────┐    │
│  │                        Port (인터페이스)                     │    │
│  │     CatalogReader  │  CharacterMatcher  │  OwnershipChecker │    │
│  └────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ 의존성 역전
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Infrastructure Layer (Adapter 구현)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

**핵심 원칙**:

| 원칙 | 설명 | 이점 |
|------|------|------|
| **의존성 역전 (DIP)** | Application이 Port를 정의, Infrastructure가 구현 | 인프라 교체 용이 |
| **단일 책임 (SRP)** | Query/Command는 오케스트레이션, Service는 로직 | 테스트/유지보수 용이 |
| **인터페이스 분리 (ISP)** | 기능별 Port 분리 (Reader, Matcher, Checker) | 필요한 의존성만 주입 |

#### 구성 요소별 역할

| 구성 요소 | 역할 | Port 의존 | 예시 |
|-----------|------|-----------|------|
| **DTO** | 계층 간 데이터 전달 | ❌ | `CatalogItem`, `RewardRequest` |
| **Port** | Infrastructure 추상화 | ❌ | `CatalogReader`, `CharacterMatcher` |
| **Service** | 순수 비즈니스 로직 | ❌ | `CatalogService`, `RewardPolicyService` |
| **Query** | 읽기 Use Case 오케스트레이션 | ✅ | `GetCatalogQuery` |
| **Command** | 쓰기/평가 Use Case 오케스트레이션 | ✅ | `EvaluateRewardCommand` |

```
application/
├── catalog/
│   ├── dto/catalog.py              # CatalogItem, CatalogResult
│   ├── ports/catalog_reader.py     # CatalogReader Port
│   ├── services/catalog_service.py # 순수 로직 (DTO 변환)
│   └── queries/get_catalog.py      # Query (오케스트레이션)
└── reward/
    ├── dto/reward.py               # RewardRequest, RewardResult
    ├── ports/
    │   ├── character_matcher.py    # CharacterMatcher Port
    │   └── ownership_checker.py    # OwnershipChecker Port
    ├── services/reward_policy_service.py  # 순수 로직 (정책)
    └── commands/evaluate_reward.py # Command (오케스트레이션)
```

#### Port 정의

```python
# application/catalog/ports/catalog_reader.py
class CatalogReader(ABC):
    """캐릭터 카탈로그 조회 포트."""
    
    @abstractmethod
    async def list_all(self) -> Sequence[Character]:
        """모든 캐릭터 목록을 조회합니다."""
        ...
```

```python
# application/reward/ports/character_matcher.py
class CharacterMatcher(Protocol):
    """캐릭터 매칭 포트."""
    
    async def match_by_label(self, match_label: str) -> Character | None: ...
    async def get_default(self) -> Character: ...
```

```python
# application/reward/ports/ownership_checker.py
class OwnershipChecker(Protocol):
    """소유권 확인 포트."""
    
    async def is_owned(self, user_id: UUID, character_id: UUID) -> bool: ...
```

**설계 판단**:

| 포트 | 분리 근거 |
|------|----------|
| `CatalogReader` | 읽기 전용 조회 (CQRS Query) |
| `CharacterMatcher` | 매칭 로직에 특화된 메서드 |
| `OwnershipChecker` | 소유권은 다른 도메인(users)의 데이터 → 별도 Port |

#### Service (순수 비즈니스 로직)

Service는 **Port 의존성 없이** 순수 애플리케이션 로직만 담당합니다. Query/Command에서 호출됩니다.

```python
# application/catalog/services/catalog_service.py
class CatalogService:
    """카탈로그 서비스 - Entity → DTO 변환 로직."""
    
    def build_catalog_items(self, characters: Sequence[Character]) -> tuple[CatalogItem, ...]:
        """Character 엔티티 목록을 CatalogItem DTO 목록으로 변환합니다.
        
        정책:
        - dialog가 없으면 description 사용
        - 둘 다 없으면 빈 문자열
        """
        return tuple(
            CatalogItem(
                code=c.code,
                name=c.name,
                type_label=c.type_label,
                dialog=c.dialog or c.description or "",
                match_label=c.match_label,
                description=c.description,
            )
            for c in characters
        )
```

```python
# application/reward/services/reward_policy_service.py
class RewardPolicyService:
    """리워드 정책 서비스 - 보상 지급 여부 판단."""
    
    def should_evaluate(self, request: RewardRequest) -> bool:
        """보상 평가를 진행해야 하는지 판단합니다.
        
        정책:
        - 분리수거 규칙 정보가 있어야 함
        - 부적절한 항목이 없어야 함
        """
        return request.disposal_rules_present and not request.insufficiencies_present
    
    def determine_match_label(self, request: RewardRequest) -> str:
        """매칭에 사용할 라벨을 결정합니다.
        
        정책: 분류 결과의 중분류(middle_category)를 사용
        """
        return request.classification.middle_category
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| Port 의존 없음 | 순수 로직만 → 단위 테스트 용이 (Mock 불필요) |
| Query/Command 분리 | 오케스트레이션(Query/Command)과 비즈니스 로직(Service) 분리 |
| 정책 캡슐화 | 변경 가능성 높은 비즈니스 규칙을 한 곳에 집중 |

#### Query (읽기 오케스트레이션)

Query는 **Port와 Service를 조합**하여 Use Case를 실행합니다.

```python
# application/catalog/queries/get_catalog.py
class GetCatalogQuery:
    """캐릭터 카탈로그 조회 Query."""
    
    def __init__(self, reader: CatalogReader, service: CatalogService) -> None:
        self._reader = reader
        self._service = service
    
    async def execute(self) -> CatalogResult:
        # 1. Port를 통한 조회 (오케스트레이션)
        characters = await self._reader.list_all()
        
        # 2. Service를 통한 변환 (로직 위임)
        items = self._service.build_catalog_items(characters)
        
        return CatalogResult(items=items, total=len(items))
```

**설계 판단**: Query는 **오케스트레이션만 담당**, DTO 변환 로직은 Service에 위임합니다.

#### Command (쓰기/평가 오케스트레이션)

```python
# application/reward/commands/evaluate_reward.py
class EvaluateRewardCommand:
    """리워드 평가 Command."""
    
    def __init__(
        self,
        matcher: CharacterMatcher,
        ownership_checker: OwnershipChecker,
        policy_service: RewardPolicyService,
    ) -> None:
        self._matcher = matcher
        self._ownership_checker = ownership_checker
        self._policy_service = policy_service
    
    async def execute(self, request: RewardRequest) -> RewardResult:
        # 1. 정책 확인 (Service 위임)
        if not self._policy_service.should_evaluate(request):
            return RewardResult(received=False, match_reason="Conditions not met")
        
        # 2. 매칭 라벨 추출 (Service 위임)
        match_label = self._policy_service.determine_match_label(request)
        character = await self._matcher.match_by_label(match_label)
        
        if character is None:
            character = await self._matcher.get_default()
        
        # 3. 소유권 확인 (Port 호출)
        already_owned = await self._ownership_checker.is_owned(
            user_id=request.user_id,
            character_id=character.id,
        )
        
        # 4. 결과 반환 (저장은 Worker에서)
        return RewardResult(
            received=not already_owned,
            already_owned=already_owned,
            character_code=character.code,
            character_name=character.name,
            character_type=character.type_label,
            dialog=character.dialog,
            match_reason=f"Matched by {match_label}",
        )
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| 저장 분리 | 평가만 수행, 저장은 별도 Worker (Eventual Consistency) |
| 정책 위임 | `should_evaluate`, `determine_match_label`을 Service에 위임 |
| 오케스트레이션 집중 | Command는 흐름 제어만, 세부 로직은 Service |

### 3.3 Infrastructure Layer

Infrastructure 계층은 **Port의 구현체**를 제공합니다.

#### PostgreSQL Adapter

```python
# infrastructure/persistence_postgres/character_reader_sqla.py
class SqlaCharacterReader(CatalogReader, CharacterMatcher):
    """SQLAlchemy 기반 캐릭터 Reader.
    
    CatalogReader와 CharacterMatcher를 동시 구현 (ISP 위반 아님: 동일 데이터).
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def list_all(self) -> Sequence[Character]:
        stmt = select(CharacterModel).order_by(CharacterModel.name)
        result = await self._session.execute(stmt)
        return [character_model_to_entity(m) for m in result.scalars().all()]
    
    async def match_by_label(self, match_label: str) -> Character | None:
        stmt = select(CharacterModel).where(CharacterModel.match_label == match_label)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return character_model_to_entity(model) if model else None
    
    async def get_default(self) -> Character:
        stmt = select(CharacterModel).where(CharacterModel.code == "char-eco")
        result = await self._session.execute(stmt)
        return character_model_to_entity(result.scalar_one())
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| 단일 클래스 다중 Port | `CatalogReader`와 `CharacterMatcher`는 같은 테이블 → 분리 불필요 |
| 기본 캐릭터 하드코딩 | `char-eco`가 기본 캐릭터 (레거시 비즈니스 규칙) |

### 3.4 Presentation Layer

#### HTTP Controller

```python
# presentation/http/controllers/catalog.py
@router.get("/character/catalog", response_model=CatalogResponse)
async def get_catalog(
    query: GetCatalogQuery = Depends(get_catalog_query),
) -> CatalogResponse:
    result = await query.execute()
    return CatalogResponse(
        characters=[CharacterItem.from_dto(item) for item in result.items],
        total=result.total,
    )
```

#### gRPC Servicer

```python
# presentation/grpc/servicers/character_servicer.py
class CharacterServicer(CharacterServiceServicer):
    def __init__(
        self,
        evaluate_command: EvaluateRewardCommand,
        character_matcher: CharacterMatcher,
    ) -> None:
        self._evaluate_command = evaluate_command
        self._character_matcher = character_matcher
    
    async def EvaluateReward(self, request, context) -> EvaluateRewardResponse:
        dto = _proto_to_request(request)
        result = await self._evaluate_command.execute(dto)
        return _result_to_proto(result)
    
    async def GetDefaultCharacter(self, request, context) -> CharacterResponse:
        character = await self._character_matcher.get_default()
        return _character_to_proto(character)
```

**설계 판단**: HTTP와 gRPC 모두 **동일한 Application 계층**(Query/Command)을 사용합니다.

---

## 4. 캐시 레이어 통합

### 4.1 설계 배경

기존 `CachedCatalogReader`는 Redis에 의존했습니다:

```python
# ❌ 기존: Redis 의존
class CachedCatalogReader(CatalogReader):
    def __init__(self, delegate: CatalogReader, redis: Redis):
        self._delegate = delegate
        self._redis = redis  # Redis 장애 = 전체 장애
```

**문제점**:

| 문제 | 영향 |
|------|------|
| Redis SPOF | Redis 장애 시 `/catalog` 전체 실패 |
| 네트워크 지연 | Redis 조회 ~2ms 추가 |
| 운영 복잡도 | Redis 클러스터 관리 필요 |

### 4.2 로컬 캐시 도입 판단

| 방식 | 레이턴시 | 장애 영향 | 운영 복잡도 |
|------|----------|----------|------------|
| DB 직접 | ~50ms | DB 장애 시 실패 | 낮음 |
| Redis 캐시 | ~2ms | Redis 장애 시 실패 | 중간 |
| **로컬 캐시** | ~0.01ms | Pod 독립 | 낮음 |

**로컬 캐시 선택 근거**:

1. **캐릭터 카탈로그 특성**: 13개 레코드, ~50KB, 변경 빈도 월 수 회
2. **읽기 비율**: 읽기 >> 쓰기 (캐싱 적합)
3. **일관성 요구**: Eventual Consistency 허용 (마스터 데이터)

### 4.3 캐시 계층 배치

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  GetCatalogQuery                                     │   │
│  │  - CatalogReader 포트에만 의존                       │   │
│  │  - 캐시 전략 모름                                    │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │ Port                              │
└─────────────────────────┼───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Infrastructure Layer                                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  LocalCachedCatalogReader (Decorator)               │   │
│  │  ├─ CharacterLocalCache (싱글톤)                    │   │
│  │  └─ SqlaCharacterReader (delegate)                  │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  CacheConsumerThread (백그라운드)                    │   │
│  │  - character.cache Fanout Exchange 구독             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**설계 판단**: 캐시는 **Infrastructure 계층의 관심사**입니다. Application은 캐시 존재를 모릅니다.

### 4.4 Thread-Safe 싱글톤 캐시

```python
# infrastructure/cache/character_cache.py
class CharacterLocalCache:
    """Thread-safe 싱글톤 캐릭터 캐시."""
    
    _instance: CharacterLocalCache | None = None
    _lock = Lock()  # 싱글톤 생성용
    
    def __new__(cls) -> CharacterLocalCache:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-Checked Locking
                    instance = super().__new__(cls)
                    instance._characters: dict[str, CachedCharacter] = {}
                    instance._initialized = False
                    instance._data_lock = Lock()  # 데이터 접근용
                    cls._instance = instance
        return cls._instance
    
    def set_all(self, characters: list) -> None:
        """전체 캐시 교체 (초기화 또는 full refresh)."""
        with self._data_lock:
            self._characters.clear()
            for char in characters:
                cached = CachedCharacter.from_entity(char)
                self._characters[str(cached.id)] = cached
            self._initialized = True
    
    def get_all(self) -> list[CachedCharacter]:
        """전체 캐릭터 목록 조회."""
        with self._data_lock:
            return list(self._characters.values())
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| Double-Checked Locking | 멀티스레드 환경에서 싱글톤 안전 생성 |
| 별도 `_data_lock` | 읽기/쓰기 분리로 싱글톤 생성과 데이터 접근 동시성 제어 |

### 4.5 Decorator 패턴 적용

```python
# infrastructure/cache/local_cached_catalog_reader.py
class LocalCachedCatalogReader(CatalogReader):
    """로컬 인메모리 캐시를 활용한 카탈로그 Reader.
    
    DB Reader를 데코레이트하여 로컬 캐시 레이어를 추가합니다.
    """
    
    def __init__(
        self,
        delegate: CatalogReader,
        cache: CharacterLocalCache | None = None,
    ) -> None:
        self._delegate = delegate
        self._cache = cache or get_character_cache()
    
    async def list_all(self) -> Sequence[Character]:
        # 1. 로컬 캐시 확인
        if self._cache.is_initialized and self._cache.count() > 0:
            logger.debug("Cache hit for catalog (local)")
            return [
                Character(
                    id=c.id, code=c.code, name=c.name,
                    type_label=c.type_label, dialog=c.dialog,
                )
                for c in self._cache.get_all()
            ]
        
        # 2. 캐시 miss → DB 조회
        logger.debug("Cache miss for catalog, fetching from DB")
        characters = await self._delegate.list_all()
        
        # 3. 로컬 캐시에 저장 (다음 요청부터 캐시 hit)
        if characters:
            self._cache.set_all(list(characters))
        
        return characters
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| Decorator 패턴 | 기존 `SqlaCharacterReader` 수정 없이 캐시 추가 (OCP) |
| Graceful Degradation | 캐시 miss 시 DB fallback → 장애 전파 방지 |

### 4.6 FastAPI Lifespan으로 워밍업

```python
# main.py
async def warmup_local_cache() -> None:
    """로컬 캐시 워밍업 (서버 시작 전 DB에서 로드)."""
    try:
        cache = get_character_cache()
        if cache.is_initialized:
            return  # 이미 초기화됨
        
        async with async_session_factory() as session:
            reader = SqlaCharacterReader(session)
            characters = await reader.list_all()
            if characters:
                cache.set_all(list(characters))
                logger.info("Local cache warmup completed", extra={"count": len(characters)})
    except Exception as e:
        logger.warning("Cache warmup failed (graceful degradation)", extra={"error": str(e)})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """애플리케이션 라이프사이클 관리."""
    # Startup
    await warmup_local_cache()
    
    if settings.celery_broker_url:
        start_cache_consumer(settings.celery_broker_url)
    
    yield
    
    # Shutdown
    stop_cache_consumer()
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| Eager Loading | Cold Start 문제 해결 - 첫 요청 전에 캐시 준비 |
| Graceful Degradation | 워밍업 실패해도 서버 시작 (첫 요청에서 DB 로드) |

### 4.7 MQ 기반 실시간 동기화

다중 Pod 환경에서 캐시 일관성을 위해 **RabbitMQ Fanout Exchange**를 사용합니다.

```python
# infrastructure/cache/cache_consumer.py
class CacheUpdateConsumer(ConsumerMixin):
    """캐릭터 캐시 업데이트 이벤트 수신 Consumer."""
    
    def __init__(self, connection: Connection, cache: CharacterLocalCache) -> None:
        self.connection = connection
        self.cache = cache
        # 각 Pod마다 고유한 임시 큐 (exclusive, auto_delete)
        self.queue = Queue(
            name="",  # RabbitMQ가 자동 생성 (amq.gen-xxxx)
            exchange=Exchange("character.cache", type="fanout"),
            exclusive=True,
            auto_delete=True,
        )
    
    def on_message(self, body: dict, message: Message):
        event_type = body.get("type")
        
        if event_type == "full_refresh":
            self.cache.set_all(body.get("characters", []))
        elif event_type == "upsert":
            self.cache.upsert(body.get("character"))
        elif event_type == "delete":
            self.cache.delete(body.get("character_id"))
        
        message.ack()
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| Fanout Exchange | 모든 Pod가 동일 이벤트 수신 (브로드캐스트) |
| Exclusive Queue | Pod 종료 시 큐 자동 삭제 (리소스 정리) |
| 백그라운드 Thread | API 요청 처리와 독립적으로 MQ 수신 |

---

## 5. 의존성 주입

```python
# setup/dependencies.py
from apps.character.application.catalog.services.catalog_service import CatalogService
from apps.character.application.reward.services.reward_policy_service import RewardPolicyService

# Service는 상태 없음 → 싱글톤으로 재사용
_catalog_service = CatalogService()
_policy_service = RewardPolicyService()


async def get_catalog_reader(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CatalogReader:
    """로컬 캐시된 Catalog Reader를 주입합니다."""
    db_reader = SqlaCharacterReader(session)
    return LocalCachedCatalogReader(db_reader)  # Decorator 적용


async def get_catalog_query(
    reader: Annotated[CatalogReader, Depends(get_catalog_reader)],
) -> GetCatalogQuery:
    return GetCatalogQuery(reader, _catalog_service)


async def get_evaluate_reward_command(
    matcher: Annotated[CharacterMatcher, Depends(get_character_matcher)],
    checker: Annotated[OwnershipChecker, Depends(get_ownership_checker)],
) -> EvaluateRewardCommand:
    return EvaluateRewardCommand(matcher, checker, _policy_service)
```

**변경 전후 비교**:

```python
# Before: Query/Command가 직접 로직 포함
class GetCatalogQuery:
    def __init__(self, reader: CatalogReader) -> None:
        self._reader = reader
    
    async def execute(self) -> CatalogResult:
        characters = await self._reader.list_all()
        items = tuple(  # ← 변환 로직이 Query에 직접 존재
            CatalogItem(dialog=c.dialog or c.description or "", ...)
            for c in characters
        )

# After: 로직을 Service로 분리
class GetCatalogQuery:
    def __init__(self, reader: CatalogReader, service: CatalogService) -> None:
        self._reader = reader
        self._service = service
    
    async def execute(self) -> CatalogResult:
        characters = await self._reader.list_all()
        items = self._service.build_catalog_items(characters)  # ← Service 위임
```

---

## 6. 비동기 처리 전략

### 6.1 비동기 처리 플로우

**단일 책임 원칙**을 적용하여 도메인 경계를 명확히 분리했습니다.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Scan Reward Flow (캐릭터 획득)                                       │
└──────────────────────────────────────────────────────────────────────┘
                    ┌──────────────────┐
                    │ character_worker │ ──► character.character_ownerships
                    │ (character.reward)│     (리워드 평가용)
┌──────────────┐   └──────────────────┘
│  scan API    │────
└──────────────┘   ┌──────────────────┐
                    │   users_worker   │ ──► users.user_characters
                    │ (users.character)│     (인벤토리 조회용)
                    └──────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  Default Character Flow (기본 캐릭터 지급)                            │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────┐   ┌────────────────────┐
│  users API   │──▶│  character_worker  │ ──► users.user_characters
│ (빈 목록 시)  │   │(character.grant_   │     (기본 캐릭터 저장)
└──────────────┘   │   default)         │
                    └────────────────────┘
```

**Worker별 책임**:

| Worker | 큐 | 태스크 | 저장 테이블 |
|--------|----|----|----------|
| `character_worker` | `character.reward` | `save_ownership_task` | `character.character_ownerships` |
| `character_worker` | `character.grant_default` | `grant_default_task` | `users.user_characters` |
| `users_worker` | `users.character` | `save_characters_task` | `users.user_characters` |

**테이블 역할 분리**:

| 테이블 | 용도 | 저장 주체 |
|--------|------|----------|
| `character.character_ownerships` | 리워드 평가 시 소유 여부 확인 | character_worker |
| `users.user_characters` | 사용자 캐릭터 목록 조회 | character_worker, users_worker |

**개선점**:

| 개선 | 설명 |
|------|------|
| **my Worker 제거** | 레거시 `domains/my` Worker 제거 → `users_worker`로 대체 |
| **도메인 분리** | 각 Worker가 담당 큐만 처리 |
| **장애 격리** | Worker 장애 시에도 API 즉시 응답 (Eventual Consistency) |
| **명확한 책임** | 리워드 평가 ↔ 인벤토리 조회 분리 |

> **Note**: 아직 두 테이블을 사용 중이지만, 향후 마이그레이션을 통해 `users.user_characters` 단일 테이블로 통합 예정입니다.

### 6.2 기본 캐릭터 지급 플로우

**레거시 (동기)** vs **Clean Architecture (비동기)** 비교:

```python
# ❌ 레거시: domains/my - 동기 조회 후 빈 리스트 반환
async def get_user_characters(user_id):
    characters = await repo.list_by_user(user_id)
    if not characters:
        return []  # 빈 리스트 반환 (기본 캐릭터 없음)
```

```python
# ✅ Clean Architecture: apps/users - 즉시 응답 + 비동기 저장
async def execute(self, user_id: UUID) -> list[UserCharacterDTO]:
    characters = await self._character_gateway.list_by_user_id(user_id)
    
    if not characters:
        # 1. 기본 캐릭터(이코) 즉시 반환 (UX 우선)
        # 2. 비동기로 DB 저장 이벤트 발행
        if self._default_publisher:
            self._default_publisher.publish(user_id)  # Fire-and-forget
        return [self._get_default_character_dto(user_id)]
    
    return [_to_character_dto(char) for char in characters]
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| 즉시 응답 | 사용자 경험 우선 - 첫 로그인 시 즉시 캐릭터 표시 |
| Fire-and-forget | 저장 실패해도 응답에 영향 없음 |
| Eventual Consistency | 다음 조회 시 DB에서 확인됨 |

### 6.3 Worker 태스크 설계

```python
# apps/character_worker/presentation/tasks/grant_default_task.py
@celery_app.task(
    name="character.grant_default",
    queue="character.grant_default",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def grant_default_character_task(self, user_id: str) -> dict[str, Any]:
    """기본 캐릭터(이코)를 사용자에게 지급합니다."""
    
    # 1. 기본 캐릭터 정보 조회 (로컬 캐시 우선)
    default_char = _get_default_character()
    
    # 2. users.user_characters에 저장 (멱등성 보장)
    result = loop.run_until_complete(
        _save_to_users_db(
            user_id=UUID(user_id),
            character_id=default_char["id"],
            character_code=default_char["code"],
            ...
        )
    )
    return {"success": True, **result}
```

```python
# 멱등성 보장: ON CONFLICT DO NOTHING
async def _save_to_users_db(...):
    await session.execute(text("""
        INSERT INTO users.user_characters
            (id, user_id, character_id, character_code, ...)
        VALUES (:id, :user_id, :character_id, :character_code, ...)
        ON CONFLICT (user_id, character_code) DO NOTHING
    """), {...})
```

**설계 판단**:

| 판단 | 근거 |
|------|------|
| `character_code` 기준 멱등성 | `character_id`는 캐시로 변할 수 있음, `code`는 불변 |
| `ON CONFLICT DO NOTHING` | 중복 지급 방지 (재시도 안전) |
| 로컬 캐시 우선 조회 | Worker 시작 시 캐시 워밍업됨 |

### 6.4 소유권 저장 배치 처리

대량 처리 효율을 위해 **Celery Batches**를 사용합니다.

```python
# apps/character_worker/presentation/tasks/ownership_task.py
@celery_app.task(
    base=Batches,
    name="character.save_ownership",
    queue="character.reward",
    flush_every=50,      # 50개 모이면 처리
    flush_interval=5,    # 또는 5초마다 처리
)
def save_ownership_task(requests: list) -> dict[str, Any]:
    """Bulk INSERT로 DB 효율성 향상."""
    batch_data = [extract_kwargs(req) for req in requests]
    return loop.run_until_complete(_save_ownership_batch_async(batch_data))
```

**레거시 vs Clean Architecture 비교**:

| 항목 | 레거시 (domains) | Clean Architecture (apps) |
|------|------------------|---------------------------|
| 저장 위치 | `character_ownerships` + `user_characters` | `users.user_characters` 단일 |
| Worker | character Worker + my Worker | character_worker 단일 |
| 멱등성 키 | `(user_id, character_id)` | `(user_id, character_code)` |
| 충돌 전략 | `DO NOTHING` | `DO NOTHING` |

### 6.6 전체 비동기 플로우

```
┌───────────────────────────────────────────────────────────────────────────┐
│  1. 사용자 요청: GET /users/me/characters                                  │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  2. users API: GetCharactersQuery.execute()                               │
│     - 캐릭터 목록 조회                                                     │
│     - 빈 목록이면 → 기본 캐릭터 즉시 반환 + 이벤트 발행                     │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  3. RabbitMQ: character.grant_default 큐                                  │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  4. character_worker: grant_default_character_task()                      │
│     - 기본 캐릭터 정보 조회 (캐시 → DB)                                    │
│     - users.user_characters에 저장 (ON CONFLICT DO NOTHING)               │
└───────────────────────────────────────────────────────────────────────────┘
```

**장점**:

| 장점 | 설명 |
|------|------|
| **즉시 응답** | 사용자는 기다리지 않고 즉시 캐릭터 확인 |
| **재시도 안전** | 멱등성으로 중복 저장 방지 |
| **장애 격리** | Worker 장애 시에도 API 정상 응답 |
| **확장성** | Worker 스케일 아웃으로 처리량 증가 |

---

## 8. Trade-off

| 장점 | 단점 |
|------|------|
| Redis 의존성 제거 | Pod 간 동기화 필요 (MQ로 해결) |
| 극한 성능 (~0.01ms) | 메모리 사용 (~50KB, 미미) |
| 장애 격리 | Eventual Consistency (수 초 지연) |
| 운영 단순화 | 캐시 미스 시 첫 요청 느림 (워밍업으로 해결) |
| 단일 소유권 저장소 | 레거시 데이터 마이그레이션 필요 |
| 비동기 저장으로 즉시 응답 | Worker 장애 시 저장 지연 |

---

## 9. 구성 요소 매핑 요약

### Port-Adapter 매핑

| Port | Adapter | 역할 |
|------|---------|------|
| `CatalogReader` | `LocalCachedCatalogReader` | 캐시된 카탈로그 조회 |
| `CatalogReader` | `SqlaCharacterReader` | DB 카탈로그 조회 |
| `CharacterMatcher` | `SqlaCharacterReader` | 매칭 라벨로 캐릭터 찾기 |
| `OwnershipChecker` | `SqlaOwnershipChecker` | 소유권 확인 |

### Service 역할

| Service | 역할 | 특징 |
|---------|------|------|
| `CatalogService` | Entity → DTO 변환 | 순수 로직, Port 의존 없음 |
| `RewardPolicyService` | 보상 지급 여부 판단 | 순수 로직, 정책 캡슐화 |

### Query/Command vs Service

| 구분 | Query/Command | Service |
|------|---------------|---------|
| 역할 | 오케스트레이션 (흐름 제어) | 순수 비즈니스 로직 |
| 의존성 | Port + Service | 없음 (순수 함수) |
| 테스트 | Port Mock 필요 | Mock 불필요 |
| 변경 빈도 | Use Case 변경 시 | 비즈니스 규칙 변경 시 |

---

## References

- [Local Cache Event Broadcast](https://rooftopsnow.tistory.com/69) - Worker 캐시 동기화
- [RabbitMQ Fanout Exchange](https://www.rabbitmq.com/tutorials/tutorial-three-python.html)
- [FastAPI Lifespan](https://fastapi.tiangolo.com/advanced/events/)
- [Decorator Pattern](https://refactoring.guru/design-patterns/decorator)

