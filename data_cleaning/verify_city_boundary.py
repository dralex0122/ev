"""
metro7_ev_chargers_new.geojson의 각 city 라벨에 대해, 실제 좌표를 VWorld
역지오코딩(좌표->행정구역)으로 대조 검증. 서울부터 시작해서 7개 도시를 순서대로
전부 처리.

- 단순 사각형 범위 체크와 달리 실제 행정경계를 보므로, 도시 경계에 바짝 붙은
  정상 주소(예: 강남구 세곡동)를 오탐하지 않음
- 불일치 발견 시 좌표는 건드리지 않고 결과만 CSV로 남김 (삭제/수정 안 함)
- 도시별로 별도 CSV 저장: boundary_check_<도시>.csv
- VWorld 키는 VWORLD_API_KEY 환경변수에서 읽음
"""

import csv
import json
import os
import sys
import time

VWORLD_URL = "http://api.vworld.kr/req/address"
INPUT_GEOJSON = "metro7_ev_chargers_new.geojson"

CITIES = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시",
    "전남광주통합특별시", "대전광역시", "울산광역시",
]


def reverse_geocode(lng, lat, api_key):
    params = {
        "service": "address", "request": "getAddress", "version": "2.0",
        "crs": "epsg:4326", "point": f"{lng},{lat}", "format": "json",
        "type": "both", "key": api_key,
    }
    import requests

    for attempt in range(1, 4):
        try:
            r = requests.get(VWORLD_URL, params=params, timeout=20)
            data = r.json()
            results = data.get("response", {}).get("result")
            if results:
                res = results[0] if isinstance(results, list) else results
                structure = res.get("structure", {})
                return {
                    "level1": structure.get("level1", ""),
                    "level2": structure.get("level2", ""),
                    "text": res.get("text", ""),
                }
            return None
        except Exception:
            time.sleep(1)
    return None


def check_city(target_city, features, api_key):
    targets = [f for f in features if f["properties"].get("city") == target_city]
    print(f"=== {target_city}: 검증 대상 {len(targets)}개 ===")
    sys.stdout.flush()

    mismatches = []
    checked = 0
    no_result = 0

    for i, f in enumerate(targets, start=1):
        lng, lat = f["geometry"]["coordinates"]
        p = f["properties"]
        result = reverse_geocode(lng, lat, api_key)
        checked += 1
        if result is None:
            no_result += 1
        elif result["level1"] != target_city:
            mismatches.append({
                "station_id": p["station_id"], "name": p.get("name", ""),
                "address": p.get("address", ""), "lat": lat, "lng": lng,
                "reverse_level1": result["level1"], "reverse_level2": result["level2"],
                "reverse_text": result["text"],
            })
            print(f"[{target_city} {i}/{len(targets)}] 불일치: {p['station_id']} {p.get('name','')} -> {result['level1']} {result['level2']}")

        if i % 500 == 0:
            print(f"[{target_city} {i}/{len(targets)}] 진행 중... (불일치 {len(mismatches)}건 누적)")
            sys.stdout.flush()

        time.sleep(0.1)

    output_csv = f"boundary_check_{target_city}.csv"
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["station_id", "name", "address", "lat", "lng", "reverse_level1", "reverse_level2", "reverse_text"])
        w.writeheader()
        w.writerows(mismatches)

    print(f"=== {target_city} 완료: {checked}개 확인, 응답 없음 {no_result}건, 불일치 {len(mismatches)}건 -> {output_csv} ===\n")
    sys.stdout.flush()
    return checked, len(mismatches)


def main():
    api_key = os.environ.get("VWORLD_API_KEY")
    if not api_key:
        print("VWORLD_API_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    d = json.load(open(INPUT_GEOJSON, encoding="utf-8"))
    features = d["features"]

    total_checked = total_mismatch = 0
    for city in CITIES:
        checked, mismatch = check_city(city, features, api_key)
        total_checked += checked
        total_mismatch += mismatch

    print(f"\n=== 전체 완료: {total_checked}개 확인, 총 불일치 {total_mismatch}건 ===")


if __name__ == "__main__":
    main()
