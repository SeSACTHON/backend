---
name: location-service
description: Guide for the Location API service (apps/location). Use when working on geospatial features, Kakao Map integration, recycling center search, nearby center queries, or location-based filtering. Triggers on "location", "kakao", "map", "geospatial", "nearby centers", "recycling centers", "store category", "pickup category".
---

# Location Service Guide

## Architecture Overview

```
apps/location/
├── domain/                          # Pure domain layer
│   ├── entities/                    # NormalizedSite
│   ├── value_objects/               # Coordinates
│   ├── enums/                       # StoreCategory, PickupCategory
│   └── exceptions/                  # LocationNotFoundError
│
├── application/
│   ├── nearby/
│   │   ├── dto/                     # LocationEntryDTO, SuggestEntryDTO, LocationDetailDTO
│   │   ├── ports/                   # LocationReader (ABC)
│   │   ├── queries/                 # GetNearbyCentersQuery, SearchByKeywordQuery, etc.
│   │   └── services/               # CategoryClassifierService, LocationEntryBuilder, ZoomPolicyService
│   └── ports/                       # KakaoLocalClientPort (ABC)
│
├── infrastructure/
│   ├── integrations/kakao/          # KakaoLocalHttpClient
│   ├── persistence_postgres/        # SqlaLocationReader
│   └── observability/               # OpenTelemetry
│
├── presentation/http/
│   ├── controllers/                 # location.py (endpoints)
│   ├── schemas/                     # LocationEntry, SuggestEntry, LocationDetail
│   └── errors/                      # Exception handlers
│
└── setup/
    ├── config.py                    # Settings (pydantic-settings)
    ├── dependencies.py              # FastAPI DI wiring
    └── database.py                  # SQLAlchemy async session
```

## API Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/locations/centers` | Nearby centers | `list[LocationEntry]` |
| GET | `/api/v1/locations/search` | Keyword search (Kakao + DB hybrid) | `list[LocationEntry]` |
| GET | `/api/v1/locations/suggest` | Autocomplete suggestions | `list[SuggestEntry]` |
| GET | `/api/v1/locations/centers/{id}` | Center detail | `LocationDetail` |

## Key Patterns

### 1. Hybrid Search Flow (SearchByKeywordQuery)

```
User Query → Kakao keyword search → Extract coordinates
                                        ↓
                                  DB spatial query (earth_distance/Haversine)
                                        ↓
                                  Merge DB + Kakao results
                                        ↓
                                  Deduplicate (50m threshold)
                                        ↓
                                  Return unified LocationEntryDTO[]
```

### 2. Category Classification

`CategoryClassifierService.classify(site, metadata)` analyzes:
- `positn_intdc_cn` (introduction text)
- `positn_nm` (name)
- `metadata.clctItemCn` (collection items)

Returns: `(StoreCategory, list[PickupCategory])`

Priority order: REFILL_ZERO > CAFE_BAKERY > VEGAN_DINING > UPCYCLE_RECYCLE > BOOK_WORKSHOP > MARKET_MART > LODGING > PUBLIC_DROPBOX > GENERAL

### 3. Distance Calculation Fallback

```python
try:
    PostGIS earth_distance (accurate, requires extension)
except DBAPIError:
    Haversine formula (fallback, pure SQL math)
```

### 4. Kakao API Integration

- Port: `KakaoLocalClientPort` (application/ports/)
- Adapter: `KakaoLocalHttpClient` (infrastructure/integrations/kakao/)
- Singleton via `get_kakao_client()` in dependencies.py
- Graceful degradation: returns None if `LOCATION_KAKAO_REST_API_KEY` not set

### 5. DTO ↔ Schema Mapping

Application layer returns DTOs (dataclasses), presentation layer maps to Pydantic schemas:

```
Query.execute() → LocationEntryDTO (application layer)
Controller       → LocationEntry (presentation schema, Pydantic)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCATION_DATABASE_URL` | `postgresql+asyncpg://...` | DB connection |
| `LOCATION_KAKAO_REST_API_KEY` | `""` (disabled) | Kakao REST API key |
| `LOCATION_KAKAO_API_TIMEOUT` | `5.0` | Kakao API timeout (seconds) |
| `LOCATION_OTEL_ENABLED` | `False` | OpenTelemetry tracing |
| `LOCATION_REDIS_URL` | `redis://localhost:6379/5` | Redis for metrics cache |

## Domain Enums

### StoreCategory
`refill_zero`, `cafe_bakery`, `vegan_dining`, `upcycle_recycle`, `book_workshop`, `market_mart`, `lodging`, `public_dropbox`, `general`

### PickupCategory
`clear_pet`, `can`, `paper`, `glass`, `plastic`, `vinyl`, `styrofoam`, `clothing`, `electronics`, `fluorescent`, `battery`, `medicine`, `cooking_oil`, `general`

## Testing

```bash
pytest apps/location/tests/ -v
```

Test structure:
- `test_domain.py` — Entities, Value Objects, Enums (no mocks)
- `test_services.py` — CategoryClassifier, LocationEntryBuilder, ZoomPolicy
- `test_queries.py` — GetNearbyCenters, SearchByKeyword, Suggest, CenterDetail (mocked ports)
- `test_controllers.py` — HTTP parameter validation, endpoint routing

## Frontend Integration

Frontend uses:
- `VITE_KAKAO_MAP_API_KEY` — Kakao Maps JS SDK (client-side, different from backend key)
- `VITE_API_BASE_URL` — Backend API base URL
- API client: `src/api/services/map/map.service.ts`
- Types: `src/api/services/map/map.type.ts`

## Common Issues

1. **Kakao features disabled**: Check `LOCATION_KAKAO_REST_API_KEY` is set
2. **earth_distance not available**: Falls back to Haversine (no PostGIS extension)
3. **Negative IDs in search results**: Kakao-only results use negative IDs (-1, -2, ...)
4. **Silent category fallback**: Unknown items default to `GENERAL`
