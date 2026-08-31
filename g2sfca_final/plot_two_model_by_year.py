"""
plot_two_model_hotspot.py(2SFCA vs Gravity 2x4 합본)를 연도별로 한 장씩 분리 —
연도당 1개 파일(2SFCA·Gravity 나란히), 총 4장. 새 폴더 output/maps/two_model_by_year/
에 저장. 기존 three_model_hotspot_k30.csv 재사용(재계산 불필요).
"""
import os
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
HOTSPOT_FP = f"{NAS}/output/three_model_hotspot_k30.csv"
OUT_DIR = f"{NAS}/output/maps/two_model_by_year"

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
    os.makedirs(OUT_DIR, exist_ok=True)

    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)

    hs = pd.read_csv(HOTSPOT_FP, dtype={"oa_code": str})

    for year in YEARS:
        fig, axes = plt.subplots(1, len(MODELS), figsize=(14, 7.5))

        for ax, model in zip(axes, MODELS):
            sub = hs[(hs["model"] == model) & (hs["year"] == year)].set_index("oa_code")
            g = gdf.copy()
            g["gi_class"] = g["TOT_REG_CD"].map(sub["gi_class"])

            g.plot(ax=ax, color=BG, edgecolor=BORDER, linewidth=0.15)
            dissolved = g.dissolve(by="gi_class")
            if "Hot Spot" in dissolved.index:
                dissolved.loc[["Hot Spot"]].plot(ax=ax, facecolor=HOT_COLOR, edgecolor=HOT_COLOR, linewidth=0.5, alpha=FILL_ALPHA)
            if "Cold Spot" in dissolved.index:
                dissolved.loc[["Cold Spot"]].plot(ax=ax, facecolor=COLD_COLOR, edgecolor=COLD_COLOR, linewidth=0.5, alpha=FILL_ALPHA)

            ax.set_axis_off()
            ax.set_title(MODEL_LABEL[model], fontsize=14, color=INK, fontweight="bold", pad=8)

        fig.suptitle(f"{year}년 평일 낮 — Gaussian 2SFCA vs Gravity Model", fontsize=17, color=INK, fontweight="bold", y=0.98)
        fig.text(0.5, 0.02, "KNN(k=30) · p<0.05 · 집계구(2016) 단위", ha="center", fontsize=9, color=MUTED)

        handles = [
            mpatches.Patch(facecolor=HOT_COLOR, edgecolor=HOT_COLOR, alpha=FILL_ALPHA, label="Hot Spot (p<0.05)"),
            mpatches.Patch(facecolor=COLD_COLOR, edgecolor=COLD_COLOR, alpha=FILL_ALPHA, label="Cold Spot (p<0.05)"),
            mpatches.Patch(facecolor=BG, edgecolor=BORDER, linewidth=0.5, label="Not Significant"),
        ]
        fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=10, bbox_to_anchor=(0.5, -0.02))

        fig.tight_layout(rect=[0, 0.05, 1, 0.94])
        out_fp = f"{OUT_DIR}/{year}.png"
        fig.savefig(out_fp, dpi=150, facecolor="white", bbox_inches="tight")
        plt.close(fig)
        print(f"saved {out_fp}")


if __name__ == "__main__":
    main()
