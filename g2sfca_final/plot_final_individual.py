import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.font_manager as fm
import os

fm.fontManager.addfont("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")
matplotlib.rcParams["font.family"] = "NanumGothic"
matplotlib.rcParams["axes.unicode_minus"] = False

BOUNDARY = "/mnt/cowork/EV/input/raw/집계구_2016/집계구.shp"
YEARS = [2021, 2022, 2023, 2024]
OUT_DIR = "/mnt/cowork/EV/output/maps/individual"
os.makedirs(OUT_DIR, exist_ok=True)

# (라벨, 파일명 접미사, 교통시나리오 한글 설명)
ROWS = [
    ("평일 오전(혼잡 congested)", "week_오전_congested"),
    ("평일 낮(보통 normal)", "week_낮_normal"),
    ("주말 오전(원활 freeflow)", "weekend_오전_freeflow"),
    ("주말 낮(보통 normal)", "weekend_낮_normal"),
]

DECAYS = {
    "gaussian": "gaussian",
    "exponential": "지수함수",
}

BLUE_RAMP = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
]
cmap = LinearSegmentedColormap.from_list("seq_blue", BLUE_RAMP)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
MUTED = "#898781"

gdf = gpd.read_file(BOUNDARY)
gdf = gdf.set_crs(epsg=5179, allow_override=True)
gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy()

bounds_report = {}

for decay_key, decay_label in DECAYS.items():
    NAS = f"/mnt/cowork/EV/output/g2sfca_sfast_final_{decay_key}"

    all_data = {}
    all_vals = []
    for row_label, suffix in ROWS:
        for year in YEARS:
            fp = f"{NAS}/g2sfca_score_{year}_{suffix}.csv"
            df = pd.read_csv(fp, dtype={"oa_code": str})
            all_data[(row_label, suffix, year)] = df
            all_vals.append(df.accessibility_score.values)

    all_vals = np.concatenate(all_vals)
    vmax = np.percentile(all_vals, 98)
    vmin = 0
    bounds_report[f"final_{decay_key}"] = (vmin, vmax)

    for row_label, suffix in ROWS:
        for year in YEARS:
            df = all_data[(row_label, suffix, year)]
            merged = gdf.merge(df.rename(columns={"accessibility_score": "score"}), left_on="TOT_REG_CD", right_on="oa_code", how="left")

            fig, ax = plt.subplots(figsize=(8, 8.5), facecolor=SURFACE)
            merged.plot(column="score", cmap=cmap, vmin=vmin, vmax=vmax, linewidth=0.05, edgecolor="#ffffff", ax=ax)
            ax.set_facecolor(SURFACE)
            ax.set_axis_off()

            mean_val = df.accessibility_score.mean()
            fig.suptitle(f"{year}년 · {row_label}", fontsize=16, color=INK, fontweight="bold", y=0.97)
            fig.text(0.5, 0.925, f"G2SFCA 접근성 ({decay_label}) · 급속+아파트제외+운영시간반영 · 평균 {mean_val*1000:.3f}‰",
                      ha="center", fontsize=10.5, color=MUTED)

            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.02, shrink=0.7)
            cbar.set_label("접근성 점수 (높을수록 좋음, 4개 연도×시나리오 공통 스케일)", color=SECONDARY_INK, fontsize=9)
            cbar.ax.xaxis.set_tick_params(color=MUTED, labelcolor=MUTED)
            cbar.outline.set_edgecolor(MUTED)

            out_fp = f"{OUT_DIR}/final_{decay_key}_{year}_{suffix}.png"
            fig.savefig(out_fp, dpi=150, bbox_inches="tight", facecolor=SURFACE)
            plt.close(fig)
            print(f"saved {out_fp}")

print("BOUNDS", bounds_report)
