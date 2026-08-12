"""
View-T 도로망(네트워크) 데이터 전국 자동 다운로드 (GeoServer WFS 직접 호출).

지역+연도만 다르면 되고 월/평일주말은 결과에 영향 없음 (2026-07-27 확인됨).
17개 시도 x 2021~2024 = 68개 파일.

파일명: <year>_<region>_sido_id_<code>.gpkg (내용은 GeoJSON, 확장자만
사이트 다운로드 관례에 맞춰 .gpkg 사용)
"""
import json
import os
import sys
import time

import requests

WFS_URL = "https://viewt.ktdb.go.kr/geoserver/sqlite/wfs/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

REGIONS = {
    "seoul": "11", "busan": "21", "daegu": "22", "incheon": "23",
    "gwangju": "24", "daejeon": "25", "ulsan": "26", "sejong": "29",
    "gyeonggi": "31", "gangwon": "32", "chungbuk": "33", "chungnam": "34",
    "jeonbuk": "35", "jeonnam": "36", "gyeongbuk": "37", "gyeongnam": "38",
    "jeju": "39",
}
YEARS = [2021, 2022, 2023, 2024]

OUT_DIR = "viewt_network_nationwide"


def fetch(year, sido_code):
    zone_id = sido_code.ljust(5, "0")
    data = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "outputFormat": "application/json",
        "typeName": f"sqlite:link_6lv_{year}",
        "CQL_FILTER": f"sido_id={zone_id}",
    }
    for attempt in range(3):
        try:
            r = requests.post(WFS_URL, data=data, headers=HEADERS, timeout=600)
            if r.status_code == 200:
                return r.json()
            print(f"  HTTP {r.status_code}, 재시도", file=sys.stderr)
        except Exception as e:
            print(f"  요청 실패({e}), 재시도", file=sys.stderr)
        time.sleep(5)
    return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    total = len(YEARS) * len(REGIONS)
    n = 0
    failures = []

    for year in YEARS:
        for region_name, sido_code in REGIONS.items():
            n += 1
            zone_id = sido_code.ljust(5, "0")
            fname = f"{year}_{region_name}_sido_id_{zone_id}.gpkg"
            path = os.path.join(OUT_DIR, fname)
            if os.path.exists(path):
                print(f"[{n}/{total}] {fname} 이미 있음, 건너뜀")
                continue
            print(f"[{n}/{total}] {fname} 요청 중...")
            sys.stdout.flush()

            result = fetch(year, sido_code)
            if result is None:
                print(f"  실패: {fname}")
                failures.append(fname)
                continue

            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
            n_features = len(result.get("features", []))
            print(f"  저장 완료: {n_features}개 링크 -> {path}")
            sys.stdout.flush()
            time.sleep(1)

    print(f"=== 전체 완료: {total - len(failures)}/{total}건 성공 ===")
    if failures:
        print(f"실패 목록: {failures}")


if __name__ == "__main__":
    main()
