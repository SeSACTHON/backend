# Location 데이터 파이프라인 개요

## 목표
- `제로웨이스트 지도`와 KECO `재활용품 회수보상제` 데이터를 별도의 스키마로 보존하면서, 조회/API는 KECO 기준 공통 스키마(`location_normalized_sites`)를 사용합니다.
- 동일 데이터를 재활용하기 위해 전용 ETL 스크립트와 Kubernetes Job, PVC를 구성했습니다.

## 테이블 & ORM

| 테이블 | 설명 | ORM 클래스 |
| --- | --- | --- |
| `location_zero_waste_sites` | 제로웨이스트 CSV를 그대로 적재 (기존) | `domains.location.models.ZeroWasteSite` |
| `location_keco_sites` | KECO CSV Raw 데이터 | `domains.location.models.KecoRecycleSite` |
| `location_normalized_sites` | KECO 스키마 기반 공통 뷰 | `domains.location.models.NormalizedLocationSite` |

- 공통 테이블은 `source`, `source_pk`, `source_metadata(JSON)`으로 출처를 구분합니다.
- API는 `NormalizedLocationRepository`를 통해 이 테이블만 조회합니다.

## Repository & Service

| 파일 | 역할 |
| --- | --- |
| `domains/location/repositories/normalized_site_repository.py` | Haversine/earthdistance 기반 근접 탐색, 카운트 |
| `domains/location/services/category_classifier.py` | 공통 스키마 + metadata 기반 카테고리 분류 |
| `domains/location/services/location.py` | Redis 캐시/메타데이터 파싱 포함, `NormalizedLocationSite` → API 응답 변환/카테고리 필터링 |
| `domains/location/api/v1/endpoints/location.py` | `zoom` 기반 반경·limit 계산 + `category` Query(Comma-separated, `all`=전체) 필터 지원 |
| `domains/location/jobs/_csv_utils.py` | KECO·제로웨이스트 공통 CSV 해상 및 클렌징 유틸 |

## ETL 스크립트

| 스크립트 | 기능 |
| --- | --- |
| `domains/location/jobs/import_zero_waste_locations.py` | 제로웨이스트 CSV → `location_zero_waste_sites` (기존) |
| `domains/location/jobs/import_keco_sites.py` | KECO CSV → `location_keco_sites` |
| `domains/location/jobs/build_common_dataset.py` | 두 CSV → 공통 스키마 CSV (`location_common_dataset.csv`) |
| `domains/location/jobs/import_common_locations.py` | 공통 CSV → `location_normalized_sites` |
| `domains/location/jobs/sync_common_dataset.py` | 두 CSV를 즉시 정규화 후 `location_normalized_sites`에 업서트 (K8s Job에서 사용) |

> 모든 스크립트는 `--batch-size`, `--csv-path`, `--database-url` 옵션을 지원하여 로컬/CI/Job 어디서든 동일하게 실행됩니다.

## Kubernetes Job

| 파일 | 역할 | Hook Weight |
| --- | --- | --- |
| `workloads/domains/location/base/keco-import-job.yaml` | KECO Raw 적재 | -40 |
| `workloads/domains/location/base/db-bootstrap-job.yaml` | cube/earthdistance 확장 설치 + location 스키마 생성 | -30 |
| `workloads/domains/location/base/common-dataset-sync-job.yaml` | 두 CSV를 정규화 후 즉시 DB 업서트 | 10 |

- PVC 의존성을 제거하고 단일 Job에서 빌드+임포트를 수행합니다.
- Hook weight를 통해 Deployment가 올라가기 전에 모든 데이터가 준비됩니다.

## 문서 참고

- `docs/data/location/common-schema.md`: 공통 스키마 매핑 규칙 상세
- 본 문서: 전체 데이터 파이프라인 구조 및 책임 정리
- API 사용 예시는 추후 OpenAPI 문서를 참고하며, `/locations/centers?category=refill_zero,market_mart&zoom=12` 형태로 필터를 걸 수 있습니다.


