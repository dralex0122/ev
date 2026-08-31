"""
2026-08-27 랩미팅: 3개 모형 x 4개년 Gi* 핫스팟/콜드스팟 개별 지도 12장.

2026-08-26 우선설치 후보지 분석(hotspot_gi_star.py) 때 확정한 v4 스타일 그대로:
중립 베이지 배경 + dissolve(by='gi_class') 후 Hot Spot=빨강, Cold Spot=파랑
외곽선만 표시(값 등급 채우기 없음, 하늘색 범람 버그 방지 위해 반드시 dissolve 먼저).
"""
import os
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
HOTSPOT_FP = f"{NAS}/output/three_model_hotspot_k30.csv"
OUT_DIR = f"{NAS}/output/maps/individual_three_model"

YEARS = [2021, 2022, 2023, 2024]
MODELS = ["2SFCA", "Gravity", "CumOpp"]
MODEL_LABEL = {"2SFCA": "Gaussian 2SFCA", "Gravity": "Gravity Model", "CumOpp": "Cumulative Opportunity"}
SCORE_FP = {
    "2SFCA": lambda y: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{y}_week_낮_normal.csv",
    "Gravity": lambda y: f"{NAS}/output/gravity_model_gaussian/gravity_score_{y}_week_낮_normal.csv",
    "CumOpp": lambda y: f"{NAS}/output/cumulative_opportunity/cumopp_score_{y}_week_낮_normal.csv",
}

BG = "#f2ede1"
BORDER = "#d8d0bd"
HOT_COLOR = "#e60000"
COLD_COLOR = "#0047ab"
INK = "#2b2b2b"
MUTED = "#7a7568"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)

    hs = pd.read_csv(HOTSPOT_FP, dtype={"oa_code": str})

    for model in MODELS:
        for year in YEARS:
            sub = hs[(hs["model"] == model) & (hs["year"] == year)].set_index("oa_code")

            g = gdf.copy()
            g["gi_class"] = g["TOT_REG_CD"].map(sub["gi_class"])

            fig, ax = plt.subplots(figsize=(8, 8))
            g.plot(ax=ax, color=BG, edgecolor=BORDER, linewidth=0.15)

            dissolved = g.dissolve(by="gi_class")
            if "Hot Spot" in dissolved.index:
                dissolved.loc[["Hot Spot"]].plot(ax=ax, facecolor=HOT_COLOR, edgecolor=HOT_COLOR, linewidth=0.8, alpha=0.85)
            if "Cold Spot" in dissolved.index:
                dissolved.loc[["Cold Spot"]].plot(ax=ax, facecolor=COLD_COLOR, edgecolor=COLD_COLOR, linewidth=0.8, alpha=0.85)

            ax.set_axis_off()
            ax.set_title(f"{MODEL_LABEL[model]} · {year}년 (평일 낮)", fontsize=14, color=INK, fontweight="bold", pad=10)

            handles = [
                mpatches.Patch(facecolor=HOT_COLOR, edgecolor=HOT_COLOR, alpha=0.85, label="Hot Spot (p<0.05)"),
                mpatches.Patch(facecolor=COLD_COLOR, edgecolor=COLD_COLOR, alpha=0.85, label="Cold Spot (p<0.05)"),
                mpatches.Patch(facecolor=BG, edgecolor=BORDER, linewidth=0.5, label="Not Significant"),
            ]
            ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=9)
            fig.text(0.5, 0.02, "KNN(k=30) · p<0.05 · 집계구(2016) 단위", ha="center", fontsize=8, color=MUTED)

            out_fp = f"{OUT_DIR}/{model}_{year}.png"
            fig.savefig(out_fp, dpi=150, facecolor="white", bbox_inches="tight")
            plt.close(fig)
            print(f"saved {out_fp}")


if __name__ == "__main__":
    main()
