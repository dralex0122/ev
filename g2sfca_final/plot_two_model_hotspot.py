"""
plot_three_model_hotspot.py에서 Cumulative Opportunity 제외, Gaussian 2SFCA vs
Gravity Model 2개 모형만 비교(2행x4열, 8장). 기존 three_model_hotspot_k30.csv
(3개 모형 Gi* 결과 전부 포함)에서 2개만 골라 씀 — 재계산 불필요.
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
HOTSPOT_FP = f"{NAS}/output/three_model_hotspot_k30.csv"
OUT_FP = f"{NAS}/output/maps/two_model_hotspot_k30.png"

YEARS = [2021, 2022, 2023, 2024]
MODELS = ["2SFCA", "Gravity"]
MODEL_LABEL = {"2SFCA": "Gaussian 2SFCA", "Gravity": "Gravity Model"}

BG = "#f2ede1"
BORDER = "#d8d0bd"
HOT_COLOR = "#e60000"
COLD_COLOR = "#0047ab"
FILL_ALPHA = 0.85
INK = "#2b2b2b"
MUTED = "#7a7568"


def main():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)

    hs = pd.read_csv(HOTSPOT_FP, dtype={"oa_code": str})

    fig = plt.figure(figsize=(20, 10.8))
    gs = fig.add_gridspec(nrows=len(MODELS), ncols=len(YEARS), top=0.87, bottom=0.10, left=0.05, right=0.98, hspace=0.12, wspace=0.03)

    for r, model in enumerate(MODELS):
        for c, year in enumerate(YEARS):
            ax = fig.add_subplot(gs[r, c])
            sub = hs[(hs["model"] == model) & (hs["year"] == year)].set_index("oa_code")
            g = gdf.copy()
            g["gi_class"] = g["TOT_REG_CD"].map(sub["gi_class"])

            g.plot(ax=ax, color=BG, edgecolor=BORDER, linewidth=0.1)

            dissolved = g.dissolve(by="gi_class")
            if "Hot Spot" in dissolved.index:
                dissolved.loc[["Hot Spot"]].plot(ax=ax, facecolor=HOT_COLOR, edgecolor=HOT_COLOR, linewidth=0.5, alpha=FILL_ALPHA)
            if "Cold Spot" in dissolved.index:
                dissolved.loc[["Cold Spot"]].plot(ax=ax, facecolor=COLD_COLOR, edgecolor=COLD_COLOR, linewidth=0.5, alpha=FILL_ALPHA)

            ax.set_axis_off()
            if r == 0:
                ax.set_title(f"{year}", fontsize=13, color=INK, fontweight="bold", pad=6)
            if c == 0:
                ax.text(-0.08, 0.5, MODEL_LABEL[model], transform=ax.transAxes,
                        ha="right", va="center", fontsize=12, color=INK, fontweight="bold", rotation=90)

    fig.text(0.5, 0.95, "Gaussian 2SFCA vs Gravity Model — Gi* 핫스팟·콜드스팟 비교 (평일 낮, 2021~2024)", ha="center",
              fontsize=17, color=INK, fontweight="bold")
    fig.text(0.5, 0.92, "KNN(k=30) 공간가중치 · p<0.05 · 집계구(2016년 경계) 단위", ha="center",
              fontsize=10.5, color=MUTED)

    legend_ax = fig.add_axes([0.35, 0.02, 0.3, 0.03])
    legend_ax.axis("off")
    handles = [
        mpatches.Patch(facecolor=HOT_COLOR, edgecolor=HOT_COLOR, alpha=FILL_ALPHA, label="Hot Spot (p<0.05)"),
        mpatches.Patch(facecolor=COLD_COLOR, edgecolor=COLD_COLOR, alpha=FILL_ALPHA, label="Cold Spot (p<0.05)"),
        mpatches.Patch(facecolor=BG, edgecolor=BORDER, linewidth=0.5, label="Not Significant"),
    ]
    legend_ax.legend(handles=handles, loc="center", ncol=3, frameon=False, fontsize=11)

    fig.savefig(OUT_FP, dpi=150, facecolor="white", bbox_inches=None)
    print(f"saved {OUT_FP}")


if __name__ == "__main__":
    main()
