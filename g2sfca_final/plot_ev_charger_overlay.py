"""
EV 급등 지역 vs EVCS 급등 지역 오버레이 지도(동 단위, 2021->2024 증가대수 중위값 기준 4분면).
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
QUAD_FP = "/tmp/ev_charger_dong_quadrant.csv"
OUT_FP = f"{NAS}/output/maps/ev_charger_mismatch.png"

BG = "#f2ede1"
BORDER = "#d8d0bd"
COLOR_MAP = {
    "미스매치(EV만 급증)": "#c0392b",  # 빨강 - 핵심 문제
    "균형성장": "#2e7d32",             # 초록
    "선제공급": "#1f5fa8",             # 파랑
    "저성장": BG,
}

def main():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)

    quad = pd.read_csv(QUAD_FP)
    quad["dong_key2"] = quad["gu"] + quad["ADM_NM"]
    gdf["dong_key2"] = gdf["ADM_NM"].apply(lambda x: None)  # placeholder, join by ADM_NM+gu below

    GU_MAP = {
        "11010":"종로구","11020":"중구","11030":"용산구","11040":"성동구","11050":"광진구",
        "11060":"동대문구","11070":"중랑구","11080":"성북구","11090":"강북구","11100":"도봉구",
        "11110":"노원구","11120":"은평구","11130":"서대문구","11140":"마포구","11150":"양천구",
        "11160":"강서구","11170":"구로구","11180":"금천구","11190":"영등포구","11200":"동작구",
        "11210":"관악구","11220":"서초구","11230":"강남구","11240":"송파구","11250":"강동구",
    }
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)
    gdf["dong_key2"] = gdf["gu"] + gdf["ADM_NM"]

    g = gdf.merge(quad[["dong_key2", "quad"]], on="dong_key2", how="left")
    g["quad"] = g["quad"].fillna("저성장")

    fig, ax = plt.subplots(figsize=(9.5, 9.5))
    g.plot(ax=ax, color=BG, edgecolor=BORDER, linewidth=0.15)

    dissolved = g.dissolve(by="quad")
    dissolved["geometry"] = dissolved.geometry.buffer(1).buffer(-1)
    for key in ["선제공급", "균형성장", "미스매치(EV만 급증)"]:
        if key in dissolved.index:
            dissolved.loc[[key]].plot(ax=ax, facecolor=COLOR_MAP[key], edgecolor=COLOR_MAP[key], linewidth=0.4, alpha=0.85)

    ax.set_axis_off()
    ax.set_title("EV 급증 지역 vs 충전소 증설 지역 — 미스매치 진단 (2021→2024)", fontsize=14, color="#2b2b2b", fontweight="bold", pad=10)

    handles = [
        mpatches.Patch(facecolor=COLOR_MAP["미스매치(EV만 급증)"], label="미스매치: EV만 급증, 충전소 정체"),
        mpatches.Patch(facecolor=COLOR_MAP["균형성장"], label="균형성장: EV·충전소 둘 다 급증"),
        mpatches.Patch(facecolor=COLOR_MAP["선제공급"], label="선제공급: 충전소만 급증"),
        mpatches.Patch(facecolor=BG, edgecolor=BORDER, label="저성장: 둘 다 완만"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8.5)
    fig.text(0.5, 0.02, "동 단위 · 2021→2024 증가대수 중위값 기준 4분면 분류", ha="center", fontsize=8, color="#7a7568")

    fig.savefig(OUT_FP, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"saved {OUT_FP}")

if __name__ == "__main__":
    main()
