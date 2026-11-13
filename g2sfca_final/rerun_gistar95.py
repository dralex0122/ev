"""
2026-11-13: 핫스팟을 Gi*(star=True)·양측 95%(|z|≥1.96)로 다시 계산 — 기존 Gi·90% 결과는 그대로 두고
output/recheck_2026-10-13/gistar95/ 와 new_output/*_gistar95*.png 에 따로 저장.

배경: 기존 코드는 esda G_Local 기본값(star=False)과 단측 p_norm<0.05를 써서 실제로는 Gi·양측 90%였음
(11/6 재점검). 2SFCA 점수·불평등 지표는 Gi와 무관하므로 그대로 사용.

다시 계산하는 것:
  1. 연도별 Gi* 분류(gi_k20_gistar95.csv, 기존 gi_k20_3ver.csv와 같은 형식) + 연도·구별 개수 + FDR 참고치
  2. 원인 분해(Shapley) — local_change_decomposition / local_change_shapley_table
  3. 도심 Cold 분해 — analyze_downtown_cold
  4. 2023 이상 월 제외 민감도 — 기존 재계산 점수(_excl_m09_11_12) 재사용, Gi* 요약만 다시
  5. KNN k 민감도(k=8·15·20·30) — 최종(nonpublic) 점수 기준
  6. 그림: 2×2 지도, 21→24 전이 지도(색 재지정판), 1×4 해석 지도
"""
import os
import sys

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal
import esda
from scipy.stats import norm

import recheck_uselimitation_week_day as R

Z_CRIT = norm.ppf(0.975)  # 양측 95%
GS_DIR = f"{R.OUT_DIR}/gistar95"
NEW = f"{R.NAS}/new_output"
os.makedirs(GS_DIR, exist_ok=True)


def gi_classes_star95(gdf, w, scores):
    y = scores.reindex(gdf["TOT_REG_CD"]).fillna(0).values
    z = esda.getisord.G_Local(y, w, transform="B", star=True, permutations=0).Zs
    return np.where(z <= -Z_CRIT, "Cold Spot", np.where(z >= Z_CRIT, "Hot Spot", "Not Sig"))


# 이후 import되는 모든 스크립트가 Gi* 95% 분류를 쓰도록 교체
R.gi_classes = gi_classes_star95

from recompute_exclude_nonpublic import NONPUBLIC_DIR  # noqa: E402

pr = lambda *a: print(*a, flush=True)


def boundary():
    gdf = gpd.read_file(R.BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    return gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)


def score(y):
    return pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{y}_week_낮_normal.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score


