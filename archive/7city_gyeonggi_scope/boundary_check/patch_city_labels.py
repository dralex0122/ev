"""
boundary_check_<도시>.csv 결과를 바탕으로 metro7_ev_chargers_new.geojson /
metropolitan_ev_stations.geojson의 도시 라벨을 실제 행정구역으로 일괄 수정.

- 좌표는 건드리지 않음 (역지오코딩으로 이미 정확함이 확인된 좌표)
- "전남광주통합특별시"는 2026-07-01 행정구역 개편으로 광주광역시가 흡수된 새 이름.
  VWorld가 아직 옛 이름("광주광역시")으로 응답할 수 있어, 이 둘은 실제 불일치가
  아니라 명칭 표기 차이일 뿐이므로 동일 지역으로 간주하고 건너뜀
- 진짜 불일치만 patch:
    metro7: city_orig(원본 보존)/city(실제 지역으로 교체)/region_mismatch=true/real_region_detail
    stations: region_mismatch=true/real_region_text (city 필드가 없으므로 원본 address는 유지)
"""
import csv
import glob
import json

METRO7_PATH = "metro7_ev_chargers_new.geojson"
STATIONS_PATH = "metropolitan_ev_stations.geojson"

CITY_EQUIVALENTS = {
    "서울특별시": {"서울특별시"},
    "부산광역시": {"부산광역시"},
    "대구광역시": {"대구광역시"},
    "인천광역시": {"인천광역시"},
    "전남광주통합특별시": {"전남광주통합특별시", "광주광역시"},
    "대전광역시": {"대전광역시"},
    "울산광역시": {"울산광역시"},
}


def load_mismatches():
    mismatches = {}
    for path in sorted(glob.glob("boundary_check_*.csv")):
        orig_city = path[len("boundary_check_"):-len(".csv")]
        equiv = CITY_EQUIVALENTS.get(orig_city, {orig_city})
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        real_count = 0
        for row in rows:
            if row["reverse_level1"] in equiv:
                continue
            row["orig_city"] = orig_city
            mismatches[row["station_id"]] = row
            real_count += 1
        print(f"  {path}: {len(rows)}건 중 실제 불일치 {real_count}건 (명칭 표기차 {len(rows) - real_count}건 제외)")
    return mismatches


def patch_metro7(mismatches):
    d = json.load(open(METRO7_PATH, encoding="utf-8"))
    patched = 0
    for f in d["features"]:
        p = f["properties"]
        row = mismatches.get(p.get("station_id"))
        if not row:
            continue
        p.setdefault("city_orig", p.get("city"))
        p["city"] = row["reverse_level1"]
        p["region_mismatch"] = True
        p["real_region_detail"] = row["reverse_text"]
        patched += 1
    with open(METRO7_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"{METRO7_PATH}: {patched}건 patch")


def patch_stations(mismatches):
    d = json.load(open(STATIONS_PATH, encoding="utf-8"))
    patched = 0
    for f in d["features"]:
        p = f["properties"]
        row = mismatches.get(p.get("station_id"))
        if not row:
            continue
        p["region_mismatch"] = True
        p["real_region_text"] = row["reverse_text"]
        patched += 1
    with open(STATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"{STATIONS_PATH}: {patched}건 patch")


def main():
    print("=== boundary_check_*.csv 취합 ===")
    mismatches = load_mismatches()
    print(f"=== 실제 불일치 총 {len(mismatches)}건 (명칭 표기차 제외) ===")
    patch_metro7(mismatches)
    patch_stations(mismatches)


if __name__ == "__main__":
    main()
