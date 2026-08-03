# 전기차 충전소 접근성 연구 — 프로젝트 요약 (2026-08-03 기준)

## 연구 개요
지리학과 도시컴퓨팅 연구실 소속 연구. 서울 동대문구 경희대학교 인근 충전소 파악에서
시작해 서울시 25개 자치구, 서울+6대 광역시(부산·대구·인천·광주·대전·울산), 경기도까지
수집 범위를 넓혔고, 현재는 **서울 단일 지역 2021-2024년 장기(longitudinal) 접근성 변화**로
연구 스코프를 좁혀 G2SFCA(2단계 부양권역법) 기반 통행시간 접근성 분석을 진행 중.

- 저장소: https://github.com/dralex0122/ev (branch: main)
- API: 한국환경공단 전기차 충전소 정보 API (공공데이터포털, B552584)
  - 2026-08-02~08-03 http(80포트) 장애로 20시간+ 수집 중단 발생, 이후 **https(443포트)로 고정** —
    공공데이터포털 공식 공지로 원인 확인
- 서비스키는 전부 환경변수(`EV_SERVICE_KEY`, 지오코딩은 `VWORLD_API_KEY`)로 관리, 코드에 하드코딩하지 않음

## 인프라
- **로컬 Mac**: 개발/조율, GitHub push
- **연구실 서버(163.180.10.188)**: SSH 키 인증, git deploy key로 GitHub 직접 push,
  tmux로 오래 걸리는 수집/분석 작업을 분리 실행 (로컬 컴퓨터를 꺼도 서버 안에서 계속 진행) —
  분석/배치 작업은 원칙적으로 서버에서 수행
- **NAS(smb://163.180.10.191)**: 대용량 데이터 산출물(geojson, graphml, 스냅샷 등)의 기본 저장 위치
- GitHub `.gitignore`로 대용량 데이터(`*.geojson`, `*.graphml`, 날짜별 수집 폴더, venv 등)는 제외,
  코드(.py/.sh)만 버전관리
- Notion 페이지("전기차 접근성")에 날짜별 토글로 분석/운영 내용을 정리, 연구 마일스톤 동기화

## 폴더 구조 및 스크립트 계보
- **`collection/`** — 초기 원본 수집 스크립트: `collect_seoul_hourly.py`(서울 25개 구 시간대별,
  현재 비활성화), `metro7_ev_chargers.py`/`metropolitan_ev_stations.py`(7개 도시 충전소 위치·
  완속/고속 GeoJSON), `collect_gyeonggi.py`
- **`availability_loops/`** — 현재 운영 중인 10분 간격 가용률 수집 루프.
  `district_availability_snapshot.py`가 서울+6대 광역시를 구/군 단위로 쪼개 가용률(전체/가용
  대수·비율, 완속/고속 구분) 계산, `run_10min_loop.py`가 스케줄링. 무한 재시도 방지용 상한
  (`MAX_CONSECUTIVE_PAGE_FAILURES=5`) 및 https 고정 적용됨
- **`data_cleaning/`** — 좌표/주소 오류, 중복 등록, 행정구역 경계 오탐 등 데이터 품질 검증·보정
  스크립트 모음 (`verify_city_boundary.py`, `verify_duplicates_*.py`, `regeocode_suspects.py`,
  `verify_grid_cities.py` 등)
- **`boundary_check/`** — 경기도 등 행정구역 경계 근처 충전소의 소속 시/도 재확인 파이프라인
- **`daily_check/`** — 매일 09시/18시 수집 완료 여부 점검 및 이메일·Notion 알림
  (`check_and_email.py`, `daily_notion_check.sh`, cron 등록됨, 로컬 Mac 실행 전제)
- **`viewt/`**, **`viewt_outputs/`** — View-T(국가교통DB) 도로망 구간별 통행속도 백분위 데이터
  전국 다운로드/포맷 변환 (17개 시도 × 4개년 × 월/요일유형/시간대)
- **`graph_years/`** — OSMnx 기반 서울 도로망 그래프 생성·시간대 평균화
  (`build_seoul_network_years.py`, `average_monthly_graphs.py`), 2021-2024년 × 요일유형 ×
  6개 시간대 → 오전/낮/밤 3구간으로 집계
- **`building_register/`** — 서울 건축물대장 지오코딩 및 이상치(연면적 등) 탐지, 상주인구
  추정 모델의 입력 데이터 정제
- **`daynight_model/`** — 서울 100m 격자 단위 주/야간 상주인구 회귀 모델 (v2~v4가 저장소에
  있음; 이상치 보정, 중복 변수 제거 등 반영). 로그변환·smearing 보정 등 추가 실험(v5-v7)은
  서버에서 진행했으나 개선 효과가 없어 채택하지 않음, 최종 채택 버전은 v6 기준(GitHub 미반영,
  서버 보관)
- **`outputs/`** — 최신 충전소 위치+완속/고속 대수 GeoJSON (예외적으로 GitHub에도 추적)

## 발견한 데이터 품질 이슈
- **원본 API의 좌표 오류**: 라벨된 시/도와 동떨어진 좌표(예: 서울 충전소인데 좌표는 제주 인근) —
  VWorld 지오코딩으로 재계산해 803건 중 766건 해결
- **원본 API의 주소 오류**: 소스 데이터 자체의 주소 오기재(대전 충전소인데 경기·강원 주소로 등록 등)
- **공유 도로명주소 지오코딩 오류**: 대형 복합단지 건물이 실제 위치가 아닌 공유 도로명주소로
  지오코딩되어 상주인구 모델에 왜곡 발생 — 필지주소 기반 좌표로 수동 보정(29건, `COORD_FIXES`)
- **중복 등록 의심**: 완전 동일 레코드가 242그룹(초과 레코드 266개, 충전기 약 1,108대)
- **테스트/더미 레코드**: "테스트용", "TEST" 등 실존하지 않는 레코드 14건 확인 후 제외
- **행정구역 경계 효과**: zscode 단일 필터링 시 인접 구의 실제로 가까운 충전소가 누락될 수 있어
  좌표 기반 반경 필터/인접 구 포함 권장

## 접근성 분석 파이프라인 (진행 중)
- G2SFCA: t0=15분 임계치(threshold-cutoff) 방식, `nx.single_source_dijkstra_path_length`로
  충전소별 통행시간 계산, `scipy.spatial.cKDTree`로 좌표→그래프 노드 매칭
- 2024년 평일 오전·Normal 시나리오로 1차 전체 파이프라인 테스트 완료(서버, GitHub 미반영):
  충전소→격자 통행시간 계산 후 G2SFCA 점수까지 산출
- 공급(S)/수요(D) 변수 정의는 아직 미확정 — 여러 시나리오(운영시간·가중치 반영 여부 등)를
  검토 중

## 진행 중 / 보류
- G2SFCA 공급/수요 정의 확정 후 72개 연도×시간대×시나리오 조합 전체 재실행 예정
- daynight 모델은 v6 기준 R²≈0.23 수준으로 개선 여지 있음(극단적 고밀도 지역 과소예측 한계 확인)
- NotebookLM 자동 업로드는 로컬 Mac의 브라우저 인증에 묶여 있어 완전 자동화(서버·클라우드
  이전)는 보류, 현재는 로컬 세션에서 수동 업로드로 진행
- 서버에서 진행 중인 일부 스크립트(`g2sfca_run.py`, `travel_time_pipeline.py`, daynight v5-v7,
  grid_population 관련 스크립트 등)는 아직 GitHub에 커밋되지 않음
