"""
전남광주통합특별시(구 광주광역시, zcode=12) 데이터를 새로 수집해서
기존 결과물(metro7_ev_chargers_new.geojson, metropolitan_ev_stations.geojson,
260719/전남광주통합특별시/17시/<구>.json)에 보충하는 1회성 스크립트.

- 기존 파일들의 광주 항목은 전부 0건이었으므로 병합 시 충돌 없음
- 구/군은 zscode로 직접 조회 (동구 12210, 서구 12240, 남구 12270, 북구 12300, 광산구 12330)
- API 서비스키는 EV_SERVICE_KEY 환경변수에서 읽음
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

BASE_URL = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
NUM_OF_ROWS = 500
FAST_THRESHOLD_KW = 50.0
CITY_NAME = "전남광주통합특별시"
ZCODE = "12"
DISTRICTS = [
    ("동구", "12210"), ("서구", "12240"), ("남구", "12270"),
    ("북구", "12300"), ("광산구", "12330"),
]

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

REQUEST_COUNT = 0


def fetch_items(zcode, zscode, service_key):
    import requests

    global REQUEST_COUNT
    page_no = 1
    all_items = []

    while True:
        url = (
            f"{BASE_URL}?serviceKey={service_key}&pageNo={page_no}"
            f"&numOfRows={NUM_OF_ROWS}&zcode={zcode}&zscode={zscode}&dataType=JSON"
        )
        page_success = False
        items = []
        total_count = 0

        for attempt in range(1, 4):
            try:
                REQUEST_COUNT += 1
                r = requests.get(url, timeout=60)
                if r.status_code == 200:
                    data = r.json()
                    items_dict = data.get("items", {})
                    if not items_dict or "item" not in items_dict:
                        page_success = True
                        break
                    items = items_dict["item"]
                    if isinstance(items, dict):
                        items = [items]
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
            print(f"  경고: {zscode} {page_no}페이지 실패, 건너뜀", file=sys.stderr)
        elif not items or len(all_items) >= total_count:
            break

        page_no += 1
        time.sleep(0.3)

    return all_items


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
            "station_id": stat_id, "name": info["name"], "address": info["address"],
            "lat": info["lat"], "lng": info["lng"],
            "total_count": info["total_count"], "available_count": info["available_count"],
            "total_percent": pct(info["available_count"], info["total_count"]),
            "slow_total": info["slow_total"], "slow_avail": info["slow_avail"],
            "slow_percent": pct(info["slow_avail"], info["slow_total"]),
            "fast_total": info["fast_total"], "fast_avail": info["fast_avail"],
            "fast_percent": pct(info["fast_avail"], info["fast_total"]),
            "latest_update": info["latest_update"],
        })

    return {
        "summary": {
            "total_count": dist_total, "available_count": dist_avail,
            "total_percent": pct(dist_avail, dist_total),
            "slow_total": dist_slow_total, "slow_avail": dist_slow_avail,
            "slow_percent": pct(dist_slow_avail, dist_slow_total),
            "fast_total": dist_fast_total, "fast_avail": dist_fast_avail,
            "fast_percent": pct(dist_fast_avail, dist_fast_total),
            "station_count": len(station_counts),
        },
        "stations": stations,
    }, station_counts


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    now_utc = datetime.now(UTC)
    now_kst = now_utc.astimezone(KST)
    hour_label = "17시"  # 260719 데이터셋 보충용으로 기존 라벨에 맞춤

    all_items_by_district = {}
    all_items_flat = []

    for gu_name, zscode in DISTRICTS:
        print(f"--- {gu_name}({zscode}) 수집 중 ---")
        items = fetch_items(ZCODE, zscode, service_key)
        all_items_by_district[gu_name] = items
        all_items_flat.extend(items)
        print(f"  {gu_name}: {len(items)}개 항목")

    # 1. 260719/전남광주통합특별시/17시/<구>.json
    city_dir = os.path.join("260719", CITY_NAME, hour_label)
    os.makedirs(city_dir, exist_ok=True)
    for gu_name, items in all_items_by_district.items():
        result, _ = analyze_items(items)
        result["city"] = CITY_NAME
        result["district"] = gu_name
        result["collected_at_kst"] = now_kst.isoformat()
        result["collected_at_utc"] = now_utc.isoformat()
        with open(os.path.join(city_dir, f"{gu_name}.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"260719/{CITY_NAME}/{hour_label}/ 저장 완료")

    # 2. metro7_ev_chargers_new.geojson 에 station feature 추가
    _, station_counts = analyze_items(all_items_flat)
    new_features = []
    for stat_id, info in station_counts.items():
        try:
            lat_f = float(info["lat"])
            lng_f = float(info["lng"])
        except (TypeError, ValueError):
            continue
        new_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng_f, lat_f]},
            "properties": {
                "station_id": stat_id, "name": info["name"], "address": info["address"],
                "city": CITY_NAME, "zcode": ZCODE,
                "slow_count": info["slow_total"], "fast_count": info["fast_total"],
                "total_count": info["total_count"],
            },
        })

    for geojson_file, name_key, slow_key, fast_key, total_key in [
        ("metro7_ev_chargers_new.geojson", "name", "slow_count", "fast_count", "total_count"),
        ("metropolitan_ev_stations.geojson", "station_name", "slow_charger_count", "fast_charger_count", "total_charger_count"),
    ]:
        if not os.path.exists(geojson_file):
            print(f"{geojson_file} 없음, 건너뜀", file=sys.stderr)
            continue
        with open(geojson_file, "r", encoding="utf-8") as f:
            gj = json.load(f)
        existing_ids = {feat["properties"]["station_id"] for feat in gj["features"]}
        added = 0
        for stat_id, info in station_counts.items():
            if stat_id in existing_ids:
                continue
            try:
                lat_f = float(info["lat"])
                lng_f = float(info["lng"])
            except (TypeError, ValueError):
                continue
            props = {
                "station_id": stat_id,
                name_key: info["name"],
                "address": info["address"],
                slow_key: info["slow_total"],
                fast_key: info["fast_total"],
                total_key: info["total_count"],
            }
            gj["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng_f, lat_f]},
                "properties": props,
            })
            added += 1
        with open(geojson_file, "w", encoding="utf-8") as f:
            json.dump(gj, f, ensure_ascii=False, indent=2)
        print(f"{geojson_file}: {added}개 충전소 추가 (총 {len(gj['features'])}개)")

    print(f"\n=== 완료: API 요청 {REQUEST_COUNT}건, 총 {len(all_items_flat)}개 항목, {len(station_counts)}개 충전소 ===")


if __name__ == "__main__":
    main()
