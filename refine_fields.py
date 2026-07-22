"""
두 geojson 파일 필드 정리:
- year(설치 연도) 필드를 API에서 재수집해서 추가
- low_precision, geocoding_suspect, limit_detail 필드 삭제
- use_time -> openinghour, limit_yn -> UseLimitation 이름 변경
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

REMOVE_KEYS = ["low_precision", "geocoding_suspect", "limit_detail"]
RENAME_KEYS = {"use_time": "openinghour", "limit_yn": "UseLimitation"}


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

    station_year = {}
    for city_name, zcode in CITIES:
        print(f"--- {city_name}(zcode={zcode}) 수집 중 ---")
        items = fetch_city_items(zcode, service_key)
        for item in items:
            sid = item.get("statId")
            if not sid or sid in station_year:
                continue
            station_year[sid] = item.get("year", "")
        print(f"  {city_name}: 누적 station {len(station_year)}개")

    for path in ("metro7_ev_chargers_new.geojson", "metropolitan_ev_stations.geojson"):
        d = json.load(open(path, encoding="utf-8"))
        n_year = n_removed = n_renamed = 0
        for f in d["features"]:
            p = f["properties"]

            sid = p.get("station_id")
            year = station_year.get(sid)
            if year:
                p["year"] = year
                n_year += 1

            for k in REMOVE_KEYS:
                if k in p:
                    del p[k]
                    n_removed += 1

            for old_k, new_k in RENAME_KEYS.items():
                if old_k in p:
                    p[new_k] = p.pop(old_k)
                    n_renamed += 1

        with open(path, "w", encoding="utf-8") as out:
            json.dump(d, out, ensure_ascii=False, indent=2)
        print(f"{path}: year 추가 {n_year}건, 필드 삭제 {n_removed}건, 이름변경 {n_renamed}건")


if __name__ == "__main__":
    main()
