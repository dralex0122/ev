"""
duplicate_candidates.csv의 "강한 의심(다른 사업자)" 그룹을 원본 API 재수집으로 검증.

- 서울+6대 광역시를 city-wide로 재수집(zscode 없이 zcode만, page-skip-not-abort)
- 이번엔 완속/고속 이분법이 아니라 각 충전기의 실제 output(kW) 값을 statId별로 보존
- duplicate_candidates.csv의 각 그룹에 대해, 그룹에 속한 station_id들의 개별 kW 값
  목록(정렬된 멀티셋)이 서로 정확히 일치하는지 확인
  - 일치 -> 진짜 중복일 가능성 유지 (capacity_match = True)
  - 불일치 -> 실제로는 다른 설비일 가능성 (capacity_match = False)
- API 서비스키는 EV_SERVICE_KEY 환경변수에서 읽음
"""

import csv
import json
import os
import sys
import time
from collections import defaultdict

BASE_URL = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
NUM_OF_ROWS = 500
INPUT_CSV = "duplicate_candidates.csv"
OUTPUT_CSV = "duplicate_candidates_verified.csv"

CITIES = [
    ("서울특별시", "11"), ("부산광역시", "26"), ("대구광역시", "27"),
    ("인천광역시", "28"), ("광주광역시", "29"), ("대전광역시", "30"),
    ("울산광역시", "31"),
]

REQUEST_COUNT = 0


def fetch_city_items(zcode, service_key):
    import requests

    global REQUEST_COUNT
    page_no = 1
    all_items = []

    while True:
        full_url = (
            f"{BASE_URL}?serviceKey={service_key}&pageNo={page_no}"
            f"&numOfRows={NUM_OF_ROWS}&zcode={zcode}&dataType=JSON"
        )
        page_success = False
        items = []
        total_count = 0

        for attempt in range(1, 4):
            try:
                REQUEST_COUNT += 1
                response = requests.get(full_url, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    items_dict = data.get("items", {})
                    if not items_dict or "item" not in items_dict:
                        page_success = True
                        break
                    items = items_dict["item"]
                    if not items:
                        page_success = True
                        break
                    all_items.extend(items)
                    total_count = int(data.get("totalCount", 0))
                    page_success = True
                    break
                else:
                    time.sleep(3)
            except Exception:
                time.sleep(5)

        if not page_success:
            print(f"  경고: zcode={zcode} {page_no}페이지 실패, 건너뜀", file=sys.stderr)
        elif not items or len(all_items) >= total_count:
            break

        page_no += 1
        time.sleep(0.3)

    return all_items


def kw_of(item):
    output_val = item.get("output")
    try:
        return round(float(output_val), 1) if output_val else 0.0
    except ValueError:
        return 7.0


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    station_kws = defaultdict(list)

    for city_name, zcode in CITIES:
        print(f"--- {city_name}(zcode={zcode}) 수집 중 ---")
        items = fetch_city_items(zcode, service_key)
        for item in items:
            sid = item.get("statId")
            if not sid:
                continue
            station_kws[sid].append(kw_of(item))
        print(f"  {city_name}: {len(items)}개 항목 수집 완료 (누적 API 요청 {REQUEST_COUNT}건)")

    for sid in station_kws:
        station_kws[sid].sort()

    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        original_fieldnames = list(reader.fieldnames)
        rows = list(reader)

    verified_rows = []
    for row in rows:
        ids = row["station_ids"].split(";")
        kw_lists = [station_kws.get(sid, []) for sid in ids]
        kw_sets_as_tuples = set(tuple(k) for k in kw_lists)
        capacity_match = len(kw_sets_as_tuples) == 1
        row["capacity_match"] = "동일" if capacity_match else "다름"
        row["kw_detail"] = " | ".join(f"{sid}:{kws}" for sid, kws in zip(ids, kw_lists))
        verified_rows.append(row)

    fieldnames = original_fieldnames + ["capacity_match", "kw_detail"]

    def sort_key(r):
        strong = r["confidence"] == "다른 사업자(강한 의심)"
        cap_diff = r["capacity_match"] == "다름"
        return (not (strong and not cap_diff), not strong, -int(r["n_ids"]))

    verified_rows.sort(key=sort_key)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(verified_rows)

    strong_total = sum(1 for r in verified_rows if r["confidence"] == "다른 사업자(강한 의심)")
    strong_and_capmatch = sum(
        1 for r in verified_rows
        if r["confidence"] == "다른 사업자(강한 의심)" and r["capacity_match"] == "동일"
    )
    strong_but_capdiff = strong_total - strong_and_capmatch

    print(f"\n=== 완료: API 요청 {REQUEST_COUNT}건 ===")
    print(f"강한 의심(다른 사업자) 총 {strong_total}그룹")
    print(f"  - 용량까지 일치 (진짜 중복 가능성 높음): {strong_and_capmatch}그룹")
    print(f"  - 용량 다름 (실제로는 다른 설비일 가능성): {strong_but_capdiff}그룹")
    print(f"결과 -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
