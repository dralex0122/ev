import csv
import os
import sys
import time

import requests

VWORLD_URL = "http://api.vworld.kr/req/address"
IN_PATH = "/tmp/unmatched_cells.csv"
OUT_PATH = os.path.expanduser("~/ev-charger-accessibility/grid_population/unmatched_cells_reverse_geocoded.csv")


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
            status = data.get("response", {}).get("status")
            if results:
                res = results[0] if isinstance(results, list) else results
                return res.get("text", ""), status
            return "", status
        except Exception:
            time.sleep(1)
    return None, "ERROR"


def main():
    api_key = os.environ.get("VWORLD_API_KEY")
    if not api_key:
        print("VWORLD_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    rows = []
    with open(IN_PATH, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)

    total = len(rows)
    print(f"총 {total:,}건 역지오코딩 시작", flush=True)

    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as out:
        w = csv.writer(out)
        w.writerow(["cell250_id", "lat", "lon", "night_avg", "day_avg", "address", "status"])
        found, notfound = 0, 0
        for i, row in enumerate(rows, start=1):
            lat, lon = float(row["lat"]), float(row["lon"])
            addr, status = reverse_geocode(lon, lat, api_key)
            if addr:
                found += 1
            else:
                notfound += 1
            w.writerow([row["cell250_id"], lat, lon, row["night_avg"], row["day_avg"], addr or "", status])
            if i % 200 == 0 or i == total:
                print(f"[{i}/{total}] 진행 중... (주소 있음 {found}건, 없음 {notfound}건)", flush=True)
            time.sleep(0.15)

    print(f"=== 완료: {total}건 중 주소 있음 {found}건, 없음 {notfound}건 -> {OUT_PATH} ===")


if __name__ == "__main__":
    main()
