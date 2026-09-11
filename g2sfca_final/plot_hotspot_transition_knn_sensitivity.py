"""
2026-09-09 개별미팅 피드백 대응 — KNN 민감도 분석(gi_star_knn_sensitivity.py) 결과를
그림4(핫스팟 전이, 2021→2024)와 동일한 스타일로 지도화. k=15, k=20 각각 1장씩.
기존 hotspot_transition.py / plot_hotspot_transition.py의 로직·색상·범례를 그대로
재사용 — 비교를 위해 스타일을 다르게 하지 않음. 포스터 파일(아티팩트/pptx)은 이 단계에서
건드리지 않음(사용자가 시작 지시하기 전까지 보류).
"""
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
SENS_FP = f"{NAS}/output/gi_star_knn_sensitivity_2sfca.csv"
OUT_DIR = f"{NAS}/output/maps"
K_LIST = [15, 20]

BG = "#f2ede1"
BORDER = "#d8d0bd"
COLOR_MAP = {
    "지속콜드": "#b30000",
    "신규악화(Hot->Cold)": "#ff8c00",
    "개선(Cold->Hot)": "#1a9850",
    "지속핫": "#4575b4",
}


def classify_transition(row):
    a, b = row["2021"], row["2024"]
    simple = lambda x: "Hot" if x == "Hot Spot" else ("Cold" if x == "Cold Spot" else "NotSig")
    a, b = simple(a), simple(b)
    if a == "Cold" and b == "Cold":
        return "지속콜드"
    if a == "Hot" and b == "Cold":
        return "신규악화(Hot->Cold)"
    if a == "Cold" and b == "Hot":
        return "개선(Cold->Hot)"
    if a == "Hot" and b == "Hot":
        return "지속핫"
    if a == "NotSig" and b == "Cold":
        return "신규콜드(NotSig->Cold)"
    if a == "Cold" and b == "NotSig":
        return "콜드탈출(Cold->NotSig)"
    return f"{a}->{b}"


def main():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)

    sens = pd.read_csv(SENS_FP, dtype={"oa_code": str})

    for k in K_LIST:
        sub = sens[sens["k"] == k]
        piv = sub[sub["year"].isin([2021, 2024])].pivot(index="oa_code", columns="year", values="gi_class")
        piv.columns = [str(c) for c in piv.columns]
        piv = piv.reset_index()
        piv["transition"] = piv.apply(classify_transition, axis=1)
        print(f"\n=== k={k} 전이 유형별 집계구 수 ===")
        print(piv["transition"].value_counts())

        g = gdf.copy()
        g["transition"] = g["TOT_REG_CD"].map(piv.set_index("oa_code")["transition"]).fillna("기타")

        fig, ax = plt.subplots(figsize=(9, 9))
        g.plot(ax=ax, color=BG, edgecolor=BORDER, linewidth=0.15)

        dissolved = g.dissolve(by="transition")
        dissolved["geometry"] = dissolved.geometry.buffer(1).buffer(-1)
        for key in ["지속핫", "신규악화(Hot->Cold)", "개선(Cold->Hot)", "지속콜드"]:
            if key in dissolved.index:
                dissolved.loc[[key]].plot(ax=ax, facecolor=COLOR_MAP[key], edgecolor=COLOR_MAP[key], linewidth=0.4, alpha=0.85)

        ax.set_axis_off()
        ax.set_title(f"Gaussian 2SFCA — 핫스팟 전이 (2021→2024), KNN k={k}", fontsize=15, color="#2b2b2b", fontweight="bold", pad=10)

        handles = [
            mpatches.Patch(facecolor=COLOR_MAP["지속콜드"], label="지속 콜드스팟 (4년 내내 소외)"),
            mpatches.Patch(facecolor=COLOR_MAP["신규악화(Hot->Cold)"], label="신규 악화 (Hot→Cold)"),
            mpatches.Patch(facecolor=COLOR_MAP["개선(Cold->Hot)"], label="개선 (Cold→Hot)"),
            mpatches.Patch(facecolor=COLOR_MAP["지속핫"], label="지속 핫스팟 (4년 내내 우수)"),
            mpatches.Patch(facecolor=BG, edgecolor=BORDER, label="기타(Not Sig 등)"),
        ]
        ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8.5)
        fig.text(0.5, 0.02, f"KNN(k={k}) Gi* 기준 · 2021년→2024년 분류 전이 · 집계구(2016) 단위 · [기존 포스터 그림4는 k=30]",
                  ha="center", fontsize=8, color="#7a7568")

        out_fp = f"{OUT_DIR}/hotspot_transition_2SFCA_k{k}_sensitivity.png"
        fig.savefig(out_fp, dpi=150, facecolor="white", bbox_inches="tight")
        plt.close(fig)
        print(f"saved {out_fp}")


if __name__ == "__main__":
    main()
