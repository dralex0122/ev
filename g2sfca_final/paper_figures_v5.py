"""
2026-11-20: 논문 얼개 v5용 그림 (11/18 개별미팅 과제) — 새 분석 없음, 기존 최종 결과 재사용.

1. k별 Gi* 분류 지도 (k=8·15·20·30, 2021·2024 각 2×2) — 4-2 KNN 민감도 그림
2. 그림4 논문판: Hot 전이 지도, 제목 제거(캡션으로), 방위표·축척 추가, 범례에 비율
3. 그림5 논문판: 지니·Palma 추이, 주석 제거(캡션으로), 흑백 인쇄 대응
4. 그림1 흐름도 후보 A(글자만)·B(단계별 작은 지도) — S/D/T 기호 없음

출력: NAS manuscript/figures_2026-11-20_v5/
"""
import os
import sys

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from g2sfca_final_supply import APT_FP, D1_FP
from recheck_uselimitation_week_day import load_stations, OUT_DIR, YEARS, NAS
from recompute_exclude_nonpublic import NONPUBLIC_DIR, CAND_FP
from presentation_nonpublic_exclusion_maps import load_boundary, fill_by, GU_LINE, INK, MUTED
from presentation_2sfca_weekday_grid_k20_2x2 import north_arrow, scale_bar
import rerun_gistar95 as G

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

OUT = f"{NAS}/manuscript/figures_2026-11-20_v5"
os.makedirs(OUT, exist_ok=True)
GI_FP = f"{OUT_DIR}/gistar95/gi_k20_gistar95.csv"
DOWNTOWN = ["종로구", "중구"]
CLS_COLOR = {"Hot Spot": "#c0392b", "Cold Spot": "#2c6fb0", "Not Sig": "#ecebe6"}
TRANS_COLOR = {"그 외": "#ecebe6", "Hot 이탈": "#9ecae1", "신규 Hot": "#fb8c3c", "Hot 유지": "#b2182b"}
pr = lambda *a: print(*a, flush=True)

gdf, gu_poly = load_boundary()
gdf = gdf.reset_index(drop=True)
codes = gdf["TOT_REG_CD"].values
N = len(gdf)
pts = np.array([[p.x, p.y] for p in gdf.geometry.centroid])


def score(y):
    return pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{y}_week_낮_normal.csv",
                       dtype={"oa_code": str}).set_index("oa_code").accessibility_score


def fill(ax, values, cmap):
    fill_by(ax, gdf, np.asarray(values), cmap)  # 값별 dissolve(경계 흰 틈 방지)


def base_axes(ax):
    gu_poly.boundary.plot(ax=ax, color=GU_LINE, linewidth=0.35)
    ax.set_axis_off()


# ---------- 1. k별 Gi* 지도 ----------
def fig_knn():
    rows = []
    for y in [2021, 2024]:
        s = score(y)
        cls = {}
        for k in (8, 15, 20, 30):
            w = libpysal.weights.KNN.from_array(pts, k=k)
            cls[k] = G.gi_classes_star95(gdf, w, s)
        fig, axes = plt.subplots(2, 2, figsize=(10, 9.2))
        for ax, k in zip(axes.flat, (8, 15, 20, 30)):
            c = cls[k]
            fill(ax, c, CLS_COLOR)
            base_axes(ax)
            agree = (c == cls[20]).mean() * 100
            hot = (c == "Hot Spot").mean() * 100
            cold = (c == "Cold Spot").mean() * 100
            sub = "기준" if k == 20 else f"k=20과 일치 {agree:.1f}%"
            ax.set_title(f"k = {k}  ({sub})", fontsize=12, color=INK, pad=2)
            ax.text(0.98, 0.02, f"Hot {hot:.1f}% · Cold {cold:.1f}%", transform=ax.transAxes,
                    ha="right", va="bottom", fontsize=8.5, color=MUTED)
            rows.append({"year": y, "k": k, "hot_pct": round(hot, 1), "cold_pct": round(cold, 1),
                         "agree_k20_pct": round(agree, 1)})
        north_arrow(axes[0, 0]); scale_bar(axes[0, 0])
        handles = [mpatches.Patch(facecolor=CLS_COLOR[k], edgecolor="#bbb", label=l)
                   for k, l in [("Hot Spot", "Hot Spot"), ("Not Sig", "유의하지 않음"), ("Cold Spot", "Cold Spot")]]
        fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=11,
                   bbox_to_anchor=(0.5, 0.0))
        fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.05, wspace=0.02, hspace=0.08)
        fig.savefig(f"{OUT}/그림_KNN민감도_k별_GiStar_{y}.png", dpi=250, facecolor="white")
        plt.close(fig)
    pd.DataFrame(rows).to_csv(f"{OUT}/그림_KNN민감도_k별_요약.csv", index=False, encoding="utf-8-sig")
    pr(pd.DataFrame(rows).to_string(index=False))


