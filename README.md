# 전기차 충전소 접근성 연구 — 프로젝트 요약 (2026-08-12 기준)

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
- **`availability_loops/`** — 현재 운영 중인 10분 간격 가용률 수집 루프.
  `district_availability_snapshot.py`가 서울+6대 광역시를 구/군 단위로 쪼개 가용률(전체/가용
  대수·비율, 완속/고속 구분) 계산, `run_10min_loop.py`가 스케줄링. 무한 재시도 방지용 상한
  (`MAX_CONSECUTIVE_PAGE_FAILURES=5`) 및 https 고정 적용됨
- **`daily_check/`** — 매일 Notion 페이지에 지난 24시간 작업 마일스톤을 자동 정리
  (`daily_notion_check.sh`, launchd `com.evcharger.dailynotioncheck` 등록, 로컬 Mac 실행 전제
  — cron이 아닌 launchd인 이유는 Notion MCP OAuth가 로그인 키체인 접근을 필요로 해서)
- **`viewt/`**, **`viewt_outputs/`** — View-T(국가교통DB) 도로망 구간별 통행속도 백분위 데이터
  전국 다운로드/포맷 변환 (17개 시도 × 4개년 × 월/요일유형/시간대)
- **`graph_years/`** — OSMnx 기반 서울 도로망 그래프 생성·시간대 평균화
  (`build_seoul_network_years.py`, `average_monthly_graphs.py`, `average_timeperiods.py`),
  2021-2024년 × 요일유형 × 6개 시간대 → 오전/낮/밤 3구간 집계. 심야는 실측 원시 데이터가 없어
  `build_late_night_proxy.py`로 오전/낮/밤 freeflow 시나리오를 평균한 근사 그래프로 대체
- **`building_register/`** — 서울 건축물대장 지오코딩·이상치 탐지, 집계구(2016년 경계) 중심점
  산출(`compute_oa_centroids_2016.py`), 집계구 생활인구를 도로망 시간대에 맞춰 연도별로 집계하는
  `aggregate_oa_population_periods.py`(G2SFCA 수요층 D1의 소스)
- **`daynight_model/`** — 서울 100m 격자 단위 주/야간 상주인구 회귀 모델. `seoul_daynight_model_v6.py`가
  최종 채택 버전(R²≈0.23, 극단적 고밀도 지역 과소예측 한계 있음), `v6_validate.py`/
  `final_sanity_check.py`로 검증. 현재 G2SFCA 수요층(D1)에는 쓰이지 않는 별도 side analysis —
  D1은 집계구 생활인구를 직접 사용(`building_register/aggregate_oa_population_periods.py`)
- **`ev_registration/`** — 서울 연도별(2021-2024) 전기차 등록 현황 재구성
- **`g2sfca_run.py`**, **`g2sfca_run_all.py`** — G2SFCA 본 파이프라인과 배치 실행기.
  아래 "접근성 분석 파이프라인" 절 참고
- **`outputs/`** — 최신 충전소 위치+완속/고속 대수 GeoJSON (예외적으로 GitHub에도 추적)
- **`archive/`** — 더 이상 쓰이지 않는 코드(연구주제 피벗으로 보류된 7개 도시+경기도 스코프,
  폐기된 모델 실험 버전, 후속 버전으로 대체된 스크립트). 삭제 대신 이력 보존 목적으로 이동,
  각 항목의 대체 이유는 `archive/README.md` 참고

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

## 접근성 분석 파이프라인
- G2SFCA: t0=15분 임계치(threshold-cutoff) 방식, `nx.single_source_dijkstra_path_length`로
  충전소별 통행시간 계산, `scipy.spatial.cKDTree`로 좌표→그래프 노드 매칭
- 수요(D1): 집계구(2016년 경계) 단위 생활인구, 연도(2021-2024)×시간대(오전/낮/밤/심야) 평균
- 공급(S)은 3가지 정의로 전체 80개 조합(4개년×2요일유형×[오전/낮/밤 3시나리오 + 심야 1시나리오])을
  모두 실행해 강건성(robustness) 비교 완료 — `g2sfca_run.py --supply {s1,s2,s2park}`:
  - **S1**: 충전소 단순 대수(무가중) — `/mnt/cowork/EV/g2sfca/`
  - **S2(채택)**: 급속:완속 = 2.4:1, 프로젝트 자체 10분 가용률 루프 실측(세션 빈도 기반) —
    `/mnt/cowork/EV/g2sfca_s2/`
  - **s2park**: 급속:완속 = 10:1, Park et al.(2022, 강남·서초·송파) 문헌값 — 강건성 비교용,
    `/mnt/cowork/EV/g2sfca_s2_park10/`
- **강건성 비교 결과(2026-08-11)**: 2021→2024 접근성 개선 추세는 가중치 방식과 무관하게 강건함
  (S1 4.78배, S2 4.67배, s2park 4.35배 증가). 집계구 단위 상관관계는 S1↔S2 Pearson 0.996,
  S1↔s2park 0.937 — S2가 S1과 공간 패턴이 더 유사하고, s2park는 급속충전기 밀집지역 점수를
  상대적으로 더 부풀리는 경향 확인. Notion "전기차 접근성" 페이지 2026-08-10 토글에 상세 기록

## 진행 중 / 보류
- 급속:완속 가중치는 문헌값(Park et al. 10:1, Schroeder & Traber 2012 계보의 12:1 등) 대신
  프로젝트 자체 실측값(2.4:1)을 최종 채택 — 근거는 Notion 참고
- daynight 모델(v6)은 R²≈0.23 수준으로 개선 여지 있음(극단적 고밀도 지역 과소예측 한계 확인),
  현재 G2SFCA 파이프라인에는 미사용
- NotebookLM 자동 업로드는 로컬 Mac의 브라우저 인증에 묶여 있어 완전 자동화(서버·클라우드
  이전)는 보류, 현재는 로컬 세션에서 수동 업로드로 진행
- EndNote 2025 라이브러리(로컬 Mac)와 AppleScript `import` 명령으로 연동 — 신규 선행논문 발견 시
  프로그래매틱 추가 가능
