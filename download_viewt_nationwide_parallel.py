"""
download_viewt_nationwide.py의 병렬 버전. 이미 받은 파일은 건너뛰고
나머지를 동시에 여러 개(기본 5개) 요청해서 다운로드 속도를 높임.
공공 서버라 너무 공격적으로 늘리지 않고 적당한 동시성(5)만 사용.
"""
import csv
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
MAX_WORKERS = 5

print_lock = threading.Lock()


def log(msg):
    with print_lock:
        print(msg)
        sys.stdout.flush()


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
            log(f"  HTTP {r.status_code}, 재시도")
        except Exception as e:
            log(f"  요청 실패({e}), 재시도")
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


def process_one(task):
    yyyymm, sido_code, week_code, fname, path = task
    items = fetch(yyyymm, sido_code, week_code)
    if items is None:
        log(f"  실패: {fname}")
        return fname, False
    cnt = save_csv(items, path)
    log(f"  저장 완료: {cnt}건 -> {path}")
    return fname, True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tasks = []
    skipped = 0
    for year in YEARS:
        for month in range(1, 13):
            yyyymm = f"{year}{month:02d}"
            yymm = f"{str(year)[2:]}{month:02d}"
            for region_name, sido_code in REGIONS.items():
                for week_name, week_code in WEEKS.items():
                    fname = f"{yymm}_{region_name}_{week_name}_percentileSpeed.csv"
                    path = os.path.join(OUT_DIR, fname)
                    if os.path.exists(path):
                        skipped += 1
                        continue
                    tasks.append((yyyymm, sido_code, week_code, fname, path))

    total_all = len(tasks) + skipped
    log(f"=== 이미 완료 {skipped}건 건너뜀, 남은 {len(tasks)}건을 동시성 {MAX_WORKERS}로 진행 ===")

    n = 0
    failures = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(process_one, t): t for t in tasks}
        for fut in as_completed(futures):
            n += 1
            fname, ok = fut.result()
            log(f"[{n}/{len(tasks)}] {fname} {'완료' if ok else '실패'}")
            if not ok:
                failures.append(fname)

    log(f"=== 전체 완료: {len(tasks) - len(failures)}/{len(tasks)}건 성공 (전체 {total_all}건 중 {skipped}건은 기존 완료분) ===")
    if failures:
        log(f"실패 목록: {failures}")


if __name__ == "__main__":
    main()
