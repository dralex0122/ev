"""
2026-11-27: 그림 4(Hot 전이 2021→2024) — 종로구·중구 도심 굵은 경계·굵은 글씨·범례 항목을 뺀 버전.
그 외는 paper_figures_v5.fig4와 같음(최종 점수 week_낮_normal, Gi* star, KNN k=20, 양측 95%). 새 분석 없음.

출력: NAS manuscript/figures_2026-11-27_fig4/
"""
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import paper_figures_v5 as P

OUT = f"{P.NAS}/manuscript/figures_2026-11-27_fig4"
os.makedirs(OUT, exist_ok=True)


def main():
    tr = np.array([P.transition(a, b) for a, b in zip(P.gi_year(2021), P.gi_year(2024))])
    n = pd.Series(tr).value_counts()
    fig, ax = plt.subplots(figsize=(9, 7.8))
    P.fill(ax, tr, P.TRANS_COLOR)
    P.base_axes(ax)
    for name, r in P.gu_poly.iterrows():
        p = r.geometry.representative_point()
        ax.text(p.x, p.y, name, fontsize=7.5, color=P.INK, ha="center", va="center", zorder=4,
                bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.6))
    P.north_arrow(ax, x=0.94, y=0.86); P.scale_bar(ax, x0_frac=0.76, y_frac=0.03)
    labels = ["Hot 유지", "Hot 이탈", "신규 Hot", "그 외"]
    handles = [mpatches.Patch(facecolor=P.TRANS_COLOR[k], edgecolor="#bbb",
                              label=f"{k}  {n.get(k, 0) / P.N * 100:.1f}%") for k in labels]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=9.5, bbox_to_anchor=(-0.04, -0.02))
    fig.savefig(f"{OUT}/그림4_Hot전이_2021-2024_도심경계없음.png", dpi=250, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    P.pr("그림4(도심 경계 없음):", (n / P.N * 100).round(1).to_dict())


if __name__ == "__main__":
    main()
