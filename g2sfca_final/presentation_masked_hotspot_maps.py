"""
2026-10-14: 산림(비거주지) 마스킹 Gi*(k=20) Hot/Cold 지도 — 최종(nonpublic) 버전.

분석(2SFCA·Gi*)은 집계구 전체 그대로이고, 지도 표현에서만 산림 위를 덮음.
넓은 산지 집계구가 Hot/Cold로 칠해져 실제보다 넓어 보이는 착시를 줄이기 위함
(예: 서초·강남 남부 그린벨트 — 실제 Hot은 세곡·내곡·양재 주거지).

산림 레이어: OpenStreetMap landuse=forest, natural=wood (osmnx, 2026-10-14 다운로드),
서울 경계로 clip, 2만m² 미만 조각 제외 → input/raw/osm_forest/seoul_forest_osm.gpkg

그림 1 (presentation_masked_grid_k20.png): 2021~2024 마스킹 지도
그림 2 (presentation_masked_2024_compare_k20.png): 2024 마스킹 전/후 비교
그림 3 (presentation_unmasked_grid_k20.png): 그림 1과 같은 레이아웃, 마스킹 없음
"""
import os

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from recheck_uselimitation_week_day import YEARS, NAS
from presentation_nonpublic_exclusion_maps import (
    load_boundary, fill_by, CLASS_COLOR, GI_FP, SUMMARY_FP, GU_LINE, INK, MUTED,
    HOT_COLOR, COLD_COLOR, NOTSIG_COLOR,
)

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

FOREST_FP = f"{NAS}/input/raw/osm_forest/seoul_forest_osm.gpkg"
GRID_FP = f"{NAS}/new_output/presentation_masked_grid_k20.png"
COMPARE_FP = f"{NAS}/new_output/presentation_masked_2024_compare_k20.png"
UNMASKED_GRID_FP = f"{NAS}/new_output/presentation_unmasked_grid_k20.png"

FOREST_COLOR = "#b7c4a6"
VERSION = "nonpublic"


def draw(ax, gdf, gu, classes, forest=None):
    fill_by(ax, gdf, classes, CLASS_COLOR)
    if forest is not None:
        forest.plot(ax=ax, color=FOREST_COLOR, linewidth=0)
    gu.boundary.plot(ax=ax, color=GU_LINE, linewidth=0.35)
    ax.set_axis_off()


def legend_handles(with_forest=True):
    h = [mpatches.Patch(color=HOT_COLOR, label="Hot Spot (p<0.05)"),
         mpatches.Patch(color=COLD_COLOR, label="Cold Spot (p<0.05)"),
         mpatches.Patch(facecolor=NOTSIG_COLOR, edgecolor="#bbb", label="Not Sig")]
    if with_forest:
        h.append(mpatches.Patch(color=FOREST_COLOR, label="산림(비거주지, 표현만 마스킹)"))
    return h


def plot_grid(gdf, gu, gi, summary, forest, out_fp):
    masked = forest is not None
    fig, axes = plt.subplots(1, 4, figsize=(20, 5.6))
    for ax, year in zip(axes, YEARS):
        cls = gi[gi.year == year].set_index("oa_code")[VERSION].reindex(gdf["TOT_REG_CD"]).values
        draw(ax, gdf, gu, cls, forest)
        s = summary[(summary.year == year) & (summary.version == VERSION)].iloc[0]
        ax.set_title(str(year), fontsize=15, color=INK, fontweight="bold", pad=8)
        ax.text(0.5, -0.02, f"공급 {int(s.chargers):,}기 · Hot {s.hot:,} · Cold {s.cold:,}", transform=ax.transAxes,
                ha="center", va="top", fontsize=10, color=MUTED)
    head = "Gi* 핫스팟 — 산림 마스킹" if masked else "Gi* 핫스팟"
    fig.suptitle(f"{head} (평일 낮 11–13시, 2SFCA, KNN k=20, 비공용 충전기 제외)",
                 fontsize=16, color=INK, fontweight="bold", y=1.0)
    fig.legend(handles=legend_handles(masked), loc="lower center", ncol=4, frameon=False, fontsize=11,
               bbox_to_anchor=(0.5, -0.06))
    if masked:
        fig.text(0.5, -0.1, "주: 분석은 집계구 전체 기준이며 산림은 지도 표현에서만 덮음. 산림: OpenStreetMap landuse=forest·natural=wood.",
                 ha="center", fontsize=9, color=MUTED)
    fig.subplots_adjust(wspace=0.02)
    fig.savefig(out_fp, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f">> 저장: {out_fp}")


def plot_compare(gdf, gu, gi, forest):
    cls = gi[gi.year == 2024].set_index("oa_code")[VERSION].reindex(gdf["TOT_REG_CD"]).values
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.4))
    draw(axes[0], gdf, gu, cls)
    axes[0].set_title("2024 마스킹 전", fontsize=14, color=INK, fontweight="bold", pad=8)
    draw(axes[1], gdf, gu, cls, forest)
    axes[1].set_title("2024 산림 마스킹 후", fontsize=14, color=INK, fontweight="bold", pad=8)
    for name, r in gu.iterrows():
        c = r.geometry.representative_point()
        axes[1].text(c.x, c.y, name, fontsize=7.5, color=INK, ha="center", va="center", zorder=4,
                     bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.6))
    fig.suptitle("산림(비거주지) 마스킹 전후 — 같은 결과, 표현만 다름", fontsize=16, color=INK,
                 fontweight="bold", y=0.99)
    fig.legend(handles=legend_handles(), loc="lower center", ncol=4, frameon=False, fontsize=11,
               bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(wspace=0.02)
    fig.savefig(COMPARE_FP, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f">> 저장: {COMPARE_FP}")


def main():
    gdf, gu = load_boundary()
    forest = gpd.read_file(FOREST_FP).to_crs(gdf.crs)
    gi = pd.read_csv(GI_FP, dtype={"oa_code": str})
    summary = pd.read_csv(SUMMARY_FP)

    # 산림에 덮이는 Hot/Cold 면적 비중 (2024)
    g24 = gdf.assign(c=gi[gi.year == 2024].set_index("oa_code")[VERSION].reindex(gdf["TOT_REG_CD"]).values)
    inter = gpd.overlay(g24[["c", "geometry"]], forest[["geometry"]], how="intersection")
    cov = (inter.area.groupby(inter["c"]).sum() / g24.area.groupby(g24["c"]).sum() * 100).round(1)
    print(f">> 2024 분류별 면적 중 산림 비중(%): {cov.to_dict()}")

    plot_grid(gdf, gu, gi, summary, forest, GRID_FP)
    plot_grid(gdf, gu, gi, summary, None, UNMASKED_GRID_FP)
    plot_compare(gdf, gu, gi, forest)


if __name__ == "__main__":
    main()
