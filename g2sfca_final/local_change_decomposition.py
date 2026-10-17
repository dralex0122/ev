"""
2026-10-14 랩미팅 과제 — 국지적 Hot 변화와 2023년 지니 반등의 원인 분해. week_낮_normal, 최종(nonpublic) 공급.

연도 전환(y0→y1)마다 세 입력을 하나씩 y1 값으로 바꾼 반사실 점수를 계산:
  - T: OD 통행시간(연도별 혼잡). y1 OD에 y0 충전소가 모두 있으므로 공급보다 먼저 교체 가능
  - D: 수요(낮_avg 생활인구)
  - S: 공급(충전소 위치·충전기 수) — 신규 충전소는 y0 OD에 없어서 항상 마지막 단계
  base(S0,D0,T0) → T(S0,D0,T1), D(S0,D1,T0) → TD(S0,D1,T1) → actual(S1,D1,T1)
  T·D 기여는 두 순서 평균(Shapley), S 기여 = actual − TD.
지표: 권역별 Hot 수(Gi* KNN k=20)·낮인구 가중 평균 점수, 지니·Palma(낮인구 가중),
      y0 점수 분위 집단(하위 40%/중위 50%/상위 10%)별 평균 점수 — 어느 집단이 더 빨리 올랐는지.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal

from g2sfca_final_supply import APT_FP, D1_FP, GAUSSIAN_OD_DIR, decay_gaussian
from recheck_uselimitation_week_day import load_stations, gi_classes, BOUNDARY_FP, OUT_DIR, K, GU_MAP
from recompute_exclude_nonpublic import NONPUBLIC_DIR, CAND_FP
from inequality_gini_palma import weighted_gini, weighted_share

YEARS = [2021, 2022, 2023, 2024]
TRANSITIONS = [(2021, 2022), (2022, 2023), (2023, 2024), (2021, 2024)]
REGIONS = {"종로·중구": ["종로구", "중구"], "성동구": ["성동구"], "마포구": ["마포구"],
           "양천구": ["양천구"], "영등포구": ["영등포구"], "송파구": ["송파구"]}
COMBOS = ["base", "T", "D", "TD", "actual"]
OUT_FP = f"{OUT_DIR}/local_change_counterfactual.csv"
GROUP_FP = f"{OUT_DIR}/local_change_score_groups.csv"
SUPPLY_FP = f"{OUT_DIR}/local_change_new_supply_gu.csv"


def g2sfca_fast(supply, demand, od):
    """recheck_uselimitation_week_day.g2sfca와 같은 계산, decay 가중치(w)를 미리 붙인 OD 사용."""
    o = od[od.station_id.isin(supply.index)]
    dem = o.oa_code.map(demand).fillna(0).values
    d_sum = pd.Series(dem * o.w.values).groupby(o.station_id.values).sum()
    R = (supply.reindex(d_sum.index).fillna(0) / d_sum).where(d_sum > 0, 0.0).fillna(0.0)
    A = pd.Series(o.station_id.map(R).values * o.w.values).groupby(o.oa_code.values).sum()
    return demand.index.to_series().map(A).fillna(0.0)


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

    S, D, T, st_gu = {}, {}, {}, {}
    for y in YEARS:
        st = load_stations(y)
        st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
        S[y] = st.groupby("station_id").fast_count.sum().astype(float)
        st_gu.update(dict(zip(st.station_id, st.address.fillna("").str.extract(r"(\S+구)\s")[0])))
        D[y] = d1[d1.year == y].set_index("집계구코드")["낮_avg"].astype(float)
        od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{y}_week_낮_normal.csv", dtype={"station_id": str, "oa_code": str},
                         usecols=["station_id", "oa_code", "travel_time_sec"])
        od["w"] = od.travel_time_sec.apply(decay_gaussian)
        T[y] = od[od.w > 0][["station_id", "oa_code", "w"]].reset_index(drop=True)
        ref = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{y}_week_낮_normal.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score
        err = (g2sfca_fast(S[y], D[y], T[y]) - ref.reindex(D[y].index)).abs().max()
        print(f"[{y}] 충전소 {len(S[y])} / 충전기 {int(S[y].sum())}, 최종 점수 재현 최대 오차 {err:.2e}", flush=True)

    # --- 신규 공급의 구별 분포 (순증 충전기, 충전소 주소 기준)
    sup_rows = []
    for y0, y1 in TRANSITIONS:
        dS = S[y1].reindex(S[y1].index.union(S[y0].index)).fillna(0) - S[y0].reindex(S[y1].index.union(S[y0].index)).fillna(0)
        by_gu = dS.groupby(dS.index.map(st_gu)).sum()
        for g, v in by_gu.items():
            sup_rows.append({"transition": f"{y0}-{y1}", "gu": g, "net_new_chargers": int(v)})
    pd.DataFrame(sup_rows).to_csv(SUPPLY_FP, index=False, encoding="utf-8-sig")

    rows, grp_rows = [], []
    for y0, y1 in TRANSITIONS:
        missing = len(set(S[y0].index) - set(T[y1].station_id))
        print(f"\n[{y0}→{y1}] y0 충전소 중 y1 OD에 없는 곳: {missing}", flush=True)
        spec = {"base": (y0, y0, y0), "T": (y0, y0, y1), "D": (y0, y1, y0), "TD": (y0, y1, y1), "actual": (y1, y1, y1)}
        # y0 실제 점수의 낮인구 가중 분위 → 집단 고정
        a0 = g2sfca_fast(S[y0], D[y0], T[y0])
        pop0 = D[y0].reindex(a0.index).fillna(0)
        o = np.argsort(a0.values)
        q = np.empty(len(a0))
        q[o] = np.cumsum(pop0.values[o]) / pop0.sum()
        group = pd.Series(np.where(q <= 0.4, "하위40", np.where(q > 0.9, "상위10", "중위50")), index=a0.index)
        for combo, (ys, yd, yt) in spec.items():
            a = g2sfca_fast(S[ys], D[yd], T[yt])
            pop = D[yd].reindex(a.index).fillna(0)
            cls = pd.Series(gi_classes(gdf, w, a), index=gdf["TOT_REG_CD"].values)
            x, wt = a.values, pop.values
            r = {"transition": f"{y0}-{y1}", "combo": combo, "mean_x1000": round(float(np.average(x, weights=wt)) * 1000, 4),
                 "gini": round(weighted_gini(x, wt), 4),
                 "palma": round(weighted_share(x, wt, 0.9, 1.0) / weighted_share(x, wt, 0.0, 0.4), 3),
                 "hot_seoul": int((cls == "Hot Spot").sum())}
            for name, gus in REGIONS.items():
                m = gu.isin(gus)
                ids = gu.index[m]
                r[f"hot_{name}"] = int((cls[ids] == "Hot Spot").sum())
                r[f"mean_{name}_x1000"] = round(float(np.average(a.reindex(ids).fillna(0), weights=pop.reindex(ids).fillna(0) + 1e-9)) * 1000, 4)
            rows.append(r)
            for gname in ["하위40", "중위50", "상위10"]:
                ids = group.index[group == gname]
                grp_rows.append({"transition": f"{y0}-{y1}", "combo": combo, "group": gname,
                                 "mean_x1000": round(float(np.average(a[ids], weights=pop[ids] + 1e-9)) * 1000, 4)})
            print(f"  {combo:6s} gini={r['gini']:.4f} hot={r['hot_seoul']} 종로·중구={r['hot_종로·중구']} 성동={r['hot_성동구']}", flush=True)

    out = pd.DataFrame(rows)
    grp = pd.DataFrame(grp_rows)
    out.to_csv(OUT_FP, index=False, encoding="utf-8-sig")
    grp.to_csv(GROUP_FP, index=False, encoding="utf-8-sig")

    # --- Shapley 기여 (T·D 순서 평균, S는 마지막)
    pd.set_option("display.width", 250)
    metrics = [c for c in out.columns if c not in ("transition", "combo")]
    print("\n=== 요인별 기여 (T·D Shapley, S=actual−TD) ===")
    for tr, g in out.groupby("transition", sort=False):
        v = g.set_index("combo")[metrics]
        contrib = pd.DataFrame({
            "base": v.loc["base"],
            "T": ((v.loc["T"] - v.loc["base"]) + (v.loc["TD"] - v.loc["D"])) / 2,
            "D": ((v.loc["D"] - v.loc["base"]) + (v.loc["TD"] - v.loc["T"])) / 2,
            "S": v.loc["actual"] - v.loc["TD"],
            "actual": v.loc["actual"],
        })
        print(f"\n--- {tr} ---\n{contrib.round(4).to_string()}")
    print("\n=== y0 점수 집단별 평균 점수(×1000) ===")
    print(grp.pivot_table(index=["transition", "group"], columns="combo", values="mean_x1000")[COMBOS].to_string())
    sup = pd.DataFrame(sup_rows).pivot_table(index="gu", columns="transition", values="net_new_chargers", fill_value=0)
    print(f"\n=== 구별 순증 충전기 ===\n{sup.sort_values('2021-2024', ascending=False).to_string()}")
    print(f"\n>> 저장: {OUT_FP}\n         {GROUP_FP}\n         {SUPPLY_FP}")


if __name__ == "__main__":
    main()
