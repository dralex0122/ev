"""
2026-10-13: UseLimitation=Y 제외에 더해, 충전소명 키워드 후보 중 수기 판정으로 '제외'된
운수사·회사 전용 충전소(UseLimitation=N)까지 빼고 week_낮_normal 재계산.

1. nonpublic_keyword_candidates.csv의 final_label 기입(1차 판정 확정안)
   - rule_label=제외 → 제외. 단 한국공항공사 '고객전용주차장'은 일반 이용객용이라 유지
   - 검토필요 중 택시회사로 보이는 영광교통·일흥교통 → 제외
   - 그 외 검토필요(개방/24시간이용가능 표기 운수사, 사옥, 공공시설, 운수사 '앞' 가로등형) → 유지
   - rule_label=유지 → 유지
2. 세 버전 비교: before(기존) / nolimit(Y 제외) / nonpublic(Y + 키워드 제외)
"""
import os

import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal

from g2sfca_final_supply import APT_FP, D1_FP, GAUSSIAN_OD_DIR
from recheck_uselimitation_week_day import (
    load_stations, g2sfca, gi_classes, BOUNDARY_FP, BEFORE_DIR, AFTER_DIR, OUT_DIR,
    YEARS, DAYTYPE, PERIOD, SCENARIO, K, GU_MAP,
)

CAND_FP = f"{OUT_DIR}/nonpublic_keyword_candidates.csv"
NONPUBLIC_DIR = f"{os.path.dirname(BEFORE_DIR)}/g2sfca_sfast_final_gaussian_nonpublic"

KEEP_OVERRIDE = ["고객전용주차장"]
EXCLUDE_OVERRIDE = ["영광교통", "일흥교통"]


def finalize_labels():
    c = pd.read_csv(CAND_FP, dtype={"station_id": str})
    lab = np.where(c.rule_label == "제외", "제외", "유지")
    lab = np.where(c.name.str.contains("|".join(KEEP_OVERRIDE)), "유지", lab)
    lab = np.where(c.name.str.contains("|".join(EXCLUDE_OVERRIDE)), "제외", lab)
    c["final_label"] = lab
    c.to_csv(CAND_FP, index=False, encoding="utf-8-sig")
    return c


def main():
    os.makedirs(NONPUBLIC_DIR, exist_ok=True)
    c = finalize_labels()
    excl = set(c[c.final_label == "제외"].station_id)
    print(f">> 최종 제외 {len(excl)}곳 / 유지 {(c.final_label == '유지').sum()}곳")
    print(c[c.final_label == "제외"][["name", "gu", "fast_2024"]].to_string(index=False))

    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)
    w = libpysal.weights.KNN.from_array(np.array([[p.x, p.y] for p in gdf.geometry.centroid]), k=K)
    gu = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)

    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})

    sum_rows, gu_rows, cls_rows = [], [], []
    for year in YEARS:
        tag = f"{year}_{DAYTYPE}_{PERIOD}_{SCENARIO}"
        st = load_stations(year)
        od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{tag}.csv", dtype={"station_id": str, "oa_code": str})
        d = d1[d1.year == year]
        demand = dict(zip(d["집계구코드"], d["낮_avg"].astype(float)))

        eff = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y")]
        kept = eff[~eff.station_id.isin(excl)]
        score = g2sfca(dict(zip(kept.station_id, kept.fast_count)), demand, od)
        pd.DataFrame({"oa_code": score.index, "accessibility_score": score.values}).to_csv(
            f"{NONPUBLIC_DIR}/g2sfca_score_{tag}.csv", index=False, encoding="utf-8-sig")

        versions = {
            "before": pd.read_csv(f"{BEFORE_DIR}/g2sfca_score_{tag}.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score,
            "nolimit": pd.read_csv(f"{AFTER_DIR}/g2sfca_score_{tag}.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score,
            "nonpublic": score,
        }
        cls = {}
        for v, s in versions.items():
            cls[v] = gi_classes(gdf, w, s)
            sum_rows.append({"year": year, "version": v,
                             "chargers": {"before": None, "nolimit": int(eff.fast_count.sum()),
                                          "nonpublic": int(kept.fast_count.sum())}[v],
                             "hot": int((cls[v] == "Hot Spot").sum()), "cold": int((cls[v] == "Cold Spot").sum()),
                             "notsig": int((cls[v] == "Not Sig").sum()),
                             "mean_score_x1000": round(float(s.mean()) * 1000, 4)})
            t = pd.DataFrame({"gu": gu, "c": cls[v]}).groupby("gu").c.value_counts().unstack(fill_value=0)
            for g, r in t.iterrows():
                gu_rows.append({"year": year, "version": v, "gu": g,
                                "hot": int(r.get("Hot Spot", 0)), "cold": int(r.get("Cold Spot", 0))})
        cls_rows.append(pd.DataFrame({"year": year, "oa_code": gdf["TOT_REG_CD"], "gu": gu, **cls}))
        print(f"[{year}] 완료 — nolimit 대비 분류 변경 {(cls['nolimit'] != cls['nonpublic']).mean() * 100:.1f}%", flush=True)

    summary = pd.DataFrame(sum_rows)
    gu_df = pd.DataFrame(gu_rows)
    summary.to_csv(f"{OUT_DIR}/hotspot_compare_3ver.csv", index=False, encoding="utf-8-sig")
    gu_df.to_csv(f"{OUT_DIR}/hotspot_compare_gu_3ver.csv", index=False, encoding="utf-8-sig")
    pd.concat(cls_rows).to_csv(f"{OUT_DIR}/gi_k20_3ver.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print(f"\n=== 전체 ===\n{summary.to_string(index=False)}")
    p = gu_df.pivot_table(index="gu", columns=["version", "year"], values=["hot", "cold"])
    r = pd.DataFrame({f"hotΔ21-24_{v}": p[("hot", v, 2024)] - p[("hot", v, 2021)] for v in ["before", "nolimit", "nonpublic"]})
    for v in ["before", "nolimit", "nonpublic"]:
        r[f"cold24_{v}"] = p[("cold", v, 2024)]
    print(f"\n=== 구별 Hot 증감(2021→2024)·2024 Cold ===\n{r.astype(int).to_string()}")


if __name__ == "__main__":
    main()