def step1_classes(gdf, w):
    gu = gdf["TOT_REG_CD"].str[:5].map(R.GU_MAP)
    rows, cnt, gu_rows = [], [], []
    for y in R.YEARS:
        s = score(y)
        c = gi_classes_star95(gdf, w, s)
        rows.append(pd.DataFrame({"year": y, "oa_code": gdf["TOT_REG_CD"], "gu": gu, "nonpublic": c}))
        lg = esda.getisord.G_Local(s.reindex(gdf["TOT_REG_CD"]).fillna(0).values, w, transform="B", star=True, permutations=0)
        p2 = 2 * norm.sf(np.abs(lg.Zs))
        o = np.sort(p2); m = len(o)
        thr = o[o <= 0.05 * np.arange(1, m + 1) / m].max() if (o <= 0.05 * np.arange(1, m + 1) / m).any() else 0
        sig = p2 <= thr
        cnt.append({"year": y, "hot": int((c == "Hot Spot").sum()), "cold": int((c == "Cold Spot").sum()),
                    "notsig": int((c == "Not Sig").sum()),
                    "hot_fdr": int((sig & (lg.Zs > 0)).sum()), "cold_fdr": int((sig & (lg.Zs < 0)).sum())})
        t = pd.DataFrame({"gu": gu, "c": c}).groupby("gu").c.value_counts().unstack(fill_value=0)
        for g, r in t.iterrows():
            gu_rows.append({"year": y, "gu": g, "hot": int(r.get("Hot Spot", 0)), "cold": int(r.get("Cold Spot", 0))})
    gi = pd.concat(rows)
    gi.to_csv(f"{GS_DIR}/gi_k20_gistar95.csv", index=False, encoding="utf-8-sig")
    cnt = pd.DataFrame(cnt); cnt.to_csv(f"{GS_DIR}/gi_counts_by_year.csv", index=False, encoding="utf-8-sig")
    gu_df = pd.DataFrame(gu_rows); gu_df.to_csv(f"{GS_DIR}/gi_counts_by_gu.csv", index=False, encoding="utf-8-sig")
    pr("=== 1. 연도별 Gi* 95% (FDR 참고) ===\n", cnt.to_string(index=False))
    a = gi[gi.year == 2021].nonpublic.values == "Hot Spot"; b = gi[gi.year == 2024].nonpublic.values == "Hot Spot"
    tr = pd.Series({"Hot 유지": (a & b).sum(), "Hot 이탈": (a & ~b).sum(), "신규 Hot": (~a & b).sum(), "그 외": (~a & ~b).sum()})
    pr("21→24 전이:", tr.to_dict())
    dt = gu.isin(["종로구", "중구"]).values
    pr("종로·중구 Hot:", [int((gi[gi.year == y].nonpublic.values[dt] == "Hot Spot").sum()) for y in R.YEARS],
       "| Cold:", [int((gi[gi.year == y].nonpublic.values[dt] == "Cold Spot").sum()) for y in R.YEARS])
    piv = gu_df.pivot(index="gu", columns="year", values="hot")
    piv["Δ21-24"] = piv[2024] - piv[2021]
    pr("구별 Hot 증감:\n", piv.sort_values("Δ21-24").to_string())
    return gi


def step2_shapley():
    import local_change_decomposition as L
    L.OUT_FP, L.GROUP_FP, L.SUPPLY_FP = (f"{GS_DIR}/local_change_counterfactual.csv",
                                         f"{GS_DIR}/local_change_score_groups.csv", f"{GS_DIR}/local_change_new_supply_gu.csv")
    pr("\n=== 2. 원인 분해 ===")
    L.main()
    import local_change_shapley_table as S
    S.OUT_FP, S.GROUP_FP = L.OUT_FP, L.GROUP_FP
    S.LONG_FP, S.PAPER_FP = f"{GS_DIR}/local_change_shapley_long.csv", f"{GS_DIR}/local_change_shapley_paper.csv"
    S.main()


def step3_downtown_cold():
    import analyze_downtown_cold as A
    A.OUT_FP, A.CF_FP = f"{GS_DIR}/downtown_cold_decomposition.csv", f"{GS_DIR}/downtown_cold_counterfactual.csv"
    pr("\n=== 3. 도심 Cold 분해 ===")
    A.main()


