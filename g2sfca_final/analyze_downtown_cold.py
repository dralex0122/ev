"""
2026-10-14 랩미팅 ② — 도심(중구·종로) Cold의 구조적 이유 검증. 2024, week_낮_normal, 최종(nonpublic) 공급.

점수 분해: A_i = Σ_j w_ij·R_j,  R_j = S_j / Σ_k w_kj·D_k
  - 도달 공급 AS_i = Σ_j w_ij·S_j            (가설 2: 충전기가 적다)
  - 충전기당 경쟁 수요 C_i = AS_i / A_i       (가설 1: 낮 수요가 많다)  → A_i = AS_i / C_i
  - 15분 내 도달 충전소·충전기 수, 최근접 충전소 통행시간 (가설 3: 혼잡으로 도달 범위가 좁다)
반사실(공급 고정, Gi* KNN k=20 재계산):
  - CF_밤수요 / CF_심야수요: 수요만 밤_avg / 심야_avg로 교체 (가설 1, 심야 ≈ 거주인구)
  - CF_비혼잡: OD만 week_낮_freeflow로 교체 (가설 3)
  - CF_둘다: 밤 수요 + 비혼잡 OD
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal

from g2sfca_final_supply import APT_FP, D1_FP, GAUSSIAN_OD_DIR, decay_gaussian
from recheck_uselimitation_week_day import load_stations, g2sfca, gi_classes, BOUNDARY_FP, OUT_DIR, K, GU_MAP
from recompute_exclude_nonpublic import NONPUBLIC_DIR, CAND_FP

YEAR = 2024
DOWNTOWN = ["중구", "종로구"]
OUT_FP = f"{OUT_DIR}/downtown_cold_decomposition.csv"
CF_FP = f"{OUT_DIR}/downtown_cold_counterfactual.csv"


def main():
    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)
    w = libpysal.weights.KNN.from_array(np.array([[p.x, p.y] for p in gdf.geometry.centroid]), k=K)

    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl = set(cand[cand.final_label == "제외"].station_id)
    st = load_stations(YEAR)
    st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
    supply = dict(zip(st.station_id, st.fast_count))

    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    d = d1[d1.year == YEAR].set_index("집계구코드")
    dem_day, dem_night = d["낮_avg"].astype(float).to_dict(), d["밤_avg"].astype(float).to_dict()
    dem_late = d["심야_avg"].astype(float).to_dict()
    od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{YEAR}_week_낮_normal.csv", dtype={"station_id": str, "oa_code": str})
    od_ff = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{YEAR}_week_낮_freeflow.csv", dtype={"station_id": str, "oa_code": str})

    # --- 기준 점수·분류 (최종 결과 재현 확인)
    base = g2sfca(supply, dem_day, od)
    ref = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{YEAR}_week_낮_normal.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score
    print(f">> 최종 점수 재현 최대 오차: {(base - ref.reindex(base.index)).abs().max():.2e}")
    cls = pd.Series(gi_classes(gdf, w, base), index=gdf["TOT_REG_CD"].values)

    # --- 점수 분해
    o = od[od.station_id.isin(supply)].copy()
    o["w"] = o.travel_time_sec.apply(decay_gaussian)
    o["S"] = o.station_id.map(supply)
    o["dem"] = o.oa_code.map(dem_day).fillna(0)
    AS = (o.w * o.S).groupby(o.oa_code).sum()
    reach = o[o.w > 0].groupby("oa_code").agg(n_station=("station_id", "nunique"), n_charger=("S", "sum"),
                                              tt_min=("travel_time_sec", "min"))
    df = pd.DataFrame({"oa_code": gdf["TOT_REG_CD"], "gu": gdf["gu"].values}).set_index("oa_code")
    df["cls"] = cls
    df["score"] = base
    df["AS"] = AS
    df["C"] = df.AS / df.score
    df = df.join(reach)
    df["dem_day"] = pd.Series(dem_day)
    df["dem_night"] = pd.Series(dem_night)
    df["day_night_ratio"] = df.dem_day / df.dem_night
    df["dem_late"] = pd.Series(dem_late)
    df["day_late_ratio"] = df.dem_day / df.dem_late
    # 도달 충전소들이 함께 받는 경쟁 수요의 낮/심야 비율 (집계구 자체가 아니라 충전소 집수구역 기준)
    o["dem_late"] = o.oa_code.map(dem_late).fillna(0)
    cd = (o.dem * o.w).groupby(o.station_id).sum() / (o.dem_late * o.w).groupby(o.station_id).sum()
    o["cd"] = o.station_id.map(cd)
    df["catch_day_late_ratio"] = (o.w * o.S * o.cd).groupby(o.oa_code).sum() / AS
    df.reset_index().to_csv(OUT_FP, index=False, encoding="utf-8-sig")

    groups = {
        "도심 Cold(중구·종로)": df[df.gu.isin(DOWNTOWN) & (df.cls == "Cold Spot")],
        "기타 Cold": df[~df.gu.isin(DOWNTOWN) & (df.cls == "Cold Spot")],
        "Hot": df[df.cls == "Hot Spot"],
        "서울 전체": df,
    }
    pd.set_option("display.width", 250)
    rows = []
    for name, g in groups.items():
        rows.append({"group": name, "n": len(g),
                     "score_x1000": g.score.median() * 1e3,
                     "AS_도달공급": g.AS.median(),
                     "C_충전기당경쟁수요": g.C.median(),
                     "15분내_충전소": g.n_station.median(),
                     "15분내_충전기": g.n_charger.median(),
                     "최근접_통행분": g.tt_min.median() / 60,
                     "낮수요": g.dem_day.median(),
                     "낮/밤": g.day_night_ratio.median(),
                     "낮/심야": g.day_late_ratio.median(),
                     "집수구역_낮/심야": g.catch_day_late_ratio.median()})
    t = pd.DataFrame(rows).set_index("group")
    print("\n=== 점수 분해 (중앙값) ===\n" + t.round(3).to_string())

    # 서울 중앙값 대비 로그 격차 분해: log(A/A_ref) = log(AS/AS_ref) − log(C/C_ref)
    seoul = groups["서울 전체"]
    dc = groups["도심 Cold(중구·종로)"]
    gap_A = np.log(dc.score.median() / seoul.score.median())
    gap_AS = np.log(dc.AS.median() / seoul.AS.median())
    gap_C = -np.log(dc.C.median() / seoul.C.median())
    print(f"\n=== 도심 Cold 점수 격차 분해 (서울 중앙값 대비, 로그) ===\n"
          f"점수 {gap_A:+.3f} ≈ 도달공급 {gap_AS:+.3f} + 경쟁수요 {gap_C:+.3f} (중앙값 근사라 합이 정확히 맞지는 않음)")

    # --- 반사실
    cf_rows = []
    scen = {"기준(낮수요·혼잡OD)": (dem_day, od), "CF_밤수요": (dem_night, od), "CF_심야수요": (dem_late, od),
            "CF_비혼잡OD": (dem_day, od_ff), "CF_심야수요+비혼잡": (dem_late, od_ff)}
    dt_mask = gdf["gu"].isin(DOWNTOWN).values
    base_cold_dt = (cls.values == "Cold Spot") & dt_mask
    for name, (dem, odx) in scen.items():
        s = g2sfca(supply, dem, odx)
        c = gi_classes(gdf, w, s)
        cf_rows.append({"scenario": name,
                        "seoul_hot": int((c == "Hot Spot").sum()), "seoul_cold": int((c == "Cold Spot").sum()),
                        "downtown_cold": int(((c == "Cold Spot") & dt_mask).sum()),
                        "downtown_hot": int(((c == "Hot Spot") & dt_mask).sum()),
                        "base_downtown_cold_still_cold_pct": round(float((c[base_cold_dt] == "Cold Spot").mean() * 100), 1),
                        "downtown_score_vs_seoul": round(float(np.median(s.reindex(gdf["TOT_REG_CD"][dt_mask]).values) / s.median()), 3)})
        print(f"[{name}] 완료", flush=True)
    cf = pd.DataFrame(cf_rows)
    cf.to_csv(CF_FP, index=False, encoding="utf-8-sig")
    print(f"\n=== 반사실 (도심 = 중구·종로 {int(dt_mask.sum())}개 집계구) ===\n{cf.to_string(index=False)}")


if __name__ == "__main__":
    main()
