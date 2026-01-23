# Location API Contracts

## GET /api/v1/locations/centers

Find recycling centers within radius of given coordinates.

### Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `lat` | float | Yes | Latitude (-90 ~ 90) |
| `lon` | float | Yes | Longitude (-180 ~ 180) |
| `radius` | int | No | Radius in meters (100 ~ 50000) |
| `zoom` | int | No | Kakao map zoom level (1 ~ 20) |
| `store_category` | string | No | Comma-separated, default "all" |
| `pickup_category` | string | No | Comma-separated, default "all" |

### Response: LocationEntry[]

```json
{
  "id": 1,
  "name": "서울 재활용 센터",
  "source": "keco",
  "road_address": "서울시 강남구 테헤란로 123",
  "latitude": 37.5665,
  "longitude": 126.978,
  "distance_km": 1.5,
  "distance_text": "1.5km",
  "store_category": "upcycle_recycle",
  "pickup_categories": ["clear_pet", "can", "paper"],
  "is_holiday": false,
  "is_open": true,
  "start_time": "09:00",
  "end_time": "18:00",
  "phone": "02-1234-5678",
  "place_url": null,
  "kakao_place_id": null
}
```

---

## GET /api/v1/locations/search

Keyword search using Kakao API + DB hybrid.

### Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | string | Yes | Search keyword (1 ~ 100 chars) |
| `radius` | int | No | Search radius in meters (default 5000) |

### Response: LocationEntry[]

Same as `/centers` response, with `place_url` and `kakao_place_id` populated for Kakao results.

---

## GET /api/v1/locations/suggest

Autocomplete suggestions from Kakao keyword search.

### Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | string | Yes | Search query (1 ~ 100 chars) |

### Response: SuggestEntry[]

```json
{
  "place_name": "강남 재활용센터",
  "address": "서울 강남구 테헤란로 123",
  "latitude": 37.497,
  "longitude": 127.028,
  "place_url": "https://place.map.kakao.com/12345"
}
```

Max 5 results, sorted by accuracy.

---

## GET /api/v1/locations/centers/{center_id}

Get detailed location information with Kakao enrichment.

### Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `center_id` | int | Yes (path) | Location ID |

### Response: LocationDetail

```json
{
  "id": 1,
  "name": "서울 재활용 센터",
  "source": "keco",
  "road_address": "서울시 강남구 테헤란로 123",
  "lot_address": "서울시 강남구 역삼동 123",
  "latitude": 37.5665,
  "longitude": 126.978,
  "store_category": "upcycle_recycle",
  "pickup_categories": ["clear_pet", "can", "paper"],
  "phone": "02-1234-5678",
  "place_url": "https://place.map.kakao.com/12345",
  "kakao_place_id": "12345",
  "collection_items": "무색페트, 캔, 종이",
  "introduction": "재활용 수거 센터입니다"
}
```

### Error Responses

| Status | Detail |
|--------|--------|
| 404 | "Location not found." |
| 503 | "Kakao API is not configured." (search/suggest only) |
| 400 | "Invalid store_category '...'." |
| 422 | Validation error (missing/invalid params) |

---

## Data Sources

| Source | Description | ID Range |
|--------|-------------|----------|
| `keco` | Korea Environment Corporation data | Positive (DB) |
| `zerowaste` | Zero-waste store listings | Positive (DB) |
| `kakao` | Kakao API search results | Negative (-1, -2, ...) |