def transition(a, b):
    if a == "Hot Spot" and b == "Hot Spot":
        return "Hot 유지"
    if a == "Hot Spot":
        return "Hot 이탈"
    if b == "Hot Spot":
        return "신규 Hot"
    return "그 외"


def gi_year(y):
    gi = pd.read_csv(GI_FP, dtype={"oa_code": str})
    return gi[gi.year == y].set_index("oa_code")["nonpublic"].reindex(codes).values


# ---------- 2. 그림4 논문판 ----------
def fig4():
    tr = np.array([transition(a, b) for a, b in zip(gi_year(2021), gi_year(2024))])
    n = pd.Series(tr).value_counts()
    fig, ax = plt.subplots(figsize=(9, 7.8))
    fill(ax, tr, TRANS_COLOR)
    base_axes(ax)
    gu_poly.loc[DOWNTOWN].dissolve().boundary.plot(ax=ax, color=INK, linewidth=1.5)
    for name, r in gu_poly.iterrows():
        p = r.geometry.representative_point()
        ax.text(p.x, p.y, name, fontsize=7.5, color=INK, ha="center", va="center", zorder=4,
                fontweight="bold" if name in DOWNTOWN else "normal",
                bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.6))
    north_arrow(ax, x=0.94, y=0.86); scale_bar(ax, x0_frac=0.76, y_frac=0.03)
    labels = {"Hot 유지": "Hot 유지", "Hot 이탈": "Hot 이탈", "신규 Hot": "신규 Hot", "그 외": "그 외"}
    handles = [mpatches.Patch(facecolor=TRANS_COLOR[k], edgecolor="#bbb",
                              label=f"{labels[k]}  {n.get(k, 0) / N * 100:.1f}%") for k in labels]
    handles.append(mpatches.Patch(facecolor="none", edgecolor=INK, linewidth=1.5, label="종로구·중구"))
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=9.5, bbox_to_anchor=(-0.04, -0.02))
    fig.savefig(f"{OUT}/그림4_Hot전이_2021-2024_논문판.png", dpi=250, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    pr("그림4:", (n / N * 100).round(1).to_dict())


# ---------- 3. 그림5 논문판 ----------
def fig5():
    gini = [0.257, 0.241, 0.250, 0.227]
    palma = [0.841, 0.803, 0.826, 0.738]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, v, lab, ylab in [(axes[0], gini, "(a) 지니계수", "지니계수"),
                             (axes[1], palma, "(b) Palma 비", "Palma 비")]:
        ax.plot(YEARS, v, color=INK, lw=1.6, marker="o", ms=5, mfc="white", mew=1.4)
        for i, (x, y) in enumerate(zip(YEARS, v)):
            up = i == 0 or (0 < i < len(v) - 1 and y > v[i - 1]) or (i == len(v) - 1 and y > v[i - 1])
            ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points", xytext=(0, 9 if up else -15),
                        ha="center", fontsize=9, color=INK)
        ax.set_xlim(YEARS[0] - 0.35, YEARS[-1] + 0.35)
        ax.set_xticks(YEARS)
        ax.set_title(lab, loc="left", fontsize=11, color=INK)
        ax.set_ylabel(ylab, fontsize=10)
        pad = (max(v) - min(v)) * 0.35
        ax.set_ylim(min(v) - pad, max(v) + pad)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e5e5e5", lw=0.6)
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(f"{OUT}/그림5_지니_Palma_추이_논문판.png", dpi=250, facecolor="white")
    plt.close(fig)


# ---------- 4. 그림1 흐름도 ----------
STEPS = [
    ("자료 구축", ["공용 급속충전기", "평일 낮 생활인구", "도로망 통행시간", "2021–2024년"]),
    ("접근성 측정", ["Gaussian 2SFCA", "임계 통행시간 15분", "집계구 19,153개"]),
    ("상대적 공간 구조·형평성", ["Getis-Ord Gi*", "(KNN k=20, 95%)", "지니계수·Palma 비"]),
    ("변화 분석", ["Hot Spot 전이", "요인 분해", "(공급·수요·통행시간)"]),
    ("민감도 분석", ["이웃 수 k=8·15·30", "인구 무가중 지니"]),
]


