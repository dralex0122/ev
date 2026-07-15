"""
GeoJSON 후처리 스크립트: 테스트/더미 레코드 제거 + 저정밀 좌표 플래그 추가.

- station_name에 '테스트'/'test'가 포함된 레코드는 실제 충전소가 아닌 것으로 보고 제거
- 위도/경도가 소수점 2자리 이하로 뭉뚱그려진 좌표는 삭제하지 않고
  properties.low_precision = true 플래그만 추가 (원본 API 데이터 자체의 정밀도 한계)
"""

import json
import re
import sys

TEST_PATTERN = re.compile(r"test|테스트", re.IGNORECASE)


def decimals(x):
    s = repr(float(x))
    return len(s.split(".")[1]) if "." in s else 0


def clean(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    kept = []
    removed = 0
    low_precision = 0

    for feature in data["features"]:
        name = feature["properties"].get("station_name") or feature["properties"].get("name") or ""
        if TEST_PATTERN.search(name):
            removed += 1
            continue

        lng, lat = feature["geometry"]["coordinates"]
        is_low_precision = decimals(lat) <= 2 and decimals(lng) <= 2
        feature["properties"]["low_precision"] = is_low_precision
        if is_low_precision:
            low_precision += 1

        kept.append(feature)

    data["features"] = kept

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"제거된 테스트/더미 레코드: {removed}개")
    print(f"저정밀 좌표로 플래그된 레코드: {low_precision}개")
    print(f"최종 충전소 수: {len(kept)}개 -> {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python3 clean_geojson.py <input.geojson> <output.geojson>", file=sys.stderr)
        sys.exit(1)
    clean(sys.argv[1], sys.argv[2])
