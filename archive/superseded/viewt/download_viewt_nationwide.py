"""
View-T(viewt.ktdb.go.kr) 혼잡지표 - Percentile Speed 데이터 전국 자동 다운로드.

2021~2024년 x 전국 17개 시도 x 평일/주말 = 1,632개 조합, 매 조합마다
모든 주요시간대(07,08,11,12,17,18시) + 모든 도로등급(101~108) 포함해서
CSV로 저장 (원본 코드값 그대로 - 별도 스크립트로 한글 라벨 변환).

파일명: <YYMM>_<region>_<week|weekend>_percentileSpeed.csv
"""
import csv
import os
import sys
import time

import requests

BASE = "https://viewt.ktdb.go.kr/cong/map/fasterIndicatorGetData.do"
HEADERS = {"User-Agent": "Mozilla/5.0"}

REGIONS = {
    "seoul": "11", "busan": "21", "daegu": "22", "incheon": "23",
    "gwangju": "24", "daejeon": "25", "ulsan": "26", "sejong": "29",
    "gyeonggi": "31", "gangwon": "32", "chungbuk": "33", "chungnam": "34",
    "jeonbuk": "35", "jeonnam": "36", "gyeongbuk": "37", "gyeongnam": "38",
    "jeju": "39",
}
WEEKS = {"week": "0", "weekend": "1"}
TIMES = ["07", "08", "11", "12", "17", "18"]
RRANKS = ["101", "102", "103", "104", "105", "106", "107", "108"]
YEARS = [2021, 2022, 2023, 2024]

OUT_DIR = "viewt_percentile_speed_nationwide"


def fetch(yyyymm, sido_code, week_code):
    data = (
        [("fi_yyyymm", yyyymm), ("fi_week", week_code)]
        + [("fi_time", t) for t in TIMES]
        + [("fi_zone_nm", sido_code), ("fi_zone_nm", ""), ("fi_zone_nm", "")]
        + [("fi_rRank", r) for r in RRANKS]
        + [("report_condition_type", "PERCENTILE SPEED")]
    )
    for attempt in range(3):
        try:
            r = requests.post(BASE, data=data, headers=HEADERS, timeout=600)
            if r.status_code == 200:
                return r.json().get("item", [])
            print(f"  HTTP {r.status_code}, 재시도", file=sys.stderr)
        except Exception as e:
            print(f"  요청 실패({e}), 재시도", file=sys.stderr)
        time.sleep(5)
    return None


def save_csv(items, path):
    if not items:
        open(path, "w").close()
        return 0
    fieldnames = list(items[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(items)
    return len(items)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    total = len(YEARS) * 12 * len(REGIONS) * len(WEEKS)
    n = 0
    failures = []

    for year in YEARS:
        for month in range(1, 13):
            yyyymm = f"{year}{month:02d}"
            yymm = f"{str(year)[2:]}{month:02d}"
            for region_name, sido_code in REGIONS.items():
                for week_name, week_code in WEEKS.items():
                    n += 1
                    fname = f"{yymm}_{region_name}_{week_name}_percentileSpeed.csv"
                    path = os.path.join(OUT_DIR, fname)
                    if os.path.exists(path):
                        print(f"[{n}/{total}] {fname} 이미 있음, 건너뜀")
                        continue
                    print(f"[{n}/{total}] {fname} 요청 중...")
                    sys.stdout.flush()

                    items = fetch(yyyymm, sido_code, week_code)
                    if items is None:
                        print(f"  실패: {fname}")
                        failures.append(fname)
                        continue

                    cnt = save_csv(items, path)
                    print(f"  저장 완료: {cnt}건 -> {path}")
                    sys.stdout.flush()
                    time.sleep(1)

    print(f"=== 전체 완료: {total - len(failures)}/{total}건 성공 ===")
    if failures:
        print(f"실패 목록: {failures}")


if __name__ == "__main__":
    main()
