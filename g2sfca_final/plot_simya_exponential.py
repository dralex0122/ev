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

DECAY = "exponential"
NAS = f"/mnt/cowork/EV/output/g2sfca_sfast_simya_{DECAY}"
BOUNDARY = "/mnt/cowork/EV/input/raw/집계구_2016/집계구.shp"
YEARS = [2021, 2022, 2023, 2024]
DAYTYPE = "week"  # week vs weekend 차이 <0.3%로 무시 가능(2026-08-21 확인) → week만 시각화

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

all_data = {}
all_vals = []
for year in YEARS:
    fp = f"{NAS}/g2sfca_score_{year}_{DAYTYPE}_심야.csv"
    df = pd.read_csv(fp, dtype={"oa_code": str})
    all_data[year] = df
    all_vals.append(df.accessibility_score.values)

all_vals = np.concatenate(all_vals)
vmax = np.percentile(all_vals, 98)
vmin = 0

fig, axes = plt.subplots(1, 4, figsize=(18, 6.2), facecolor=SURFACE)

for j, year in enumerate(YEARS):
    ax = axes[j]
    df = all_data[year]
    merged = gdf.merge(df.rename(columns={"accessibility_score": "score"}), left_on="TOT_REG_CD", right_on="oa_code", how="left")
    merged.plot(column="score", cmap=cmap, vmin=vmin, vmax=vmax, linewidth=0.03, edgecolor="#ffffff", ax=ax)
    ax.set_facecolor(SURFACE)
    ax.set_axis_off()
    mean_val = df.accessibility_score.mean()
    ax.set_title(str(year), fontsize=17, color=INK, fontweight="bold", pad=8)
    ax.text(0.5, 0.03, f"평균 {mean_val*1000:.3f}‰", transform=ax.transAxes,
             ha="center", va="top", fontsize=10, color=SECONDARY_INK)

fig.suptitle(f"서울 심야(00~05시) G2SFCA — {DECAY} × 2021–2024",
             fontsize=21, color=INK, fontweight="bold", y=1.03)
fig.text(0.5, 0.985,
          "집계구(2016년 경계) 단위 · 급속+아파트제외+운영시간반영 · freeflow 교통시나리오 · 평일/주말 차이 <0.3%로 평일만 표시 · 색상 스케일 4패널 공통(0–98th percentile)",
          ha="center", fontsize=11, color=MUTED)

sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
sm.set_array([])
cbar = fig.colorbar(sm, ax=axes, orientation="horizontal", fraction=0.04, pad=0.08, shrink=0.5)
cbar.set_label("접근성 점수 (높을수록 접근성 좋음)", color=SECONDARY_INK, fontsize=11)
cbar.ax.xaxis.set_tick_params(color=MUTED, labelcolor=MUTED)
cbar.outline.set_edgecolor(MUTED)

fig.savefig(f"/mnt/cowork/EV/output/maps/g2sfca_simya_{DECAY}_4maps.png", dpi=150, bbox_inches="tight", facecolor=SURFACE)
print("saved", DECAY)

means = [all_data[y].accessibility_score.mean() for y in YEARS]
print("추이: " + " -> ".join(f"{m*1000:.3f}" for m in means))
