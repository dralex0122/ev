"""
duplicate_candidates_verified.csv를 운영기관(busiNm)/사업자명(bnm)/설치연도(year)로 재검증.

- 서울+6대 광역시 city-wide 재수집 (page-skip-not-abort)
- 이번엔 statId별로 busiId, bnm, busiNm, year, maker를 집합으로 보존
  (한 충전소 안 여러 충전기 값이 다를 수 있어 set으로 저장)
- 그룹 내 모든 station_id의 (bnm, busiNm, year) 조합이 전부 일치하는지 확인
  - 전부 일치 -> operator_year_match = "동일" (중복 가능성 강화)
  - 하나라도 다름 -> "다름" (별개 설비/등록일 가능성)
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
INPUT_CSV = "duplicate_candidates_verified.csv"
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


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    station_info = defaultdict(lambda: {"bnm": set(), "busiNm": set(), "busiId": set(), "year": set(), "maker": set()})

    for city_name, zcode in CITIES:
        print(f"--- {city_name}(zcode={zcode}) 수집 중 ---")
        items = fetch_city_items(zcode, service_key)
        for item in items:
            sid = item.get("statId")
            if not sid:
                continue
            info = station_info[sid]
            info["bnm"].add(item.get("bnm") or "")
            info["busiNm"].add(item.get("busiNm") or "")
            info["busiId"].add(item.get("busiId") or "")
            info["year"].add(item.get("year") or "")
            info["maker"].add(item.get("maker") or "")
        print(f"  {city_name}: {len(items)}개 항목 수집 완료 (누적 API 요청 {REQUEST_COUNT}건)")

    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        original_fieldnames = list(reader.fieldnames)
        rows = list(reader)

    for row in rows:
        ids = row["station_ids"].split(";")
        bnm_sets = [tuple(sorted(station_info[sid]["bnm"])) for sid in ids]
        busiNm_sets = [tuple(sorted(station_info[sid]["busiNm"])) for sid in ids]
        year_sets = [tuple(sorted(station_info[sid]["year"])) for sid in ids]
        maker_sets = [tuple(sorted(station_info[sid]["maker"])) for sid in ids]

        all_match = (
            len(set(bnm_sets)) == 1
            and len(set(busiNm_sets)) == 1
            and len(set(year_sets)) == 1
        )
        row["operator_year_match"] = "동일" if all_match else "다름"
        row["operator_detail"] = " | ".join(
            f"{sid}:bnm={sorted(station_info[sid]['bnm'])},busiNm={sorted(station_info[sid]['busiNm'])},"
            f"year={sorted(station_info[sid]['year'])},maker={sorted(station_info[sid]['maker'])}"
            for sid in ids
        )

    fieldnames = original_fieldnames + ["operator_year_match", "operator_detail"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    strong = [r for r in rows if r["confidence"] == "다른 사업자(강한 의심)"]
    strong_op_match = sum(1 for r in strong if r["operator_year_match"] == "동일")
    print(f"\n=== 완료: API 요청 {REQUEST_COUNT}건 ===")
    print(f"강한 의심(다른 사업자) 총 {len(strong)}그룹")
    print(f"  - 운영기관/사업자명/설치연도까지 일치: {strong_op_match}그룹")
    print(f"  - 그중 하나라도 다름: {len(strong) - strong_op_match}그룹")
    print(f"결과 -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
