import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.font_manager as fm

fm.fontManager.addfont("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")
matplotlib.rcParams["font.family"] = "NanumGothic"
matplotlib.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV/output/g2sfca_sfast_final_gaussian"
BOUNDARY = "/mnt/cowork/EV/input/raw/집계구_2016/집계구.shp"
YEARS = [2021, 2022, 2023, 2024]

# (행 라벨, 파일명 접미사, 선택한 교통시나리오 설명)
ROWS = [
    ("평일 오전\n(혼잡 congested)", "week_오전_congested"),
    ("평일 낮\n(보통 normal)", "week_낮_normal"),
    ("주말 오전\n(원활 freeflow)", "weekend_오전_freeflow"),
    ("주말 낮\n(보통 normal)", "weekend_낮_normal"),
]

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

# 모든 데이터 로드
all_data = {}
all_vals = []
for row_label, suffix in ROWS:
    for year in YEARS:
        fp = f"{NAS}/g2sfca_score_{year}_{suffix}.csv"
        df = pd.read_csv(fp, dtype={"oa_code": str})
        all_data[(row_label, year)] = df
        all_vals.append(df.accessibility_score.values)

all_vals = np.concatenate(all_vals)
vmax = np.percentile(all_vals, 98)
vmin = 0

fig, axes = plt.subplots(4, 4, figsize=(18, 19), facecolor=SURFACE)

for i, (row_label, suffix) in enumerate(ROWS):
    for j, year in enumerate(YEARS):
        ax = axes[i, j]
        df = all_data[(row_label, year)]
        merged = gdf.merge(df.rename(columns={"accessibility_score": "score"}), left_on="TOT_REG_CD", right_on="oa_code", how="left")
        merged.plot(column="score", cmap=cmap, vmin=vmin, vmax=vmax, linewidth=0.03, edgecolor="#ffffff", ax=ax)
        ax.set_facecolor(SURFACE)
        ax.set_axis_off()
        mean_val = df.accessibility_score.mean()
        if i == 0:
            ax.set_title(str(year), fontsize=17, color=INK, fontweight="bold", pad=8)
        if j == 0:
            ax.text(-0.06, 0.5, row_label, transform=ax.transAxes, ha="right", va="center",
                     fontsize=13, color=INK, fontweight="bold", linespacing=1.4)
        ax.text(0.5, 0.03, f"평균 {mean_val*1000:.3f}‰", transform=ax.transAxes,
                 ha="center", va="top", fontsize=10, color=SECONDARY_INK)

fig.suptitle("서울 최종안(급속+아파트제외+운영시간반영) G2SFCA — gaussian × 2021–2024",
             fontsize=21, color=INK, fontweight="bold", y=0.995)
fig.text(0.5, 0.975,
          "집계구(2016년 경계) 단위 · 시간대별로 현실적인 교통시나리오 선택(평일오전=혼잡·평일낮/주말낮=보통·주말오전=원활) · 색상 스케일 16개 패널 공통(0–98th percentile)",
          ha="center", fontsize=11.5, color=MUTED)

sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
sm.set_array([])
cbar = fig.colorbar(sm, ax=axes, orientation="horizontal", fraction=0.02, pad=0.03, shrink=0.4)
cbar.set_label("접근성 점수 (높을수록 접근성 좋음)", color=SECONDARY_INK, fontsize=11)
cbar.ax.xaxis.set_tick_params(color=MUTED, labelcolor=MUTED)
cbar.outline.set_edgecolor(MUTED)

fig.savefig("/mnt/cowork/EV/output/maps/g2sfca_final_gaussian_16maps.png", dpi=150, bbox_inches="tight", facecolor=SURFACE)
print("saved")

for row_label, suffix in ROWS:
    means = [all_data[(row_label, y)].accessibility_score.mean() for y in YEARS]
    print(f"{row_label.replace(chr(10),' ')}: " + " -> ".join(f"{m*1000:.3f}" for m in means))
