"""
gridpop_7cities.csv(사각형 경계로 1차 필터링된 격자, 서울/부산/인천 등은
이웃 지역 인구가 섞여 과대평가됨)의 각 격자를 VWorld 역지오코딩으로 검증해서,
실제 그 도시가 맞는 격자만 남긴 정밀 버전을 생성.

- 전남광주통합특별시는 2026-07-01 행정구역 개편으로 VWorld가 아직 옛 이름
  "광주광역시"로 응답할 수 있어 동일 지역으로 간주
"""
import csv
import os
import sys
import time

import requests

VWORLD_URL = "http://api.vworld.kr/req/address"
IN_PATH = "gridpop_7cities.csv"
OUT_PATH = "gridpop_7cities_verified.csv"

CITY_EQUIVALENTS = {
    "서울특별시": {"서울특별시"},
    "부산광역시": {"부산광역시"},
    "대구광역시": {"대구광역시"},
    "인천광역시": {"인천광역시"},
    "전남광주통합특별시": {"전남광주통합특별시", "광주광역시"},
    "대전광역시": {"대전광역시"},
    "울산광역시": {"울산광역시"},
}


def reverse_geocode(lng, lat, api_key):
    params = {
        "service": "address", "request": "getAddress", "version": "2.0",
        "crs": "epsg:4326", "point": f"{lng},{lat}", "format": "json",
        "type": "both", "key": api_key,
    }
    for attempt in range(3):
        try:
            r = requests.get(VWORLD_URL, params=params, timeout=20)
            data = r.json()
            results = data.get("response", {}).get("result")
            if results:
                res = results[0] if isinstance(results, list) else results
                structure = res.get("structure", {})
                return structure.get("level1", "")
            return None
        except Exception:
            time.sleep(1)
    return None


def main():
    api_key = os.environ.get("VWORLD_API_KEY")
    if not api_key:
        print("VWORLD_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    with open(IN_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    print(f"=== 검증 대상 {total}개 ===")
    sys.stdout.flush()

    kept = 0
    no_result = 0
    with open(OUT_PATH, "w", newline="", encoding="utf-8-sig") as out:
        w = csv.writer(out)
        w.writerow(["grid_id", "city", "lat", "lng", "total_population", "male_population", "female_population"])

        for i, row in enumerate(rows, start=1):
            lat, lng = float(row["lat"]), float(row["lng"])
            city = row["city"]
            level1 = reverse_geocode(lng, lat, api_key)
            if level1 is None:
                no_result += 1
            elif level1 in CITY_EQUIVALENTS.get(city, {city}):
                w.writerow([row["grid_id"], city, row["lat"], row["lng"],
                            row["total_population"], row["male_population"], row["female_population"]])
                kept += 1

            if i % 2000 == 0:
                print(f"[{i}/{total}] 진행 중... (유지 {kept}건, 응답없음 {no_result}건)")
                sys.stdout.flush()

            time.sleep(0.1)

    print(f"=== 완료: {total}개 중 {kept}개 유지, 응답없음 {no_result}건 -> {OUT_PATH} ===")


if __name__ == "__main__":
    main()
