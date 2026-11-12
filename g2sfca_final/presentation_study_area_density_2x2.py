"""
2026-11-11 개별미팅 요청: 연구지역 지도 4패널(2021~2024).
각 패널 = 집계구별 평일 낮(11~13시) 생활인구 밀도 + 해당 연도 최종 공급 급속충전소 위치(점 크기 = 급속충전기 대수).
공급 필터는 최종 결과(nonpublic)와 동일: 아파트·11~13시 비운영·이용제한(Y)·운수사 전용 제외.
밀도 구간은 4개 연도를 합친 분위수로 고정해 연도 간 비교 가능하게 함. 새 분석 아님(입력 자료 시각화).
"""
import os

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

from g2sfca_final_supply import APT_FP, D1_FP
from recheck_uselimitation_week_day import load_stations, YEARS, NAS
from recompute_exclude_nonpublic import CAND_FP
from presentation_nonpublic_exclusion_maps import load_boundary, fill_by, GU_LINE, INK, MUTED

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

OUT_FP = f"{NAS}/new_output/presentation_study_area_density_2x2.png"
DENS_COLORS = ["#eef2f6", "#cbd8e4", "#97afc6", "#5f84a6", "#2f5679"]
PT_COLOR = "#d7301f"


def final_stations(year, apt_set, excl):
    st = load_stations(year)
    st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
    st = st[st.lng.notna()]
    return gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.lng, st.lat), crs="EPSG:4326").to_crs(epsg=5179)


def main():
    gdf, gu = load_boundary()
    area_km2 = pd.Series(gdf.geometry.area.values / 1e6, index=gdf["TOT_REG_CD"].values)
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    dens = {y: (d1[d1.year == y].set_index("집계구코드")["낮_avg"].astype(float)
                .reindex(gdf["TOT_REG_CD"]).fillna(0).values / area_km2.values) for y in YEARS}
    pooled = np.concatenate([dens[y] for y in YEARS])
    edges = np.quantile(pooled, [0.2, 0.4, 0.6, 0.8])
    print("밀도 구간(명/km²):", np.round(edges).astype(int))

    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl = set(cand[cand.final_label == "제외"].station_id)

    fig, axes = plt.subplots(2, 2, figsize=(13, 11.4))
    for ax, y in zip(axes.flat, YEARS):
        cls = np.digitize(dens[y], edges)
        fill_by(ax, gdf, cls, dict(enumerate(DENS_COLORS)))
        gu.boundary.plot(ax=ax, color=GU_LINE, linewidth=0.35)
        st = final_stations(y, apt_set, excl)
        n_chg = int(st.fast_count.sum())
        st.plot(ax=ax, color=PT_COLOR, markersize=2.5 + 2.2 * st.fast_count.clip(upper=10), alpha=0.75,
                edgecolor="white", linewidth=0.25, zorder=3)
        print(y, f"충전소 {len(st):,}개소, 급속충전기 {n_chg:,}기")
        ax.set_title(f"{y}년  ·  급속충전기 {n_chg:,}기 ({len(st):,}개소)", fontsize=13, color=INK,
                     fontweight="bold", loc="left")
        ax.set_axis_off()

    lab = [f"< {int(edges[0]):,}"] + [f"{int(a):,}–{int(b):,}" for a, b in zip(edges[:-1], edges[1:])] + [f"≥ {int(edges[-1]):,}"]
    h1 = [mpatches.Patch(facecolor=c, edgecolor="#bbb", label=l) for c, l in zip(DENS_COLORS, lab)]
    h2 = [Line2D([], [], marker="o", ls="", markerfacecolor=PT_COLOR, markeredgecolor="white", alpha=0.75,
                 markersize=np.sqrt(2.5 + 2.2 * k), label=f"{k}기" + (" 이상" if k == 10 else ""))
          for k in (1, 4, 10)]
    leg1 = fig.legend(handles=h1, title="평일 낮 생활인구 밀도 (명/km²)", loc="lower center",
                      bbox_to_anchor=(0.33, 0.0), ncol=5, frameon=False, fontsize=9.5, title_fontsize=10)
    fig.legend(handles=h2, title="급속충전소 (급속충전기 대수)", loc="lower center",
               bbox_to_anchor=(0.8, 0.0), ncol=3, frameon=False, fontsize=9.5, title_fontsize=10)
    fig.text(0.5, -0.025, "주: 집계구 19,153개(2016년 경계), 생활인구는 평일 11–13시 평균. 밀도 구간은 4개 연도 합산 5분위로 고정. "
             "공급은 아파트·11–13시 비운영·이용제한·운수사 전용 충전소 제외.", ha="center", fontsize=9, color=MUTED)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(OUT_FP, dpi=200, facecolor="white", bbox_inches="tight")
    print(OUT_FP)


if __name__ == "__main__":
    main()
