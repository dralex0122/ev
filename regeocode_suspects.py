"""
좌표 이상치(라벨된 도시 범위 밖, 원본 API 좌표 오류로 확인된 항목)를
VWorld 지오코딩 API로 주소 기반 재지오코딩하는 스크립트.

- metro7_ev_chargers_new.geojson의 'city' 속성 기준으로 이상치 station_id를 먼저 추출
- 각 station_id의 address로 VWorld geocoding 호출 (도로명 실패 시 지번으로 재시도)
- 성공하면 metro7_ev_chargers_new.geojson과 metropolitan_ev_stations.geojson 양쪽에서
  해당 station_id의 좌표를 갱신
- 실패한 항목은 좌표를 건드리지 않고 properties.geocoding_suspect = true 플래그만 남김
- VWORLD_API_KEY 환경변수에서 키를 읽음 (레포에 하드코딩하지 않음)
"""

import json
import os
import sys
import time

CITY_BOUNDS = {
    "서울특별시": (37.40, 37.75, 126.75, 127.20),
    "부산광역시": (34.95, 35.40, 128.75, 129.35),
    "대구광역시": (35.75, 36.05, 128.35, 128.75),
    "인천광역시": (37.30, 37.65, 126.35, 126.80),
    "전남광주통합특별시": (35.05, 35.25, 126.70, 127.00),
    "대전광역시": (36.20, 36.50, 127.25, 127.55),
    "울산광역시": (35.40, 35.70, 129.20, 129.50),
}

VWORLD_URL = "http://api.vworld.kr/req/address"

FILES_TO_UPDATE = [
    "metro7_ev_chargers_new.geojson",
    "metropolitan_ev_stations.geojson",
]


def find_suspects(city_labeled_file):
    with open(city_labeled_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    suspects = {}
    for feature in data["features"]:
        city = feature["properties"].get("city")
        bounds = CITY_BOUNDS.get(city)
        if not bounds:
            continue
        lng, lat = feature["geometry"]["coordinates"]
        lat_min, lat_max, lng_min, lng_max = bounds
        if not (lat_min <= lat <= lat_max and lng_min <= lng <= lng_max):
            sid = feature["properties"]["station_id"]
            suspects[sid] = feature["properties"].get("address") or feature["properties"].get("name")
    return suspects


def geocode(address, api_key):
    import requests

    for addr_type in ("ROAD", "PARCEL"):
        params = {
            "service": "address",
            "request": "getcoord",
            "version": "2.0",
            "crs": "epsg:4326",
            "address": address,
            "refine": "true",
            "simple": "false",
            "format": "json",
            "type": addr_type,
            "key": api_key,
        }
        try:
            resp = requests.get(VWORLD_URL, params=params, timeout=20)
            data = resp.json()
            result = data.get("response", {}).get("result")
            if result and result.get("point"):
                lng = float(result["point"]["x"])
                lat = float(result["point"]["y"])
                return lng, lat
        except Exception:
            pass
        time.sleep(0.2)
    return None


def main():
    api_key = os.environ.get("VWORLD_API_KEY")
    if not api_key:
        print("VWORLD_API_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    suspects = find_suspects("metro7_ev_chargers_new.geojson")
    print(f"이상치 {len(suspects)}개 발견, 재지오코딩 시작")

    resolved = {}
    unresolved = []
    for i, (sid, address) in enumerate(suspects.items(), start=1):
        result = geocode(address, api_key)
        if result:
            resolved[sid] = result
            print(f"[{i}/{len(suspects)}] {sid} 성공: {address} -> {result}")
        else:
            unresolved.append((sid, address))
            print(f"[{i}/{len(suspects)}] {sid} 실패: {address}")
        time.sleep(0.3)

    print(f"\n성공: {len(resolved)}개, 실패: {len(unresolved)}개")

    for filename in FILES_TO_UPDATE:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        updated = 0
        flagged = 0
        for feature in data["features"]:
            sid = feature["properties"]["station_id"]
            if sid in resolved:
                lng, lat = resolved[sid]
                feature["geometry"]["coordinates"] = [lng, lat]
                feature["properties"]["geocoding_suspect"] = False
                updated += 1
            elif sid in suspects:
                feature["properties"]["geocoding_suspect"] = True
                flagged += 1

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"{filename}: 좌표 갱신 {updated}개, 실패 플래그 {flagged}개")


if __name__ == "__main__":
    main()
