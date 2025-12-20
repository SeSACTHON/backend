# Answer Pipeline 응답 속도 최적화 계획

> **상태**: 📋 계획 수립 완료 (MQ 마이그레이션 이후 진행)  
> **작성일**: 2024-12-20  
> **우선순위**: P2 (MQ 완료 후)

---

## 1. 현황 분석

### 1.1 현재 파이프라인 구조

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Vision/Text    │ →  │  Lite RAG       │ →  │  Answer Gen     │
│  Classification │    │  (JSON 매칭)     │    │  (GPT-5.1)      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│  ~2-3초         │    │  ~10ms          │    │  ~3-5초 ⚠️      │
│  (병목 1)       │    │  (최적)         │    │  (병목 2)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 1.2 병목 지점

| 단계 | 평균 소요시간 | 최적화 가능성 | 비고 |
|------|-------------|--------------|------|
| Vision Classification | 2-3초 | 낮음 | 이미지마다 다름 |
| Lite RAG | ~10ms | - | 이미 최적 |
| **Answer Generation** | **3-5초** | **높음** | 주요 최적화 대상 |

---

## 2. 최적화 전략

### 2.1 Phase 1: 즉시 적용 가능 (코드 수정만)

#### 2.1.1 입력 토큰 감소

**현재 문제**: `lite_rag` JSON 전체를 프롬프트에 포함 (~1-2KB)

**개선안**: 필요한 필드만 추출

```python
# Before
rag_json = json.dumps(disposal_rules, ensure_ascii=False, indent=2)

# After
filtered_rag = {
    "disposal_common": disposal_rules.get("disposal_common"),
    "disposal_detail": disposal_rules.get("disposal_detail"),
}
rag_json = json.dumps(filtered_rag, ensure_ascii=False)  # indent 제거
```

**예상 효과**: 입력 토큰 20-30% 감소 → 응답 시간 10-15% 개선

---

#### 2.1.2 출력 토큰 감소

**현재 문제**: `DisposalSteps` 10단계 정의 (대부분 3-4단계만 사용)

**개선안**: 5단계로 축소

```python
# Before
class DisposalSteps(BaseModel):
    단계1: Optional[str] = None
    ...
    단계10: Optional[str] = None  # 거의 사용 안 됨

# After
class DisposalSteps(BaseModel):
    단계1: Optional[str] = None
    단계2: Optional[str] = None
    단계3: Optional[str] = None
    단계4: Optional[str] = None
    단계5: Optional[str] = None
```

**예상 효과**: 출력 스키마 단순화 → 응답 시간 5-10% 개선

---

#### 2.1.3 프롬프트 간소화

**현재**: 103줄, ~2,500자  
**목표**: 50줄, ~1,200자 (핵심만 유지)

**제거 대상**:
- 중복 설명
- 예시 과다
- JSON 스키마 중복 명시

**예상 효과**: 시스템 프롬프트 토큰 50% 감소

---

### 2.2 Phase 2: 캐싱 전략

#### 2.2.1 구조화된 캐시 키 (권장 - 정확도 100%)

**핵심 원칙**: 캐시 키에 모든 변별 요소를 명시적으로 포함

```python
import hashlib
from functools import lru_cache

# In-Memory 캐시 (서버 재시작 시 초기화)
answer_cache: dict[str, dict] = {}

def generate_cache_key(classification_result: dict) -> str:
    """
    정확도 100% 보장하는 캐시 키 생성
    핵심 변별 요소를 모두 포함
    """
    classification = classification_result.get("classification", {})
    situation_tags = classification_result.get("situation_tags", [])
    
    key_components = (
        classification.get("major_category", ""),
        classification.get("middle_category", ""),
        classification.get("sub_category", ""),
        tuple(sorted(situation_tags)),  # 정렬하여 순서 무관하게
    )
    
    key_string = str(key_components)
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]

def get_cached_answer(classification_result: dict) -> Optional[dict]:
    """캐시에서 답변 조회"""
    cache_key = generate_cache_key(classification_result)
    return answer_cache.get(cache_key)

def set_cached_answer(classification_result: dict, answer: dict) -> None:
    """캐시에 답변 저장"""
    cache_key = generate_cache_key(classification_result)
    answer_cache[cache_key] = answer
```

**예상 캐시 히트율**: ~25-30%  
**정확도**: 100% (동일 입력에만 캐시 히트)

---

#### 2.2.2 하이브리드 캐싱 (Phase 2 확장)

**조건부 캐싱**: 태그 상태에 따라 캐싱 범위 조정

