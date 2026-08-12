"""
서울 + 6대 광역시(부산·대구·인천·광주·대전·울산) 충전소 위치와
충전소별 완속/고속 충전기 수를 GeoJSON으로 생성.

- API가 각 충전기 레코드에 lat/lng를 직접 제공하므로 별도 지오코딩 없이 좌표를 그대로 사용
- zscode 없이 zcode(시도코드)만 지정해 도시 전체를 한 번에 페이지네이션 수집
- API 서비스키는 EV_SERVICE_KEY 환경변수에서 읽음 (레포에 하드코딩하지 않음)
"""

import json
import os
import sys
import time

BASE_URL = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
NUM_OF_ROWS = 500
OUTPUT_FILE = "metro7_ev_chargers_new.geojson"
FAST_THRESHOLD_KW = 50.0

METRO_CITIES = [
    ("서울특별시", "11"),
    ("부산광역시", "26"),
    ("대구광역시", "27"),
    ("인천광역시", "28"),
    ("전남광주통합특별시", "12"),
    ("대전광역시", "30"),
    ("울산광역시", "31"),
]

REQUEST_COUNT = 0  # 이번 실행에서 API에 실제로 보낸 요청 수(재시도 포함, 일일 트래픽 추적용)


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


def build_station_features(city_name, zcode, items):
    stations = {}
    for item in items:
        stat_id = item.get("statId")
        if not stat_id:
            continue
        try:
            lat_f = float(item.get("lat"))
            lng_f = float(item.get("lng"))
        except (TypeError, ValueError):
            continue

        output_val = item.get("output")
        try:
            kw = float(output_val) if output_val else 0.0
        except ValueError:
            kw = 7.0
        is_slow = kw < FAST_THRESHOLD_KW

        s = stations.setdefault(stat_id, {
            "name": item.get("statNm"),
            "address": item.get("addr", ""),
            "lat": lat_f,
            "lng": lng_f,
            "slow_count": 0,
            "fast_count": 0,
        })
        if is_slow:
            s["slow_count"] += 1
        else:
            s["fast_count"] += 1

    features = []
    for stat_id, info in stations.items():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [info["lng"], info["lat"]],
            },
            "properties": {
                "station_id": stat_id,
                "name": info["name"],
                "address": info["address"],
                "city": city_name,
                "zcode": zcode,
                "slow_count": info["slow_count"],
                "fast_count": info["fast_count"],
                "total_count": info["slow_count"] + info["fast_count"],
            },
        })
    return features


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    all_features = []
    for city_name, zcode in METRO_CITIES:
        print(f"=== {city_name}(zcode={zcode}) 수집 중 ===")
        items = fetch_city_items(zcode, service_key)
        features = build_station_features(city_name, zcode, items)
        all_features.extend(features)
        print(f"- {city_name}: {len(features)}개 충전소")

    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"=== 완료: 총 {len(all_features)}개 충전소, API 요청 {REQUEST_COUNT}건 → {OUTPUT_FILE} ===")


if __name__ == "__main__":
    main()
