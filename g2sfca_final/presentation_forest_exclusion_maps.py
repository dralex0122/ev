"""
2026-10-14: 산지 집계구 제외 민감도 지도 — 최종(nonpublic) vs 산림 50% 이상 집계구 제외.

입력은 recompute_exclude_forest_oa.py 산출물(gi_k20_noforest.csv, forest_exclusion_summary.csv).
제외된 집계구는 '분석 제외'로 따로 칠함.

그림 (presentation_forest_exclusion_grid_k20.png): 2행(최종 / 산지 제외) x 4열(2021~2024)
"""
import os

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from recheck_uselimitation_week_day import YEARS, NAS, OUT_DIR
from presentation_nonpublic_exclusion_maps import (
    load_boundary, fill_by, CLASS_COLOR, GI_FP, SUMMARY_FP, GU_LINE, INK, MUTED,
    HOT_COLOR, COLD_COLOR, NOTSIG_COLOR,
)

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

THRESHOLD = 0.5
NOFOREST_FP = f"{OUT_DIR}/gi_k20_noforest.csv"
FOREST_SUMMARY_FP = f"{OUT_DIR}/forest_exclusion_summary.csv"
OUT_FP = f"{NAS}/new_output/presentation_forest_exclusion_grid_k20.png"

EXCLUDED = "분석 제외"
EXCLUDED_COLOR = "#b7c4a6"
COLORS = {**CLASS_COLOR, EXCLUDED: EXCLUDED_COLOR}


def main():
    gdf, gu = load_boundary()
    gi = pd.read_csv(GI_FP, dtype={"oa_code": str})
    nf = pd.read_csv(NOFOREST_FP, dtype={"oa_code": str})
    nf = nf[nf.threshold == THRESHOLD]
    summary = pd.read_csv(SUMMARY_FP)
    fsum = pd.read_csv(FOREST_SUMMARY_FP)
    fsum = fsum[fsum.threshold == THRESHOLD]

    rows = [("최종\n(집계구 전체)", "ref"), (f"산지 집계구 제외\n(산림 {int(THRESHOLD * 100)}% 이상)", "noforest")]
    fig, axes = plt.subplots(2, 4, figsize=(18, 9.4))
    for r, (label, kind) in enumerate(rows):
        for c, year in enumerate(YEARS):
            ax = axes[r, c]
            if kind == "ref":
                cls = gi[gi.year == year].set_index("oa_code").nonpublic.reindex(gdf["TOT_REG_CD"]).values
                s = summary[(summary.year == year) & (summary.version == "nonpublic")].iloc[0]
                note = f"Hot {s.hot:,} · Cold {s.cold:,}"
            else:
                cls = nf[nf.year == year].set_index("oa_code").noforest.reindex(gdf["TOT_REG_CD"]).fillna(EXCLUDED).values
                s = fsum[fsum.year == year].iloc[0]
                note = f"Hot {int(s.hot):,} · Cold {int(s.cold):,} · 분류 변경 {s.changed_pct:.1f}%"
            fill_by(ax, gdf, cls, COLORS)
            gu.boundary.plot(ax=ax, color=GU_LINE, linewidth=0.35)
            ax.set_axis_off()
            ax.text(0.5, -0.02, note, transform=ax.transAxes, ha="center", va="top", fontsize=10, color=MUTED)
            if r == 0:
                ax.set_title(str(year), fontsize=15, color=INK, fontweight="bold", pad=8)
            if c == 0:
                ax.text(-0.08, 0.5, label, transform=ax.transAxes, ha="right", va="center",
                        fontsize=13, color=INK, fontweight="bold")

    n_removed = int(fsum.n_removed.iloc[0])
    fig.suptitle("산지 집계구 제외 민감도 — Gi* 핫스팟 (평일 낮 11–13시, 2SFCA, KNN k=20, 비공용 충전기 제외)",
                 fontsize=16, color=INK, fontweight="bold", y=0.995)
    handles = [mpatches.Patch(color=HOT_COLOR, label="Hot Spot (p<0.05)"),
               mpatches.Patch(color=COLD_COLOR, label="Cold Spot (p<0.05)"),
               mpatches.Patch(facecolor=NOTSIG_COLOR, edgecolor="#bbb", label="Not Sig"),
               mpatches.Patch(color=EXCLUDED_COLOR, label=f"분석 제외 집계구 {n_removed}곳")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=12, bbox_to_anchor=(0.5, -0.01))
    fig.text(0.5, -0.04, "주: 산림 비율 = OpenStreetMap landuse=forest·natural=wood 면적 / 집계구 면적. "
             "제외 집계구는 수요·OD에서 빼고 남은 집계구로 KNN 이웃 재구성. 분류 변경 = 남은 집계구 중 최종 대비 분류가 바뀐 비율.",
             ha="center", fontsize=9, color=MUTED)
    fig.subplots_adjust(left=0.1, right=0.99, top=0.93, bottom=0.05, wspace=0.02, hspace=0.12)
    fig.savefig(OUT_FP, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f">> 저장: {OUT_FP}")


if __name__ == "__main__":
    main()