```python
# 긍정적 태그 (분리배출 완료 상태)
POSITIVE_TAGS = {
    "내용물_없음", 
    "라벨_제거됨", 
    "뚜껑_없음", 
    "깨끗함",
    "분리완료"
}

# 부정적 태그 (추가 작업 필요)
NEGATIVE_TAGS = {
    "내용물_있음",
    "라벨_부착",
    "뚜껑_있음",
    "오염됨"
}

def get_cache_level(situation_tags: list) -> str:
    """상황 태그에 따른 캐시 레벨 결정"""
    tag_set = set(situation_tags)
    
    # 부정적 태그가 있으면 정밀 캐싱 (태그 포함)
    if tag_set.intersection(NEGATIVE_TAGS):
        return "precise"  # 캐시 키에 태그 포함
    
    # 긍정적 태그만 있으면 범용 캐싱 (카테고리만)
    if tag_set.issubset(POSITIVE_TAGS):
        return "general"  # 캐시 키에서 태그 제외
    
    return "precise"
```

---

#### 2.2.3 반대 태그 감지 (안전장치)

```python
# 반대 의미 태그 쌍 정의
OPPOSITE_TAGS = {
    "내용물_있음": "내용물_없음",
    "내용물_없음": "내용물_있음",
    "라벨_부착": "라벨_제거됨",
    "라벨_제거됨": "라벨_부착",
    "뚜껑_있음": "뚜껑_없음",
    "뚜껑_없음": "뚜껑_있음",
    "오염됨": "깨끗함",
    "깨끗함": "오염됨",
}

def has_conflicting_tags(tags_a: list, tags_b: list) -> bool:
    """두 태그 세트 간 충돌 여부 검사"""
    for tag_a in tags_a:
        opposite = OPPOSITE_TAGS.get(tag_a)
        if opposite and opposite in tags_b:
            return True
    return False
```

---

### 2.3 Phase 3: 시맨틱 캐싱 (선택적)

#### 2.3.1 임베딩 기반 유사도 검색

**주의**: 정확도 트레이드오프 존재

```python
from openai import OpenAI
import numpy as np

# 시맨틱 캐시 (임베딩 + 응답)
semantic_cache: dict[str, tuple[list, dict, dict]] = {}
# key -> (embedding, original_query, response)

def get_embedding(text: str) -> list[float]:
    """텍스트 임베딩 생성"""
    client = OpenAI()
    response = client.embeddings.create(
        model="text-embedding-3-small",  # 빠르고 저렴
        input=text
    )
    return response.data[0].embedding

def cosine_similarity(a: list, b: list) -> float:
    """코사인 유사도 계산"""
    a_arr, b_arr = np.array(a), np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))

def semantic_lookup(
    query: dict, 
    threshold: float = 0.98  # 높은 임계값으로 정확도 보장
) -> Optional[dict]:
    """시맨틱 유사도 기반 캐시 조회"""
    query_text = json.dumps(query, ensure_ascii=False, sort_keys=True)
    query_embedding = get_embedding(query_text)
    query_tags = query.get("situation_tags", [])
    
    best_match = None
    best_similarity = 0.0
    
    for key, (cached_embedding, cached_query, cached_response) in semantic_cache.items():
        similarity = cosine_similarity(query_embedding, cached_embedding)
        
        if similarity >= threshold and similarity > best_similarity:
            cached_tags = cached_query.get("situation_tags", [])
            
            # 안전장치: 반대 태그 검사
            if has_conflicting_tags(query_tags, cached_tags):
                continue
            
            best_match = cached_response
            best_similarity = similarity
    
    if best_match:
        logger.info(f"Semantic cache HIT (similarity: {best_similarity:.4f})")
    
    return best_match
```

**임계값 가이드라인**:
| 임계값 | 히트율 | 정확도 | 권장 사용 |
|--------|--------|--------|----------|
| 0.99+ | ~15% | 99%+ | 프로덕션 초기 |
| 0.98 | ~25% | 97%+ | 프로덕션 안정화 후 |
| 0.95 | ~40% | 90%+ | 비권장 (위험) |
| 0.90 | ~55% | 80%+ | 사용 금지 |

---

### 2.4 Phase 4: 인프라 레벨

#### 2.4.1 Redis 캐시 (서버 재시작에도 유지)

```python
import redis
import json

redis_client = redis.Redis(
    host="dev-redis.redis.svc.cluster.local",
    port=6379,
    decode_responses=True
)

CACHE_TTL = 3600 * 24  # 24시간

def get_redis_cached_answer(cache_key: str) -> Optional[dict]:
    """Redis에서 캐시 조회"""
    cached = redis_client.get(f"answer:{cache_key}")
    if cached:
        return json.loads(cached)
    return None

def set_redis_cached_answer(cache_key: str, answer: dict) -> None:
    """Redis에 캐시 저장"""
    redis_client.setex(
        f"answer:{cache_key}",
        CACHE_TTL,
        json.dumps(answer, ensure_ascii=False)
    )
```

