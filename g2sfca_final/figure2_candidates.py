"""
2026-11-24: 그림 2(연구 지역) 단순화 후보 3개 — 교수님 #4(2×2 밀도+충전소 지도 재사용 반대), 사용자 "너무 복잡" 요청.
새 분석 없음: 최종 공급(아파트·미운영·이용제한·운수사 전용 제외) 충전소 위치만 다시 그림.

A: 지도 1장 — 2024년 충전소를 처음 나타난 연도(2021 이전/2022/2023/2024)로 색 구분, 점 크기 동일, 바탕 없음
B: 지도 1장 — 2021년에 있던 충전소(회색) vs 2022–2024년 신규(주황), 도심(종로·중구) 경계 강조
C: 지도 2장 — 왼쪽 연구 지역(25개 자치구 이름, 도심 음영), 오른쪽 2024년 충전소(대수별 크기)
"""
import os
import sys

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches

from g2sfca_final_supply import APT_FP
from recheck_uselimitation_week_day import YEARS, NAS
from recompute_exclude_nonpublic import CAND_FP
from presentation_nonpublic_exclusion_maps import load_boundary
from presentation_study_area_density_2x2_v2 import final_stations, scale_north, size_of, SIZE_BINS

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = f"{NAS}/new_output/figure2_candidates"
os.makedirs(OUT_DIR, exist_ok=True)
INK, MUTED, LAND, EDGE = "#222222", "#6b6b6b", "#f4f4f2", "#9a9a94"
YEAR_C = {2021: "#9a9a9a", 2022: "#fdae6b", 2023: "#f16913", 2024: "#a63603"}  # 회색 = 기존, 주황 진할수록 최근
OLD_C, NEW_C = "#8c8c8c", "#e8590c"
DOWNTOWN = ["종로구", "중구"]


def base(ax, gu, downtown=False):
    gu.plot(ax=ax, facecolor=LAND, edgecolor="white", linewidth=1.0, zorder=1)
    gu.boundary.plot(ax=ax, color=EDGE, linewidth=0.4, zorder=2)
    gu.dissolve().boundary.plot(ax=ax, color="#4a4a46", linewidth=0.9, zorder=2)
    if downtown:  # 도심은 옅은 음영으로만 표시(굵은 선·화살표 주석은 점과 겹침)
        gu[gu.gu.isin(DOWNTOWN)].plot(ax=ax, facecolor="#e2dccd", edgecolor="white", linewidth=1.0, zorder=1.5)
    ax.set_axis_off()


def load():
    _, gu = load_boundary()
    gu = gu.reset_index()[["gu", "geometry"]]
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    excl = set(cand[cand.final_label == "제외"].station_id)
    st = {y: final_stations(y, apt_set, excl) for y in YEARS}
    first = {}
    for y in YEARS:
        for sid in st[y].station_id:
            first.setdefault(sid, y)
    s24 = st[2024].copy()
    s24["first"] = s24.station_id.map(first)
    return gu, st, s24


def cand_A(gu, st, s24):
    fig, ax = plt.subplots(figsize=(8.2, 7.4))
    base(ax, gu)
    lab = {2021: "2021년 이전", 2022: "2022년 신규", 2023: "2023년 신규", 2024: "2024년 신규"}
    for y in YEARS:  # 오래된 것부터 그려 최근 것이 위에
        p = s24[s24["first"] == y]
        ax.scatter(p.geometry.x, p.geometry.y, s=14, facecolor=YEAR_C[y], edgecolor="white", linewidth=0.3, zorder=3)
    h = [Line2D([], [], marker="o", ls="", markersize=7, markerfacecolor=YEAR_C[y], markeredgecolor="white",
                label=f"{lab[y]} ({(s24['first'] == y).sum():,}개소)") for y in YEARS]
    ax.legend(handles=h, title="급속충전소 설치 시기", loc="upper left", frameon=False, fontsize=9.5, title_fontsize=10)
    scale_north(ax, gu)
    return fig


def cand_B(gu, st, s24):
    fig, ax = plt.subplots(figsize=(8.2, 7.4))
    base(ax, gu, downtown=True)
    old = s24[s24["first"] == 2021]
    new = s24[s24["first"] > 2021]
    ax.scatter(old.geometry.x, old.geometry.y, s=12, facecolor=OLD_C, edgecolor="white", linewidth=0.3, zorder=3)
    ax.scatter(new.geometry.x, new.geometry.y, s=14, facecolor=NEW_C, edgecolor="white", linewidth=0.3, zorder=3)
    h = [Line2D([], [], marker="o", ls="", markersize=7, markerfacecolor=OLD_C, markeredgecolor="white", label=f"2021년에 있던 충전소 ({len(old):,}개소)"),
         Line2D([], [], marker="o", ls="", markersize=7, markerfacecolor=NEW_C, markeredgecolor="white", label=f"2022–2024년 신규 ({len(new):,}개소)"),
         mpatches.Patch(facecolor="#e2dccd", edgecolor="#999", linewidth=0.5, label="도심(종로구·중구)")]
    ax.legend(handles=h, title="급속충전소", loc="upper left", frameon=False, fontsize=9.5, title_fontsize=10)
    scale_north(ax, gu)
    return fig


def cand_C(gu, st, s24):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 6.2))
    base(a1, gu)
    gu[gu.gu.isin(DOWNTOWN)].plot(ax=a1, facecolor="#d9d4c7", edgecolor="white", linewidth=1.0, zorder=1.5)
    for _, r in gu.iterrows():
        pt = r.geometry.representative_point()
        a1.text(pt.x, pt.y, (r.gu[:-1] if len(r.gu) > 2 else r.gu), fontsize=7.5, color=INK, ha="center", va="center", zorder=5)
    a1.set_title("(a) 연구 지역: 서울시 25개 자치구, 집계구 19,153개", fontsize=11, loc="left", color=INK)
    a1.legend(handles=[mpatches.Patch(facecolor="#d9d4c7", edgecolor="#999", label="도심(종로구·중구)")],
              loc="lower right", frameon=False, fontsize=9)
    scale_north(a1, gu)
    base(a2, gu)
    p = s24.assign(s=s24.fast_count.astype(int).map(size_of)).sort_values("s", ascending=False)
    a2.scatter(p.geometry.x, p.geometry.y, s=p.s * 0.6, facecolor="#b2182b", edgecolor="white", linewidth=0.4, alpha=0.9, zorder=3)
    a2.set_title(f"(b) 2024년 급속충전소 {len(s24):,}개소 · 급속충전기 {int(s24.fast_count.sum()):,}기", fontsize=11, loc="left", color=INK)
    h = [Line2D([], [], marker="o", ls="", markerfacecolor="#b2182b", markeredgecolor="white", markersize=(s * 0.6) ** 0.5,
                label=(f"{lo}–{hi}기" if hi < 999 else f"{lo}기 이상")) for lo, hi, s in SIZE_BINS]
    a2.legend(handles=h, title="급속충전기 대수", loc="lower right", frameon=False, fontsize=9, title_fontsize=9.5)
    fig.tight_layout(w_pad=1.5)
    return fig


def main(which):
    gu, st, s24 = load()
    print("first-year counts:", s24["first"].value_counts().sort_index().to_dict(), "total", len(s24), int(s24.fast_count.sum()))
    for k, fn in {"A": cand_A, "B": cand_B, "C": cand_C}.items():
        if k in which:
            fig = fn(gu, st, s24)
            out = f"{OUT_DIR}/그림2_후보{k}.png"
            fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
            plt.close(fig)
            print(out)


if __name__ == "__main__":
    main(sys.argv[1:] or ["A", "B", "C"])
