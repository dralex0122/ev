"""
2026-10-14 민감도 분석: 산지(산림 비율 높은) 집계구를 분석 대상에서 빼고 week_낮_normal 재계산.

공급은 최종(nonpublic) 버전 그대로. 산지 집계구는 수요·OD에서 빼고(2SFCA 경쟁 수요에서 제외),
Gi*는 남은 집계구만으로 KNN(k=20)을 다시 구성.
산림 비율: OSM landuse=forest·natural=wood 면적 / 집계구 면적 (output/recheck_2026-10-13/oa_forest_share.csv)
기준: 50%(주), 30%·70%(민감도)

비교 대상: 최종(nonpublic) 결과의 같은 집계구(남은 집계구) 분류.
"""
import os

import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal

from g2sfca_final_supply import D1_FP, GAUSSIAN_OD_DIR
from recheck_uselimitation_week_day import (
    g2sfca, gi_classes, load_stations, BOUNDARY_FP, OUT_DIR, YEARS, DAYTYPE, PERIOD, SCENARIO, K, GU_MAP,
)
from recompute_exclude_nonpublic import NONPUBLIC_DIR, CAND_FP
from g2sfca_final_supply import APT_FP

FOREST_SHARE_FP = f"{OUT_DIR}/oa_forest_share.csv"
GI_FP = f"{OUT_DIR}/gi_k20_3ver.csv"
THRESHOLDS = [0.3, 0.5, 0.7]
FOREST_DIR = lambda t: f"{os.path.dirname(NONPUBLIC_DIR)}/g2sfca_sfast_final_gaussian_noforest{int(t * 100)}"


def main():
    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)
    fs = pd.read_csv(FOREST_SHARE_FP, dtype={"TOT_REG_CD": str}).set_index("TOT_REG_CD").forest_share
    gdf["forest_share"] = gdf["TOT_REG_CD"].map(fs).fillna(0)
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)

    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl = set(cand[cand.final_label == "제외"].station_id)
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    gi_all = pd.read_csv(GI_FP, dtype={"oa_code": str})

    sum_rows, gu_rows, cls_rows = [], [], []
    for t in THRESHOLDS:
        os.makedirs(FOREST_DIR(t), exist_ok=True)
        keep = gdf[gdf.forest_share < t].reset_index(drop=True)
        keep_set = set(keep["TOT_REG_CD"])
        w = libpysal.weights.KNN.from_array(np.array([[p.x, p.y] for p in keep.geometry.centroid]), k=K)
        for year in YEARS:
            tag = f"{year}_{DAYTYPE}_{PERIOD}_{SCENARIO}"
            st = load_stations(year)
            kept_st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
            od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{tag}.csv", dtype={"station_id": str, "oa_code": str})
            od = od[od.oa_code.isin(keep_set)]
            d = d1[d1.year == year]
            demand = {k: v for k, v in zip(d["집계구코드"], d["낮_avg"].astype(float)) if k in keep_set}

            score = g2sfca(dict(zip(kept_st.station_id, kept_st.fast_count)), demand, od)
            pd.DataFrame({"oa_code": score.index, "accessibility_score": score.values}).to_csv(
                f"{FOREST_DIR(t)}/g2sfca_score_{tag}.csv", index=False, encoding="utf-8-sig")
            base = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{tag}.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score

            cls = gi_classes(keep, w, score)
            ref = gi_all[gi_all.year == year].set_index("oa_code").nonpublic.reindex(keep["TOT_REG_CD"]).values
            sum_rows.append({
                "threshold": t, "year": year, "n_oa": len(keep), "n_removed": len(gdf) - len(keep),
                "hot": int((cls == "Hot Spot").sum()), "cold": int((cls == "Cold Spot").sum()),
                "hot_ref_kept": int((ref == "Hot Spot").sum()), "cold_ref_kept": int((ref == "Cold Spot").sum()),
                "changed_pct": round(float((cls != ref).mean() * 100), 2),
                "score_ratio_median": round(float((score / base.reindex(score.index)).median()), 4),
            })
            t_df = pd.DataFrame({"gu": keep["gu"], "new": cls, "ref": ref})
            for g, sub in t_df.groupby("gu"):
                gu_rows.append({"threshold": t, "year": year, "gu": g,
                                "hot": int((sub.new == "Hot Spot").sum()), "cold": int((sub.new == "Cold Spot").sum()),
                                "hot_ref": int((sub.ref == "Hot Spot").sum()), "cold_ref": int((sub.ref == "Cold Spot").sum())})
            cls_rows.append(pd.DataFrame({"threshold": t, "year": year, "oa_code": keep["TOT_REG_CD"], "gu": keep["gu"],
                                          "nonpublic": ref, "noforest": cls}))
            print(f"[산림 {int(t * 100)}% / {year}] 분류 변경 {sum_rows[-1]['changed_pct']}%", flush=True)

    summary = pd.DataFrame(sum_rows)
    gu_df = pd.DataFrame(gu_rows)
    summary.to_csv(f"{OUT_DIR}/forest_exclusion_summary.csv", index=False, encoding="utf-8-sig")
    gu_df.to_csv(f"{OUT_DIR}/forest_exclusion_gu.csv", index=False, encoding="utf-8-sig")
    pd.concat(cls_rows).to_csv(f"{OUT_DIR}/gi_k20_noforest.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print(f"\n=== 전체 ===\n{summary.to_string(index=False)}")
    for t in THRESHOLDS:
        p = gu_df[gu_df.threshold == t].pivot_table(index="gu", columns="year", values=["hot", "cold", "hot_ref", "cold_ref"])
        r = pd.DataFrame({
            "hotΔ21-24_ref": p[("hot_ref", 2024)] - p[("hot_ref", 2021)],
            "hotΔ21-24_new": p[("hot", 2024)] - p[("hot", 2021)],
            "hot24_ref": p[("hot_ref", 2024)], "hot24_new": p[("hot", 2024)],
            "cold24_ref": p[("cold_ref", 2024)], "cold24_new": p[("cold", 2024)],
        }).astype(int)
        print(f"\n=== 산림 {int(t * 100)}% 기준: 구별 (남은 집계구만, ref=최종) ===\n{r.sort_values('hotΔ21-24_new').to_string()}")


if __name__ == "__main__":
    main()
