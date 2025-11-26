## Location 데이터 정규화 가이드

> 목적: `location.location_normalized_sites` 기반으로 모든 위치 데이터를 통합하고, 배포/운영 시 필요한 체크리스트를 한 문서에서 확인합니다.

### 1. 전체 흐름 한눈에 보기

1. **Raw 데이터 확보**  
   - `domains/location/data/keco_recycle_compensation_sites.csv`  
   - `domains/location/data/제로웨이스트 지도 데이터.csv`
2. **정규화 CSV 생성**  
   - `domains/location/jobs/build_common_dataset.py`  
   - `domains/location/jobs/sync_common_dataset.py`  
   - 산출물: `domains/location/data/location_common_dataset.csv.gz`
3. **데이터 업서트**  
   - 로컬/Docker Compose: `normalized-import` 서비스  
   - Kubernetes Job: `workloads/domains/location/base/normalized-import-job.yaml`
4. **API 사용**  
   - `domains/location/repositories/normalized_site_repository.py`  
   - `domains/location/services/location.py`

### 2. 정규화 스키마 요약

`docs/data/location/common-schema.md` 참고. 핵심 필드:

| 컬럼 | 설명 |
| --- | --- |
| `source` / `source_pk` | 데이터 출처(Keco/Zero)와 고유 ID |
| `positn_pstn_lat`, `positn_pstn_lot` | 위도/경도 |
| `positn_nm`, `positn_rgn_nm` | 장소 이름/지역 |
| `positn_lotno_addr`, `positn_rdnm_addr` | 지번/도로명 주소 |
| `positn_intdc_cn` | 한 줄 소개 |
| `prk_mthd_expln`, `mon_sals_hr_expln_cn` 등 | 운영 관련 텍스트 필드 |
| `source_metadata` | 원본 JSON 전체 |

### 3. 로컬 정규화 실행법

```bash
# 1) Raw CSV → 정규화 CSV 생성
python domains/location/jobs/sync_common_dataset.py \
  --raw-keco domains/location/data/keco_recycle_compensation_sites.csv \
  --raw-zero domains/location/data/제로웨이스트\ 지도\ 데이터.csv \
  --output domains/location/data/location_common_dataset.csv.gz

# 2) 정규화 CSV를 로컬 Postgres에 업서트
docker compose -f domains/location/docker-compose.location-local.yml run --rm normalized-import \
  --csv-path /app/domains/location/data/location_common_dataset.csv.gz \
  --database-url postgresql://postgres:postgres@postgres:5432/ecoeco
```

### 4. Kubernetes 배포 시 필수 Job

| Hook | 파일 | 역할 |
| --- | --- | --- |
| wave -30 | `db-bootstrap-job.yaml` | `location` 스키마 + cube/earthdistance 확장 설치 |
| wave 10 | `normalized-import-job.yaml` | 정규화 CSV를 DB에 업서트 |

동기화 명령:
```bash
kubectl -n argocd annotate application dev-api-location argocd.argoproj.io/refresh=hard --overwrite
kubectl -n argocd patch application dev-api-location --type merge -p '{"operation":{"sync":{"prune":true}}}'
```

### 5. 점검 체크리스트

- [ ] `kubectl get jobs -n location` → `location-db-bootstrap`, `location-normalized-import` 성공 여부  
- [ ] `psql ... -c "\dt location.*"` → `location_normalized_sites` 존재  
- [ ] `SELECT count(*) FROM location.location_normalized_sites;` → 레코드 수 확인  
- [ ] `/api/v1/location/centers?zoom=12&category=refill_zero` 호출 테스트  
- [ ] Redis 캐시 초기화 필요 시 `kubectl exec` 로 `redis-cli FLUSHDB` (dev 전용)

### 6. 트러블슈팅 메모

- **UndefinedTableError**: Job 미실행 → `location-db-bootstrap`, `normalized-import` Job 재실행  
- **earth_distance not found**: cube/earthdistance 확장 미설치 → 부트스트랩 Job 로그 확인  
- **데이터 미반영**: 새로운 CSV를 커밋했는지, Docker 이미지에 포함됐는지 확인

추가 세부 사항은 `docs/development/location/DATA_PIPELINE.md` 와 `docs/data/location/common-schema.md` 를 참고하세요.

