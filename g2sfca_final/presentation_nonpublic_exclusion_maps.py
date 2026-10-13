"""
2026-10-13 랩미팅 발표용: 비공용 충전기 제외 전/후 Gi*(k=20) Hot/Cold 지도.

그림 1 (presentation_nonpublic_3ver_grid_k20.png)
  3행(기존 / UseLimitation=Y 제외 / +운수사·회사 전용 제외) x 4열(2021~2024)
그림 2 (presentation_nonpublic_2024_change_k20.png)
  2024년 기존 vs 최종 분류 변화 + 제외된 충전소 위치(Y / 키워드 판정)

입력은 recheck_uselimitation_week_day.py, recompute_exclude_nonpublic.py 산출물.
"""
import os

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

from g2sfca_final_supply import APT_FP
from recheck_uselimitation_week_day import load_stations, BOUNDARY_FP, OUT_DIR, YEARS, GU_MAP, NAS

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

GI_FP = f"{OUT_DIR}/gi_k20_3ver.csv"
CAND_FP = f"{OUT_DIR}/nonpublic_keyword_candidates.csv"
SUMMARY_FP = f"{OUT_DIR}/hotspot_compare_3ver.csv"
GRID_FP = f"{NAS}/output/maps/presentation_nonpublic_3ver_grid_k20.png"
CHANGE_FP = f"{NAS}/output/maps/presentation_nonpublic_2024_change_k20.png"

HOT_COLOR = "#e60000"
COLD_COLOR = "#0047ab"
NOTSIG_COLOR = "#ecebe6"
GU_LINE = "#5c5850"
INK = "#2b2b2b"
MUTED = "#7a7568"
CLASS_COLOR = {"Hot Spot": HOT_COLOR, "Cold Spot": COLD_COLOR, "Not Sig": NOTSIG_COLOR}

VERSIONS = [
    ("before", "기존\n(이용제한 포함)"),
    ("nolimit", "이용제한(Y)\n제외"),
    ("nonpublic", "+ 운수사·전용\n제외 (최종)"),
]

CHANGE_COLOR = {
    "변화 없음": "#ecebe6",
    "Hot 이탈 (Hot에서 빠짐)": "#f4a582",
    "Hot 신규 (새로 Hot)": "#b2182b",
    "Cold 이탈 (Cold에서 빠짐)": "#92c5de",
    "Cold 신규 (새로 Cold)": "#2166ac",
}


def load_boundary():
    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)
    gu = gdf.dissolve(by="gu")
    gu["geometry"] = gu.geometry.buffer(1).buffer(-1)  # 집계구 사이 미세 틈 제거
    return gdf, gu


def draw_classes(ax, gdf, classes, gu):
    gdf.assign(c=classes).plot(ax=ax, color=[CLASS_COLOR[c] for c in classes], linewidth=0)
    gu.boundary.plot(ax=ax, color=GU_LINE, linewidth=0.35)
    ax.set_axis_off()


def plot_grid(gdf, gu, gi, summary):
    fig, axes = plt.subplots(3, 4, figsize=(18, 13.5))
    for r, (v, vlabel) in enumerate(VERSIONS):
        for c, year in enumerate(YEARS):
            ax = axes[r, c]
            cls = gi[gi.year == year].set_index("oa_code")[v].reindex(gdf["TOT_REG_CD"]).values
            draw_classes(ax, gdf, cls, gu)
            s = summary[(summary.year == year) & (summary.version == v)].iloc[0]
            sup = "" if pd.isna(s.chargers) else f"공급 {int(s.chargers):,}기 · "
            ax.text(0.5, -0.02, f"{sup}Hot {s.hot:,} · Cold {s.cold:,}", transform=ax.transAxes,
                    ha="center", va="top", fontsize=10, color=MUTED)
            if r == 0:
                ax.set_title(str(year), fontsize=15, color=INK, fontweight="bold", pad=8)
            if c == 0:
                ax.text(-0.08, 0.5, vlabel, transform=ax.transAxes, ha="right", va="center",
                        fontsize=13, color=INK, fontweight="bold")
    fig.suptitle("비공용 충전기 제외 전후 Gi* 핫스팟 (평일 낮 11–13시, 2SFCA, KNN k=20)",
                 fontsize=17, color=INK, fontweight="bold", y=0.995)
    handles = [mpatches.Patch(color=HOT_COLOR, label="Hot Spot (p<0.05)"),
               mpatches.Patch(color=COLD_COLOR, label="Cold Spot (p<0.05)"),
               mpatches.Patch(facecolor=NOTSIG_COLOR, edgecolor="#bbb", label="Not Sig")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=12,
               bbox_to_anchor=(0.5, -0.005))
    fig.subplots_adjust(left=0.1, right=0.99, top=0.95, bottom=0.05, wspace=0.02, hspace=0.12)
    fig.savefig(GRID_FP, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f">> 저장: {GRID_FP}")


