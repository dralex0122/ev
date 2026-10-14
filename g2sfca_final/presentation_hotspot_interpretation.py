"""
12월 지도학회 발표 준비(2026-09-30 랩미팅: "왜 바뀌었는지 해석") — 2SFCA 단일모형 × week_낮_normal.

1. Gi* KNN k=20 기준 4개년 지도 재작성 (포스터 그림 4는 k=30 파일을 읽고 있었음)
2. 핫스팟 변화 정리: 연도별 분류 수, 연도쌍 전이행렬, 4개년 궤적 유형, 구별 Hot/Cold 수
3. 구별 절대 점수 vs 상대 위치(서울 평균 대비) + 유효 공급·수요 추이 → 축소가 절대 하락인지 상대 하락인지

유효 공급은 g2sfca_final_supply.py와 동일 규칙(급속만, 아파트 v3 제외, 평일 11-13시 운영).
연도별 스냅샷은 2024 데이터 설치연도 누적 필터라 철거 충전기가 빠져 있음 → 공급 감소는 원천적으로 관측 불가.

2026-10-14: 비공용 충전기 제외 최종 버전(nonpublic)으로 전환 — 이용제한(UseLimitation=Y) +
운수사·전용 키워드 26곳 제외(recompute_exclude_nonpublic.py). 제외 전 산출물은 output/presentation_k20에 남아 있음.
"""
import json
import os
import sys
import unicodedata

import numpy as np
import pandas as pd
import geopandas as gpd
import mapclassify
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.cm import Greys
from matplotlib.colors import Normalize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g2sfca_final_supply import parse_open_window, is_open, APT_FP, D1_FP, CHARGER_DIR_FASTONLY
from hotspot_transition import GU_MAP

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
RECHECK_DIR = f"{NAS}/output/recheck_2026-10-13"
GI_FP = f"{RECHECK_DIR}/gi_k20_3ver.csv"
CAND_FP = f"{RECHECK_DIR}/nonpublic_keyword_candidates.csv"
SCORE_PATH = lambda y: f"{NAS}/output/g2sfca_sfast_final_gaussian_nonpublic/g2sfca_score_{y}_week_낮_normal.csv"
OUT_DIR = f"{NAS}/output/presentation_k20_nonpublic"
MAP_FP = f"{NAS}/new_output/presentation_2sfca_weekday_grid_k20.png"
GU_FIG_FP = f"{NAS}/new_output/presentation_gu_relative_position_k20.png"

YEARS = [2021, 2022, 2023, 2024]
K = 20
K_CLASSES = 15
BORDER = "#c9c2ae"
HOT_COLOR = "#e60000"
COLD_COLOR = "#0047ab"
INK = "#2b2b2b"
MUTED = "#7a7568"
SHORT = {"Hot Spot": "H", "Cold Spot": "C", "Not Sig": "N"}


def load_boundary():
    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)
    return gdf


def plot_map(gdf, gi, scores):
    pooled = np.concatenate([scores[y].reindex(gdf["TOT_REG_CD"]).fillna(0).values for y in YEARS])
    bins = mapclassify.NaturalBreaks(pooled, k=K_CLASSES).bins
    norm = Normalize(vmin=0, vmax=K_CLASSES - 1)

    fig, axes = plt.subplots(1, len(YEARS), figsize=(20, 5.2))
    for ax, year in zip(axes, YEARS):
        g = gdf.copy()
        g["score"] = scores[year].reindex(g["TOT_REG_CD"]).fillna(0).values
        g["cls"] = np.digitize(g["score"], bins[:-1], right=True)
        g.plot(ax=ax, color=[Greys(norm(v)) for v in g["cls"]], edgecolor=BORDER, linewidth=0.08)

        sub = gi[gi["year"] == year].set_index("oa_code")
        g["gi_class"] = g["TOT_REG_CD"].map(sub["gi_class"])
        dissolved = g.dissolve(by="gi_class")
        dissolved["geometry"] = dissolved.geometry.buffer(1).buffer(-1)
        if "Hot Spot" in dissolved.index:
            dissolved.loc[["Hot Spot"]].boundary.plot(ax=ax, color=HOT_COLOR, linewidth=1.1)
        if "Cold Spot" in dissolved.index:
            dissolved.loc[["Cold Spot"]].boundary.plot(ax=ax, color=COLD_COLOR, linewidth=1.1)
        ax.set_axis_off()
        ax.set_title(f"{year}", fontsize=14, color=INK, fontweight="bold", pad=6)

    fig.suptitle("Gaussian 2SFCA — 접근성 점수(자연분류) + Gi* 경계 오버레이 (평일 낮, 2021~2024)",
                 fontsize=16, color=INK, fontweight="bold", y=1.04)
    fig.text(0.5, 0.96, f"배경: Natural Breaks(Jenks, k={K_CLASSES}) 그레이스케일 · 4개년 공통 스케일  |  경계선: KNN(k={K}) Gi* Hot/Cold, p<0.05",
             ha="center", fontsize=10, color=MUTED)
    legend_ax = fig.add_axes([0.32, 0.02, 0.36, 0.05])
    legend_ax.axis("off")
    handles = [
        mpatches.Patch(facecolor=Greys(0.0), edgecolor=BORDER, label="접근성 낮음"),
        mpatches.Patch(facecolor=Greys(1.0), edgecolor=BORDER, label="접근성 높음"),
        Line2D([0], [0], color=HOT_COLOR, linewidth=1.5, label="Hot Spot 경계"),
        Line2D([0], [0], color=COLD_COLOR, linewidth=1.5, label="Cold Spot 경계"),
    ]
    legend_ax.legend(handles=handles, loc="center", ncol=4, frameon=False, fontsize=10)
    fig.savefig(MAP_FP, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"saved {MAP_FP}")


