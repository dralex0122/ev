"""
2026-10-21: 종로·중구 Hot 소멸 해석 보강 — 기존 최종(nonpublic) 결과 재집계, 새 분석 아님.

1. 구별 낮인구 1만 명당 충전기(2021·2024)와 순증 — 절대 개수 대신 낮인구 규모 반영
2. Hot 전이 지도(2021→2024, Gi* k=20): Hot 유지 / Hot 이탈 / 신규 Hot / 그 외
3. 구별 낮인구 가중 평균 점수 ÷ 서울 평균 비율의 연도별 추이(2021~2024)

충전소→구 배정은 local_change_decomposition.py와 같이 주소의 "○○구"로 함.
"""
import os

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from g2sfca_final_supply import APT_FP, D1_FP
from recheck_uselimitation_week_day import load_stations, OUT_DIR, YEARS, NAS
from recompute_exclude_nonpublic import NONPUBLIC_DIR, CAND_FP
from presentation_nonpublic_exclusion_maps import load_boundary, fill_by, GU_LINE, INK, MUTED

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

GI_FP = f"{OUT_DIR}/gi_k20_3ver.csv"
SUPPLY_OUT = f"{OUT_DIR}/downtown_supply_per_daypop_gu.csv"
RATIO_OUT = f"{OUT_DIR}/downtown_score_ratio_gu_year.csv"
TRANS_OUT = f"{OUT_DIR}/downtown_hot_transition_gu.csv"
MAP_OUT = f"{NAS}/new_output/hot_transition_2021_2024_k20.png"
DOWNTOWN = ["종로구", "중구"]

TRANS_COLOR = {
    "그 외": "#ecebe6",
    "Hot 이탈": "#f4a582",
    "신규 Hot": "#2166ac",
    "Hot 유지": "#b2182b",
}


def transition(a, b):
    if a == "Hot Spot" and b == "Hot Spot":
        return "Hot 유지"
    if a == "Hot Spot":
        return "Hot 이탈"
    if b == "Hot Spot":
        return "신규 Hot"
    return "그 외"


