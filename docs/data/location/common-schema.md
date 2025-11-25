# Location 공통 스키마 개요

## 배경

- `keco_recycle_compensation_sites.csv`는 환경공단(KECO)의 유가보상제 거점 정보를, `제로웨이스트 지도 데이터.csv`는 커뮤니티 제로웨이스트 맵을 담고 있습니다.
- 서비스 레이어에서는 두 데이터셋을 동시에 다루기 위해 **원본 스키마는 그대로 유지**하면서, 조회 전용 공통 스키마(KECO 컬럼 기반)를 별도로 정의합니다.
- 모든 변환은 전처리 스크립트(`domains/location/jobs/build_common_dataset.py`)가 담당하고, 원본 CSV는 변경하지 않습니다.

## 원본 스키마 요약

### KECO (재활용품 회수보상제)

| 컬럼 | 설명 | 타입(권장) | 비고 |
| --- | --- | --- | --- |
| positnSn | KECO 거점 일련번호 | int | 기본 PK |
| positnNm | 거점 명칭 | text |  |
| positnRgnNm | 권역/지자체명 | text |  |
| positnLotnoAddr | 지번 주소 | text |  |
| positnRdnmAddr | 도로명 주소 | text |  |
| positnPstnAddExpln | 위치 설명 | text |  |
| positnPstnLat | 위도 | float | WGS84 |
| positnPstnLot | 경도 | float | WGS84 |
| positnIntdcCn | 소개 문구 | text |  |
| positnCnvncFcltSrvcExpln | 편의시설 정보 | text |  |
| prkMthdExpln | 주차 안내 | text |  |
| mon~sunSalsHrExplnCn | 요일별 운영시간 | text | 7개 필드 |
| lhldySalsHrExplnCn | 공휴일 운영시간 | text |  |
| lhldyDyoffCn | 정기 휴무 안내 | text |  |
| tmprLhldyCn | 임시 휴무 안내 | text |  |
| dyoffBgndeCn / dyoffEnddtCn | 휴무 시작/종료일 | text | yyyy-MM-dd |
| dyoffRsnExpln | 휴무 사유 | text |  |
| bscTelnoCn / rprsTelnoCn | 대표 전화 | text |  |
| telnoExpln / indivTelnoCn | 기타 연락처 | text |  |
| lnkgHmpgUrlAddr | 링크 URL | text |  |
| indivRelSrchListCn / comRelSrwrdListCn | 연관 검색어 | text |  |
| clctItemCn | 수거 품목 | text |  |
| etcMttrCn | 비고 | text |  |

### 제로웨이스트 지도

| 컬럼 | 설명 | 타입(권장) | 비고 |
| --- | --- | --- | --- |
| folderId | 폴더 ID | bigint |  |
| seq | 항목 ID | bigint | 기본 PK |
| favoriteType | 타입(PLACE/ADDRESS 등) | text |  |
| color | 마커 색상 코드 | int |  |
| memo | 메모/소개 | text |  |
| display1 | 대표명 | text |  |
| display2 | 주소 | text |  |
| x / y | 국토정보 TM 좌표 | float | 선택 |
| lon / lat | 경위도 | float | WGS84 |
| key | 카카오 장소 키 | text |  |
| createdAt / updatedAt | 작성/업데이트 시각 | timestamp |  |

## 공통 스키마 정의

| 컬럼 | 설명 |
| --- | --- |
| source | `keco` / `zerowaste` 등 데이터 출처 |
| source_pk | 출처별 원본 PK (문자열) |
| positnSn | KECO 기준 일련번호 (제로웨이스트는 seq 재사용) |
| positnNm ~ etcMttrCn | KECO 원본 컬럼을 동일 순서로 유지 |
| source_metadata | 원본 스키마 전체를 JSON 문자열로 보관 (UI/디버깅용) |

> ⚙️ 타입 규칙: 텍스트 계열은 `text`, 좌표는 `numeric(10,7)` 또는 `double precision`, 일련번호는 `bigint` 권장.

## 매핑 규칙

### KECO → 공통

- `source = "keco"`
- `source_pk = positnSn`
- KECO 컬럼들은 1:1 복사
- `source_metadata`는 빈 문자열 (필요 시 전체 행 JSON 직렬화 가능)

### 제로웨이스트 → 공통

| 공통 컬럼 | 값 |
| --- | --- |
| source | `"zerowaste"` |
| source_pk | `seq` |
| positnSn | `seq` |
| positnNm | `display1` → `display2` → `memo` 순으로 첫 번째 유효 텍스트 |
| positnLotnoAddr / positnRdnmAddr | `display2` (도로명) 및 필요 시 동일 값 재사용 |
| positnPstnAddExpln | `memo` |
| positnPstnLat / positnPstnLot | `lat` / `lon` (float) |
| positnIntdcCn | `memo` |
| positnCnvncFcltSrvcExpln | `favoriteType` |
| clctItemCn / etcMttrCn | `memo` 재사용 (정보 부족 시 빈 문자열) |
| 나머지 KECO 전용 필드 | 값이 없으면 `NULL`/빈 문자열 |
| source_metadata | `folderId`, `color`, `favoriteType`, `x`, `y`, `lon`, `lat`, `key`, `memo`, `display1`, `display2`, `createdAt`, `updatedAt` 전체를 JSON으로 직렬화 |

## 전처리 파이프라인

1. `domains/location/jobs/build_common_dataset.py` 실행
   - 인자: `--keco-csv`, `--zero-waste-csv`, `--output-csv`
   - 기본 경로는 `domains/location/data` 하위 CSV를 자동 탐색
2. 스크립트는 두 CSV를 로드하고 위 매핑 규칙을 적용하여 공통 스키마 DataFrame(사전 리스트)을 생성합니다.
3. 결과를 CSV로 저장하여 API/DB 로딩용으로 사용합니다.
4. 필요한 경우 `source_metadata`를 읽어 원본 스키마 전체를 추적할 수 있습니다.

## 후속 작업

- 공통 스키마 기반 DB 테이블(`location_normalized_sites` 등) 추가
- API `LocationService`가 공통 테이블을 조회하도록 Repository/Schema 업데이트
- 향후 타 데이터셋 추가 시 동일 스키마로 `source` 값만 확장


