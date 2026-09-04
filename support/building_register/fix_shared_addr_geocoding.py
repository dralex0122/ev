import csv
import glob
import math
import os
import sys
import time

import pandas as pd
import requests

VWORLD_URL = "http://api.vworld.kr/req/address"
BASE = "/home/jmw/ev-charger-accessibility/building_register"


def geocode(address, addr_type, api_key):
    params = {
        "service": "address", "request": "getcoord", "version": "2.0",
        "crs": "epsg:4326", "address": address, "refine": "true", "simple": "false",
        "format": "json", "type": addr_type, "key": api_key,
    }
    try:
        resp = requests.get(VWORLD_URL, params=params, timeout=20)
        data = resp.json()
        result = data.get("response", {}).get("result")
        if result and result.get("point"):
            return float(result["point"]["x"]), float(result["point"]["y"])
    except Exception:
        pass
    return None


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def main():
    api_key = os.environ.get("VWORLD_API_KEY")
    if not api_key:
        print("VWORLD_API_KEY 없음", file=sys.stderr)
        sys.exit(1)

    rows = []
    for f in glob.glob(BASE + "/building_register_seoul/*.csv"):
        df = pd.read_csv(
            f, encoding="utf-8-sig",
            usecols=["대지위치", "도로명대지위치", "건물명", "연면적(㎡)", "주용도코드명", "세대수(세대)"],
        )
        df["__file"] = f.split("/")[-1]
        rows.append(df)
    full = pd.concat(rows, ignore_index=True)
    full["gu"] = full["__file"].str.split(" ").str[0]
    full["연면적(㎡)"] = pd.to_numeric(full["연면적(㎡)"], errors="coerce")

    has_road = full[full["도로명대지위치"].notna() & (full["도로명대지위치"].str.strip() != "")]
    group_lots = has_road.groupby("도로명대지위치")["대지위치"].nunique()
    shared_addrs = set(group_lots[group_lots >= 3].index)
    candidates = has_road[has_road["도로명대지위치"].isin(shared_addrs)].copy()
    print(f"대상 건물: {len(candidates)}건 (공유 도로명주소 {len(shared_addrs)}개 그룹)")

    # 현재 지오코딩된 결과 로드 (gu, main_use, units, floor_area로 매칭)
    geocoded_lookup = {}
    with open(BASE + "/building_register_seoul_geocoded.csv", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                area = float(row["floor_area_m2"])
            except ValueError:
                continue
            units = int(row["units"]) if row["units"] else 0
            key = (row["gu"], row["main_use"], units, area)
            geocoded_lookup[key] = (float(row["lat"]), float(row["lon"]))

    results = []
    for i, (_, row) in enumerate(candidates.iterrows(), start=1):
        area = row["연면적(㎡)"]
        units = int(row["세대수(세대)"]) if pd.notna(row["세대수(세대)"]) else 0
        main_use = row["주용도코드명"] if pd.notna(row["주용도코드명"]) else ""
        gu = row["gu"]
        key = (gu, main_use, units, area)
        current = geocoded_lookup.get(key)

        # 지번(파셀) 주소로 재지오코딩
        parcel_result = geocode(row["대지위치"], "PARCEL", api_key)
        time.sleep(0.15)

        dist = None
        parcel_lat = parcel_lon = None
        if parcel_result:
            plon, plat = parcel_result
            parcel_lat, parcel_lon = plat, plon
            if current:
                clat, clon = current
                dist = haversine_m(clat, clon, plat, plon)

        results.append({
            "gu": gu, "대지위치": row["대지위치"], "도로명대지위치": row["도로명대지위치"],
            "건물명": row["건물명"], "주용도": main_use, "세대수": units, "연면적": area,
            "현재_lat": current[0] if current else None, "현재_lon": current[1] if current else None,
            "지번재지오코딩_lat": parcel_lat, "지번재지오코딩_lon": parcel_lon,
            "차이_m": dist,
        })
        print(f"[{i}/{len(candidates)}] {row['대지위치']} - 차이: {dist:.0f}m" if dist else
              f"[{i}/{len(candidates)}] {row['대지위치']} - 비교불가", flush=True)

    out_fp = BASE + "/shared_addr_recheck.csv"
    with open(out_fp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"\n저장: {out_fp}")

    big_diff = [r for r in results if r["차이_m"] and r["차이_m"] > 150]
    print(f"\n150m 이상 차이나는 건: {len(big_diff)}건")
    for r in sorted(big_diff, key=lambda x: -x["차이_m"]):
        print(f"{r['대지위치']} ({r['건물명']}, {r['주용도']}) - {r['차이_m']:.0f}m 차이")


if __name__ == "__main__":
    main()
