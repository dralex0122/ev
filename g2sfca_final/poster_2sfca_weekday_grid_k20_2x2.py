"""
포스터 그림 4 교체용 — Gaussian 2SFCA 접근성 점수 + Gi* (KNN k=20) Hot/Cold 경계, 2x2 배치.

포스터 그림 4는 k=30 경계(poster_2sfca_weekday_grid_mw.png)를 쓰고 있었으나 본문은 k=20.
입력은 2026-10-01 presentation_hotspot_interpretation.py(커밋 449aed7)와 동일:
  - 점수: g2sfca_sfast_final_gaussian (비공용 제외 전, 포스터 공급 수치와 같은 기준)
  - Gi*: gi_star_knn_sensitivity_2sfca.csv 중 model=2SFCA, k=20
배경 스타일(Natural Breaks k=15, 4개년 공통 스케일, 그레이스케일)도 동일.
레이아웃만 포스터 편집본처럼 2x2 + 하단 2열 범례, 제목 없음, 2021 패널에 방위표·축척.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import mapclassify
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.cm import Greys
from matplotlib.colors import Normalize

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
GI_FP = f"{NAS}/output/gi_star_knn_sensitivity_2sfca.csv"
SCORE_PATH = lambda y: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{y}_week_낮_normal.csv"
OUT_FP = f"{NAS}/output/maps/poster_2sfca_weekday_grid_k20_2x2.png"

YEARS = [2021, 2022, 2023, 2024]
K = 20
K_CLASSES = 15
BORDER = "#c9c2ae"
HOT_COLOR = "#d7301f"
COLD_COLOR = "#1f5fbf"
INK = "#1a1a1a"


def load_boundary():
    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    return gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)


def north_arrow(ax, x=0.07, y=0.86, size=0.07):
    ax.annotate("", xy=(x, y + size), xytext=(x, y), xycoords="axes fraction",
                arrowprops=dict(facecolor=INK, edgecolor=INK, width=2.2, headwidth=10, headlength=11))
    ax.text(x, y + size + 0.015, "N", transform=ax.transAxes, ha="center", va="bottom",
            fontsize=13, fontweight="bold", color=INK)


def scale_bar(ax, x0_frac=0.04, y_frac=0.04, seg_m=2500, n=2):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    sx = x0 + (x1 - x0) * x0_frac
    sy = y0 + (y1 - y0) * y_frac
    h = (y1 - y0) * 0.012
    for i in range(n):
        ax.add_patch(mpatches.Rectangle((sx + i * seg_m, sy), seg_m, h,
                                        facecolor=INK if i % 2 == 0 else "white", edgecolor=INK, linewidth=0.8))
    for i, lab in enumerate(["0", "2.5", "5 km"]):
        ax.text(sx + i * seg_m, sy + h * 1.6, lab, ha="center", va="bottom", fontsize=10, color=INK)


def main():
    gdf = load_boundary()
    gi = pd.read_csv(GI_FP, dtype={"oa_code": str})
    gi = gi[(gi["model"] == "2SFCA") & (gi["k"] == K)]
    scores = {y: pd.read_csv(SCORE_PATH(y), dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"]
              for y in YEARS}

    pooled = np.concatenate([scores[y].reindex(gdf["TOT_REG_CD"]).fillna(0).values for y in YEARS])
    bins = mapclassify.NaturalBreaks(pooled, k=K_CLASSES).bins
    norm = Normalize(vmin=0, vmax=K_CLASSES - 1)

    fig, axes = plt.subplots(2, 2, figsize=(11, 10.6))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.11, wspace=0.03, hspace=0.08)
    for ax, year in zip(axes.flat, YEARS):
        g = gdf.copy()
        g["score"] = scores[year].reindex(g["TOT_REG_CD"]).fillna(0).values
        g["cls"] = np.digitize(g["score"], bins[:-1], right=True)
        g.plot(ax=ax, color=[Greys(norm(v)) for v in g["cls"]], edgecolor=BORDER, linewidth=0.05)

        sub = gi[gi["year"] == year].set_index("oa_code")
        g["gi_class"] = g["TOT_REG_CD"].map(sub["gi_class"])
        dissolved = g.dissolve(by="gi_class")
        dissolved["geometry"] = dissolved.geometry.buffer(1).buffer(-1)
        if "Hot Spot" in dissolved.index:
            dissolved.loc[["Hot Spot"]].boundary.plot(ax=ax, color=HOT_COLOR, linewidth=1.6)
        if "Cold Spot" in dissolved.index:
            dissolved.loc[["Cold Spot"]].boundary.plot(ax=ax, color=COLD_COLOR, linewidth=1.6)
        ax.set_axis_off()
        ax.set_aspect("equal")
        ax.set_title(f"{year}", fontsize=17, color=INK, fontweight="bold", pad=4)
        if year == 2021:
            north_arrow(ax)
            scale_bar(ax)

    handles = [
        Line2D([0], [0], color=HOT_COLOR, linewidth=2, label="Hot Spot (p < 0.05)"),
        Line2D([0], [0], color=COLD_COLOR, linewidth=2, label="Cold Spot (p < 0.05)"),
        mpatches.Patch(facecolor=Greys(0.15), edgecolor=BORDER, label="접근성 낮음 (Low)"),
        mpatches.Patch(facecolor=Greys(1.0), edgecolor=BORDER, label="접근성 높음 (High)"),
    ]
    fig.legend(handles=[handles[0], handles[2], handles[1], handles[3]], loc="lower center", ncol=2,
               frameon=False, fontsize=13, handlelength=2.6, columnspacing=4, bbox_to_anchor=(0.5, 0.015))
    fig.savefig(OUT_FP, dpi=220, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"saved {OUT_FP}")

    counts = gi.groupby(["year", "gi_class"]).size().unstack(fill_value=0)
    print(counts)


if __name__ == "__main__":
    main()
