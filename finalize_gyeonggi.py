"""
boundary_check_경기도.csv의 불일치 건을 원본 주소 재지오코딩으로 교차검증해서
자동 분류/처리. 판단 기준은 서울/부산/대구/인천/광주/대전/울산 7개 도시 검증 때와
동일 (2026-07-20~21 작업에서 검증된 방식):

- 주소 자체가 경기도가 아닌 다른 시/도를 명시 -> REMOVE (이 파일 범위 밖, 삭제)
- 주소는 경기도(또는 경기도 산하 시/군)인데 저장 좌표와 원본 주소 재지오코딩 결과가
  가까움(<3km) -> KEEP_ASIS (도 경계 인근 VWorld 역지오코딩 자체 오차, 실제 문제 아님)
- 주소는 경기도인데 재지오코딩 결과와 많이 다름(>5km) -> FIX_COORD (저장 좌표 자체가
  버그였던 것으로 보고 좌표를 재지오코딩 결과로 교체)
- 3~5km 사이 애매한 경우 -> AMBIGUOUS (자동 처리하지 않고 플래그만 남김)

모든 처리 내역은 properties.boundary_review 필드에 남겨 사용자가 나중에
감사(audit)할 수 있게 함. 최종적으로 23년/24년 누적 스냅샷도 함께 생성.
"""
import csv
import json
import math
import os
import re
import sys
import time

VWORLD_URL = "http://api.vworld.kr/req/address"
INPUT_GEOJSON = "gyeonggi_ev_chargers.geojson"
BOUNDARY_CSV = "boundary_check_경기도.csv"

GYEONGGI_CITY_NAMES = {
    "경기도", "경기",
    "수원시", "성남시", "의정부시", "안양시", "부천시", "광명시", "평택시", "동두천시",
    "안산시", "고양시", "과천시", "구리시", "남양주시", "오산시", "시흥시", "군포시",
    "의왕시", "하남시", "용인시", "파주시", "이천시", "안성시", "김포시", "화성시",
    "광주시", "양주시", "포천시", "여주시", "연천군", "가평군", "양평군",
}


def is_gyeonggi_address(addr):
    parts = (addr or "").split()
    if not parts:
        return False
    return parts[0] in GYEONGGI_CITY_NAMES


def clean_address(addr):
    tokens = addr.split()
    cleaned = []
    for tok in tokens:
        m = re.match(r'^(\d+(-\d+)?)[^\d\-\s].+$', tok)
        if m:
            cleaned.append(m.group(1))
            break
        cleaned.append(tok)
    return " ".join(cleaned)


def geocode(addr, addr_type, api_key):
    import requests

    params = {
        "service": "address", "request": "getcoord", "version": "2.0",
        "crs": "epsg:4326", "address": addr, "refine": "true", "simple": "false",
        "format": "json", "type": addr_type, "key": api_key,
    }
    try:
        r = requests.get(VWORLD_URL, params=params, timeout=20)
        data = r.json()
        result = data.get("response", {}).get("result")
        if result:
            pt = result["point"]
            return float(pt["x"]), float(pt["y"])
    except Exception:
        pass
    return None


def dist_km(lat1, lng1, lat2, lng2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def main():
    api_key = os.environ.get("VWORLD_API_KEY")
    if not api_key:
        print("VWORLD_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    mismatches = {}
    with open(BOUNDARY_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            mismatches[row["station_id"]] = row

    print(f"=== 불일치 {len(mismatches)}건 교차검증 시작 ===")
    sys.stdout.flush()

    decisions = {}
    for i, (sid, row) in enumerate(mismatches.items(), start=1):
        addr = row["address"]
        lat, lng = float(row["lat"]), float(row["lng"])

        if not is_gyeonggi_address(addr):
            decisions[sid] = {"action": "REMOVE", "reason": f"주소 자체가 다른 시/도: {addr}"}
            print(f"[{i}/{len(mismatches)}] REMOVE {sid} ({row['name']}) - 주소={addr}")
            sys.stdout.flush()
            continue

        cleaned = clean_address(addr)
        coord = geocode(addr, "ROAD", api_key)
        if coord is None:
            coord = geocode(addr, "PARCEL", api_key)
        if coord is None and cleaned != addr:
            coord = geocode(cleaned, "ROAD", api_key)
            if coord is None:
                coord = geocode(cleaned, "PARCEL", api_key)

        if coord is None:
            decisions[sid] = {"action": "AMBIGUOUS", "reason": "주소 지오코딩 실패, 수동 확인 필요"}
            print(f"[{i}/{len(mismatches)}] AMBIGUOUS {sid} ({row['name']}) - 주소 지오코딩 실패")
        else:
            glng, glat = coord
            d = dist_km(lat, lng, glat, glng)
            if d < 3:
                decisions[sid] = {"action": "KEEP_ASIS", "reason": f"주소지오코딩과 {d:.2f}km 차이, 경계 근처 오차로 판단"}
            elif d > 5:
                decisions[sid] = {
                    "action": "FIX_COORD", "reason": f"주소지오코딩과 {d:.2f}km 차이, 저장 좌표 버그로 판단",
                    "new_coord": [glng, glat],
                }
                print(f"[{i}/{len(mismatches)}] FIX_COORD {sid} ({row['name']}) - {d:.2f}km 차이")
            else:
                decisions[sid] = {"action": "AMBIGUOUS", "reason": f"주소지오코딩과 {d:.2f}km 차이, 애매한 범위"}
                print(f"[{i}/{len(mismatches)}] AMBIGUOUS {sid} ({row['name']}) - {d:.2f}km 차이")

        sys.stdout.flush()
        time.sleep(0.15)

    d = json.load(open(INPUT_GEOJSON, encoding="utf-8"))
    counts = {"REMOVE": 0, "KEEP_ASIS": 0, "FIX_COORD": 0, "AMBIGUOUS": 0}
    new_features = []
    for f in d["features"]:
        sid = f["properties"].get("station_id")
        dec = decisions.get(sid)
        if dec is None:
            new_features.append(f)
            continue

        counts[dec["action"]] += 1
        if dec["action"] == "REMOVE":
            continue  # 이 파일에서 제외

        f["properties"]["boundary_review"] = {"action": dec["action"], "reason": dec["reason"]}
        if dec["action"] == "FIX_COORD":
            f["geometry"]["coordinates"] = dec["new_coord"]
        new_features.append(f)

    d["features"] = new_features
    with open(INPUT_GEOJSON, "w", encoding="utf-8") as out:
        json.dump(d, out, ensure_ascii=False, indent=2)

    print(f"=== 처리 완료: REMOVE {counts['REMOVE']}, KEEP_ASIS {counts['KEEP_ASIS']}, "
          f"FIX_COORD {counts['FIX_COORD']}, AMBIGUOUS {counts['AMBIGUOUS']} ===")
    print(f"=== 최종 {INPUT_GEOJSON}: {len(new_features)}건 ===")

    # 23년/24년 누적 스냅샷 생성
    os.makedirs("yearly_snapshots", exist_ok=True)
    for target_year in (2023, 2024):
        yr_features = []
        for f in new_features:
            y = f["properties"].get("year")
            if not y:
                continue
            try:
                y_int = int(y)
            except ValueError:
                continue
            if y_int <= target_year:
                yr_features.append(f)
        out_path = f"yearly_snapshots/gyeonggi_ev_chargers_{target_year}.geojson"
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump({"type": "FeatureCollection", "features": yr_features}, fp, ensure_ascii=False, indent=2)
        print(f"{target_year}년 누적: {len(yr_features)}건 -> {out_path}")


if __name__ == "__main__":
    main()