def trajectory_type(traj):
    s = traj.replace("-", "")
    if s == "HHHH":
        return "지속핫"
    if s == "CCCC":
        return "지속콜드"
    if s == "NNNN":
        return "지속비유의"
    if "H" in s and "C" in s:
        return "핫↔콜드 반전"
    if "H" in s:
        if s[0] == "H" and s[-1] != "H":
            return "핫 소멸"
        if s[0] != "H" and s[-1] == "H":
            return "핫 신규"
        return "핫 간헐"
    if "C" in s:
        if s[0] == "C" and s[-1] != "C":
            return "콜드 탈출"
        if s[0] != "C" and s[-1] == "C":
            return "콜드 신규"
        return "콜드 간헐"
    return "기타"


def transitions(gdf, gi):
    piv = gi.pivot(index="oa_code", columns="year", values="gi_class")
    counts = gi.groupby(["year", "gi_class"]).size().unstack().reindex(columns=["Hot Spot", "Not Sig", "Cold Spot"])
    counts.to_csv(f"{OUT_DIR}/gi_class_counts_by_year.csv", encoding="utf-8-sig")
    print("\n=== 연도별 Gi* 분류 수 (k=20) ===\n", counts)

    rows = []
    for a, b in [(2021, 2022), (2022, 2023), (2023, 2024), (2021, 2024)]:
        m = pd.crosstab(piv[a], piv[b])
        print(f"\n=== 전이행렬 {a}→{b} ===\n", m)
        for fr in m.index:
            for to in m.columns:
                rows.append({"from_year": a, "to_year": b, "from": fr, "to": to, "n": int(m.loc[fr, to])})
    pd.DataFrame(rows).to_csv(f"{OUT_DIR}/transition_matrices.csv", index=False, encoding="utf-8-sig")

    traj = piv[YEARS].apply(lambda r: "-".join(SHORT[v] for v in r), axis=1).rename("trajectory").to_frame()
    traj["type"] = traj["trajectory"].map(trajectory_type)
    traj = traj.join(gdf.set_index("TOT_REG_CD")[["ADM_NM", "gu"]])
    traj.reset_index().rename(columns={"index": "oa_code"}).to_csv(f"{OUT_DIR}/trajectory_by_oa.csv", index=False, encoding="utf-8-sig")
    print("\n=== 4개년 궤적 유형 ===\n", traj["type"].value_counts())
    print("\n=== 상위 궤적 패턴 ===\n", traj["trajectory"].value_counts().head(15))

    gu_type = traj.groupby(["gu", "type"]).size().unstack(fill_value=0)
    gu_type.to_csv(f"{OUT_DIR}/trajectory_type_by_gu.csv", encoding="utf-8-sig")

    gi2 = gi.merge(gdf[["TOT_REG_CD", "gu"]], left_on="oa_code", right_on="TOT_REG_CD")
    gu_cnt = gi2.groupby(["gu", "year", "gi_class"]).size().unstack(fill_value=0)
    gu_wide = gu_cnt.unstack("year")
    gu_wide.columns = [f"{c}_{y}" for c, y in gu_wide.columns]
    gu_wide["hot_change_21_24"] = gu_wide["Hot Spot_2024"] - gu_wide["Hot Spot_2021"]
    gu_wide["cold_change_21_24"] = gu_wide["Cold Spot_2024"] - gu_wide["Cold Spot_2021"]
    gu_wide.sort_values("hot_change_21_24").to_csv(f"{OUT_DIR}/gu_hot_cold_counts.csv", encoding="utf-8-sig")
    print("\n=== 구별 Hot/Cold 변화 (2021→2024) ===\n",
          gu_wide[["Hot Spot_2021", "Hot Spot_2024", "hot_change_21_24", "Cold Spot_2021", "Cold Spot_2024", "cold_change_21_24"]]
          .sort_values("hot_change_21_24").to_string())
    return traj


