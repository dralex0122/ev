"""
원본 View-T percentile speed CSV(코드값 그대로)를 실제 사이트 다운로드 형식
(한글 헤더 + 코드->이름 변환)으로 변환.

- sido_id/sigungu_id/emd_id: fasterIndicatorZoneNm.do에서 받은 코드->이름
  매핑으로 변환 (해당 연도 매핑 사용)
- week_code: 0/1 -> 평일/주말
- road_rank: 101~108 -> 고속도로 등 한글 명칭
- v_link_id/date/peak_time/속도값들은 그대로 유지
"""
import csv
import glob
import json
import os
import sys

import requests

ZONE_URL = "https://viewt.ktdb.go.kr/cong/map/fasterIndicatorZoneNm.do"
HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

IN_DIR = "viewt_percentile_speed_nationwide"
OUT_DIR = "viewt_percentile_speed_nationwide_labeled"

RRANK_NAMES = {
    "101": "고속도로", "102": "도시고속도로", "103": "일반국도", "104": "특별광역시도",
    "105": "국가지원지방도", "106": "지방도", "107": "시군도", "108": "고속도로_연결로",
}
WEEK_NAMES = {"0": "평일", "1": "주말"}

OUT_FIELDS = [
    "level6 LINK ID", "연월", "평일 / 주말", "주요시간대", "도로등급",
    "시도명", "시군구명", "읍면동명",
    "15% 주행속도 (km/h)", "25% 주행속도 (km/h)", "30% 주행속도 (km/h)",
    "50% 주행속도 (km/h)", "75% 주행속도 (km/h)", "85% 주행속도 (km/h)",
    "평균속도 (km/h)", "속도 표준편차 (km/h)", "최대속도 (km/h)",
]


def fetch_zone_nm():
    r = requests.post(ZONE_URL, headers=HEADERS, data="null", timeout=60)
    return r.json()["zoneNm"]


def convert_file(in_path, out_path, zone_nm, year):
    zn = zone_nm[str(year)]
    with open(in_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    for row in rows:
        sido_raw = row["sido_id"]
        sigungu_raw = row["sigungu_id"]
        emd_raw = row["emd_id"]
        sido_code = sido_raw[:2]
        sigungu_suffix = sigungu_raw[2:5]
        emd_suffix = emd_raw[5:8]

        sido_nm = zn["sido"].get(sido_code, sido_raw)
        sigungu_nm = zn["sigungu"].get(sido_code, {}).get(sigungu_suffix, sigungu_raw)
        emd_nm = zn["emd"].get(emd_raw[:5], {}).get(emd_suffix, emd_raw)

        out_rows.append({
            "level6 LINK ID": row["v_link_id"],
            "연월": row["date"],
            "평일 / 주말": WEEK_NAMES.get(row["week_code"], row["week_code"]),
            "주요시간대": row["peak_time"],
            "도로등급": RRANK_NAMES.get(row["road_rank"], row["road_rank"]),
            "시도명": sido_nm,
            "시군구명": sigungu_nm,
            "읍면동명": emd_nm,
            "15% 주행속도 (km/h)": row["spped_15th"],
            "25% 주행속도 (km/h)": row["spped_25th"],
            "30% 주행속도 (km/h)": row["spped_30th"],
            "50% 주행속도 (km/h)": row["spped_50th"],
            "75% 주행속도 (km/h)": row["spped_75th"],
            "85% 주행속도 (km/h)": row["spped_85th"],
            "평균속도 (km/h)": row["speed_avg"],
            "속도 표준편차 (km/h)": row["speed_sd"],
            "최대속도 (km/h)": row["speed_max"],
        })

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    return len(out_rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=== zoneNm 데이터 조회 중 ===")
    zone_nm = fetch_zone_nm()

    in_files = sorted(glob.glob(os.path.join(IN_DIR, "*.csv")))
    print(f"=== 변환 대상 {len(in_files)}개 파일 ===")
    for i, in_path in enumerate(in_files, start=1):
        fname = os.path.basename(in_path)
        year = 2000 + int(fname[:2])
        out_path = os.path.join(OUT_DIR, fname)
        n = convert_file(in_path, out_path, zone_nm, year)
        print(f"[{i}/{len(in_files)}] {fname}: {n}건 변환 완료")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
