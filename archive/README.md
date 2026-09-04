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
개별적으로 더 나은 후속 버전이 있어 대체된 스크립트. **2026-09-04부터 원래 있던
폴더(또는 루트)별로 하위 폴더를 나눠서 정리** — 예전엔 전부 평평하게 섞여 있었음.

### `superseded/g2sfca_final/`
- `cumulative_opportunity_supply.py` — 2SFCA·Gravity·Cumulative Opportunity 3모형
  비교 중 2026-08-31 사용자 결정으로 최종 비교는 2모형(2SFCA·Gravity)만 채택,
  Cumulative Opportunity는 제외됨(계산은 정상 완료, 결과도 틀리지 않음 — 순전히
  범위 축소 결정)
- `three_model_hotspot.py`, `plot_three_model_hotspot.py`,
  `plot_three_model_hotspot_individual.py` → `two_model_hotspot.py`,
  `plot_two_model_hotspot.py`, `plot_two_model_by_year.py` (위와 같은 이유로
  계산 단계부터 3모형 포함 구버전을 2모형 버전으로 교체, 2026-08-31~09-04에 걸쳐
  단계적으로 진행 — 처음엔 지도 스크립트만, 나중에 계산 스크립트 `three_model_hotspot.py`
  자체도 CumOpp 없는 `two_model_hotspot.py`로 교체)

### `superseded/root_scripts/`
- `travel_time_pipeline.py` → `g2sfca_run.py` (250m 인구격자 기반 테스트 실행 →
  집계구 기반 파라미터화 버전으로 대체, 2026-08-05)
- `compute_s2_weighted_supply.py` — S2(급속:완속=2.4:1) 가중치 계산 초기 버전,
  이후 `g2sfca_run.py --supply s2`로 파라미터화되며 대체
- `chain_s2park.sh` — S2→s2park 배치 자동 연계용 일회성 스크립트, 2026-08-10 실행
  완료 후 더 이상 쓰이지 않음(크론/tmux 어디에도 등록 안 됨 확인)
- `compute_supply_weights.py` — 운영시간을 "24시간 대비 실제 운영 비율(%)"로
  할인하는 공급 가중치 방식(2026-08-19). 최종 확정 방법론에서는 시간대별로 따로
  계산하는 구조와 안 맞아 폐기되고, `openinghour`를 분석 시간창과 대조해 0/1로
  반영하는 방식(`g2sfca_final_supply.py`)으로 교체됨 — README.md 163행 참고
- `check_fast_slow_utilization.py` — S2 가중치(급속:완속 비율) 검증용 실측 가동률
  계산 스크립트, docstring에 "확정 아님" 명시. S2 자체가 sfast(완속 배제)로
  대체되며 함께 불필요해짐
- `watch_api_recovery.py` — 공공데이터포털 API 장애 감시용 1회성 유틸리티
  (2026-08-12). 크론/launchd 어디에도 등록 안 됨, 연구 파이프라인과 무관한
  운영 도구라 결과물 코드가 아님 — 필요 시(API 재장애) 참고용으로만 보존

### `superseded/building_register/`
- `compute_oa_centroids.py` → `compute_oa_centroids_2016.py`
  (2025년 SGIS 집계구 경계가 인구 데이터 코드와 37%만 일치하는 버그 발견 →
  100% 일치하는 2016년 경계로 교체)

### `superseded/viewt/`
- `download_viewt_percentile.py` → `download_viewt_nationwide.py` →
  `download_viewt_nationwide_parallel.py` (단일 도시 테스트 → 전국 → 병렬화, 3세대)
- `download_viewt_network.py` → `download_viewt_detailed_network.py`
  (WFS 직접 호출 방식 → 공식 상세도로망 shapefile 패키지로 교체, 실제 산출물 폴더도
  `viewt_detailed_network/`만 존재해 후자만 사용됐음을 확인)