def effective_supply_by_gu(gdf):
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl_set = apt_set | set(cand[cand.final_label == "제외"].station_id)
    rows = []
    for year in YEARS:
        fp = unicodedata.normalize("NFD", os.path.join(CHARGER_DIR_FASTONLY, f"metro7_ev_chargers_{year}_fastonly.geojson"))
        if not os.path.exists(fp):
            fp = os.path.join(CHARGER_DIR_FASTONLY, f"metro7_ev_chargers_{year}_fastonly.geojson")
        ch = gpd.read_file(fp)
        ch = ch[ch["city"] == "서울특별시"].to_crs(5179)
        ch["station_id"] = ch["station_id"].astype(str)
        ch["eff"] = [
            0 if (sid in excl_set or ul == "Y" or not is_open(parse_open_window(oh or ""), 11, 13, "week")) else (fc or 0)
            for sid, ul, oh, fc in zip(ch["station_id"], ch["UseLimitation"], ch["openinghour"], ch["fast_count"])
        ]
        j = gpd.sjoin(ch, gdf[["gu", "geometry"]], how="left", predicate="within")
        agg = j.groupby("gu").agg(fast_all=("fast_count", "sum"), fast_eff=("eff", "sum"),
                                  stations_eff=("eff", lambda s: int((s > 0).sum())))
        agg["year"] = year
        rows.append(agg.reset_index())
        print(f"{year}: 서울 급속 {int(ch['fast_count'].sum())}기 / 유효(비아파트·낮운영·공용) {int(ch['eff'].sum())}기, 구 미매칭 {int(j['gu'].isna().sum())}개소")
    return pd.concat(rows, ignore_index=True)


