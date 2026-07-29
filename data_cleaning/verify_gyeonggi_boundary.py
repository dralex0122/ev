"""
gyeonggi_ev_chargers.geojson의 각 station 좌표를 VWorld 역지오코딩으로 대조해서
실제로 경기도가 맞는지 검증. 좌표는 건드리지 않고 결과만 CSV로 남김.
"""
import csv
import json
import os
import sys
import time

VWORLD_URL = "http://api.vworld.kr/req/address"
INPUT_GEOJSON = "gyeonggi_ev_chargers.geojson"
OUTPUT_CSV = "boundary_check_경기도.csv"


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
        print("VWORLD_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    d = json.load(open(INPUT_GEOJSON, encoding="utf-8"))
    features = d["features"]
    print(f"=== 경기도: 검증 대상 {len(features)}개 ===")
    sys.stdout.flush()

    mismatches = []
    checked = 0
    no_result = 0

    for i, f in enumerate(features, start=1):
        lng, lat = f["geometry"]["coordinates"]
        p = f["properties"]
        result = reverse_geocode(lng, lat, api_key)
        checked += 1
        if result is None:
            no_result += 1
        elif result["level1"] != "경기도":
            mismatches.append({
                "station_id": p["station_id"], "name": p.get("name", ""),
                "address": p.get("address", ""), "lat": lat, "lng": lng,
                "reverse_level1": result["level1"], "reverse_level2": result["level2"],
                "reverse_text": result["text"],
            })
            print(f"[{i}/{len(features)}] 불일치: {p['station_id']} {p.get('name','')} -> {result['level1']} {result['level2']}")

        if i % 1000 == 0:
            print(f"[{i}/{len(features)}] 진행 중... (불일치 {len(mismatches)}건 누적)")
            sys.stdout.flush()

        time.sleep(0.12)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["station_id", "name", "address", "lat", "lng", "reverse_level1", "reverse_level2", "reverse_text"])
        w.writeheader()
        w.writerows(mismatches)

    print(f"=== 완료: {checked}개 확인, 응답 없음 {no_result}건, 불일치 {len(mismatches)}건 -> {OUTPUT_CSV} ===")


if __name__ == "__main__":
    main()
