"""
2026-09-09 개별미팅 실제 지시 재확인(녹음 재전사) — "XY그래프"는 집계구 전체
접근성 산점도가 아니라, 급증 상위 10개 동(spike_cause_decomposition.py 결과)을
공급 변화(X) vs 이동성 변화(Y) 4분면으로 그리라는 것이었음.
"수요는 그대로니까... 이동이 좋아졌다 아니면 공급이 좋아졌다, 그래서 요거를
그려. 여기에 그냥 동을 말해. 그러면 그냥 xy그래프 해가지고" — 원본 발언 기준.

poster_spike_cause_summary.py(막대+표)와 같은 데이터를 재사용하되, 4분면
산점도로 재시각화. 그림5 세트와 팔레트 통일(신규공급=적, 복합=청).
"""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
SPIKE_FP = f"{NAS}/output/spike_cause_decomposition_2021_2022.csv"
OUT_PNG = f"{NAS}/output/maps/spike_cause_xy_quadrant.png"

COLOR_SUPPLY = "#c0392b"
COLOR_MIXED = "#33586b"
INK = "#2b2b2b"
MUTED = "#7a7568"

VERDICT_COLOR = {"신규 공급형": COLOR_SUPPLY, "공급+도로망 복합": COLOR_MIXED}
VERDICT_LABEL = {"신규 공급형": "신규공급형", "공급+도로망 복합": "공급+도로망 복합"}


def main():
    spike = pd.read_csv(SPIKE_FP)
    spike["tt_shortened_sec"] = -spike["mean_tt_delta_sec"].fillna(0)  # 양수=단축(개선)

    fig, ax = plt.subplots(figsize=(8.5, 7.5))

    for verdict, sub in spike.groupby("verdict"):
        ax.scatter(sub["n_new_stations"], sub["tt_shortened_sec"], s=110,
                   color=VERDICT_COLOR[verdict], edgecolor="white", linewidth=0.8,
                   zorder=3, label=VERDICT_LABEL[verdict])

    for _, r in spike.iterrows():
        ax.annotate(f"{r['gu']} {r['dong']}", (r["n_new_stations"], r["tt_shortened_sec"]),
                    textcoords="offset points", xytext=(7, 5), fontsize=9, color=INK)

    ax.axhline(0, color=MUTED, linewidth=0.7, zorder=1)
    ax.axvline(0, color=MUTED, linewidth=0.7, zorder=1)

    xmax = spike["n_new_stations"].max() * 1.25
    ymax = max(spike["tt_shortened_sec"].max() * 1.3, 10)
    ymin = min(spike["tt_shortened_sec"].min() * 1.3, -10)
    ax.set_xlim(-xmax * 0.08, xmax)
    ax.set_ylim(ymin, ymax)

    ax.text(0.02, 0.97, "도로망만 개선\n(신규 공급 없음)", transform=ax.transAxes, ha="left", va="top",
            fontsize=8.5, color=MUTED, style="italic")
    ax.text(0.98, 0.03, "신규 공급만\n(이동시간 변화 없음)", transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8.5, color=MUTED, style="italic")
    ax.text(0.98, 0.97, "공급+도로망\n복합 개선", transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color=MUTED, style="italic")

    ax.set_xlabel("신규 도달 급속충전소 수 (개, 2021→2022)", fontsize=11)
    ax.set_ylabel("기존 충전소까지 평균 이동시간 단축 (초, 2021→2022)", fontsize=11)
    ax.set_title("급증 상위 10개 동 — 공급 변화 vs 이동성 변화", fontsize=14.5, fontweight="bold", color=INK, pad=14)
    ax.legend(frameon=False, fontsize=10, loc="lower left", bbox_to_anchor=(0.02, 0.55))
    ax.spines[["top", "right"]].set_visible(False)

    fig.text(0.5, -0.02,
              "Δ2SFCA score(week_낮_normal) 상위 10개 동 · x=0(도로망 단독)·둘 다 0(계산 이상치)인 동은 없음",
              ha="center", fontsize=8.5, color=MUTED)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"saved {OUT_PNG}")
    print(spike[["gu", "dong", "n_new_stations", "tt_shortened_sec", "verdict"]].to_string(index=False))


if __name__ == "__main__":
    main()
