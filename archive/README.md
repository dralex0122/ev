# 아카이브 (2026-08-12 정리)

현재 파이프라인에서는 쓰이지 않지만, 연구 이력 보존을 위해 삭제 대신 이곳으로 옮긴 코드.
전체 커밋 이력은 `git log --follow <파일 경로>`로 그대로 조회 가능.

## `7city_gyeonggi_scope/`
2026-07-30 연구주제 피벗(서울 단일 지역 2021-2024 종단분석으로 축소) 이전,
서울+6대 광역시(부산·대구·인천·광주·대전·울산)+경기도를 대상으로 한 정적(cross-sectional)
분석 스코프의 수집/정제 코드. **보류된 것이지 폐기된 것이 아님** — 7개 도시 스코프가
다시 열리면 재사용 가능.
- `collection/` — 도시별 초기 수집 스크립트 (동대문구 시작점 포함)
- `data_cleaning/` — 좌표/주소 오류, 중복 등록 정제
- `boundary_check/` — 경기도 등 행정구역 경계 근처 충전소 재확인

## `daynight_model_rejected/`
서울 100m 격자 주/야간 상주인구 회귀 모델의 초기~실험 버전(v2-v5, v7).
`daynight_model/seoul_daynight_model_v6.py`가 최종 채택 버전(README.md 참고) —
v5/v7의 로그변환·smearing 보정 실험은 개선 효과가 없어 미채택.

## `superseded/`
개별적으로 더 나은 후속 버전이 있어 대체된 스크립트.
- `travel_time_pipeline.py` → `g2sfca_run.py` (250m 인구격자 기반 테스트 실행 →
  집계구 기반 파라미터화 버전으로 대체, 2026-08-05)
- `building_register/compute_oa_centroids.py` → `compute_oa_centroids_2016.py`
  (2025년 SGIS 집계구 경계가 인구 데이터 코드와 37%만 일치하는 버그 발견 →
  100% 일치하는 2016년 경계로 교체)
- `viewt/download_viewt_percentile.py` → `download_viewt_nationwide.py` →
  `download_viewt_nationwide_parallel.py` (단일 도시 테스트 → 전국 → 병렬화, 3세대)
- `viewt/download_viewt_network.py` → `download_viewt_detailed_network.py`
  (WFS 직접 호출 방식 → 공식 상세도로망 shapefile 패키지로 교체, 실제 산출물 폴더도
  `viewt_detailed_network/`만 존재해 후자만 사용됐음을 확인)
- `viewt/convert_viewt_format.py` → `convert_viewt_format_nationwide.py`
- `availability_loops/run_24h_hourly.py` → `run_monthly_hourly.py` →
  `run_10min_loop.py` (24시간 1회성 → 1개월 시간 단위 → 10분 간격, 3세대.
  `run_10min_loop.py` 자체 docstring에 "run_monthly_hourly.py를 대체" 명시)

**정정(2026-08-14)**: `daily_check/check_and_email.py`를 여기 올렸던 건 판단 착오였음 —
당시 로컬 Mac의 crontab/launchd만 확인하고 **서버 crontab을 확인하지 않아서**, 매일
09시 서버 크론으로 실제 운영 중인 걸 몰랐음. archive 이동으로 경로가 깨져 2026-08-13,
08-14 이틀간 이메일 발송 실패 — `daily_check/`로 원상복구함. 교훈: 스크립트가 정말
안 쓰이는지 확인할 땐 로컬뿐 아니라 서버 crontab(`crontab -l`)도 반드시 같이 확인.

## `STATUS.md`
2026-07-14 최초 24시간 수집 작업의 진행 기록. 그 작업은 완료됐고, 이후 프로젝트
전체 현황은 루트 `README.md`가 대체.