def main():
    gdf, gu_poly = load_boundary()
    oa_gu = pd.Series(gdf["gu"].values, index=gdf["TOT_REG_CD"].values)
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    D = {y: d1[d1.year == y].set_index("집계구코드")["낮_avg"].astype(float) for y in YEARS}

    # --- 1. 구별 낮인구 1만 명당 충전기
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl = set(cand[cand.final_label == "제외"].station_id)
    rows = []
    for y in [2021, 2024]:
        st = load_stations(y)
        st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
        st_gu = st.address.fillna("").str.extract(r"(\S+구)\s")[0]
        chg = st.fast_count.groupby(st_gu.values).sum()
        pop = D[y].groupby(D[y].index.map(oa_gu)).sum()
        for g in pop.index:
            rows.append({"year": y, "gu": g, "chargers": int(chg.get(g, 0)), "daypop": round(pop[g])})
    sup = pd.DataFrame(rows).pivot_table(index="gu", columns="year", values=["chargers", "daypop"])
    sup.columns = [f"{a}_{b}" for a, b in sup.columns]
    for y in [2021, 2024]:
        sup[f"per10k_{y}"] = (sup[f"chargers_{y}"] / sup[f"daypop_{y}"] * 1e4).round(3)
    sup["net_new"] = (sup.chargers_2024 - sup.chargers_2021).astype(int)
    sup["net_new_per10k"] = (sup.net_new / ((sup.daypop_2021 + sup.daypop_2024) / 2) * 1e4).round(3)
    sup["rank_net_new"] = sup.net_new.rank(ascending=False, method="min").astype(int)
    sup["rank_net_new_per10k"] = sup.net_new_per10k.rank(ascending=False, method="min").astype(int)
    sup = sup.sort_values("net_new_per10k", ascending=False)
    seoul = {f"per10k_{y}": sup[f"chargers_{y}"].sum() / sup[f"daypop_{y}"].sum() * 1e4 for y in [2021, 2024]}
    seoul["net_new_per10k"] = sup.net_new.sum() / ((sup.daypop_2021.sum() + sup.daypop_2024.sum()) / 2) * 1e4
    sup.to_csv(SUPPLY_OUT, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    print("=== 1. 구별 낮인구 1만 명당 충전기 ===")
    print(sup[["daypop_2024", "per10k_2021", "per10k_2024", "net_new", "rank_net_new",
               "net_new_per10k", "rank_net_new_per10k"]].to_string())
    print(f"서울: 2021 {seoul['per10k_2021']:.3f} → 2024 {seoul['per10k_2024']:.3f}, 순증 {seoul['net_new_per10k']:.3f}/1만 명")

    # --- 3. 구별 평균 점수 ÷ 서울 평균
    rows = []
    for y in YEARS:
        s = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{y}_week_낮_normal.csv",
                        dtype={"oa_code": str}).set_index("oa_code").accessibility_score
        pop = D[y].reindex(s.index).fillna(0)
        g = oa_gu.reindex(s.index)
        seoul_mean = np.average(s, weights=pop)
        for name, m in [("종로·중구", g.isin(DOWNTOWN))] + [(k, g == k) for k in sorted(g.dropna().unique())]:
            mean = np.average(s[m], weights=pop[m] + 1e-9)
            rows.append({"year": y, "region": name, "mean_x1000": round(mean * 1000, 4),
                         "seoul_mean_x1000": round(seoul_mean * 1000, 4), "ratio": round(mean / seoul_mean, 3)})
    ratio = pd.DataFrame(rows)
    ratio.to_csv(RATIO_OUT, index=False, encoding="utf-8-sig")
    piv = ratio.pivot_table(index="region", columns="year", values="ratio").sort_values(2021, ascending=False)
    print("\n=== 3. 낮인구 가중 평균 점수 ÷ 서울 평균 ===")
    print(piv.to_string())
    print(ratio[ratio.region == "종로·중구"].to_string(index=False))

    # --- 2. Hot 전이 지도
    gi = pd.read_csv(GI_FP, dtype={"oa_code": str})
    c = {y: gi[gi.year == y].set_index("oa_code")["nonpublic"].reindex(gdf["TOT_REG_CD"]).values for y in [2021, 2024]}
    tr = pd.Series([transition(a, b) for a, b in zip(c[2021], c[2024])], index=gdf["TOT_REG_CD"].values)
    tab = pd.crosstab(oa_gu.reindex(tr.index).values, tr.values)
    tab = tab.reindex(columns=["Hot 유지", "Hot 이탈", "신규 Hot"], fill_value=0)
    tab["hot_2021"] = tab["Hot 유지"] + tab["Hot 이탈"]
    tab["hot_2024"] = tab["Hot 유지"] + tab["신규 Hot"]
    tab = tab.sort_values("Hot 이탈", ascending=False)
    tab.to_csv(TRANS_OUT, encoding="utf-8-sig")
    print("\n=== 2. 구별 Hot 전이 (2021→2024) ===")
    print(tab.to_string())
    n = tr.value_counts()
    print(n.to_string())

    fig, ax = plt.subplots(figsize=(10, 8.6))
    fill_by(ax, gdf, tr.values, TRANS_COLOR)
    gu_poly.boundary.plot(ax=ax, color=GU_LINE, linewidth=0.35)
    gu_poly.loc[DOWNTOWN].dissolve().boundary.plot(ax=ax, color=INK, linewidth=1.6)
    for name, r in gu_poly.iterrows():
        p = r.geometry.representative_point()
        ax.text(p.x, p.y, name, fontsize=7.5, color=INK, ha="center", va="center", zorder=4,
                fontweight="bold" if name in DOWNTOWN else "normal",
                bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.6))
    ax.set_axis_off()
    ax.set_title("Hot Spot 전이 (2021→2024, 평일 낮, 2SFCA, Gi* KNN k=20)", fontsize=14, color=INK,
                 fontweight="bold", pad=8)
    handles = [mpatches.Patch(facecolor=TRANS_COLOR[k], edgecolor="#bbb", label=f"{k} ({n.get(k, 0):,})")
               for k in ["Hot 유지", "Hot 이탈", "신규 Hot", "그 외"]]
    handles.append(mpatches.Patch(facecolor="none", edgecolor=INK, linewidth=1.6, label="종로구·중구"))
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=10)
    ax.text(0.5, -0.01, "괄호 = 집계구 수 · 그 외 = 두 해 모두 Hot 아님(Not Sig·Cold)", transform=ax.transAxes,
            ha="center", va="top", fontsize=9, color=MUTED)
    fig.savefig(MAP_OUT, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"\n>> 저장: {SUPPLY_OUT}\n         {RATIO_OUT}\n         {TRANS_OUT}\n         {MAP_OUT}")


if __name__ == "__main__":
    main()
