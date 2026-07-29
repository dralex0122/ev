"""
View-T "네트워크 다운로드"(moveNetworkDownload.do) 페이지의 공식 상세도로망
(Level6, CATEGORY_2_CODE=C02) shapefile 패키지를 2019~2024년 전체 지역
자동 다운로드.

- 로그인 불필요 (확인됨)
- 연도 코드: A03=2019 ~ A08=2024
- CATEGORY_1_CODE=B01(네트워크), CATEGORY_2_CODE=C02(상세도로망Level6)
- 목록: DownLoadNetworkData_list.do -> 다운로드: file/network_download.do
  (DATA_ID + FILE_NAME + NAME_PHYSICAL_CODE 필요)
- 저장: viewt_detailed_network/<year>/<region>_lev6_<year>.zip
"""
import os
import sys
import time

import requests

BASE = "https://viewt.ktdb.go.kr/cong"
LIST_URL = f"{BASE}/map/DownLoadNetworkData_list.do"
DOWNLOAD_URL = f"{BASE}/file/network_download.do"
HEADERS = {"User-Agent": "Mozilla/5.0"}

YEAR_CODES = {
    2019: "A03", 2020: "A04", 2021: "A05",
    2022: "A06", 2023: "A07", 2024: "A08",
}

OUT_DIR = "viewt_detailed_network"


def fetch_file_list(year_code):
    data = {
        "DATABASE": "DOWNLOAD_NETWORK_DATA",
        "YEAR_CODE": year_code,
        "CATEGORY_1_CODE": "B01",
        "CATEGORY_2_CODE": "C02",
        "DELETE_CODE": "0",
        "SEARCH_CODE": f"{year_code}B01C02",
        "PAGING_NOW_NUM": "1",
        "PAGING_ONEPAGE_NUM": "50",
        "SORTCOLUMN": "YEAR",
        "SORTKIND": "desc",
        "DTYPE": "NETWORK",
    }
    for attempt in range(3):
        try:
            r = requests.post(LIST_URL, data=data, headers=HEADERS, timeout=60)
            if r.status_code == 200:
                return r.json().get("item", [])
        except Exception as e:
            print(f"  목록 조회 실패({e}), 재시도", file=sys.stderr)
        time.sleep(5)
    return None


def download_file(data_id, filename, filecode, out_path):
    data = {
        "file_downLoad_Number": str(data_id),
        "file_downLoad_filename": filename,
        "file_downLoad_filecode": filecode,
    }
    for attempt in range(3):
        try:
            r = requests.post(DOWNLOAD_URL, data=data, headers=HEADERS, timeout=300)
            if r.status_code == 200 and len(r.content) > 0:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return len(r.content)
        except Exception as e:
            print(f"  다운로드 실패({e}), 재시도", file=sys.stderr)
        time.sleep(5)
    return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_files = []
    for year, year_code in YEAR_CODES.items():
        items = fetch_file_list(year_code)
        if items is None:
            print(f"{year}년 목록 조회 실패", file=sys.stderr)
            continue
        print(f"{year}년: {len(items)}개 파일 확인")
        for it in items:
            all_files.append((year, it))

    total = len(all_files)
    n = 0
    failures = []
    for year, it in all_files:
        n += 1
        year_dir = os.path.join(OUT_DIR, str(year))
        os.makedirs(year_dir, exist_ok=True)
        fname = it["FILE_NAME"]
        out_path = os.path.join(year_dir, fname)
        if os.path.exists(out_path):
            print(f"[{n}/{total}] {year}/{fname} 이미 있음, 건너뜀")
            continue
        print(f"[{n}/{total}] {year}/{fname} 다운로드 중...")
        sys.stdout.flush()
        size = download_file(it["DATA_ID"], fname, it["NAME_PHYSICAL_CODE"], out_path)
        if size is None:
            print(f"  실패: {year}/{fname}")
            failures.append(f"{year}/{fname}")
        else:
            print(f"  저장 완료: {size}바이트 -> {out_path}")
        sys.stdout.flush()
        time.sleep(1)

    print(f"=== 전체 완료: {total - len(failures)}/{total}건 성공 ===")
    if failures:
        print(f"실패 목록: {failures}")


if __name__ == "__main__":
    main()