def change_class(b, a):
    if b == a:
        return "변화 없음"
    if b == "Hot Spot":
        return "Hot 이탈 (Hot에서 빠짐)"
    if a == "Hot Spot":
        return "Hot 신규 (새로 Hot)"
    if b == "Cold Spot":
        return "Cold 이탈 (Cold에서 빠짐)"
    return "Cold 신규 (새로 Cold)"


def excluded_stations_2024():
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    kw_set = set(cand[cand.final_label == "제외"].station_id)
    st = load_stations(2024)
    eff = st[~st.station_id.isin(apt_set) & st.is_open].copy()
    eff["kind"] = np.where(eff.UseLimitation == "Y", "Y",
                  np.where(eff.station_id.isin(kw_set), "KW", None))
    ex = eff[eff.kind.notna()]
    pts = gpd.GeoDataFrame(ex, geometry=gpd.points_from_xy(ex.lng, ex.lat), crs=4326).to_crs(5179)
    return pts


def plot_change(gdf, gu, gi):
    g24 = gi[gi.year == 2024].set_index("oa_code").reindex(gdf["TOT_REG_CD"])
    chg = [change_class(b, a) for b, a in zip(g24["before"], g24["nonpublic"])]
    pts = excluded_stations_2024()

    fig, axes = plt.subplots(1, 3, figsize=(20, 6.6))
    for ax, v, title in [(axes[0], "before", "2024 기존 (이용제한 포함)"),
                         (axes[1], "nonpublic", "2024 최종 (비공용 제외)")]:
        draw_classes(ax, gdf, g24[v].values, gu)
        ax.set_title(title, fontsize=14, color=INK, fontweight="bold", pad=8)

    ax = axes[2]
    gdf.plot(ax=ax, color=[CHANGE_COLOR[c] for c in chg], linewidth=0)
    gu.boundary.plot(ax=ax, color=GU_LINE, linewidth=0.35)
    for kind, color, label in [("Y", "#1a1a1a", "이용제한(Y)"), ("KW", "#e08a00", "운수사·전용")]:
        p = pts[pts.kind == kind]
        ax.scatter(p.geometry.x, p.geometry.y, s=6 + p.fast_count * 5, facecolor=color,
                   edgecolor="white", linewidth=0.6, alpha=0.9, zorder=3)
    for name, r in gu.iterrows():
        c = r.geometry.representative_point()
        ax.text(c.x, c.y, name, fontsize=7.5, color=INK, ha="center", va="center", zorder=4,
                bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.6))
    ax.set_axis_off()
    ax.set_title("분류 변화 + 제외된 충전소 위치", fontsize=14, color=INK, fontweight="bold", pad=8)

    n_changed = sum(c != "변화 없음" for c in chg)
    fig.suptitle(f"2024년 비공용 충전기 제외 효과 — 집계구 {n_changed:,}곳({n_changed / len(chg) * 100:.1f}%) 분류 변경",
                 fontsize=16, color=INK, fontweight="bold", y=0.98)
    h1 = [mpatches.Patch(color=HOT_COLOR, label="Hot Spot"), mpatches.Patch(color=COLD_COLOR, label="Cold Spot"),
          mpatches.Patch(facecolor=NOTSIG_COLOR, edgecolor="#bbb", label="Not Sig")]
    h2 = [mpatches.Patch(facecolor=col, edgecolor="#bbb", label=lab) for lab, col in CHANGE_COLOR.items()]
    h3 = [Line2D([0], [0], marker="o", linestyle="", markerfacecolor="#1a1a1a", markeredgecolor="white",
                 markersize=8, label=f"이용제한(Y) {int((pts.kind == 'Y').sum())}곳 · {int(pts[pts.kind == 'Y'].fast_count.sum())}기"),
          Line2D([0], [0], marker="o", linestyle="", markerfacecolor="#e08a00", markeredgecolor="white",
                 markersize=8, label=f"운수사·전용 {int((pts.kind == 'KW').sum())}곳 · {int(pts[pts.kind == 'KW'].fast_count.sum())}기")]
    axes[0].legend(handles=h1, loc="upper center", ncol=3, frameon=False, fontsize=11, bbox_to_anchor=(1.0, -0.01))
    axes[2].legend(handles=h2 + h3, loc="upper center", ncol=2, frameon=False, fontsize=10, bbox_to_anchor=(0.5, -0.01))
    axes[2].text(0.5, -0.27, "점 크기 = 급속충전기 수", transform=axes[2].transAxes, ha="center", fontsize=9, color=MUTED)
    fig.subplots_adjust(wspace=0.02)
    fig.savefig(CHANGE_FP, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f">> 저장: {CHANGE_FP}")


def main():
    gdf, gu = load_boundary()
    gi = pd.read_csv(GI_FP, dtype={"oa_code": str})
    summary = pd.read_csv(SUMMARY_FP)
    plot_grid(gdf, gu, gi, summary)
    plot_change(gdf, gu, gi)


if __name__ == "__main__":
    main()
