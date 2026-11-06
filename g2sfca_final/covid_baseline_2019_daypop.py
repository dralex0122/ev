"""
2026-11-06: 코로나 이전(2019) 기준선과 2021~2024 평일 낮 인구 분포 비교.
질문: 2021년(코로나 시기) 낮 인구가 업무지구보다 주거지에 상대적으로 많았는가?
입력: oa_population_periods_2019.csv(support/building_register/aggregate_oa_population_periods_2019.py),
      d1_final_2021_2024.csv — 둘 다 12개월 전체 평일, 낮=11·12시, 심야=00~05시 평균.
출력: covid_baseline_2019_biz5.csv(업무 5구 비중·낮/심야 비), covid_baseline_2019_gu_ratio.csv(구별 낮/심야 비)
※ 접근성 재계산 없음 — 인구 분포만 비교.
"""
import os
import unicodedata
import pandas as pd

NAS = "/mnt/cowork/EV" if os.path.isdir("/mnt/cowork/EV") else "/Volumes/cowork/EV"
P = f"{NAS}/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)"
if not os.path.isdir(P):  # macOS SMB 마운트는 NFD 경로
    P = unicodedata.normalize("NFD", P)
OUT_DIR = f"{NAS}/output/recheck_2026-10-13"
GU = {"11010": "종로", "11020": "중구", "11030": "용산", "11040": "성동", "11050": "광진", "11060": "동대문",
      "11070": "중랑", "11080": "성북", "11090": "강북", "11100": "도봉", "11110": "노원", "11120": "은평",
      "11130": "서대문", "11140": "마포", "11150": "양천", "11160": "강서", "11170": "구로", "11180": "금천",
      "11190": "영등포", "11200": "동작", "11210": "관악", "11220": "서초", "11230": "강남", "11240": "송파", "11250": "강동"}
BIZ5 = ["종로", "중구", "강남", "서초", "영등포"]
COLS = ["집계구코드", "year", "낮_avg", "심야_avg"]


def main():
    d = pd.concat([pd.read_csv(f"{P}/oa_population_periods_2019.csv", dtype={"집계구코드": str})[COLS],
                   pd.read_csv(f"{P}/d1_final_2021_2024.csv", dtype={"집계구코드": str})[COLS]])
    d["gu"] = d["집계구코드"].str[:5].map(GU)
    rows = []
    for y, g in d.groupby("year"):
        b = g[g.gu.isin(BIZ5)]
        rows.append({"year": y, "seoul_day": round(g.낮_avg.sum()), "seoul_night": round(g.심야_avg.sum()),
                     "biz5_day": round(b.낮_avg.sum()),
                     "biz5_day_share_pct": round(b.낮_avg.sum() / g.낮_avg.sum() * 100, 2),
                     "biz5_night_share_pct": round(b.심야_avg.sum() / g.심야_avg.sum() * 100, 2),
                     "biz5_day_night_ratio": round(b.낮_avg.sum() / b.심야_avg.sum(), 3)})
    biz = pd.DataFrame(rows)
    s = d.groupby(["gu", "year"])[["낮_avg", "심야_avg"]].sum()
    r = (s.낮_avg / s.심야_avg).unstack().round(3)
    r["ratio_2021_vs_2019"] = (r[2021] / r[2019]).round(3)
    r["ratio_2024_vs_2019"] = (r[2024] / r[2019]).round(3)
    biz.to_csv(f"{OUT_DIR}/covid_baseline_2019_biz5.csv", index=False, encoding="utf-8-sig")
    r.to_csv(f"{OUT_DIR}/covid_baseline_2019_gu_ratio.csv", encoding="utf-8-sig")
    print(biz.to_string(index=False))
    print(r.sort_values(2019, ascending=False).to_string())


if __name__ == "__main__":
    main()
