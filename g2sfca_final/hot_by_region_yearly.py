"""
2026-11-26: 구성표 4-1 "2023년 이후 서남권에서 Hot Spot이 늘어남" 문장 확인용.
최종 Gi*(star, 양측 95%, KNN k=20) 연도별(2021–2024) Hot/Cold 집계구 수를 생활권·자치구·도심(종로·중구)별로 집계.
새 분석 아님 — 기존 최종 점수(week_낮_normal)와 기존 Gi* 분류를 권역별로 세기만 함.

출력: NAS manuscript/tables_2026-11-26_region/
"""
import os

import numpy as np
import pandas as pd
import libpysal

import paper_figures_v5 as P
import rerun_gistar95 as G
from new_supply_location_analysis import REGION, GU2REGION

YEARS = [2021, 2022, 2023, 2024]
OUT = f"{P.NAS}/manuscript/tables_2026-11-26_region"
os.makedirs(OUT, exist_ok=True)


def main():
    gdf, pts = P.gdf, P.pts
    gu = gdf["TOT_REG_CD"].str[:5].map(G.R.GU_MAP).values
    region = pd.Series(gu).map(GU2REGION).values
    downtown = np.isin(gu, P.DOWNTOWN)
    w = libpysal.weights.KNN.from_array(pts, k=20)

    rows = []
    for y in YEARS:
        cls = G.gi_classes_star95(gdf, w, P.score(y))
        groups = [("서울 전체", np.ones(len(cls), bool)), ("도심(종로·중구)", downtown)]
        groups += [(r, region == r) for r in REGION]
        groups += [(g, gu == g) for g in sorted(set(gu))]
        for name, m in groups:
            n = int(m.sum())
            rows.append({"year": y, "group": name, "n_oa": n,
                         "hot": int((cls[m] == "Hot Spot").sum()), "cold": int((cls[m] == "Cold Spot").sum())})
        P.pr(f"{y} 완료")

    df = pd.DataFrame(rows)
    df["hot_pct"] = (df.hot / df.n_oa * 100).round(1)
    df["cold_pct"] = (df.cold / df.n_oa * 100).round(1)
    tot_hot = df[df.group == "서울 전체"].set_index("year").hot
    df["share_of_seoul_hot_pct"] = (df.hot / df.year.map(tot_hot) * 100).round(1)
    df.to_csv(f"{OUT}/Hot_Cold_연도별_권역_자치구.csv", index=False, encoding="utf-8-sig")

    reg = ["서울 전체", "도심(종로·중구)"] + list(REGION)
    for col in ["hot", "hot_pct", "share_of_seoul_hot_pct", "cold_pct"]:
        piv = df[df.group.isin(reg)].pivot(index="group", columns="year", values=col).reindex(reg)
        P.pr(f"\n=== {col} ===\n", piv.to_string())
    sw = df[df.group.isin(REGION["서남권"])].pivot(index="group", columns="year", values="hot")
    P.pr("\n=== 서남권 자치구 hot ===\n", sw.to_string())
    P.pr("저장:", OUT)


if __name__ == "__main__":
    main()
