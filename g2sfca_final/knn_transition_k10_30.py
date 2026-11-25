"""
2026-11-25 개별미팅: Gi* 인접성 행렬(이웃 수) 민감도 — k=10·15·20·25·30 (5 간격, 규칙적으로).
k별로 2021→2024 Hot 전이 지도 1장씩(총 5장) + 5장을 한 판에 모은 비교 그림 + 요약표.
스타일·분류는 논문 그림4(paper_figures_v5.fig4)와 같음. 점수는 최종(nonpublic) week_낮_normal.

출력: NAS manuscript/figures_2026-11-25_knn/
"""
import os

import numpy as np
import pandas as pd
import libpysal
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import paper_figures_v5 as P
import rerun_gistar95 as G

KS = [10, 15, 20, 25, 30]
OUT = f"{P.NAS}/manuscript/figures_2026-11-25_knn"
os.makedirs(OUT, exist_ok=True)
pr = P.pr
gdf, gu_poly, pts, N = P.gdf, P.gu_poly, P.pts, P.N
gu = gdf["TOT_REG_CD"].str[:5].map(G.R.GU_MAP).values
downtown = np.isin(gu, P.DOWNTOWN)
LABELS = ["Hot 유지", "Hot 이탈", "신규 Hot", "그 외"]


def draw(ax, tr, n, k, legend_fs=9.5, label_gu=True):
    P.fill(ax, tr, P.TRANS_COLOR)
    P.base_axes(ax)
    gu_poly.loc[P.DOWNTOWN].dissolve().boundary.plot(ax=ax, color=P.INK, linewidth=1.5)
    if label_gu:
        for name, r in gu_poly.iterrows():
            p = r.geometry.representative_point()
            ax.text(p.x, p.y, name, fontsize=7.5, color=P.INK, ha="center", va="center", zorder=4,
                    fontweight="bold" if name in P.DOWNTOWN else "normal",
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.6))
    handles = [mpatches.Patch(facecolor=P.TRANS_COLOR[l], edgecolor="#bbb",
                              label=f"{l}  {n.get(l, 0) / N * 100:.1f}%") for l in LABELS]
    handles.append(mpatches.Patch(facecolor="none", edgecolor=P.INK, linewidth=1.5, label="종로구·중구"))
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=legend_fs, bbox_to_anchor=(-0.04, -0.02))


def main():
    s21, s24 = P.score(2021), P.score(2024)
    res, rows = {}, []
    for k in KS:
        w = libpysal.weights.KNN.from_array(pts, k=k)
        a = G.gi_classes_star95(gdf, w, s21)
        b = G.gi_classes_star95(gdf, w, s24)
        tr = np.array([P.transition(x, y) for x, y in zip(a, b)])
        res[k] = (a, b, tr)
        pr(f"k={k} 완료")
    base_tr = res[20][2]
    for k in KS:
        a, b, tr = res[k]
        n = pd.Series(tr).value_counts()
        rows.append({
            "k": k,
            "hot_2021": int((a == "Hot Spot").sum()), "hot_2024": int((b == "Hot Spot").sum()),
            "cold_2021": int((a == "Cold Spot").sum()), "cold_2024": int((b == "Cold Spot").sum()),
            "종로중구_hot_2021": int((a[downtown] == "Hot Spot").sum()),
            "종로중구_hot_2024": int((b[downtown] == "Hot Spot").sum()),
            **{f"{l}_pct": round(n.get(l, 0) / N * 100, 1) for l in LABELS},
            "전이_k20일치_pct": round((tr == base_tr).mean() * 100, 1),
        })
        fig, ax = plt.subplots(figsize=(9, 7.8))
        draw(ax, tr, n, k)
        P.north_arrow(ax, x=0.94, y=0.86); P.scale_bar(ax, x0_frac=0.76, y_frac=0.03)
        fig.savefig(f"{OUT}/그림_Hot전이_2021-2024_k{k}.png", dpi=250, facecolor="white", bbox_inches="tight")
        plt.close(fig)

    summ = pd.DataFrame(rows)
    summ.to_csv(f"{OUT}/Hot전이_k별_요약.csv", index=False, encoding="utf-8-sig")
    pr("\n=== k별 요약 ===\n", summ.to_string(index=False))

    # 5장 한 판(2×3, 마지막 칸은 범례)
    fig, axes = plt.subplots(2, 3, figsize=(15, 9.6))
    for ax, k in zip(axes.flat, KS):
        _, _, tr = res[k]
        P.fill(ax, tr, P.TRANS_COLOR)
        P.base_axes(ax)
        gu_poly.loc[P.DOWNTOWN].dissolve().boundary.plot(ax=ax, color=P.INK, linewidth=1.2)
        r = summ.set_index("k").loc[k]
        sub = "기준" if k == 20 else f"k=20과 일치 {r['전이_k20일치_pct']:.1f}%"
        ax.set_title(f"k = {k}  ({sub})", fontsize=12, color=P.INK, pad=2)
        ax.text(0.98, 0.02, f"종로·중구 Hot {int(r['종로중구_hot_2021'])}→{int(r['종로중구_hot_2024'])}",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=9, color=P.MUTED)
    P.north_arrow(axes[0, 0]); P.scale_bar(axes[0, 0])
    lax = axes.flat[-1]; lax.set_axis_off()
    handles = [mpatches.Patch(facecolor=P.TRANS_COLOR[l], edgecolor="#bbb", label=l) for l in LABELS]
    handles.append(mpatches.Patch(facecolor="none", edgecolor=P.INK, linewidth=1.5, label="종로구·중구"))
    lax.legend(handles=handles, loc="center", frameon=False, fontsize=13, title="2021→2024", title_fontsize=13)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.02, wspace=0.02, hspace=0.08)
    fig.savefig(f"{OUT}/그림_Hot전이_k별_5패널.png", dpi=250, facecolor="white")
    plt.close(fig)
    pr("저장:", OUT)


if __name__ == "__main__":
    main()
