"""
metro7_ev_chargers_new.geojson에서 city='서울특별시'로 라벨된 충전소의 좌표를
VWorld 역지오코딩(좌표->행정구역)으로 실제 행정구역과 대조 검증.

- 단순 사각형 범위 체크와 달리 실제 행정경계를 보므로, 서울 경계에 바짝 붙은
  정상 주소(예: 강남구 세곡동)를 오탐하지 않음
- 불일치 발견 시 좌표는 건드리지 않고 결과만 CSV로 남김 (삭제/수정 안 함)
- VWorld 키는 VWORLD_API_KEY 환경변수에서 읽음
"""

import csv
import json
import os
import sys
import time

VWORLD_URL = "http://api.vworld.kr/req/address"
INPUT_GEOJSON = "metro7_ev_chargers_new.geojson"
OUTPUT_CSV = "seoul_boundary_check.csv"
TARGET_CITY = "서울특별시"


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


def main():
    api_key = os.environ.get("VWORLD_API_KEY")
    if not api_key:
        print("VWORLD_API_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    d = json.load(open(INPUT_GEOJSON, encoding="utf-8"))
    targets = [f for f in d["features"] if f["properties"].get("city") == TARGET_CITY]
    print(f"검증 대상: {len(targets)}개 ({TARGET_CITY})")

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
        elif result["level1"] != TARGET_CITY:
            mismatches.append({
                "station_id": p["station_id"], "name": p.get("name", ""),
                "address": p.get("address", ""), "lat": lat, "lng": lng,
                "reverse_level1": result["level1"], "reverse_level2": result["level2"],
                "reverse_text": result["text"],
            })
            print(f"[{i}/{len(targets)}] 불일치: {p['station_id']} {p.get('name','')} -> {result['level1']} {result['level2']}")

        if i % 500 == 0:
            print(f"[{i}/{len(targets)}] 진행 중... (불일치 {len(mismatches)}건 누적)")
            sys.stdout.flush()

        time.sleep(0.2)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["station_id", "name", "address", "lat", "lng", "reverse_level1", "reverse_level2", "reverse_text"])
        w.writeheader()
        w.writerows(mismatches)

    print(f"\n=== 완료: {checked}개 확인, 응답 없음 {no_result}건, 불일치 {len(mismatches)}건 ===")
    print(f"결과 -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
