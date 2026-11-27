"""
2026-11-27: 그림 1(연구 지역) 후보 D·E — 사용자 요청: 생활인구 밀도 빼고, 기존 충전소 = 검정 점, 신규 충전소 = 빨간 점.
새 분석 없음: figure2_candidates.py와 같은 최종 공급(아파트·미운영·이용제한·운수사 전용 제외) 충전소 위치만 다시 그림.

D: 지도 1장(도심 음영 없음, 11/27 수정) — 2021년에 있던 충전소(검정) vs 2022–2024년 신규(빨강)
E: 2×2 연도별 — 그 해 기존 충전소(검정) vs 그 해 신규(빨강), 2021년은 모두 검정
"""
import os
import sys

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from recheck_uselimitation_week_day import YEARS, NAS
from presentation_study_area_density_2x2_v2 import scale_north
from figure2_candidates import base, load, INK

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = f"{NAS}/manuscript/figures_2026-11-27_studyarea"
os.makedirs(OUT_DIR, exist_ok=True)
OLD_C, NEW_C = "#1a1a1a", "#d7191c"


def dots(ax, p, color, s):
    ax.scatter(p.geometry.x, p.geometry.y, s=s, facecolor=color, edgecolor="white", linewidth=0.3, zorder=3)


def cand_D(gu, st, s24):
    fig, ax = plt.subplots(figsize=(8.2, 7.4))
    base(ax, gu)
    old, new = s24[s24["first"] == 2021], s24[s24["first"] > 2021]
    dots(ax, old, OLD_C, 11)
    dots(ax, new, NEW_C, 13)
    h = [Line2D([], [], marker="o", ls="", markersize=6.5, markerfacecolor=OLD_C, markeredgecolor="white",
                label=f"2021년에 있던 충전소 ({len(old):,}개소)"),
         Line2D([], [], marker="o", ls="", markersize=6.5, markerfacecolor=NEW_C, markeredgecolor="white",
                label=f"2022–2024년 신규 충전소 ({len(new):,}개소)")]
    ax.legend(handles=h, title="급속충전소", loc="upper left", frameon=False, fontsize=9.5, title_fontsize=10)
    scale_north(ax, gu)
    return fig


def cand_E(gu, st, s24):
    fig, axes = plt.subplots(2, 2, figsize=(12, 10.6))
    prev = set()
    for ax, y in zip(axes.flat, YEARS):
        base(ax, gu)
        s = st[y]
        is_new = ~s.station_id.isin(prev) if y > YEARS[0] else s.station_id.isin([])
        old, new = s[~is_new], s[is_new]
        dots(ax, old, OLD_C, 9)
        dots(ax, new, NEW_C, 11)
        sub = f"급속충전소 {len(s):,}개소 · 급속충전기 {int(s.fast_count.sum()):,}기"
        if y > YEARS[0]:
            sub += f"  (신규 {len(new):,}개소)"
        ax.set_title(f"{y}년", fontsize=14, fontweight="bold", loc="left", color=INK, pad=22)
        ax.text(0.0, 1.01, sub, transform=ax.transAxes, fontsize=9.5, color="#555", va="bottom")  # 지도 바깥 위
        scale_north(ax, gu)
        prev = set(s.station_id)
    h = [Line2D([], [], marker="o", ls="", markersize=7, markerfacecolor=OLD_C, markeredgecolor="white", label="기존 충전소"),
         Line2D([], [], marker="o", ls="", markersize=7, markerfacecolor=NEW_C, markeredgecolor="white", label="신규 충전소")]
    fig.legend(handles=h, loc="lower center", ncol=2, frameon=False, fontsize=11)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.94, bottom=0.05, wspace=0.03, hspace=0.18)
    return fig


def main(which):
    gu, st, s24 = load()
    print("first-year counts:", s24["first"].value_counts().sort_index().to_dict(), "total", len(s24))
    for k, fn in {"D": cand_D, "E": cand_E}.items():
        if k in which:
            fig = fn(gu, st, s24)
            out = f"{OUT_DIR}/그림1_후보{k}_기존검정_신규빨강.png"
            fig.savefig(out, dpi=250, facecolor="white", bbox_inches="tight")
            plt.close(fig)
            print(out)


if __name__ == "__main__":
    main(sys.argv[1:] or ["D", "E"])