def thumbnails():
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    pop = d1[d1.year == 2024].set_index("집계구코드")["낮_avg"].astype(float).reindex(codes).fillna(0).values
    dens = pop / (gdf.geometry.area.values / 1e6)
    apt = pd.read_csv(APT_FP, dtype={"station_id": str}); apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str}); excl = set(cand[cand.final_label == "제외"].station_id)
    st = load_stations(2024)
    st = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(excl)]
    stg = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.lng, st.lat), crs=4326).to_crs(5179)
    s24 = score(2024).reindex(codes).fillna(0).values
    tr = np.array([transition(a, b) for a, b in zip(gi_year(2021), gi_year(2024))])
    w8 = libpysal.weights.KNN.from_array(pts, k=8)
    c8 = G.gi_classes_star95(gdf, w8, score(2024))

    def q(v):  # 분위 회색
        r = pd.Series(v).rank(pct=True).values
        return plt.cm.Greys(0.08 + 0.8 * r)

    out = []
    specs = [
        ("t1", lambda ax: (gdf.plot(ax=ax, color=q(dens), edgecolor=q(dens), linewidth=0.1),
                           stg.plot(ax=ax, color="#c0392b", markersize=1.2, linewidth=0))),
        ("t2", lambda ax: gdf.plot(ax=ax, color=q(s24), edgecolor=q(s24), linewidth=0.1)),
        ("t3", lambda ax: fill(ax, gi_year(2024), CLS_COLOR)),
        ("t4", lambda ax: fill(ax, tr, TRANS_COLOR)),
        ("t5", lambda ax: fill(ax, c8, CLS_COLOR)),
    ]
    for name, f in specs:
        fig, ax = plt.subplots(figsize=(3, 2.6))
        f(ax)
        gu_poly.boundary.plot(ax=ax, color="#9a9a9a", linewidth=0.25)
        ax.set_axis_off()
        fp = f"{OUT}/_thumb_{name}.png"
        fig.savefig(fp, dpi=220, facecolor="white", bbox_inches="tight", pad_inches=0.02)
        plt.close(fig)
        out.append(fp)
    return out


def flow(thumbs=None):
    n = len(STEPS)
    W, gap = 1.0, 0.32
    H_box = 1.15
    top_img = 0.82 if thumbs else 0
    fig_w = n * W + (n - 1) * gap
    fig, ax = plt.subplots(figsize=(fig_w * 2.0, (H_box + top_img + 0.45) * 2.0))
    ax.set_xlim(-0.05, fig_w + 0.05)
    ax.set_ylim(-0.05, H_box + top_img + 0.42)
    ax.set_axis_off()
    for i, (title, lines) in enumerate(STEPS):
        x = i * (W + gap)
        ytop = H_box + top_img
        ax.text(x + W / 2, ytop + 0.27, f"{i + 1}", ha="center", va="center", fontsize=10, color="white",
                fontweight="bold", bbox=dict(boxstyle="circle,pad=0.28", facecolor="#3d4b5c", edgecolor="none"))
        ax.text(x + W / 2, ytop + 0.08, title, ha="center", va="center", fontsize=11.5, color=INK, fontweight="bold")
        if thumbs:
            img = plt.imread(thumbs[i])
            h, w_ = img.shape[:2]
            iw = W * 0.92
            ih = min(iw * h / w_, top_img * 0.95)
            iw = ih * w_ / h
            ax.imshow(img, extent=(x + (W - iw) / 2, x + (W + iw) / 2, H_box + 0.02, H_box + 0.02 + ih), zorder=1)
        ax.add_patch(FancyBboxPatch((x, 0), W, H_box, boxstyle="round,pad=0,rounding_size=0.04",
                                    facecolor="#f4f5f7", edgecolor="#c5cad1", linewidth=0.9))
        yy = H_box / 2 + (len(lines) - 1) * 0.11
        for j, line in enumerate(lines):
            ax.text(x + W / 2, yy - j * 0.22, line, ha="center", va="center", fontsize=10, color="#2b2b2b")
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + W + 0.04, H_box / 2), (x + W + gap - 0.04, H_box / 2),
                                         arrowstyle="-|>", mutation_scale=13, color="#3d4b5c", lw=1.2))
    ax.set_aspect("equal")
    name = "그림1_연구흐름도_후보B_지도포함.png" if thumbs else "그림1_연구흐름도_후보A_글자.png"
    fig.savefig(f"{OUT}/{name}", dpi=250, facecolor="white", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


if __name__ == "__main__":
    steps = sys.argv[1:] or ["knn", "fig4", "fig5", "flow"]
    if "knn" in steps: fig_knn()
    if "fig4" in steps: fig4()
    if "fig5" in steps: fig5()
    if "flow" in steps:
        flow()
        flow(thumbnails())
    pr("저장:", OUT)
