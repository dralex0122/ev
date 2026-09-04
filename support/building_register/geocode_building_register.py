"""
서울 건축물대장 총괄표제부(25개 구 CSV)를 VWorld 지오코딩으로 좌표화해서
연면적/주용도 정보를 100m/250m 격자 조인에 쓸 수 있게 만든다.

- 도로명대지위치가 있으면 ROAD 타입으로 먼저 시도, 없거나 실패하면
  대지위치(지번)를 PARCEL 타입으로 재시도 (regeocode_suspects.py와 동일 패턴)
- VWORLD_API_KEY 환경변수 사용
"""
import csv
import glob
import os
import sys
import time

import requests

VWORLD_URL = "http://api.vworld.kr/req/address"
INPUT_DIR = os.path.expanduser("~/ev-charger-accessibility/building_register_seoul")
OUTPUT_FP = os.path.expanduser("~/ev-charger-accessibility/building_register_seoul_geocoded.csv")
LOG_EVERY = 200


def geocode(address, addr_type, api_key):
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
    return None


def main():
    api_key = os.environ.get("VWORLD_API_KEY")
    if not api_key:
        print("VWORLD_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    rows = []
    for fp in sorted(glob.glob(os.path.join(INPUT_DIR, "*.csv"))):
        gu = os.path.basename(fp).split(" ")[0]
        with open(fp, encoding="utf-8-sig") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append({
                    "gu": gu,
                    "parcel_addr": row.get("대지위치", "").strip(),
                    "road_addr": row.get("도로명대지위치", "").strip(),
                    "floor_area": row.get("연면적(㎡)", "").strip(),
                    "main_use": row.get("주용도코드명", "").strip(),
                    "households": row.get("가구수(가구)", "").strip(),
                    "units": row.get("세대수(세대)", "").strip(),
                })

    total = len(rows)
    print(f"총 {total:,}건 로드 완료. 지오코딩 시작.")

    resolved = 0
    failed = 0
    with open(OUTPUT_FP, "w", encoding="utf-8-sig", newline="") as out:
        w = csv.writer(out)
        w.writerow(["gu", "floor_area_m2", "main_use", "households", "units", "lat", "lon", "geocode_source"])
        for i, row in enumerate(rows, start=1):
            result = None
            source = None
            if row["road_addr"]:
                result = geocode(row["road_addr"], "ROAD", api_key)
                source = "road"
            if not result and row["parcel_addr"]:
                result = geocode(row["parcel_addr"], "PARCEL", api_key)
                source = "parcel"

            if result:
                lon, lat = result
                w.writerow([row["gu"], row["floor_area"], row["main_use"], row["households"], row["units"],
                            f"{lat:.6f}", f"{lon:.6f}", source])
                resolved += 1
            else:
                failed += 1

            if i % LOG_EVERY == 0 or i == total:
                print(f"[{i}/{total}] 진행 중... (성공 {resolved}건, 실패 {failed}건)", flush=True)

            time.sleep(0.15)

    print(f"=== 완료: {total}건 중 {resolved}건 지오코딩 성공, {failed}건 실패 -> {OUTPUT_FP} ===")


if __name__ == "__main__":
    main()
