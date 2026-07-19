"""
서울 + 6대 광역시(부산·대구·인천·광주·대전·울산) 구/군별 전기차 충전기 가용률 스냅샷.

- zscode 없이 zcode(시도코드)만 지정해 도시 전체를 한 번에 페이지네이션 수집
  (city-wide fetch; page-skip-not-abort — 한 페이지 실패해도 그 페이지만 건너뛰고 계속 진행)
- 각 항목의 addr 필드에서 두 번째 단어(예: "서울특별시 강남구 ..." -> "강남구")를 구/군으로 파싱
- 저장 구조: <OUTPUT_ROOT>/<도시>/<HH시>/<구군>.json
- API 서비스키는 EV_SERVICE_KEY 환경변수에서 읽음 (레포에 하드코딩하지 않음)
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

BASE_URL = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
NUM_OF_ROWS = 500
OUTPUT_ROOT = "260719"
FAST_THRESHOLD_KW = 50.0

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

CITIES = [
    ("서울특별시", "11"),
    ("부산광역시", "26"),
    ("대구광역시", "27"),
    ("인천광역시", "28"),
    ("광주광역시", "29"),
    ("대전광역시", "30"),
    ("울산광역시", "31"),
]

REQUEST_COUNT = 0


def fetch_city_items(zcode, service_key):
    import requests

    global REQUEST_COUNT
    page_no = 1
    all_items = []

    while True:
        full_url = (
            f"{BASE_URL}?"
            f"serviceKey={service_key}"
            f"&pageNo={page_no}"
            f"&numOfRows={NUM_OF_ROWS}"
            f"&zcode={zcode}"
            f"&dataType=JSON"
        )

        page_success = False
        items = []
        total_count = 0

        for attempt in range(1, 4):
            try:
                REQUEST_COUNT += 1
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
                    page_success = True
                    break
                else:
                    time.sleep(3)
            except Exception:
                time.sleep(5)

        if not page_success:
            print(f"  경고: zcode={zcode} {page_no}페이지 수집 실패, 해당 페이지만 건너뜁니다.", file=sys.stderr)
        elif not items or len(all_items) >= total_count:
            break

        page_no += 1
        time.sleep(0.3)

    return all_items


def extract_district(addr):
    parts = (addr or "").split()
    if len(parts) < 2:
        return None
    return parts[1]


def analyze_items(items):
    dist_total = dist_avail = 0
    dist_slow_total = dist_slow_avail = 0
    dist_fast_total = dist_fast_avail = 0
    station_counts = {}

    for item in items:
        stat_id = item.get("statId")
        if not stat_id:
            continue
        stat_nm = item.get("statNm")
        addr = item.get("addr", "")
        lat = item.get("lat", "-")
        lng = item.get("lng", "-")
        stat_code = item.get("stat", "0")
        stat_upd_dt = item.get("statUpdDt", "")
        output_val = item.get("output")

        is_available = 1 if stat_code == "2" else 0
        try:
            kw = float(output_val) if output_val else 0.0
        except ValueError:
            kw = 7.0
        is_slow = kw < FAST_THRESHOLD_KW

        dist_total += 1
        dist_avail += is_available
        if is_slow:
            dist_slow_total += 1
            dist_slow_avail += is_available
        else:
            dist_fast_total += 1
            dist_fast_avail += is_available

        s = station_counts.setdefault(stat_id, {
            "name": stat_nm, "address": addr, "lat": lat, "lng": lng,
            "total_count": 0, "available_count": 0,
            "slow_total": 0, "slow_avail": 0,
            "fast_total": 0, "fast_avail": 0,
            "latest_update": "",
        })
        s["total_count"] += 1
        s["available_count"] += is_available
        if is_slow:
            s["slow_total"] += 1
            s["slow_avail"] += is_available
        else:
            s["fast_total"] += 1
            s["fast_avail"] += is_available
        if stat_upd_dt and stat_upd_dt > s["latest_update"]:
            s["latest_update"] = stat_upd_dt

    def pct(n, d):
        return round((n / d) * 100, 1) if d else 0.0

    stations = []
    for stat_id, info in sorted(station_counts.items(), key=lambda x: x[1]["total_count"], reverse=True):
        stations.append({
            "station_id": stat_id,
            "name": info["name"],
            "address": info["address"],
            "lat": info["lat"],
            "lng": info["lng"],
            "total_count": info["total_count"],
            "available_count": info["available_count"],
            "total_percent": pct(info["available_count"], info["total_count"]),
            "slow_total": info["slow_total"],
            "slow_avail": info["slow_avail"],
            "slow_percent": pct(info["slow_avail"], info["slow_total"]),
            "fast_total": info["fast_total"],
            "fast_avail": info["fast_avail"],
            "fast_percent": pct(info["fast_avail"], info["fast_total"]),
            "latest_update": info["latest_update"],
        })

    return {
        "summary": {
            "total_count": dist_total,
            "available_count": dist_avail,
            "total_percent": pct(dist_avail, dist_total),
            "slow_total": dist_slow_total,
            "slow_avail": dist_slow_avail,
            "slow_percent": pct(dist_slow_avail, dist_slow_total),
            "fast_total": dist_fast_total,
            "fast_avail": dist_fast_avail,
            "fast_percent": pct(dist_fast_avail, dist_fast_total),
            "station_count": len(station_counts),
        },
        "stations": stations,
    }


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    now_utc = datetime.now(UTC)
    now_kst = now_utc.astimezone(KST)
    hour_label = now_kst.strftime("%H시")

    print(f"=== {now_kst.strftime('%Y-%m-%d %H:%M')} KST 서울+6대 광역시 구/군별 가용률 수집 시작 ===")

    for city_name, zcode in CITIES:
        print(f"--- {city_name}(zcode={zcode}) 수집 중 ---")
        items = fetch_city_items(zcode, service_key)

        by_district = defaultdict(list)
        skipped = 0
        for item in items:
            d = extract_district(item.get("addr", ""))
            if d:
                by_district[d].append(item)
            else:
                skipped += 1

        city_dir = os.path.join(OUTPUT_ROOT, city_name, hour_label)
        os.makedirs(city_dir, exist_ok=True)

        for district, ditems in by_district.items():
            result = analyze_items(ditems)
            result["city"] = city_name
            result["district"] = district
            result["collected_at_kst"] = now_kst.isoformat()
            result["collected_at_utc"] = now_utc.isoformat()
            file_path = os.path.join(city_dir, f"{district}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"  {city_name}: {len(by_district)}개 구/군, 총 {len(items)}개 항목 (주소 파싱 실패 {skipped}건)")

    print(f"=== 완료: API 요청 {REQUEST_COUNT}건 ===")


if __name__ == "__main__":
    main()