#### 2.4.2 스트리밍 응답 (체감 속도 개선)

```python
# 프론트엔드 연동 필요
async def generate_answer_streaming(
    classification_result: dict,
    disposal_rules: dict
) -> AsyncGenerator[str, None]:
    """스트리밍으로 답변 생성"""
    client = get_openai_client()
    
    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=[...],
        stream=True
    )
    
    for chunk in response:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

---

## 3. 구현 로드맵

### 3.1 마일스톤

| Phase | 작업 | 예상 효과 | 소요 시간 | 의존성 |
|-------|------|----------|----------|--------|
| **1a** | 입력 토큰 감소 | -15% 지연 | 2시간 | 없음 |
| **1b** | 출력 토큰 감소 | -10% 지연 | 1시간 | 없음 |
| **1c** | 프롬프트 간소화 | -10% 지연 | 2시간 | 없음 |
| **2a** | 구조화된 캐시 (In-Memory) | -30% avg | 4시간 | 1a-1c |
| **2b** | 하이브리드 캐싱 | -40% avg | 4시간 | 2a |
| **3** | Redis 캐시 | 영속성 | 2시간 | 2b |
| **4** | 스트리밍 응답 | 체감 -50% | 8시간 | FE 연동 |

### 3.2 단계별 진행

```
MQ 완료 후
    │
    ├─▶ Phase 1 (즉시 적용) ─────────────────▶ 배포 & 모니터링
    │       │
    │       └─ 토큰 최적화, 프롬프트 간소화
    │
    ├─▶ Phase 2 (캐싱 구현) ─────────────────▶ A/B 테스트
    │       │
    │       └─ 구조화된 캐시 키 → 하이브리드
    │
    └─▶ Phase 3-4 (인프라) ──────────────────▶ 프로덕션
            │
            └─ Redis, 스트리밍
```

---

## 4. 모니터링 & 검증

### 4.1 메트릭

```python
# 캐시 히트율 모니터링
from prometheus_client import Counter, Histogram

answer_cache_hits = Counter(
    'answer_cache_hits_total', 
    'Total cache hits',
    ['cache_level']  # exact, semantic
)

answer_cache_misses = Counter(
    'answer_cache_misses_total',
    'Total cache misses'
)

answer_latency = Histogram(
    'answer_generation_seconds',
    'Answer generation latency',
    ['cache_status']  # hit, miss
)
```

### 4.2 대시보드 항목

- 캐시 히트율 (목표: >30%)
- 평균 응답 시간 (목표: <2초)
- p95 응답 시간 (목표: <4초)
- 캐시 사이즈 증가율

### 4.3 알럿 조건

- 캐시 히트율 < 10% (7일 평균)
- 평균 응답 시간 > 5초 (1시간 평균)
- 캐시 미스 후 응답 정확도 < 95%

---

## 5. 리스크 & 완화

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| 캐시 오염 (잘못된 답변 캐싱) | 높음 | 구조화된 캐시 키 사용, 반대 태그 검증 |
| 메모리 부족 | 중간 | LRU 캐시 정책, 최대 크기 제한 |
| 캐시 무효화 규칙 변경 시 | 중간 | 버전 키 포함, TTL 설정 |
| 프롬프트 변경 시 캐시 불일치 | 중간 | 프롬프트 해시를 캐시 키에 포함 |

---

## 6. 참고 자료

### 6.1 OpenAI 공식 문서
- [Prompt Caching](https://platform.openai.com/docs/guides/prompt-caching)
- [Latency Optimization](https://platform.openai.com/docs/guides/latency-optimization)

### 6.2 연구 논문
- Block-Attention: TTFT 98.7% 감소 ([arXiv](https://arxiv.org/abs/2409.15355))
- METIS: Configuration Adaptation ([Microsoft Research](https://www.microsoft.com/en-us/research/))
- Semantic Caching for LLMs ([arXiv](https://arxiv.org/abs/2411.05276))

### 6.3 관련 내부 문서
- [MQ Migration Plan](./MQ_MIGRATION_PLAN.md)
- [CDC Architecture Plan](./CDC_ARCHITECTURE_PLAN.md)

---

## 변경 이력

| 날짜 | 변경 내용 | 작성자 |
|------|----------|--------|
| 2024-12-20 | 초안 작성 | - |
