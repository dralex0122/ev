"""
경기도(zcode=41) 전체 충전소 수집.

- 정부 API(zcode=41)로 전체 페이지네이션 수집 (page-skip-not-abort)
- statId 기준으로 충전기 -> 충전소 단위 집계 (slow/fast/total count, year,
  openinghour, UseLimitation, parking_free, note 등 metro7 스키마와 동일하게)
- 좌표는 lat/lng 그대로 저장 (이상치 보정은 다음 단계 스크립트에서)
"""
import json
import os
import sys
import time

BASE_URL = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
NUM_OF_ROWS = 500
ZCODE = "41"
CITY_NAME = "경기도"
FAST_THRESHOLD_KW = 50.0

OUT_PATH = "gyeonggi_ev_chargers.geojson"


def fetch_all_items(service_key):
    page_no = 1
    all_items = []
    import requests

    while True:
        url = (
            f"{BASE_URL}?serviceKey={service_key}&pageNo={page_no}"
            f"&numOfRows={NUM_OF_ROWS}&zcode={ZCODE}&dataType=JSON"
        )
        page_success = False
        items = []
        total_count = 0
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=60)
                if r.status_code == 200:
                    data = r.json()
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
            print(f"  경고: {page_no}페이지 수집 실패, 건너뜁니다.", file=sys.stderr)
        elif not items or len(all_items) >= total_count:
            break

        if page_no % 20 == 0:
            print(f"  ...{page_no}페이지까지 진행, 누적 {len(all_items)}건")
            sys.stdout.flush()

        page_no += 1
        time.sleep(0.2)

    return all_items


def aggregate_stations(items):
    stations = {}
    for item in items:
        sid = item.get("statId")
        if not sid:
            continue
        s = stations.setdefault(sid, {
            "station_id": sid,
            "name": item.get("statNm"),
            "address": item.get("addr", ""),
            "city": CITY_NAME,
            "zcode": ZCODE,
            "slow_count": 0,
            "fast_count": 0,
            "total_count": 0,
            "lat": item.get("lat"),
            "lng": item.get("lng"),
            "year": item.get("year", ""),
            "openinghour": item.get("useTime", ""),
            "UseLimitation": item.get("limitYn", ""),
            "parking_free": item.get("parkingFree", ""),
            "note": item.get("note", ""),
        })
        try:
            kw = float(item.get("output")) if item.get("output") else 0.0
        except ValueError:
            kw = 7.0
        is_slow = kw < FAST_THRESHOLD_KW
        s["total_count"] += 1
        if is_slow:
            s["slow_count"] += 1
        else:
            s["fast_count"] += 1
    return stations


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    print(f"=== 경기도(zcode={ZCODE}) 전체 수집 시작 ===")
    sys.stdout.flush()
    items = fetch_all_items(service_key)
    print(f"=== 전체 항목 수집 완료: {len(items)}건 ===")

    stations = aggregate_stations(items)
    print(f"=== 충전소 단위 집계 완료: {len(stations)}개 station ===")

    features = []
    skipped_no_coord = 0
    for sid, s in stations.items():
        lat, lng = s.pop("lat", None), s.pop("lng", None)
        try:
            lat_f, lng_f = float(lat), float(lng)
        except (TypeError, ValueError):
            skipped_no_coord += 1
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng_f, lat_f]},
            "properties": s,
        })

    out = {"type": "FeatureCollection", "features": features}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"=== {OUT_PATH} 저장 완료: {len(features)}건 (좌표 없어 제외 {skipped_no_coord}건) ===")


if __name__ == "__main__":
    main()