def step4_2023(gdf, w):
    from inequality_gini_palma import weighted_gini, weighted_share
    from g2sfca_final_supply import D1_FP
    gu = gdf["TOT_REG_CD"].str[:5].map(R.GU_MAP)
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    ex = pd.read_csv(f"{R.OUT_DIR}/g2sfca_score_2023_week_낮_normal_excl_m09_11_12.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score
    vers = {str(y): (y, score(y)) for y in R.YEARS}
    vers["2023_이상월제외"] = (2023, ex)
    rows, cls = [], {}
    for name, (y, s) in vers.items():
        dw = d1[d1.year == y].set_index("집계구코드")["낮_avg"].astype(float).reindex(s.index).fillna(0).values
        c = gi_classes_star95(gdf, w, s); cls[name] = c
        hot = pd.Series(c == "Hot Spot").groupby(gu.values).sum()
        rows.append({"version": name, "gini": round(weighted_gini(s.values, dw), 4),
                     "palma": round(weighted_share(s.values, dw, 0.9, 1.0) / weighted_share(s.values, dw, 0.0, 0.4), 3),
                     "hot": int((c == "Hot Spot").sum()), "cold": int((c == "Cold Spot").sum()),
                     "hot_종로중구": int(hot.get("종로구", 0) + hot.get("중구", 0))})
    out = pd.DataFrame(rows); out.to_csv(f"{GS_DIR}/od2023_anomaly_month_sensitivity.csv", index=False, encoding="utf-8-sig")
    pr("\n=== 4. 2023 이상 월 제외 민감도 ===\n", out.to_string(index=False))
    pr(f"2023 원본 vs 이상월 제외 분류 변경 {(cls['2023'] != cls['2023_이상월제외']).mean():.1%}")


def step5_knn(gdf):
    pts = np.array([[p.x, p.y] for p in gdf.geometry.centroid])
    dt = gdf["TOT_REG_CD"].str[:5].map(R.GU_MAP).isin(["종로구", "중구"]).values
    base, rows = {}, []
    for k in (8, 15, 20, 30):
        wk = libpysal.weights.KNN.from_array(pts, k=k)
        for y in R.YEARS:
            c = gi_classes_star95(gdf, wk, score(y))
            if k == 20:
                base[y] = c
            rows.append({"k": k, "year": y, "c": c})
    out = []
    for r in rows:
        c, y = r["c"], r["year"]
        out.append({"k": r["k"], "year": y, "hot": int((c == "Hot Spot").sum()), "cold": int((c == "Cold Spot").sum()),
                    "agree_k20": round(float((c == base[y]).mean()), 4), "hot_종로중구": int((c[dt] == "Hot Spot").sum())})
    out = pd.DataFrame(out); out.to_csv(f"{GS_DIR}/knn_sensitivity.csv", index=False, encoding="utf-8-sig")
    pr("\n=== 5. KNN 민감도 ===\n", out.to_string(index=False))


def step6_figures():
    gi_fp = f"{GS_DIR}/gi_k20_gistar95.csv"
    import presentation_2sfca_weekday_grid_k20_2x2 as M
    M.GI_FP, M.OUT_FP = gi_fp, f"{NEW}/presentation_2sfca_weekday_grid_k20_2x2_gistar95.png"
    M.main()
    import downtown_hot_loss_supplement as D
    D.GI_FP = gi_fp
    D.SUPPLY_OUT, D.RATIO_OUT, D.TRANS_OUT = (f"{GS_DIR}/downtown_supply_per_daypop_gu.csv",
                                              f"{GS_DIR}/downtown_score_ratio_gu_year.csv", f"{GS_DIR}/downtown_hot_transition_gu.csv")
    D.MAP_OUT = f"{NEW}/presentation_hot_transition_2021_2024_k20_gistar95.png"
    D.TRANS_COLOR = {"그 외": "#ecebe6", "Hot 이탈": "#9ecae1", "신규 Hot": "#fb8c3c", "Hot 유지": "#b2182b"}
    D.main()
    import presentation_hotspot_interpretation as H
    H.GI_FP = gi_fp
    H.OUT_DIR = f"{GS_DIR}/interpretation"
    os.makedirs(H.OUT_DIR, exist_ok=True)
    H.MAP_FP = f"{NEW}/presentation_2sfca_weekday_grid_k20_gistar95.png"
    H.GU_FIG_FP = f"{NEW}/presentation_gu_relative_position_k20_gistar95.png"
    H.main()


if __name__ == "__main__":
    gdf = boundary()
    w = libpysal.weights.KNN.from_array(np.array([[p.x, p.y] for p in gdf.geometry.centroid]), k=R.K)
    steps = sys.argv[1:] or ["1", "2", "3", "4", "5", "6"]
    if "1" in steps: step1_classes(gdf, w)
    if "2" in steps: step2_shapley()
    if "3" in steps: step3_downtown_cold()
    if "4" in steps: step4_2023(gdf, w)
    if "5" in steps: step5_knn(gdf)
    if "6" in steps: step6_figures()
    pr("\n완료")
