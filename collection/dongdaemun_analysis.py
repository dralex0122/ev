import os
import sys
import requests
import json
import time

def get_dongdaemun_complete_analysis(service_key):
    """
    동대문구 전체 데이터를 수집하여 최상단에 구 전체의 종합/완속/고속 가용률을 요약하고,
    하단에 충전소별 상세 분석 데이터를 내림차순으로 출력하는 함수
    """
    base_url = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"

    page_no = 1
    num_of_rows = 500  # 서버 타임아웃 방지를 위한 분할 수집 단위
    all_items = []     # 수집된 원천 충전기 리스트
    request_count = 0  # 이번 실행에서 API에 실제로 보낸 요청 수(재시도 포함, 일일 트래픽 추적용)

    print("📡 동대문구 관내 전체 전기차 충전기 데이터를 분할 수집하고 있습니다...")

    # [1단계] 데이터 끝까지 안전하게 분할 수집 (페이지네이션 및 재시도)
    while True:
        full_url = (
            f"{base_url}?"
            f"serviceKey={service_key}"
            f"&pageNo={page_no}"
            f"&numOfRows={num_of_rows}"
            f"&zcode=11"
            f"&zscode=11230"
            f"&dataType=JSON"
        )

        max_retries = 3
        page_success = False

        for attempt in range(1, max_retries + 1):
            try:
                request_count += 1
                response = requests.get(full_url, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    items_dict = data.get("items", {})

                    if not items_dict or "item" not in items_dict:
                        page_success = True
                        break

                    items = items_dict["item"]
                    if not items:
                        page_success = True
                        break

                    all_items.extend(items)
                    total_count = int(data.get("totalCount", 0))

                    if len(all_items) >= total_count:
                        page_success = True
                        break

                    page_success = True
                    break
                else:
                    time.sleep(3)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                time.sleep(5)
            except Exception:
                break

        if not page_success:
            print(f" ❌ {page_no}페이지 수집 실패로 일부 데이터가 누락되었을 수 있습니다.")
            break

        if page_success and (not items_dict or "item" not in items_dict or not items or len(all_items) >= total_count):
            break

        page_no += 1
        time.sleep(0.5)

    # 동대문구 전체(Global) 집계를 위한 카운터 변수 초기화
    dist_total = 0
    dist_avail = 0
    dist_slow_total = 0
    dist_slow_avail = 0
    dist_fast_total = 0
    dist_fast_avail = 0

    # [2단계] 충전소(statId) 기준으로 그룹화 및 구 전체 통계 연산
    station_counts = {}

    for item in all_items:
        stat_id = item.get('statId')          # 고유 충전소 ID
        stat_nm = item.get('statNm')          # 충전소 이름
        addr = item.get('addr', '')           # 주소
        lat = item.get('lat', '-')            # 위도
        lng = item.get('lng', '-')            # 경도
        stat_code = item.get('stat', '0')      # 상태 코드
        stat_upd_dt = item.get('statUpdDt', '') # 상태갱신일시
        output_val = item.get('output')       # 충전 용량 (kW)

        if not stat_id:
            continue

        # 1. 실시간 가용 여부 판별 (stat_code '2'는 사용가능)
        is_available = 1 if stat_code == '2' else 0

        # 2. 50kW 기준 완속/고속 분기 판별
        try:
            kw = float(output_val) if output_val else 0.0
        except ValueError:
            kw = 7.0  # 결측치 방어 코드

        is_slow = kw < 50.0

        # 3. 구 전체(Global) 카운터 누적
        dist_total += 1
        dist_avail += is_available
        if is_slow:
            dist_slow_total += 1
            dist_slow_avail += is_available
        else:
            dist_fast_total += 1
            dist_fast_avail += is_available

        # 4. 개별 충전소 그룹핑 데이터 세부 축적
        if stat_id not in station_counts:
            station_counts[stat_id] = {
                'name': stat_nm,
                'address': addr,
                'lat': lat,
                'lng': lng,
                'total_count': 1,
                'available_count': is_available,
                'slow_total': 1 if is_slow else 0,
                'slow_avail': is_available if is_slow else 0,
                'fast_total': 0 if is_slow else 1,
                'fast_avail': 0 if is_slow else is_available,
                'latest_update': stat_upd_dt
            }
        else:
            station_counts[stat_id]['total_count'] += 1
            station_counts[stat_id]['available_count'] += is_available

            if is_slow:
                station_counts[stat_id]['slow_total'] += 1
                station_counts[stat_id]['slow_avail'] += is_available
            else:
                station_counts[stat_id]['fast_total'] += 1
                station_counts[stat_id]['fast_avail'] += is_available

            if stat_upd_dt and stat_upd_dt > station_counts[stat_id]['latest_update']:
                station_counts[stat_id]['latest_update'] = stat_upd_dt

    # 구 전체의 가용률 퍼센트 연산 (0 나누기 방어 적용)
    global_total_percent = (dist_avail / dist_total) * 100 if dist_total > 0 else 0.0
    global_slow_percent = (dist_slow_avail / dist_slow_total) * 100 if dist_slow_total > 0 else 0.0
    global_fast_percent = (dist_fast_avail / dist_fast_total) * 100 if dist_fast_total > 0 else 0.0

    # [3단계] 최상단 동대문구 종합 대시보드 요약 출력
    print(f"\n==================================================")
    print(f" 🚀 [종합 리포트] 서울시 동대문구 전기차 인프라 실시간 현황")
    print(f"==================================================")
    print(f" 📊 동대문구 전체 충전기 가용률 : {global_total_percent:.1f}% ({dist_avail}대 사용 가능 / 총 {dist_total}대)")
    print(f" 🔹 50kW 미만 완속 충전기 가용률: {global_slow_percent:.1f}% ({dist_slow_avail}대 사용 가능 / 총 {dist_slow_total}대)")
    print(f" 🔸 50kW 이상 고속 충전기 가용률: {global_fast_percent:.1f}% ({dist_fast_avail}대 사용 가능 / 총 {dist_fast_total}대)")
    print(f"==================================================")
    print(f"💡 구내 고속/완속 충전기 비율: 완속 {dist_slow_total}대 ({dist_slow_total/dist_total*100:.1f}%) | 고속 {dist_fast_total}대 ({dist_fast_total/dist_total*100:.1f}%)")
    print(f"==================================================\n")

    # [4단계] 개별 충전소별 상세 결과 출력
    print(f"==================================================")
    print(f"🏢 관내 개별 충전소별 상세 가용성 리스트 (설치 대수순 정렬)")
    print(f"==================================================")

    sorted_stations = sorted(station_counts.items(), key=lambda x: x[1]['total_count'], reverse=True)

    for idx, (stat_id, info) in enumerate(sorted_stations, start=1):
        total = info['total_count']
        avail = info['available_count']
        total_percent = (avail / total) * 100 if total > 0 else 0.0

        s_total = info['slow_total']
        s_avail = info['slow_avail']
        slow_percent = (s_avail / s_total) * 100 if s_total > 0 else 0.0

        f_total = info['fast_total']
        f_avail = info['fast_avail']
        fast_percent = (f_avail / f_total) * 100 if f_total > 0 else 0.0

        raw_dt = info['latest_update']
        if len(raw_dt) == 14:
            formatted_dt = f"{raw_dt[0:4]}년 {raw_dt[4:6]}월 {raw_dt[6:8]}일 {raw_dt[8:10]}시 {raw_dt[10:12]}분 {raw_dt[12:14]}초"
        else:
            formatted_dt = "상태 정보 없음"

        print(f"[{idx}] 🏢 충전소명: {info['name']}")
        print(f" 🟢 종합 가용률: {total_percent:.1f}% ({avail}대 가능 / 총 {total}대)")

        if s_total > 0:
            print(f"   🔹 50kW 미만 완속 충전기 : {slow_percent:.1f}% ({s_avail}대 가능 / 총 {s_total}대)")
        else:
            print(f"   🔹 50kW 미만 완속 충전기 : 없음")

        if f_total > 0:
            print(f"   🔸 50kW 이상 고속 충전기 : {fast_percent:.1f}% ({f_avail}대 가능 / 총 {f_total}대)")
        else:
            print(f"   🔸 50kW 이상 고속 충전기 : 없음")

        print(f" ⏰ 최신 업데이트 시간: {formatted_dt}")
        print(f" 🌐 좌표 및 주소: {info['lat']}, {info['lng']} | {info['address']}")
        print(f" 🪪 충전소 고유 ID: {stat_id}")
        print(f"--------------------------------------------------")

    print(f"\n✅ 분석 완료: 동대문구 내 {len(station_counts)}개 충전소의 거시·미시 가용성 분석을 모두 마쳤습니다.")
    print(f"📶 이번 실행 API 요청 횟수: {request_count}건")

# ==========================================
# 하단 실행 제어부
# ==========================================
if __name__ == "__main__":
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)
    get_dongdaemun_complete_analysis(service_key)
