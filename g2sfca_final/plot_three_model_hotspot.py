"""
2026-08-27 랩미팅: Gaussian 2SFCA vs Gravity Model vs Cumulative Opportunity
3개 모형 x 4개년(2021~2024) Gi* 핫스팟/콜드스팟 비교 지도 (12장, 3행x4열).

색상은 지난번(2026-08-26) 우선설치 후보지 분석 때 확정한 "교수님 코드 방식(v4)"과
동일하게: 중립색(베이지) 배경 + dissolve(by='gi_class') 후 군집만 외곽선(Hot=빨강,
Cold=파랑, Not Sig=배경과 동일/외곽선 없음). 컬러바 없음(범주형이라 범례만 하단에
별도 reserved 영역으로 분리, 지도 그리드와 안 겹치게).
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
OUT_FP = f"{NAS}/output/maps/three_model_hotspot_k30.png"

YEARS = [2021, 2022, 2023, 2024]
MODELS = ["2SFCA", "Gravity", "CumOpp"]
MODEL_LABEL = {"2SFCA": "Gaussian 2SFCA", "Gravity": "Gravity Model", "CumOpp": "Cumulative Opportunity"}

BG = "#f2ede1"       # 중립 베이지 배경(비유의)
BORDER = "#d8d0bd"   # 집계구 경계선(옅게)
HOT_COLOR = "#e60000"   # Hot Spot 채우기(선명한 빨강)
COLD_COLOR = "#0047ab"  # Cold Spot 채우기(선명한 파랑)
FILL_ALPHA = 0.85
INK = "#2b2b2b"
MUTED = "#7a7568"


def main():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)

    hs = pd.read_csv(HOTSPOT_FP, dtype={"oa_code": str})

    fig = plt.figure(figsize=(20, 15.5))
    gs = fig.add_gridspec(nrows=len(MODELS), ncols=len(YEARS), top=0.90, bottom=0.08, left=0.04, right=0.98, hspace=0.15, wspace=0.03)

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

    fig.text(0.5, 0.96, "3개 접근성 모형 Gi* 핫스팟·콜드스팟 비교 (평일 낮, 2021~2024)", ha="center",
              fontsize=17, color=INK, fontweight="bold")
    fig.text(0.5, 0.935, "KNN(k=30) 공간가중치 · p<0.05 · 집계구(2016년 경계) 단위", ha="center",
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
