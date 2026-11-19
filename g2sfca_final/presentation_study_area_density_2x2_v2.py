"""
2026-11-16: 그림 2(연구지역 4패널) 다듬은 후보 — 기존 presentation_study_area_density_2x2.py 결과는 그대로 두고 후보로 추가.
11/11 개별미팅 지시 유지: 연도별 4개 지도, 각 지도에 그 해 집계구 낮 인구 밀도 + 그 해 충전소 위치·급속충전기 대수,
막대그래프는 넣지 않음(복잡해 보이지 않게, 입력 자료가 잘 드러나게).

바꾼 점
- 밀도 바탕을 채도 낮은 회색 계열로 → 충전소 점이 먼저 보이게(바탕은 배경 역할)
- 충전소 점 확대·진한 빨강·흰 테두리, 대수 구간 3단계(1–2 / 3–5 / 6기 이상)
- 축척(5 km)·방위표 추가, 구 경계 약간 진하게, 패널 제목 간결화
- 후보 C: 그 해 새로 생긴 충전소를 주황으로 구분(전년도부터 있던 곳은 빨강)
"""
import os
import sys

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
from presentation_nonpublic_exclusion_maps import load_boundary, fill_by

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = f"{NAS}/new_output"
DENS_COLORS = ["#f3f3f0", "#d8dcdc", "#b0bcc2", "#7f95a2", "#4f6a7b"]
OLD_C, NEW_C = "#b2182b", "#f28e2b"
INK, MUTED = "#222222", "#6b6b6b"
SIZE_BINS = [(1, 2, 18), (3, 5, 38), (6, 999, 75)]  # (최소, 최대, 점 면적)


def final_stations(year, apt_set, excl):
    st = load_stations(year)
    st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
    st = st[st.lng.notna()]
    return gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.lng, st.lat), crs="EPSG:4326").to_crs(epsg=5179)


def size_of(n):
    for lo, hi, s in SIZE_BINS:
        if lo <= n <= hi:
            return s
    return SIZE_BINS[0][2]


def scale_north(ax, gu):
    x0, y0, x1, y1 = gu.total_bounds
    bx, by = x0 + 0.02 * (x1 - x0), y0 + 0.03 * (y1 - y0)
    for i in range(2):
        ax.add_patch(mpatches.Rectangle((bx + i * 2500, by), 2500, 350, facecolor=INK if i == 0 else "white",
                                        edgecolor=INK, linewidth=0.6, zorder=5))
    for k, t in [(0, "0"), (5000, "5 km")]:
        ax.text(bx + k, by + 700, t, ha="center", va="bottom", fontsize=8, color=INK, zorder=5)
    nx, ny = x1 - 0.04 * (x1 - x0), y1 - 0.06 * (y1 - y0)
    ax.annotate("", xy=(nx, ny + 2200), xytext=(nx, ny), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2), zorder=5)
    ax.text(nx, ny + 2500, "N", ha="center", va="bottom", fontsize=10, color=INK, fontweight="bold", zorder=5)


def main(variant):
    gdf, gu = load_boundary()
    area_km2 = pd.Series(gdf.geometry.area.values / 1e6, index=gdf["TOT_REG_CD"].values)
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    dens = {y: (d1[d1.year == y].set_index("집계구코드")["낮_avg"].astype(float)
                .reindex(gdf["TOT_REG_CD"]).fillna(0).values / area_km2.values) for y in YEARS}
    edges = np.quantile(np.concatenate([dens[y] for y in YEARS]), [0.2, 0.4, 0.6, 0.8])

    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl = set(cand[cand.final_label == "제외"].station_id)

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 11))
    prev_ids = set()
    for ax, y in zip(axes.flat, YEARS):
        fill_by(ax, gdf, np.digitize(dens[y], edges), dict(enumerate(DENS_COLORS)))
        gu.boundary.plot(ax=ax, color="#ffffff", linewidth=0.9, zorder=2)
        gu.boundary.plot(ax=ax, color="#8a8a84", linewidth=0.35, zorder=2)
        gu.dissolve().boundary.plot(ax=ax, color="#4a4a46", linewidth=0.8, zorder=2)
        st = final_stations(y, apt_set, excl)
        st["s"] = st.fast_count.astype(int).map(size_of)
        st = st.sort_values("s", ascending=False)
        is_new = ~st.station_id.isin(prev_ids) if (variant == "C" and y != YEARS[0]) else pd.Series(False, index=st.index)
        for mask, c in [(~is_new, OLD_C), (is_new, NEW_C)]:
            p = st[mask]
            ax.scatter(p.geometry.x, p.geometry.y, s=p.s, facecolor=c, edgecolor="white", linewidth=0.5, alpha=0.9, zorder=3)
        prev_ids = set(st.station_id)
        n_chg = int(st.fast_count.sum())
        ax.set_title(f"{y}년", fontsize=15, color=INK, fontweight="bold", loc="left", pad=2)
        ax.text(0.0, 0.965, f"급속충전기 {n_chg:,}기 · {len(st):,}개소" + (f" (신규 {int(is_new.sum()):,}개소)" if variant == "C" and y != YEARS[0] else ""),
                transform=ax.transAxes, fontsize=10.5, color=MUTED, ha="left", va="top")
        scale_north(ax, gu)
        ax.set_axis_off()
        print(y, n_chg, len(st), int(is_new.sum()))

    lab = [f"< {int(edges[0]):,}"] + [f"{int(a):,}–{int(b):,}" for a, b in zip(edges[:-1], edges[1:])] + [f"≥ {int(edges[-1]):,}"]
    h1 = [mpatches.Patch(facecolor=c, edgecolor="#999", linewidth=0.5, label=l) for c, l in zip(DENS_COLORS, lab)]
    h2 = [Line2D([], [], marker="o", ls="", markerfacecolor=OLD_C, markeredgecolor="white", markersize=np.sqrt(s),
                 label=(f"{lo}–{hi}기" if hi < 999 else f"{lo}기 이상")) for lo, hi, s in SIZE_BINS]
    if variant == "C":
        h2 += [Line2D([], [], marker="o", ls="", markerfacecolor=NEW_C, markeredgecolor="white", markersize=np.sqrt(34), label="그 해 신규")]
    fig.legend(handles=h1, title="평일 낮 생활인구 밀도 (명/km²)", loc="lower center", bbox_to_anchor=(0.3, 0.005),
               ncol=5, frameon=False, fontsize=9.5, title_fontsize=10, handlelength=1.6, columnspacing=1.0)
    fig.legend(handles=h2, title="급속충전소 (급속충전기 대수)", loc="lower center", bbox_to_anchor=(0.79, 0.005),
               ncol=len(h2), frameon=False, fontsize=9.5, title_fontsize=10, columnspacing=1.0)
    fig.tight_layout(rect=[0, 0.06, 1, 1], h_pad=1.0, w_pad=0.5)
    out = f"{OUT_DIR}/presentation_study_area_density_2x2_v2{variant}.png"
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    print(out)


if __name__ == "__main__":
    for v in (sys.argv[1:] or ["B", "C"]):
        main(v)