- `convert_viewt_format.py` → `convert_viewt_format_nationwide.py`

### `superseded/availability_loops/`
- `run_24h_hourly.py` → `run_monthly_hourly.py` → `run_10min_loop.py`
  (24시간 1회성 → 1개월 시간 단위 → 10분 간격, 3세대. `run_10min_loop.py` 자체
  docstring에 "run_monthly_hourly.py를 대체" 명시)

**정정(2026-08-14)**: `daily_check/check_and_email.py`를 여기 올렸던 건 판단 착오였음 —
당시 로컬 Mac의 crontab/launchd만 확인하고 **서버 crontab을 확인하지 않아서**, 매일
09시 서버 크론으로 실제 운영 중인 걸 몰랐음. archive 이동으로 경로가 깨져 2026-08-13,
08-14 이틀간 이메일 발송 실패 — `daily_check/`로 원상복구함. 교훈: 스크립트가 정말
안 쓰이는지 확인할 땐 로컬뿐 아니라 서버 crontab(`crontab -l`)도 반드시 같이 확인.

## `initial_24h_test/`
2026-07-14 최초 24시간 수집 작업 관련 일체 (연구 시작 직후 파일럿). 그 작업은
완료됐고, 이후 프로젝트 전체 현황은 루트 `README.md`가 대체.
- `STATUS.md` — 당시 진행 기록
- `0713/` — 그 24시간 동안 수집된 원본 JSON(서울 25개 구, 시간대별) — **2026-08-14
  정리 시점까지 실수로 GitHub에 그대로 커밋되어 있던 것 발견**(.gitignore 규칙은
  나중에 추가되어 이미 추적 중이던 파일엔 적용 안 됐음), 코드 저장소엔 데이터를
  안 올린다는 원칙에 맞게 이 위치로 정리
- `view_report.ipynb` — 위 0713 JSON을 콘솔 리포트 형식으로 보는 뷰어, 그 데이터
  전용이라 같이 이동

## `7city_gyeonggi_scope/outputs/`
7개도시+경기도 스코프 시절 최종 GeoJSON 산출물(충전소 위치+완속/고속 대수).
`collection/`·`data_cleaning/`의 archive된 스크립트에서만 참조되고 현재 파이프라인
(연도별 `input/processed/yearly_snapshots_fastonly/`, NAS)과는 무관해 함께 이동.

## `7city_gyeonggi_scope/legacy_root_outputs/`
2026-09-04 서버 정리 때 루트에 그대로 남아있던 걸 발견해서 옮김(서버 전용 —
로컬 repo엔 애초에 없었음).
- `yearly_snapshots/` — `gyeonggi_ev_chargers_*`, `metro7_ev_chargers_*` geojson.
  이름이 비슷한 `g2sfca_final_supply.py`가 참조하는 NAS 경로
  `{NAS}/input/processed/yearly_snapshots/`와는 **다른 파일** — 그쪽은 NAS 마운트,
  이건 리포 루트에 남아있던 7개도시 스코프 시절 원본이라 혼동 주의
- `dedup_outputs/` — 7개도시 스코프 중복 후보 CSV 3종(`archive/7city_gyeonggi_scope/
  data_cleaning/`의 archive된 스크립트들이 만든 산출물)
- `logs/` — 실행 로그 모음, 대부분 7개도시 스코프·daynight_model v2\~v7 실험·
  `superseded/root_scripts/`로 옮겨진 스크립트(chain_s2park, travel_time_pipeline
  등)에서 나온 것. **단, `g2sfca_run_all*.log`류 일부는 루트에 남아있는
  `g2sfca_run.py`/`g2sfca_run_all.py`(강건성 비교, 지금도 README에 인용됨) 실행
  기록이라 완전히 죽은 로그는 아님** — 결과 자체는 다른 곳(NAS)에 이미 있으므로
  로그만 보존 목적으로 함께 이동, 필요하면 꺼내 쓸 것
