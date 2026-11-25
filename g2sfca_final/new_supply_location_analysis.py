"""
2026-11-24: 교수님 11/23 피드백 #13(#3) — 연도별 신규 공급 위치 분석.
"각 연도별로 공급이 많이 추가된 위치를 분석 → 그 때문에 특정 공간의 접근성이 상승 → 도심 접근성이 상대적으로 감소"를
확인하기 위한 분석. 최종 공급(아파트·11–13시 미운영·이용제한·운수사 전용 제외), 평일 낮, Gaussian 2SFCA(t0=900초).

연도 전환(2021→22, 22→23, 23→24, 21→24)마다:
  1. 신규 공급 위치: 충전소별 순증 충전기(dS) → 자치구(좌표 공간결합)·생활권별 합계, 서울 전체 대비 비중, 낮 생활인구 1만 명당
     (2026-11-25: 새 장소 vs 기존 장소 추가 설치 구분 — 연도별 자료는 충전소 ID별 대수가 고정(2026년 목록 역산)이라
      같은 ID 안의 증설은 안 보임. 대신 앞 연도 공급 충전소와 주소가 같거나 50m 이내에 새로 생긴 충전소 ID를
      '기존 장소 추가 설치'로 봄. 좌표 50m만 쓴 좁은 기준도 함께 집계)
  2. 집계구가 15분 안에 닿는 신규 공급량: NS_i = Σ_j dS_j·G(t_ij) (뒤 연도 OD 기준)
  3. 접근성 상대 위치 변화: 집계구 점수의 서울 내 백분위(0–100) 변화 Δpct, 자치구·생활권 평균
  4. 신규 충전기 1기가 감당하는 낮 수요: 신규 공급 충전소의 L_j = Σ_k D_k·G(t_kj) (뒤 연도) — 도심은 같은 충전기라도
     나눠 쓰는 낮 인구가 많아 접근성 상승 폭이 작은지 확인
출력: NAS output/recheck_2026-10-13/gistar95/new_supply/*.csv, new_output/new_supply/*.png
"""
import os

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import spearmanr
from scipy.spatial import cKDTree

from g2sfca_final_supply import APT_FP, D1_FP, GAUSSIAN_OD_DIR, decay_gaussian
from recheck_uselimitation_week_day import load_stations, OUT_DIR, NAS, YEARS
from recompute_exclude_nonpublic import NONPUBLIC_DIR, CAND_FP
from presentation_nonpublic_exclusion_maps import load_boundary

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

CSV_DIR = f"{OUT_DIR}/gistar95/new_supply"
FIG_DIR = f"{NAS}/new_output/new_supply"
os.makedirs(CSV_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)
TRANSITIONS = [(2021, 2022), (2022, 2023), (2023, 2024), (2021, 2024)]
DOWNTOWN = ["종로구", "중구"]
SITE_M = 50  # 기존 장소 판정 거리(m)
NEW_SITE, OLD_SITE = "새 장소", "기존 장소 추가 설치"
REGION = {  # 서울시 5대 생활권(2030 서울플랜). 논문의 '도심'은 종로·중구라서 따로 집계
    "도심권": ["종로구", "중구", "용산구"],
    "동북권": ["성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구"],
    "서북권": ["은평구", "서대문구", "마포구"],
    "서남권": ["양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구"],
    "동남권": ["서초구", "강남구", "송파구", "강동구"],
}
GU2REGION = {g: r for r, gs in REGION.items() for g in gs}


def pr(*a):
    print(*a, flush=True)


def load_all():
    gdf, gu_poly = load_boundary()
    gu_poly = gu_poly.reset_index()[["gu", "geometry"]]
    oa_gu = pd.Series(gdf["gu"].values, index=gdf["TOT_REG_CD"].values)
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl = set(cand[cand.final_label == "제외"].station_id)
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    S, D, W, SCORE, XY, ADDR = {}, {}, {}, {}, {}, {}
    for y in YEARS:
        st = load_stations(y)
        st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
        S[y] = st.groupby("station_id").fast_count.sum().astype(float)
        XY.update({r.station_id: (r.lng, r.lat) for r in st.itertuples() if pd.notna(r.lng)})
        ADDR.update({r.station_id: " ".join(str(r.address or "").split()) for r in st.itertuples()})
        D[y] = d1[d1.year == y].set_index("집계구코드")["낮_avg"].astype(float)
        od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{y}_week_낮_normal.csv", dtype={"station_id": str, "oa_code": str},
                         usecols=["station_id", "oa_code", "travel_time_sec"])
        od["w"] = od.travel_time_sec.apply(decay_gaussian)
        W[y] = od[od.w > 0][["station_id", "oa_code", "w"]].reset_index(drop=True)
        SCORE[y] = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{y}_week_낮_normal.csv",
                               dtype={"oa_code": str}).set_index("oa_code").accessibility_score
        pr(f"[{y}] 충전소 {len(S[y]):,} / 충전기 {int(S[y].sum()):,}")
    # 충전소 → 자치구: 좌표 공간결합(주소 문자열보다 정확)
    pts = gpd.GeoDataFrame({"station_id": list(XY)}, geometry=gpd.points_from_xy([v[0] for v in XY.values()],
                           [v[1] for v in XY.values()]), crs="EPSG:4326").to_crs(gu_poly.crs)
    j = gpd.sjoin_nearest(pts, gu_poly, how="left", max_distance=500)
    st_gu = j.drop_duplicates("station_id").set_index("station_id")["gu"]
    pxy = pts.set_index("station_id").geometry  # EPSG:5179(m)
    XYM = {i: (g.x, g.y) for i, g in pxy.items()}
    return gdf, gu_poly, oa_gu, S, D, W, SCORE, XY, st_gu, XYM, ADDR