def gu_position(gdf, scores, traj):
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    oa_gu = gdf.set_index("TOT_REG_CD")["gu"]
    rows = []
    for year in YEARS:
        s = scores[year].rename("score").to_frame()
        s["gu"] = s.index.map(oa_gu)
        dem = d1[d1["year"] == year].set_index("집계구코드")["낮_avg"]
        s["demand"] = dem.reindex(s.index).fillna(0)
        seoul_mean = s["score"].mean()
        seoul_wmean = np.average(s["score"], weights=s["demand"]) if s["demand"].sum() > 0 else np.nan
        g = s.groupby("gu")[["score", "demand"]].apply(lambda x: pd.Series({
            "mean_score": x["score"].mean(),
            "pop_weighted_score": np.average(x["score"], weights=x["demand"]) if x["demand"].sum() > 0 else np.nan,
            "demand_sum": x["demand"].sum(),
            "mean_z": ((x["score"] - seoul_mean) / s["score"].std()).mean(),
        }))
        g["year"] = year
        g["seoul_mean"] = seoul_mean
        g["seoul_pop_weighted"] = seoul_wmean
        g["relative_to_seoul"] = g["mean_score"] / seoul_mean
        g["rank"] = g["mean_score"].rank(ascending=False).astype(int)
        rows.append(g.reset_index())
    pos = pd.concat(rows, ignore_index=True)

    sup = effective_supply_by_gu(gdf)
    pos = pos.merge(sup, on=["gu", "year"], how="left")
    seoul_sup = pos.groupby("year")[["fast_eff", "demand_sum"]].sum()
    pos["supply_share"] = pos["fast_eff"] / pos["year"].map(seoul_sup["fast_eff"])
    pos["demand_share"] = pos["demand_sum"] / pos["year"].map(seoul_sup["demand_sum"])
    pos["eff_per_10k_demand"] = pos["fast_eff"] / pos["demand_sum"] * 1e4
    pos.to_csv(f"{OUT_DIR}/gu_score_supply_demand_by_year.csv", index=False, encoding="utf-8-sig")

    w = pos.pivot(index="gu", columns="year")
    summ = pd.DataFrame({
        "score_2021": w["mean_score"][2021], "score_2024": w["mean_score"][2024],
        "score_growth_x": w["mean_score"][2024] / w["mean_score"][2021],
        "rel_2021": w["relative_to_seoul"][2021], "rel_2024": w["relative_to_seoul"][2024],
        "rank_2021": w["rank"][2021], "rank_2022": w["rank"][2022], "rank_2023": w["rank"][2023], "rank_2024": w["rank"][2024],
        "eff_2021": w["fast_eff"][2021], "eff_2024": w["fast_eff"][2024],
        "eff_growth_x": w["fast_eff"][2024] / w["fast_eff"][2021],
        "supply_share_2021": w["supply_share"][2021], "supply_share_2024": w["supply_share"][2024],
        "demand_change_pct": (w["demand_sum"][2024] / w["demand_sum"][2021] - 1) * 100,
    })
    seoul_growth = pos.groupby("year")["seoul_mean"].first()
    summ["seoul_growth_x"] = seoul_growth[2024] / seoul_growth[2021]
    hot = pd.read_csv(f"{OUT_DIR}/gu_hot_cold_counts.csv", index_col=0)
    summ = summ.join(hot[["Hot Spot_2021", "Hot Spot_2024", "hot_change_21_24", "cold_change_21_24"]])
    summ["verdict"] = np.where(summ["score_growth_x"] < 1, "절대 하락",
                      np.where(summ["score_growth_x"] < summ["seoul_growth_x"], "절대 상승·상대 하락", "서울 평균 이상 상승"))
    summ = summ.sort_values("hot_change_21_24")
    summ.to_csv(f"{OUT_DIR}/gu_absolute_vs_relative_2021_2024.csv", encoding="utf-8-sig")
    pd.set_option("display.width", 250)
    print(f"\n서울 평균 점수 성장: {seoul_growth[2024] / seoul_growth[2021]:.2f}배")
    print("\n=== 구별 절대 vs 상대 (Hot 변화 오름차순) ===\n", summ.round(3).to_string())
    plot_gu(summ)


def plot_gu(summ):
    """구별 서울평균 대비 상대점수 2021→2024 덤벨. 2024년 핫스팟이 완전히 사라진 구만 강조."""
    s = summ.sort_values("rel_2024")
    focus = set(summ[(summ["Hot Spot_2021"] >= 50) & (summ["Hot Spot_2024"] == 0)].index)
    fig, ax = plt.subplots(figsize=(8, 9))
    y = np.arange(len(s))
    for yi, (gu, r) in zip(y, s.iterrows()):
        c = HOT_COLOR if gu in focus else "#9a958a"
        ax.plot([r.rel_2021, r.rel_2024], [yi, yi], color=c, linewidth=2, zorder=1)
        ax.scatter(r.rel_2021, yi, s=40, facecolor="white", edgecolor=c, linewidth=1.5, zorder=2)
        ax.scatter(r.rel_2024, yi, s=40, color=c, zorder=3)
    ax.axvline(1, color=MUTED, linewidth=0.8, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(s.index, fontsize=10, color=INK)
    for lbl in ax.get_yticklabels():
        if lbl.get_text() in focus:
            lbl.set_fontweight("bold")
    ax.set_xlabel("구 평균 접근성 / 서울 평균 (1 = 서울 평균)", color=INK)
    ax.set_title("구별 상대 접근성 변화 (평일 낮, 2021 ○ → 2024 ●)\n강조: 2024년 핫스팟이 모두 사라진 구 (2021년 핫스팟 50개 이상)",
                 fontsize=12, color=INK, loc="left")
    ax.grid(axis="x", color="#e6e2d8", linewidth=0.6)
    ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    fig.savefig(GU_FIG_FP, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"saved {GU_FIG_FP}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    gdf = load_boundary()
    gi = pd.read_csv(GI_FP, dtype={"oa_code": str}).rename(columns={"nonpublic": "gi_class"})[["year", "oa_code", "gi_class"]]
    scores = {y: pd.read_csv(SCORE_PATH(y), dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"] for y in YEARS}

    plot_map(gdf, gi, scores)
    traj = transitions(gdf, gi)
    gu_position(gdf, scores, traj)


if __name__ == "__main__":
    main()
