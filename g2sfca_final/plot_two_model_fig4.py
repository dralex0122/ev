"""
Park et al.(2022, IJGIS) Fig.4 형식 재현 — 2SFCA vs Gravity Model 비교 지도.

랩미팅(9/2) 녹음 전사 원본 확인(2026-09-04) 기준 지시: natural-breaks 그레이스케일
그라디언트 배경(원본 접근성 점수) + 그 위에 Gi* Hot/Cold 경계선만 오버레이(면
채우기 아님). 4개년(2021~2024)을 비교하려면 배경 스케일이 통일돼 있어야 해서,
natural-breaks 구간 경계를 모형별로 4개년 점수를 합친 뒤 한 번만 계산해서 4개
연도 전부에 동일하게 적용(연도별로 따로 구간을 나누면 "2022년이 어두운 이유"가
실제 악화인지 단순 구간 재조정 때문인지 구분이 안 됨).

배경 grayscale: Jenks natural breaks(k=15) — 원본 발화 "내추럴 브레이크가
15개짜만 한단 말이야"를 그대로 반영(이전 버전은 k=5로 잘못 구현했었음).
밝을수록 접근성 낮음 / 어두울수록 높음. 충전소 포인트 오버레이는 이 지도가
아니라 별도의 "연구지역 지도"(포스터 필수 콘텐츠) 몫 — 이 지도엔 안 넣음.
Hot/Cold 오버레이: two_model_hotspot_k30.csv의 Gi* 판정(dissolve 후 경계선만,
면 채우기 없음) — Hot=빨강 굵은선, Cold=파랑 굵은선.

계산 재사용: 접근성 점수는 g2sfca_final_supply.py/gravity_model_supply.py 원본 CSV,
Gi* 판정은 two_model_hotspot.py 결과(two_model_hotspot_k30.csv) 그대로 사용 —
재계산 없음.
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
OUT_FP = f"{NAS}/output/maps/two_model_hotspot_fig4.png"

YEARS = [2021, 2022, 2023, 2024]
MODELS = ["2SFCA", "Gravity"]
MODEL_LABEL = {"2SFCA": "Gaussian 2SFCA", "Gravity": "Gravity Model"}
SCORE_PATH = {
    "2SFCA": lambda year: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{year}_week_낮_normal.csv",
    "Gravity": lambda year: f"{NAS}/output/gravity_model_gaussian/gravity_score_{year}_week_낮_normal.csv",
}

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


def load_scores(gdf, model):
    """모형별 4개년 점수를 한 번에 로드 — 공통 natural-breaks 계산에 씀."""
    by_year = {}
    for year in YEARS:
        acc = pd.read_csv(SCORE_PATH[model](year), dtype={"oa_code": str})
        acc = acc.set_index("oa_code").reindex(gdf["TOT_REG_CD"])["accessibility_score"].fillna(0)
        by_year[year] = acc.values
    return by_year


def main():
    gdf = load_boundary()
    hs = pd.read_csv(HOTSPOT_FP, dtype={"oa_code": str})

    fig = plt.figure(figsize=(20, 11.5))
    gs = fig.add_gridspec(nrows=len(MODELS), ncols=len(YEARS), top=0.87, bottom=0.11, left=0.05, right=0.98, hspace=0.12, wspace=0.03)

    for r, model in enumerate(MODELS):
        by_year = load_scores(gdf, model)
        pooled = np.concatenate(list(by_year.values()))

        # 4개년 공통 natural-breaks 구간 — 한 번만 계산해서 4개 연도 전부에 동일 적용
        nb = mapclassify.NaturalBreaks(pooled, k=K_CLASSES)
        bins = nb.bins  # 상한 경계값, 길이 K_CLASSES
        norm = Normalize(vmin=0, vmax=K_CLASSES - 1)

        for c, year in enumerate(YEARS):
            ax = fig.add_subplot(gs[r, c])
            g = gdf.copy()
            g["score"] = by_year[year]
            g["cls"] = np.digitize(g["score"], bins[:-1], right=True)  # 0~K_CLASSES-1
            g["gray"] = [Greys(norm(v)) for v in g["cls"]]

            g.plot(ax=ax, color=g["gray"], edgecolor=BORDER, linewidth=0.08)

            sub = hs[(hs["model"] == model) & (hs["year"] == year)].set_index("oa_code")
            g["gi_class"] = g["TOT_REG_CD"].map(sub["gi_class"])
            dissolved = g.dissolve(by="gi_class")
            # dissolve 후 부동소수점 오차로 남는 미세 seam을 작은 버퍼로 스냅
            # (boundary만 그리는 지도라 이게 없으면 경계선이 부서져 보임)
            dissolved["geometry"] = dissolved.geometry.buffer(1).buffer(-1)
            if "Hot Spot" in dissolved.index:
                dissolved.loc[["Hot Spot"]].boundary.plot(ax=ax, color=HOT_COLOR, linewidth=1.1)
            if "Cold Spot" in dissolved.index:
                dissolved.loc[["Cold Spot"]].boundary.plot(ax=ax, color=COLD_COLOR, linewidth=1.1)

            ax.set_axis_off()
            if r == 0:
                ax.set_title(f"{year}", fontsize=13, color=INK, fontweight="bold", pad=6)
            if c == 0:
                ax.text(-0.08, 0.5, MODEL_LABEL[model], transform=ax.transAxes,
                        ha="right", va="center", fontsize=12, color=INK, fontweight="bold", rotation=90)

    fig.text(0.5, 0.95, "Gaussian 2SFCA vs Gravity Model — 접근성 점수(자연분류) + Gi* 경계 오버레이 (평일 낮, 2021~2024)",
              ha="center", fontsize=16, color=INK, fontweight="bold")
    fig.text(0.5, 0.925, "배경: Natural Breaks(Jenks, k=15) 그레이스케일 · 모형별 4개년 공통 스케일  |  경계선: KNN(k=30) Gi* Hot/Cold, p<0.05",
              ha="center", fontsize=10, color=MUTED)

    legend_ax = fig.add_axes([0.30, 0.02, 0.4, 0.04])
    legend_ax.axis("off")
    handles = [
        mpatches.Patch(facecolor=Greys(Normalize(0, K_CLASSES - 1)(0)), edgecolor=BORDER, label="접근성 낮음"),
        mpatches.Patch(facecolor=Greys(Normalize(0, K_CLASSES - 1)(K_CLASSES - 1)), edgecolor=BORDER, label="접근성 높음"),
        Line2D([0], [0], color=HOT_COLOR, linewidth=1.5, label="Hot Spot 경계 (p<0.05)"),
        Line2D([0], [0], color=COLD_COLOR, linewidth=1.5, label="Cold Spot 경계 (p<0.05)"),
    ]
    legend_ax.legend(handles=handles, loc="center", ncol=4, frameon=False, fontsize=10)

    fig.savefig(OUT_FP, dpi=150, facecolor="white", bbox_inches=None)
    print(f"saved {OUT_FP}")


if __name__ == "__main__":
    main()
