"""
2026-11-27: 그림 5(이웃 수 k=10~30별 Hot 전이 5패널) — 종로구·중구 도심 굵은 경계, 패널별 "종로·중구 Hot" 글씨,
범례 항목을 뺀 버전. 그 외는 knn_transition_k10_30.py의 5패널과 같음. 새 분석 없음.

출력: NAS manuscript/figures_2026-11-27_fig5/
"""
import os

import numpy as np
import libpysal
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import paper_figures_v5 as P
import rerun_gistar95 as G
from knn_transition_k10_30 import KS, LABELS, panel_scale_bar

OUT = f"{P.NAS}/manuscript/figures_2026-11-27_fig5"
os.makedirs(OUT, exist_ok=True)


def main():
    s21, s24 = P.score(2021), P.score(2024)
    res = {}
    for k in KS:
        w = libpysal.weights.KNN.from_array(P.pts, k=k)
        a = G.gi_classes_star95(P.gdf, w, s21)
        b = G.gi_classes_star95(P.gdf, w, s24)
        res[k] = np.array([P.transition(x, y) for x, y in zip(a, b)])
        P.pr(f"k={k} 완료")
    base = res[20]
    fig, axes = plt.subplots(2, 3, figsize=(15, 9.6))
    for ax, k in zip(axes.flat, KS):
        P.fill(ax, res[k], P.TRANS_COLOR)
        P.base_axes(ax)
        sub = "기준" if k == 20 else f"k=20과 일치 {(res[k] == base).mean() * 100:.1f}%"
        ax.set_title(f"k = {k}  ({sub})", fontsize=12, color=P.INK, pad=2)
    P.north_arrow(axes[0, 0]); panel_scale_bar(axes[0, 0])
    lax = axes.flat[-1]; lax.set_axis_off()
    handles = [mpatches.Patch(facecolor=P.TRANS_COLOR[l], edgecolor="#bbb", label=l) for l in LABELS]
    lax.legend(handles=handles, loc="center", frameon=False, fontsize=13, title="2021→2024", title_fontsize=13)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.02, wspace=0.02, hspace=0.08)
    fig.savefig(f"{OUT}/그림5_Hot전이_k별_5패널_도심경계없음.png", dpi=250, facecolor="white")
    plt.close(fig)
    P.pr("저장:", OUT)


if __name__ == "__main__":
    main()
