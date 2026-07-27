"""
View-T(viewt.ktdb.go.kr) 혼잡지표 - Percentile Speed 데이터 자동 다운로드.

2023년 1~12월 x 서울/경기/인천 x 평일/주말 = 72개 조합, 매 조합마다
모든 주요시간대(07,08,11,12,17,18시) + 모든 도로등급(101~108) 포함해서
CSV로 저장. 로그인 불필요 (fasterIndicatorGetData.do POST 엔드포인트,
정적 페이지 JS 분석으로 파라미터 확인함 - 브라우저 자동화 불필요).

파일명: <YYMM>_<region>_<week|weekend>_percentileSpeed.csv
"""
import csv
import os
import sys
import time

import requests

BASE = "https://viewt.ktdb.go.kr/cong/map/fasterIndicatorGetData.do"
HEADERS = {"User-Agent": "Mozilla/5.0"}

REGIONS = {"seoul": "11", "gyeonggi": "31", "incheon": "23"}
WEEKS = {"week": "0", "weekend": "1"}
TIMES = ["07", "08", "11", "12", "17", "18"]
RRANKS = ["101", "102", "103", "104", "105", "106", "107", "108"]

OUT_DIR = "viewt_percentile_speed_2023"


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
            r = requests.post(BASE, data=data, headers=HEADERS, timeout=300)
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
    total = 12 * len(REGIONS) * len(WEEKS)
    n = 0
    failures = []

    for month in range(1, 13):
        yyyymm = f"2023{month:02d}"
        yymm = f"23{month:02d}"
        for region_name, sido_code in REGIONS.items():
            for week_name, week_code in WEEKS.items():
                n += 1
                fname = f"{yymm}_{region_name}_{week_name}_percentileSpeed.csv"
                path = os.path.join(OUT_DIR, fname)
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
