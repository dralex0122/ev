"""
2026-11-11: 최종(비공용 제외) Gaussian 2SFCA 점수 + Gi(KNN k=20) Hot/Cold 경계, 2x2 배치.
presentation_hotspot_interpretation.py의 1x4 그림(new_output/presentation_2sfca_weekday_grid_k20.png)과
입력·분류·색이 같고 레이아웃만 poster_2sfca_weekday_grid_k20_2x2.py의 2x2 + 방위표·축척.
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
GI_FP = f"{NAS}/output/recheck_2026-10-13/gi_k20_3ver.csv"
SCORE_PATH = lambda y: f"{NAS}/output/g2sfca_sfast_final_gaussian_nonpublic/g2sfca_score_{y}_week_낮_normal.csv"
OUT_FP = f"{NAS}/new_output/presentation_2sfca_weekday_grid_k20_2x2.png"

YEARS = [2021, 2022, 2023, 2024]
K = 20
K_CLASSES = 15
BORDER = "#c9c2ae"
HOT_COLOR = "#e60000"
COLD_COLOR = "#0047ab"
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
    gi = gi.rename(columns={"nonpublic": "gi_class"})[["year", "oa_code", "gi_class"]]
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
