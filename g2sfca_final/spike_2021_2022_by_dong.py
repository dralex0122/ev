"""
2021→2022 접근성 급변(어제 구 단위 분석: 2022년 증가분의 상위5구 집중도 40.8%)을
동(dong) 단위로 한 단계 더 파고드는 분석 — 3순위 후속 작업(2026-09-04).

구 단위까지는 이미 나왔으니, 그 상위 구 안에서도 특정 동에 더 몰렸는지 확인.
2SFCA·Gravity 둘 다 각각 계산(모형 의존적인 결과인지 교차검증).

방법: 집계구별 Δscore(2022-2021)를 구·동 단위로 합산 → 구 순위·상위5구 집중도
재확인(어제 40.8%와 같은 방향인지) → 그 상위 구들 안에서 동 단위 순위·집중도.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
MODELS = ["2SFCA", "Gravity"]
SCORE_PATH = {
    "2SFCA": lambda year: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{year}_week_낮_normal.csv",
    "Gravity": lambda year: f"{NAS}/output/gravity_model_gaussian/gravity_score_{year}_week_낮_normal.csv",
}
OUT_CSV = f"{NAS}/output/spike_2021_2022_by_dong.csv"
OUT_PNG = f"{NAS}/output/maps/spike_2021_2022_by_dong.png"
TOP_N_GU = 5

GU_MAP = {
    "11010": "종로구", "11020": "중구", "11030": "용산구", "11040": "성동구", "11050": "광진구",
    "11060": "동대문구", "11070": "중랑구", "11080": "성북구", "11090": "강북구", "11100": "도봉구",
    "11110": "노원구", "11120": "은평구", "11130": "서대문구", "11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구", "11180": "금천구", "11190": "영등포구", "11200": "동작구",
    "11210": "관악구", "11220": "서초구", "11230": "강남구", "11240": "송파구", "11250": "강동구",
}
MODEL_COLOR = {"2SFCA": "#0047ab", "Gravity": "#e60000"}
INK = "#2b2b2b"
MUTED = "#7a7568"


def load_boundary():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")][["TOT_REG_CD", "ADM_NM"]].copy()
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)
    return gdf


def main():
    gdf = load_boundary()
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    all_rows = []
    for mi, model in enumerate(MODELS):
        s21 = pd.read_csv(SCORE_PATH[model](2021), dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"]
        s22 = pd.read_csv(SCORE_PATH[model](2022), dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"]
        df = gdf.copy()
        df["delta"] = df["TOT_REG_CD"].map(s22 - s21).fillna(0)
        df["model"] = model
        all_rows.append(df)

        # 구 단위 집중도
        gu_sum = df.groupby("gu")["delta"].sum().sort_values(ascending=False)
        total = gu_sum.sum()
        gu_share = gu_sum / total * 100
        top5_share = gu_share.head(TOP_N_GU).sum()
        cum_share = gu_share.cumsum()
        print(f"\n=== [{model}] 구 단위 Δscore(2022-2021) 순위 ===")
        for gu, v in gu_share.head(10).items():
            print(f"  {gu}: {v:5.1f}%  (누적 {cum_share[gu]:5.1f}%)")
        print(f"  상위{TOP_N_GU}구 집중도: {top5_share:.1f}%")

        top_gu_list = gu_share.head(TOP_N_GU).index.tolist()

        # 상위 구들 안에서 동 단위 순위
        within = df[df["gu"].isin(top_gu_list)]
        dong_sum = within.groupby(["gu", "ADM_NM"])["delta"].sum().sort_values(ascending=False)
        within_total = within["delta"].sum()
        print(f"\n=== [{model}] 상위{TOP_N_GU}구({', '.join(top_gu_list)}) 안 동 단위 Δscore 순위 (Top 10) ===")
        for (gu, dong), v in dong_sum.head(10).items():
            print(f"  {gu} {dong}: {v:.6f}  ({v/within_total*100:5.1f}% of 상위구 합)")
        top5_dong_share = dong_sum.head(5).sum() / within_total * 100
        print(f"  상위구 내 상위5동이 상위구 전체 증가분의 {top5_dong_share:.1f}% 차지")

        # 좌: 구 단위 바 (상위5 강조)
        ax = axes[mi, 0]
        colors = [MODEL_COLOR[model] if g in top_gu_list else "#c9c2ae" for g in gu_share.index]
        ax.bar(range(len(gu_share)), gu_share.values, color=colors)
        ax.set_xticks(range(len(gu_share)))
        ax.set_xticklabels(gu_share.index, rotation=75, fontsize=7)
        ax.set_ylabel("구별 Δscore 점유율 (%)", fontsize=9.5)
        ax.set_title(f"[{model}] 구 단위 — 상위{TOP_N_GU}구 집중도 {top5_share:.1f}%", fontsize=11.5, color=INK, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)

        # 우: 상위구 안 동 단위 바 (Top 15)
        ax = axes[mi, 1]
        top_dong = dong_sum.head(15)
        labels = [f"{g} {d}" for g, d in top_dong.index]
        ax.barh(range(len(top_dong)), (top_dong.values / within_total * 100)[::-1], color=MODEL_COLOR[model])
        ax.set_yticks(range(len(top_dong)))
        ax.set_yticklabels(labels[::-1], fontsize=8)
        ax.set_xlabel("상위구 합 대비 점유율 (%)", fontsize=9.5)
        ax.set_title(f"[{model}] 상위{TOP_N_GU}구 내 동 단위 Top 15", fontsize=11.5, color=INK, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)

        all_rows[mi] = df

    result = pd.concat(all_rows, ignore_index=True)
    result.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    fig.suptitle("2021→2022 접근성 급변 — 구 단위 집중도의 동 단위 분해 (평일 낮)", fontsize=15.5, color=INK, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"\nsaved {OUT_CSV}")
    print(f"saved {OUT_PNG}")


if __name__ == "__main__":
    main()
