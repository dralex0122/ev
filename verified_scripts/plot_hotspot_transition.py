"""
2021 vs 2024 핫스팟 전이(transition) 지도 — 2SFCA, Gravity 각각 1장씩.
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
TRANS_FP = f"{NAS}/output/hotspot_transition_2021_2024.csv"
OUT_DIR = f"{NAS}/output/maps"

MODEL_LABEL = {"2SFCA": "Gaussian 2SFCA", "Gravity": "Gravity Model"}

BG = "#f2ede1"
BORDER = "#d8d0bd"
COLOR_MAP = {
    "지속콜드": "#b30000",       # 진한 빨강 - 최우선
    "신규악화(Hot->Cold)": "#ff8c00",  # 주황 - 경고
    "개선(Cold->Hot)": "#1a9850",     # 초록 - 긍정
    "지속핫": "#4575b4",         # 파랑 - 안정적 우수
}
DEFAULT_COLOR = BG

def main():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)

    trans = pd.read_csv(TRANS_FP, dtype={"oa_code": str})

    for model in ["2SFCA", "Gravity"]:
        sub = trans[trans["model"] == model].set_index("oa_code")
        g = gdf.copy()
        g["transition"] = g["TOT_REG_CD"].map(sub["transition"]).fillna("기타")

        fig, ax = plt.subplots(figsize=(9, 9))
        g.plot(ax=ax, color=BG, edgecolor=BORDER, linewidth=0.15)

        dissolved = g.dissolve(by="transition")
        dissolved["geometry"] = dissolved.geometry.buffer(1).buffer(-1)
        # 배경성 카테고리 먼저(있어도 안 보이게), 강조 카테고리는 나중에 그려서 위에 오도록
        for key in ["지속핫", "신규악화(Hot->Cold)", "개선(Cold->Hot)", "지속콜드"]:
            if key in dissolved.index:
                dissolved.loc[[key]].plot(ax=ax, facecolor=COLOR_MAP[key], edgecolor=COLOR_MAP[key], linewidth=0.4, alpha=0.85)

        ax.set_axis_off()
        ax.set_title(f"{MODEL_LABEL[model]} — 핫스팟 전이 (2021→2024)", fontsize=15, color="#2b2b2b", fontweight="bold", pad=10)

        handles = [
            mpatches.Patch(facecolor=COLOR_MAP["지속콜드"], label="지속 콜드스팟 (4년 내내 소외)"),
            mpatches.Patch(facecolor=COLOR_MAP["신규악화(Hot->Cold)"], label="신규 악화 (Hot→Cold)"),
            mpatches.Patch(facecolor=COLOR_MAP["개선(Cold->Hot)"], label="개선 (Cold→Hot)"),
            mpatches.Patch(facecolor=COLOR_MAP["지속핫"], label="지속 핫스팟 (4년 내내 우수)"),
            mpatches.Patch(facecolor=BG, edgecolor=BORDER, label="기타(Not Sig 등)"),
        ]
        ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8.5)
        fig.text(0.5, 0.02, "KNN(k=30) Gi* 기준 · 2021년→2024년 분류 전이 · 집계구(2016) 단위", ha="center", fontsize=8, color="#7a7568")

        out_fp = f"{OUT_DIR}/hotspot_transition_{model}.png"
        fig.savefig(out_fp, dpi=150, facecolor="white", bbox_inches="tight")
        plt.close(fig)
        print(f"saved {out_fp}")

if __name__ == "__main__":
    main()
