# 프로젝트 현황 요약 (2026-07-14 기준)

## 목표
서울시 25개 자치구 전기차 충전기 가용률을 2026-07-13 17:00 KST ~ 2026-07-14 16:00 KST
24시간 동안 매시간 자동 수집해서 GitHub에 정리.

## 저장소
https://github.com/dralex210-byte/ev (branch: main)

## 데이터 저장 구조
```
0713/<구 이름>/<HH시>.json   예: 0713/동대문구/17시.json
```
각 JSON에는 구 전체 요약(summary: 총 대수/가용 대수/가용률, 완속·고속 구분)과
충전소별 상세 리스트(stations)가 들어있음.

## 핵심 파일
- `collect_seoul_hourly.py` — 매시간 실행되는 수집 스크립트
  - 서울 25개 구를 병렬(ThreadPoolExecutor, 10 workers)로 수집
  - 실행 시각이 수집 대상 24시간 창(WINDOW_START_UTC~WINDOW_END_UTC) 밖이면 아무 것도 안 하고 종료
  - **안전장치**: 사전 점검(동대문구 1건 조회)과 전체 합계 최소 기준(1000대) 미달 시
    커밋하지 않고 종료 — 네트워크 오류로 0건이 잘못 저장되는 것을 방지
  - API 서비스키는 `EV_SERVICE_KEY` 환경변수에서 읽음 (코드에 하드코딩 안 함)
- `view_report.ipynb` — 저장된 JSON을 원래 콘솔 리포트 형식으로 보거나,
  구별 비교표/시간대 추이를 확인하는 노트북

## 자동화 (클라우드 routine)
- 이름: `seoul-ev-charger-hourly`
- ID: `trig_01Hm99rjc98RifzmXN7wKTXi`
- 확인/관리: https://claude.ai/code/routines/trig_01Hm99rjc98RifzmXN7wKTXi
- 매시간 정각(cron `0 * * * *`) 실행, Anthropic 클라우드에서 도는 것이라
  **이 Mac이 꺼져 있어도 계속 작동함**
- ⚠️ 24시간 창이 끝난 뒤(2026-07-14 16:00 KST 이후)에도 무기한 계속 켜져서
  매시간 헛돌기만 함 (데이터는 안 씀). 다 끝나면 위 링크에서 꺼주거나
  Claude에게 꺼달라고 요청할 것.

## 현재까지 수집 현황 (2026-07-14 10:39 KST 기준)
- 정상 수집됨: 17, 20, 21, 22, 00, 01, 02, 03, 04, 05, 06, 07, 08, 10시
- **영구 누락 (복구 불가, 실시간 데이터라 재수집 안 됨)**:
  - 18시, 19시 — 초기 네트워크 차단 + git detached HEAD 버그
  - 09시 — 안전장치가 작동해 잘못된 데이터 저장은 막았지만, 그 시각 실제 데이터는 못 받음
- 남은 시간대: 11 ~ 16시 (자동으로 계속 진행됨)

## 겪었던 문제와 해결
1. GitHub App 연결이 claude.ai 매직 링크로 안 돼서 `/install-github-app` 명령으로 해결
2. 클라우드 환경 네트워크 허용 목록에 `apis.data.go.kr`이 없어서 첫 실행 실패
   → 환경 설정(Network access: Custom)에서 도메인 추가
3. 클라우드 세션이 detached HEAD 상태로 시작해서 git push 실패
   → 프롬프트에 `git checkout -B main origin/main` 단계 추가
4. 위 두 문제가 겹쳐 20시 데이터가 전부 0으로 잘못 커밋된 적 있음
   → 삭제 후 재수집, 스크립트에 안전장치(사전 점검 + 최소 합계 기준) 추가

## 세션 이어가기
이 대화는 로컬에 계속 저장되므로 컴퓨터를 껐다 켜도 사라지지 않음.
재부팅 후:
```
cd ~/ev-charger-accessibility
claude --continue      # 최근 세션 자동 이어가기
# 또는
claude --resume         # 여러 세션 중 선택
```

## 마무리 시 할 일 (2026-07-14 16:00 KST 이후)
1. `seoul-ev-charger-hourly` routine 비활성화
2. `view_report.ipynb`로 24시간 전체 데이터 확인/분석
3. (선택) 접근성 분석 등 다음 단계 진행 — `CLAUDE.md` 참고
