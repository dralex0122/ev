"""
모형(2SFCA vs Gravity)에 따른 원본 접근성 점수(raw accessibility_score) 자체의
분포·변화량 비교 — Figure4 지도의 그레이스케일 변화(2023~2024년 어두운 영역 증가)가
실제 절대적 개선인지, 단순 재분배(자연분류 구간 재조정 효과)인지 raw 값으로 검증.

산출:
1. 모형x연도별 원본 점수 분포 요약(mean/median/std/min/max/p25/p75)
2. 집계구별 Δscore = score_2024 - score_2021, 모형별 분포(평균/중위값/개선비율)
3. 두 모형의 Δscore 상관관계(같은 집계구가 두 모형에서 같은 방향으로 움직이는지)
4. 시각화: (a) 연도별 원본 점수 분포(박스플롯), (b) 두 모형 Δscore 산점도
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
YEARS = [2021, 2022, 2023, 2024]
MODELS = ["2SFCA", "Gravity"]
MODEL_LABEL = {"2SFCA": "Gaussian 2SFCA", "Gravity": "Gravity Model"}
SCORE_PATH = {
    "2SFCA": lambda year: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{year}_week_낮_normal.csv",
    "Gravity": lambda year: f"{NAS}/output/gravity_model_gaussian/gravity_score_{year}_week_낮_normal.csv",
}
OUT_SUMMARY_CSV = f"{NAS}/output/raw_score_summary_by_model_year.csv"
OUT_DELTA_CSV = f"{NAS}/output/raw_score_delta_2021_2024.csv"
OUT_PNG = f"{NAS}/output/maps/raw_score_change_comparison.png"

MODEL_COLOR = {"2SFCA": "#0047ab", "Gravity": "#e60000"}
INK = "#2b2b2b"
MUTED = "#7a7568"


def load_all():
    scores = {}
    for model in MODELS:
        for year in YEARS:
            df = pd.read_csv(SCORE_PATH[model](year), dtype={"oa_code": str})
            scores[(model, year)] = df.set_index("oa_code")["accessibility_score"]
    return scores


def main():
    scores = load_all()

    # 1. 연도별 분포 요약
    rows = []
    for model in MODELS:
        for year in YEARS:
            s = scores[(model, year)]
            rows.append({
                "model": model, "year": year, "n": len(s),
                "mean": s.mean(), "median": s.median(), "std": s.std(),
                "p25": s.quantile(0.25), "p75": s.quantile(0.75),
                "min": s.min(), "max": s.max(),
            })
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    print("=== 모형x연도별 원본 점수 분포 ===")
    print(summary.to_string(index=False))

    # 2~3. Δscore(2024-2021) 및 모형 간 비교
    delta = {}
    for model in MODELS:
        common_idx = scores[(model, 2021)].index.intersection(scores[(model, 2024)].index)
        d = scores[(model, 2024)].reindex(common_idx) - scores[(model, 2021)].reindex(common_idx)
        delta[model] = d
        pct_pos = (d > 0).mean() * 100
        pct_neg = (d < 0).mean() * 100
        print(f"\n=== {MODEL_LABEL[model]} Δscore(2024-2021) ===")
        print(f"평균 {d.mean():.4f} | 중위값 {d.median():.4f} | 개선(양수) {pct_pos:.1f}% | 악화(음수) {pct_neg:.1f}%")

    delta_df = pd.DataFrame(delta).dropna()
    delta_df.to_csv(OUT_DELTA_CSV, encoding="utf-8-sig")

    # 절대 Δscore는 두 모형 스케일이 5~6자리 다르므로(2SFCA ~0.0001대, Gravity ~100대)
    # 상관·시각화는 %변화율(unitless)로 정규화해서 비교 — 2021년 점수가 0인 집계구는
    # 분모가 0이라 %변화율 정의 불가라 제외.
    pct = {}
    for model in MODELS:
        base = scores[(model, 2021)].reindex(delta_df.index)
        valid = base > 0
        pct[model] = (delta_df[model][valid] / base[valid]) * 100
    n_excluded = len(delta_df) - len(pct["2SFCA"].index.intersection(pct["Gravity"].index))
    pct_df = pd.DataFrame(pct).dropna()
    corr = pct_df["2SFCA"].corr(pct_df["Gravity"])
    same_dir = ((pct_df["2SFCA"] > 0) == (pct_df["Gravity"] > 0)).mean() * 100
    print(f"\n=== 모형 간 %변화율 비교 ({len(pct_df):,}개 집계구 공통, 2021년 점수 0인 {n_excluded}개 제외) ===")
    print(f"상관계수: {corr:.3f}")
    print(f"두 모형이 같은 방향(둘 다 개선 또는 둘 다 악화)으로 움직인 비율: {same_dir:.1f}%")

    # 4. 시각화 — 절대 스케일이 다른 두 모형을 한 축에 놓지 않고, 모형별 별도 패널(원본
    # 점수 분포) + 2021=100 기준 인덱스 비교 + %변화율 산점도 3분할로 구성.
    fig = plt.figure(figsize=(19, 6.5))
    gs = fig.add_gridspec(nrows=1, ncols=3, width_ratios=[1, 1.1, 1], wspace=0.32)

    # (a) 모형별 원본 점수 분포 — 모형마다 자기 스케일의 y축(twin) 사용
    ax1 = fig.add_subplot(gs[0, 0])
    ax1b = ax1.twinx()
    bp1 = ax1.boxplot([scores[("2SFCA", y)].values for y in YEARS], positions=np.arange(len(YEARS)) - 0.18,
                       widths=0.3, patch_artist=True, showfliers=False)
    bp2 = ax1b.boxplot([scores[("Gravity", y)].values for y in YEARS], positions=np.arange(len(YEARS)) + 0.18,
                        widths=0.3, patch_artist=True, showfliers=False)
    for bp, color in [(bp1, MODEL_COLOR["2SFCA"]), (bp2, MODEL_COLOR["Gravity"])]:
        for patch in bp["boxes"]:
            patch.set_facecolor(color)
            patch.set_alpha(0.55)
            patch.set_edgecolor(color)
        for median in bp["medians"]:
            median.set_color(INK)
    ax1.set_xticks(np.arange(len(YEARS)))
    ax1.set_xticklabels(YEARS, fontsize=9)
    ax1.set_ylabel("2SFCA 원본 점수", fontsize=9.5, color=MODEL_COLOR["2SFCA"])
    ax1b.set_ylabel("Gravity 원본 점수", fontsize=9.5, color=MODEL_COLOR["Gravity"])
    ax1.tick_params(axis="y", labelcolor=MODEL_COLOR["2SFCA"])
    ax1b.tick_params(axis="y", labelcolor=MODEL_COLOR["Gravity"])
    ax1.set_title("(a) 연도별 원본 점수 분포\n(모형별 별도 축, 이상치 제외)", fontsize=11, color=INK, fontweight="bold")
    ax1.spines[["top"]].set_visible(False)

    # (b) 2021=100 기준 인덱스 — 스케일이 다른 두 모형을 같은 축에서 성장률로 비교
    ax2 = fig.add_subplot(gs[0, 1])
    for model in MODELS:
        base = scores[(model, 2021)]
        valid = base > 0
        idx_medians = []
        for year in YEARS:
            idx = (scores[(model, year)][valid] / base[valid]) * 100
            idx_medians.append(idx.median())
        ax2.plot(YEARS, idx_medians, marker="o", color=MODEL_COLOR[model], linewidth=2, label=MODEL_LABEL[model])
        for x, y in zip(YEARS, idx_medians):
            ax2.annotate(f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8.5, color=MODEL_COLOR[model])
    ax2.axhline(100, color=MUTED, linewidth=0.7, linestyle="--")
    ax2.set_ylabel("접근성 점수 인덱스 (2021=100, 중위값)", fontsize=9.5)
    ax2.set_title("(b) 2021년 기준 성장률 비교", fontsize=11, color=INK, fontweight="bold")
    ax2.legend(frameon=False, fontsize=9, loc="upper left")
    ax2.spines[["top", "right"]].set_visible(False)

    # (c) 집계구별 %변화율 산점도 — 두 모형 다 unitless라 같은 축에서 비교 가능
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.scatter(pct_df["2SFCA"], pct_df["Gravity"], s=3, alpha=0.12, color="#555555")
    lim = max(pct_df["2SFCA"].abs().quantile(0.99), pct_df["Gravity"].abs().quantile(0.99))
    ax3.set_xlim(-20, lim)
    ax3.set_ylim(-20, lim)
    ax3.axhline(0, color=MUTED, linewidth=0.6)
    ax3.axvline(0, color=MUTED, linewidth=0.6)
    ax3.plot([-20, lim], [-20, lim], color="#999999", linewidth=0.6, linestyle="--")
    ax3.set_xlabel("2SFCA %변화율 (2024 vs 2021)", fontsize=9.5)
    ax3.set_ylabel("Gravity %변화율 (2024 vs 2021)", fontsize=9.5)
    ax3.set_title(f"(c) 집계구별 %변화율 상관\n(r={corr:.3f}, 같은 방향 {same_dir:.0f}%)", fontsize=11, color=INK, fontweight="bold")
    ax3.spines[["top", "right"]].set_visible(False)

    fig.suptitle("모형별 접근성 점수 변화량 비교 (평일 낮, 2021→2024)", fontsize=15, color=INK, fontweight="bold", y=1.03)
    fig.savefig(OUT_PNG, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"\nsaved {OUT_PNG}")


if __name__ == "__main__":
    main()
