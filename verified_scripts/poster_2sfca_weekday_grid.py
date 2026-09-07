"""
포스터 Option A(시계열 변화) 전용 — 2SFCA 단일모형 × week_낮_normal만, 1행×4열
(2021~2024). 기존 g2sfca_final_gaussian_16maps.png는 4개 시나리오(16장)라
스코프 축소 결정([[scenario_scope_week_day_only]])과 안 맞아서 대체.

배경·경계선 스타일은 plot_two_model_fig4.py와 동일(natural breaks k=15 +
Gi* 경계 오버레이) — 모형 하나만 뺀 버전.
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
HOTSPOT_FP = f"{NAS}/output/two_model_hotspot_k30.csv"
OUT_FP = f"{NAS}/output/maps/poster_2sfca_weekday_grid.png"

YEARS = [2021, 2022, 2023, 2024]
SCORE_PATH = lambda year: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{year}_week_낮_normal.csv"

K_CLASSES = 15
BORDER = "#c9c2ae"
HOT_COLOR = "#e60000"
COLD_COLOR = "#0047ab"
INK = "#2b2b2b"
MUTED = "#7a7568"


def load_boundary():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)
    return gdf


def main():
    gdf = load_boundary()
    hs = pd.read_csv(HOTSPOT_FP, dtype={"oa_code": str})
    hs = hs[hs["model"] == "2SFCA"]

    by_year = {}
    for year in YEARS:
        acc = pd.read_csv(SCORE_PATH(year), dtype={"oa_code": str})
        acc = acc.set_index("oa_code").reindex(gdf["TOT_REG_CD"])["accessibility_score"].fillna(0)
        by_year[year] = acc.values
    pooled = np.concatenate(list(by_year.values()))
    nb = mapclassify.NaturalBreaks(pooled, k=K_CLASSES)
    bins = nb.bins
    norm = Normalize(vmin=0, vmax=K_CLASSES - 1)

    fig, axes = plt.subplots(1, len(YEARS), figsize=(20, 6.2))
    for c, year in enumerate(YEARS):
        ax = axes[c]
        g = gdf.copy()
        g["score"] = by_year[year]
        g["cls"] = np.digitize(g["score"], bins[:-1], right=True)
        g["gray"] = [Greys(norm(v)) for v in g["cls"]]
        g.plot(ax=ax, color=g["gray"], edgecolor=BORDER, linewidth=0.08)

        sub = hs[hs["year"] == year].set_index("oa_code")
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
    fig.text(0.5, 0.96, "배경: Natural Breaks(Jenks, k=15) 그레이스케일 · 4개년 공통 스케일  |  경계선: KNN(k=30) Gi* Hot/Cold, p<0.05",
              ha="center", fontsize=10, color=MUTED)

    legend_ax = fig.add_axes([0.32, -0.04, 0.36, 0.05])
    legend_ax.axis("off")
    handles = [
        mpatches.Patch(facecolor=Greys(0.0), edgecolor=BORDER, label="접근성 낮음"),
        mpatches.Patch(facecolor=Greys(1.0), edgecolor=BORDER, label="접근성 높음"),
        Line2D([0], [0], color=HOT_COLOR, linewidth=1.5, label="Hot Spot 경계"),
        Line2D([0], [0], color=COLD_COLOR, linewidth=1.5, label="Cold Spot 경계"),
    ]
    legend_ax.legend(handles=handles, loc="center", ncol=4, frameon=False, fontsize=10)

    fig.savefig(OUT_FP, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"saved {OUT_FP}")


if __name__ == "__main__":
    main()
