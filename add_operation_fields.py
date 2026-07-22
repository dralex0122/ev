"""
API에서 운영시간(useTime), 이용제한(limitYn/limitDetail), 주차무료(parkingFree),
비고(note) 필드를 7개 도시 전체 재수집해서 station_id 기준으로
metro7_ev_chargers_new.geojson / metropolitan_ev_stations.geojson에 추가하는
일회성 스크립트.
"""
import json
import os
import sys
import time

BASE_URL = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
NUM_OF_ROWS = 500

CITIES = [
    ("서울특별시", "11"), ("부산광역시", "26"), ("대구광역시", "27"),
    ("인천광역시", "28"), ("전남광주통합특별시", "12"),
    ("대전광역시", "30"), ("울산광역시", "31"),
]


def fetch_city_items(zcode, service_key):
    import requests

    page_no = 1
    all_items = []
    while True:
        full_url = (
            f"{BASE_URL}?serviceKey={service_key}&pageNo={page_no}"
            f"&numOfRows={NUM_OF_ROWS}&zcode={zcode}&dataType=JSON"
        )
        page_success = False
        items = []
        total_count = 0
        for attempt in range(1, 4):
            try:
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
            print(f"  경고: zcode={zcode} {page_no}페이지 수집 실패, 건너뜁니다.", file=sys.stderr)
        elif not items or len(all_items) >= total_count:
            break

        page_no += 1
        time.sleep(0.3)

    return all_items


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    station_extra = {}
    for city_name, zcode in CITIES:
        print(f"--- {city_name}(zcode={zcode}) 수집 중 ---")
        items = fetch_city_items(zcode, service_key)
        for item in items:
            sid = item.get("statId")
            if not sid or sid in station_extra:
                continue
            station_extra[sid] = {
                "use_time": item.get("useTime", ""),
                "limit_yn": item.get("limitYn", ""),
                "limit_detail": item.get("limitDetail", ""),
                "parking_free": item.get("parkingFree", ""),
                "note": item.get("note", ""),
            }
        print(f"  {city_name}: 누적 station {len(station_extra)}개")

    for path in ("metro7_ev_chargers_new.geojson", "metropolitan_ev_stations.geojson"):
        d = json.load(open(path, encoding="utf-8"))
        n = 0
        for f in d["features"]:
            sid = f["properties"].get("station_id")
            extra = station_extra.get(sid)
            if extra:
                f["properties"].update(extra)
                n += 1
        with open(path, "w", encoding="utf-8") as out:
            json.dump(d, out, ensure_ascii=False, indent=2)
        print(f"{path}: {n}건에 필드 추가 (전체 {len(d['features'])}건 중)")


if __name__ == "__main__":
    main()