def site_kind(S, y0, ids, s0, XYM, ADDR, use_addr=True):
    """앞 연도에 없던 충전소 ID가 앞 연도 공급 충전소와 같은 장소(주소 동일 또는 SITE_M 이내)면 기존 장소 추가 설치."""
    old = list(S[y0].index)
    tree = cKDTree(np.array([XYM[i] for i in old]))
    old_addr = {ADDR[i] for i in old if ADDR.get(i)}
    out = {}
    for i in ids:
        if s0[i] > 0:
            out[i] = "기존 ID"
            continue
        near = len(tree.query_ball_point(XYM[i], SITE_M)) > 0
        same = use_addr and bool(ADDR.get(i)) and ADDR[i] in old_addr
        out[i] = OLD_SITE if (near or same) else NEW_SITE
    return pd.Series(out)


def pct_rank(s):
    return s.rank(pct=True, method="average") * 100


def main():
    gdf, gu_poly, oa_gu, S, D, W, SCORE, XY, st_gu, XYM, ADDR = load_all()
    gu_rows, reg_rows, oa_rows, load_rows, summ = [], [], [], [], []
    KIND = {}
    for y0, y1 in TRANSITIONS:
        tr = f"{y0}-{y1}"
        ids = S[y1].index.union(S[y0].index)
        s0, s1 = S[y0].reindex(ids).fillna(0), S[y1].reindex(ids).fillna(0)
        dS = (s1 - s0)
        kind = site_kind(S, y0, ids, s0, XYM, ADDR).reindex(ids)
        kind_xy = site_kind(S, y0, ids, s0, XYM, ADDR, use_addr=False).reindex(ids)
        KIND[(y0, y1)] = kind
        assert dS[kind == "기존 ID"].abs().sum() == 0  # 같은 ID 대수 변화 없음(역산 자료 특성)
        g = st_gu.reindex(ids)
        assert g.notna().all(), f"자치구 미배정 충전소 {g.isna().sum()}"
        pop1 = D[y1].groupby(oa_gu.reindex(D[y1].index).values).sum()
        tot = dS[dS > 0].sum()
        # 1. 자치구별 신규 공급
        for gu in sorted(pop1.index):
            m = (g == gu)
            add = dS[m & (dS > 0)].sum()
            gu_rows.append({"transition": tr, "gu": gu, "region": GU2REGION[gu],
                            "new_chargers": int(add), "net_chargers": int(dS[m].sum()),
                            "from_new_site": int(dS[m & (dS > 0) & (kind == NEW_SITE)].sum()),
                            "from_existing_site": int(dS[m & (dS > 0) & (kind == OLD_SITE)].sum()),
                            "from_existing_site_50m_only": int(dS[m & (dS > 0) & (kind_xy == OLD_SITE)].sum()),
                            "new_stations": int((m & (s0 == 0) & (s1 > 0)).sum()),
                            "share_pct": round(add / tot * 100, 1), "daypop_y1": int(pop1[gu]),
                            "new_per10k": round(add / pop1[gu] * 1e4, 3),
                            "chargers_y0": int(s0[m].sum()), "chargers_y1": int(s1[m].sum())})
        # 2–3. 집계구: 15분 안 신규 공급, 백분위 변화
        w1 = W[y1]
        add_j = dS.clip(lower=0)
        ns = (w1.station_id.map(add_j).fillna(0) * w1.w).groupby(w1.oa_code).sum()
        a0, a1 = SCORE[y0], SCORE[y1].reindex(SCORE[y0].index)
        p0, p1 = pct_rank(a0), pct_rank(a1)
        oa = pd.DataFrame({"transition": tr, "oa_code": a0.index, "gu": oa_gu.reindex(a0.index).values,
                           "score0": a0.values, "score1": a1.values, "pct0": p0.values, "pct1": p1.values,
                           "dpct": (p1 - p0).values, "new_supply_15min": ns.reindex(a0.index).fillna(0).values,
                           "daypop_y1": D[y1].reindex(a0.index).fillna(0).values})
        oa["region"] = oa.gu.map(GU2REGION)
        oa["downtown"] = oa.gu.isin(DOWNTOWN)
        oa_rows.append(oa)
        # 4. 신규 충전기가 놓인 곳의 낮 수요 부담 L_j (뒤 연도)
        L = (w1.oa_code.map(D[y1]).fillna(0) * w1.w).groupby(w1.station_id).sum()
        nj = add_j[add_j > 0]
        lj = pd.DataFrame({"add": nj, "L": L.reindex(nj.index), "gu": g.reindex(nj.index)})
        lj["region"] = lj.gu.map(GU2REGION)
        lj["downtown"] = lj.gu.isin(DOWNTOWN)
        for name, m in [("서울 전체", lj.index == lj.index)] + [(r, lj.region == r) for r in REGION] + [("도심(종로·중구)", lj.downtown)]:
            sub = lj[m & lj.L.notna()]
            load_rows.append({"transition": tr, "area": name, "new_chargers": int(sub["add"].sum()),
                              "median_load_per_new_charger": round(float(np.median(np.repeat(sub.L.values, sub["add"].astype(int).values))), 0) if len(sub) else np.nan})
        # 생활권·도심 요약
        for name, m in [("서울 전체", oa.index == oa.index)] + [(r, oa.region == r) for r in REGION] + [("도심(종로·중구)", oa.downtown)]:
            sub = oa[m]
            gsub = (g.map(GU2REGION) == name) if name in REGION else (g.isin(DOWNTOWN) if name.startswith("도심(") else g.notna())
            add = dS[gsub & (dS > 0)].sum()
            ex = dS[gsub & (dS > 0) & (kind == OLD_SITE)].sum()
            ex2 = dS[gsub & (dS > 0) & (kind_xy == OLD_SITE)].sum()
            reg_rows.append({"transition": tr, "area": name, "new_chargers": int(add), "share_pct": round(add / tot * 100, 1),
                             "existing_site_chargers": int(ex), "existing_site_pct": round(ex / add * 100, 1) if add else np.nan,
                             "existing_site_50m_only_pct": round(ex2 / add * 100, 1) if add else np.nan,
                             "daypop_share_pct": round(sub.daypop_y1.sum() / oa.daypop_y1.sum() * 100, 1),
                             "mean_pct0": round(sub.pct0.mean(), 1), "mean_pct1": round(sub.pct1.mean(), 1),
                             "mean_dpct": round(sub.dpct.mean(), 1),
                             "median_new_supply_15min": round(float(sub.new_supply_15min.median()), 2)})
        rho = spearmanr(oa.new_supply_15min / (oa.daypop_y1 + 1), oa.dpct, nan_policy="omit")
        rho2 = spearmanr(oa.new_supply_15min, oa.dpct, nan_policy="omit")
        summ.append({"transition": tr, "new_chargers_total": int(tot),
                     "existing_site_chargers": int(dS[(dS > 0) & (kind == OLD_SITE)].sum()),
                     "existing_site_chargers_50m_only": int(dS[(dS > 0) & (kind_xy == OLD_SITE)].sum()),
                     "spearman_newsupply_vs_dpct": round(rho2.correlation, 3),
                     "spearman_newsupply_perpop_vs_dpct": round(rho.correlation, 3)})
        pr(f"\n=== {tr}: 순증 충전기 {int(dS.sum()):,} (증가분 {int(tot):,}) ===")

    gu_df, reg_df, oa_df = pd.DataFrame(gu_rows), pd.DataFrame(reg_rows), pd.concat(oa_rows)
    load_df, summ_df = pd.DataFrame(load_rows), pd.DataFrame(summ)
    gu_df.to_csv(f"{CSV_DIR}/new_supply_by_gu.csv", index=False, encoding="utf-8-sig")
    reg_df.to_csv(f"{CSV_DIR}/new_supply_by_region.csv", index=False, encoding="utf-8-sig")
    oa_df.to_csv(f"{CSV_DIR}/new_supply_oa_change.csv", index=False, encoding="utf-8-sig")
    load_df.to_csv(f"{CSV_DIR}/new_supply_demand_load.csv", index=False, encoding="utf-8-sig")
    summ_df.to_csv(f"{CSV_DIR}/new_supply_summary.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pr("\n=== 생활권·도심별 신규 공급 비중과 접근성 백분위 변화 ===")
    pr(reg_df.to_string(index=False))
    pr("\n=== 자치구별 신규 충전기 상위 8 (전환별) ===")
    for tr, sub in gu_df.groupby("transition", sort=False):
        pr(f"-- {tr}"); pr(sub.sort_values("new_chargers", ascending=False).head(8)[
            ["gu", "region", "new_chargers", "share_pct", "from_new_site", "from_existing_site", "new_per10k"]].to_string(index=False))
    pr("\n=== 종로·중구 (전환별) ===")
    pr(gu_df[gu_df.gu.isin(DOWNTOWN)][["transition", "gu", "new_chargers", "share_pct", "new_per10k", "chargers_y0", "chargers_y1"]].to_string(index=False))
    pr("\n=== 신규 충전기 1기가 감당하는 낮 수요(중앙값, 거리가중 15분 내 생활인구) ===")
    pr(load_df.pivot_table(index="area", columns="transition", values="median_load_per_new_charger").to_string())
    pr("\n=== 15분 내 신규 공급 vs 백분위 변화 (Spearman) ===")
    pr(summ_df.to_string(index=False))

    pr("\n=== 기존 장소 추가 설치 예시(2021→2024, 도심) ===")
    k = KIND[(2021, 2024)]
    ex = [i for i in k[k == OLD_SITE].index if st_gu.get(i) in DOWNTOWN][:10]
    for i in ex:
        pr(f"  {i} {ADDR.get(i)}  +{int(S[2024][i])}기")
    figures(gdf, gu_poly, oa_df, S, XY, st_gu, KIND)
    pr(f"\n저장: {CSV_DIR}\n      {FIG_DIR}")


def figures(gdf, gu_poly, oa_df, S, XY, st_gu, KIND):
    INK = "#222222"
    dt = gu_poly[gu_poly.gu.isin(DOWNTOWN)].dissolve()
    # (1) 전환별 신규 충전기 위치 1×3
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.2))
    for ax, (y0, y1) in zip(axes, TRANSITIONS[:3]):
        gu_poly.plot(ax=ax, facecolor="#f4f4f2", edgecolor="#9a9a94", linewidth=0.4)
        dt.plot(ax=ax, facecolor="#e2dccd", edgecolor="none")
        gu_poly.boundary.plot(ax=ax, color="#9a9a94", linewidth=0.4)
        ids = S[y1].index.union(S[y0].index)
        dS = S[y1].reindex(ids).fillna(0) - S[y0].reindex(ids).fillna(0)
        add = dS[dS > 0]
        xy = gpd.GeoSeries(gpd.points_from_xy([XY[i][0] for i in add.index], [XY[i][1] for i in add.index]), crs="EPSG:4326").to_crs(gu_poly.crs)
        new = (KIND[(y0, y1)].reindex(add.index) == NEW_SITE).values
        ax.scatter(xy.x[~new], xy.y[~new], s=add[~new].values * 9, facecolor="#2b8cbe", edgecolor="white", linewidth=0.3, alpha=0.85, zorder=3)
        ax.scatter(xy.x[new], xy.y[new], s=add[new].values * 9, facecolor="#e8590c", edgecolor="white", linewidth=0.3, alpha=0.85, zorder=3)
        ax.set_title(f"{y0}→{y1}년 추가 급속충전기 {int(add.sum()):,}기", fontsize=12, loc="left", color=INK)
        ax.set_axis_off()
    h = [Line2D([], [], marker="o", ls="", markerfacecolor="#e8590c", markeredgecolor="white", markersize=8, label="새 장소"),
         Line2D([], [], marker="o", ls="", markerfacecolor="#2b8cbe", markeredgecolor="white", markersize=8, label=f"기존 장소 추가 설치(같은 주소 또는 {SITE_M}m 이내)"),
         Line2D([], [], marker="s", ls="", markerfacecolor="#e2dccd", markeredgecolor="#999", markersize=10, label="도심(종로구·중구)")]
    fig.legend(handles=h, loc="lower center", ncol=3, frameon=False, fontsize=10, title="점 크기 = 추가된 급속충전기 대수")
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(f"{FIG_DIR}/신규공급_위치_연도별.png", dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    # (2) 2021→2024 접근성 백분위 변화(집계구)
    sub = oa_df[oa_df.transition == "2021-2024"].set_index("oa_code")
    v = sub.dpct.reindex(gdf["TOT_REG_CD"]).values
    fig, ax = plt.subplots(figsize=(8.5, 7.4))
    g2 = gdf.assign(v=v)
    g2.plot(ax=ax, column="v", cmap="RdBu", vmin=-50, vmax=50, linewidth=0, legend=True,
            legend_kwds={"shrink": 0.6, "label": "서울 내 접근성 백분위 변화(2021→2024, %p)"})
    gu_poly.boundary.plot(ax=ax, color="#555555", linewidth=0.5)
    dt.boundary.plot(ax=ax, color=INK, linewidth=1.4)
    ax.set_axis_off()
    fig.savefig(f"{FIG_DIR}/접근성_백분위변화_2021-2024.png", dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
