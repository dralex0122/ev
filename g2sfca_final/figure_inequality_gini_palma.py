"""
논문 Results 그림 — 2021~2024 접근성 불평등: (a) 지니계수 (b) Palma ratio 추이 (c) 로렌츠 곡선 2021 vs 2024.

(a)(b)는 inequality_gini_palma.py 산출 CSV를 읽기만 함. 주 가중치 = 낮인구, 심야인구·집계구(무가중)는 민감도로 옅게.
(c)는 낮인구 가중 로렌츠 곡선을 점수에서 다시 계산.
지니·Palma는 축 척도가 달라 이중축 대신 패널 분리.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from g2sfca_final_supply import D1_FP
from recheck_uselimitation_week_day import DAYTYPE, PERIOD, SCENARIO
from recompute_exclude_nonpublic import NONPUBLIC_DIR
from inequality_gini_palma import OUT_FP as IN_FP

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
OUT_FP = f"{NAS}/new_output/inequality_gini_palma_lorenz.png"
INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"
MAIN = "#1d4ed8"
WEIGHT_STYLE = {"낮인구": dict(color=MAIN, lw=2.2, marker="o", ms=6, zorder=3),
                "심야인구": dict(color="#9ca3af", lw=1.2, ls="--", marker="s", ms=4),
                "집계구": dict(color="#9ca3af", lw=1.2, ls=":", marker="^", ms=4)}
WEIGHT_LABEL = {"낮인구": "낮인구 가중(주)", "심야인구": "심야인구 가중", "집계구": "무가중(집계구)"}
LORENZ_YEARS = {2021: "#9ca3af", 2024: MAIN}


def lorenz(year):
    tag = f"{year}_{DAYTYPE}_{PERIOD}_{SCENARIO}"
    s = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{tag}.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    w = d1[d1.year == year].set_index("집계구코드")["낮_avg"].astype(float)
    df = pd.DataFrame({"x": s}).join(w.rename("w"))
    df = df[df.x.notna()]
    df["w"] = df.w.fillna(0)
    df = df.sort_values("x")
    cw = np.concatenate([[0], np.cumsum(df.w.values) / df.w.sum()])
    cx = np.concatenate([[0], np.cumsum((df.x * df.w).values) / (df.x * df.w).sum()])
    return cw, cx


def style(ax):
    ax.grid(color=GRID, lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=INK, labelsize=9)


def trend(ax, df, col, ylabel, title, fmt):
    for wname, g in df.groupby("weight", sort=False):
        ax.plot(g.year, g[col], **WEIGHT_STYLE[wname])
        if wname == "낮인구":
            # 국소 최저점(2022·2024)은 라벨을 아래로 — 민감도 선과 겹침 방지
            for x, y in zip(g.year, g[col]):
                dy = -14 if x in (2022, 2024) else 8
                ax.annotate(fmt.format(y), (x, y), xytext=(10 if x == 2024 else 0, dy), textcoords="offset points",
                            ha="center", fontsize=8.5, color=INK)
    ax.set_xticks([2021, 2022, 2023, 2024])
    ax.set_xlim(2020.6, 2024.5)
    ax.set_ylabel(ylabel, fontsize=10, color=INK)
    ax.set_title(title, fontsize=11, color=INK, loc="left")
    style(ax)


def main():
    df = pd.read_csv(IN_FP)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), gridspec_kw={"width_ratios": [1, 1, 1.05]})
    trend(axes[0], df, "gini", "지니계수", "(a) 지니계수", "{:.3f}")
    trend(axes[1], df, "palma", "Palma ratio (상위10% / 하위40%)", "(b) Palma ratio", "{:.3f}")
    handles = [Line2D([], [], **{k: v for k, v in WEIGHT_STYLE[w].items() if k != "zorder"}, label=WEIGHT_LABEL[w])
               for w in WEIGHT_STYLE]
    axes[1].legend(handles=handles, loc="upper right", frameon=False, fontsize=8.5)

    ax = axes[2]
    ax.plot([0, 1], [0, 1], color=MUTED, lw=0.8, ls="--")
    ax.text(0.52, 0.56, "완전 균등", rotation=45, fontsize=8, color=MUTED)
    main_ = df[df.weight == "낮인구"].set_index("year")
    for year, color in LORENZ_YEARS.items():
        cw, cx = lorenz(year)
        ax.plot(cw, cx, color=color, lw=2 if year == 2024 else 1.5,
                label=f"{year} (G={main_.loc[year, 'gini']:.3f})")
    ax.axvline(0.4, color=GRID, lw=1)
    ax.axvline(0.9, color=GRID, lw=1)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.set_xlabel("누적 낮인구 비율 (접근성 낮은 순)", fontsize=10, color=INK)
    ax.set_ylabel("누적 접근성 비율", fontsize=10, color=INK)
    ax.set_title("(c) 로렌츠 곡선 (낮인구 가중)", fontsize=11, color=INK, loc="left")
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    style(ax)

    fig.text(0.01, -0.02, "주: 평일 낮(11–13시) Gaussian 2SFCA 점수, 집계구 19,153개. 비공용(이용제한·운수사 전용)·아파트 충전기 제외. "
             "(c)의 세로 보조선은 하위 40%·상위 10% 경계.", fontsize=8, color=MUTED)
    fig.tight_layout()
    fig.savefig(OUT_FP, dpi=200, facecolor="white", bbox_inches="tight")
    print(OUT_FP)


if __name__ == "__main__":
    main()
