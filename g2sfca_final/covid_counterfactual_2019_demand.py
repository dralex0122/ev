"""
2026-11-08: 코로나 반사실 — 2021년 점수를 수요만 2019년(코로나 이전) 낮 인구로 바꿔 재계산.

공급(S)·통행시간(T)은 2021 그대로, 수요(D)만 2019 낮_avg로 교체(week_낮_normal, 최종 nonpublic 공급).
  actual_2021 : S2021, D2021, T2021  (본문 결과)
  cf_2021     : S2021, D2019, T2021  (코로나가 없었다면)
  actual_2024 : S2024, D2024, T2024
cf − actual_2021 = 2021년 수요가 코로나로 달라진 효과.
지니·Palma·평균은 각 경우에 쓴 수요로 가중(cf는 2019 낮인구), 비교용으로 2021 낮인구 가중도 함께 출력.
2019 수요: oa_population_periods_2019.csv(2021~24와 같은 정의, 평일 252일 평균). 신규 분석 — 교수님 상의 전 탐색용.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal

from g2sfca_final_supply import APT_FP, D1_FP, GAUSSIAN_OD_DIR, decay_gaussian
from recheck_uselimitation_week_day import load_stations, gi_classes, BOUNDARY_FP, OUT_DIR, K, GU_MAP
from recompute_exclude_nonpublic import NONPUBLIC_DIR, CAND_FP
from inequality_gini_palma import weighted_gini, weighted_share
from local_change_decomposition import g2sfca_fast, REGIONS

POP2019_FP = "/mnt/cowork/EV/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)/oa_population_periods_2019.csv"
OUT_FP = f"{OUT_DIR}/covid_counterfactual_2019_demand.csv"
OA_FP = f"{OUT_DIR}/covid_counterfactual_2019_demand_oa.csv"


def supply_od(y, apt_set, excl):
    st = load_stations(y)
    st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
    S = st.groupby("station_id").fast_count.sum().astype(float)
    od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{y}_week_낮_normal.csv", dtype={"station_id": str, "oa_code": str},
                     usecols=["station_id", "oa_code", "travel_time_sec"])
    od["w"] = od.travel_time_sec.apply(decay_gaussian)
    return S, od[od.w > 0][["station_id", "oa_code", "w"]].reset_index(drop=True)


def main():
    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)
    gu = pd.Series(gdf["TOT_REG_CD"].str[:5].map(GU_MAP).values, index=gdf["TOT_REG_CD"].values)
    w = libpysal.weights.KNN.from_array(np.array([[p.x, p.y] for p in gdf.geometry.centroid]), k=K)

    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl = set(cand[cand.final_label == "제외"].station_id)
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    D = {y: d1[d1.year == y].set_index("집계구코드")["낮_avg"].astype(float) for y in (2021, 2024)}
    p19 = pd.read_csv(POP2019_FP, dtype={"집계구코드": str}).set_index("집계구코드")["낮_avg"].astype(float)
    D[2019] = p19.reindex(D[2021].index).fillna(0)
    print(f"2019 낮인구 합 {D[2019].sum():,.0f} / 2021 {D[2021].sum():,.0f} / 2024 {D[2024].sum():,.0f}")

    S21, T21 = supply_od(2021, apt_set, excl)
    S24, T24 = supply_od(2024, apt_set, excl)
    scores = {"actual_2021": (g2sfca_fast(S21, D[2021], T21), D[2021]),
              "cf_2021_D2019": (g2sfca_fast(S21, D[2019], T21), D[2019]),
              "actual_2024": (g2sfca_fast(S24, D[2024], T24), D[2024])}
    ref = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_2021_week_낮_normal.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score
    print(f"2021 최종 점수 재현 최대 오차 {(scores['actual_2021'][0] - ref.reindex(D[2021].index)).abs().max():.2e}")

    rows, cls_all = [], {}
    for name, (a, pop) in scores.items():
        cls = pd.Series(gi_classes(gdf, w, a), index=gdf["TOT_REG_CD"].values)
        cls_all[name] = cls
        for wname, wt in [("own", pop), ("pop2021", D[2021])]:
            x, ww = a.values, wt.reindex(a.index).fillna(0).values
            r = {"case": name, "weight": wname,
                 "mean_x1000": round(float(np.average(x, weights=ww)) * 1000, 4),
                 "gini": round(weighted_gini(x, ww), 4),
                 "palma": round(weighted_share(x, ww, 0.9, 1.0) / weighted_share(x, ww, 0.0, 0.4), 3),
                 "hot_seoul": int((cls == "Hot Spot").sum()), "cold_seoul": int((cls == "Cold Spot").sum())}
            for rn, gus in REGIONS.items():
                ids = gu.index[gu.isin(gus)]
                r[f"hot_{rn}"] = int((cls[ids] == "Hot Spot").sum())
                r[f"mean_{rn}_x1000"] = round(float(np.average(a.reindex(ids).fillna(0), weights=wt.reindex(ids).fillna(0) + 1e-9)) * 1000, 4)
            rows.append(r)
    out = pd.DataFrame(rows)
    out.to_csv(OUT_FP, index=False, encoding="utf-8-sig")

    oa = pd.DataFrame({k: v[0] for k, v in scores.items()})
    oa["gu"] = gu.reindex(oa.index).values
    for k, c in cls_all.items():
        oa[f"cls_{k}"] = c.reindex(oa.index).values
    oa.index.name = "oa_code"
    oa.to_csv(OA_FP, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print("\n=== 지표 (own = 각 경우의 수요로 가중) ===")
    print(out.set_index(["case", "weight"]).T.to_string())

    a21, acf = oa["actual_2021"], oa["cf_2021_D2019"]
    gu_ratio = (oa.groupby("gu")[["cf_2021_D2019", "actual_2021"]].apply(
        lambda g: np.average(g["cf_2021_D2019"], weights=D[2019].reindex(g.index).fillna(0) + 1e-9)
        / np.average(g["actual_2021"], weights=D[2021].reindex(g.index).fillna(0) + 1e-9))).sort_values()
    print("\n=== 구별 평균 점수 비 (cf ÷ actual_2021, 각자 수요 가중) ===")
    print(gu_ratio.round(3).to_string())
    print(f"\n집계구 점수 상관 actual vs cf: {np.corrcoef(a21, acf)[0, 1]:.4f}")
    ct = pd.crosstab(oa["cls_actual_2021"], oa["cls_cf_2021_D2019"])
    print(f"\n=== Gi 분류 전이 (행 actual_2021, 열 cf) ===\n{ct.to_string()}")
    print(f"분류 일치율 {(oa['cls_actual_2021'] == oa['cls_cf_2021_D2019']).mean() * 100:.1f}%")
    print(f"\n>> 저장: {OUT_FP}\n         {OA_FP}")


if __name__ == "__main__":
    main()
