# 전기차 충전소 접근성 연구

## 연구 개요
- 지리학과 도시컴퓨팅 연구실 소속 연구
- 주제: 전기차 충전소 접근성(accessibility) 분석
- 시작점: 서울 동대문구 경희대학교 인근 충전소 파악 → 서울시 전체 구별 확장 예정

## 사용 API
- 한국환경공단 전기차 충전소 정보 API (공공데이터포털, B552584)
- Endpoint: `http://apis.data.go.kr/B552584/EvCharger/getChargerInfo`
- 주요 파라미터: `serviceKey`, `pageNo`, `numOfRows`, `zcode`(시도코드), `zscode`(시군구코드), `dataType`
- 서울 zcode=11, 동대문구 zscode=11230
- 응답 필드: statId(충전소ID), chgerId(충전기ID), statNm, addr, addrDetail, lat, lng, stat(상태코드), chgerType(타입코드), output, statUpdDt 등

## 코드 리뷰에서 나온 주의사항
1. **serviceKey URL 인코딩**: 디코딩 키를 쓸 경우 `+`, `/` 등 특수문자가 있으면 URL이 깨질 수 있음. `requests.get(url, params={...})` 방식 또는 `urllib.parse.quote()` 사용 권장.
2. **응답은 "충전기" 단위**: 한 충전소(같은 statId)에 여러 충전기가 있으면 행이 여러 개로 나뉨. 충전소 단위 분석(좌표 dissolve 등) 시 `statId` + 좌표 기준으로 groupby 필요.
3. **행정구역 경계 필터의 boundary effect**: zscode로 특정 구만 필터링하면 경계 바로 밖에 있는 실제로 가까운 충전소가 누락될 수 있음. 접근성 분석 시 인접 구 포함 또는 좌표 기반 반경 필터 권장.
4. **텍스트 키워드 매칭의 한계**: 주소/충전소명에 특정 키워드(예: "경희")로 필터링하면 오탐/누락 가능. 좌표 기반 거리 계산이 더 신뢰도 높음.

## 진행 중인 작업
- 동대문구 충전소별 가용률(availability rate) 계산 코드 존재 (stat 코드 기준 사용가능/전체 비율)
- 서울시 전체 25개 구로 확장 예정: `zcode=11`만 주고 전체 수집 후 구별 groupby 방식 권장 (API 호출 횟수 최소화)
- 시계열(시간대별 가용률 변화) 수집 여부는 미정 — 필요 시 로컬 반복 실행 또는 클라우드 스케줄링 검토

