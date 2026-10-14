"""
발표용 비교 도표 — 구별 유효 공급 증가율 vs 접근성 점수 증가율(2021→2024), 핫스팟 증감 + 보도자료 그룹 표시.

presentation_hotspot_interpretation.py 산출물(gu_absolute_vs_relative_2021_2024.csv)을 읽기만 함.
보도자료 그룹은 2026-10-01 노션 「구별 보도자료 조사」 기준:
  - 초기 시 집중투자: 서울형 집중충전소 1차(강남·광진·마포·서초·중구)
  - 2022~23 구 자체 확충계획: 양천·성북·도봉·노원·강동·구로
2026-10-14: 비공용 충전기 제외 최종 버전(nonpublic)으로 전환.
"""
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
IN_FP = f"{NAS}/output/presentation_k20_nonpublic/gu_absolute_vs_relative_2021_2024.csv"
OUT_FP = f"{NAS}/new_output/presentation_gu_growth_scatter_k20.png"
SEOUL_SUPPLY_X = 2661 / 786

EARLY = {"강남구", "광진구", "마포구", "서초구", "중구"}
SELF_PLAN = {"양천구", "성북구", "도봉구", "노원구", "강동구", "구로구"}
INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"
# 서울 평균 부근에 몰린 구는 라벨 위치를 수동 지정(points)
LABEL_OFFSET = {"마포구": (-30, 2), "성동구": (7, -5), "서초구": (7, -5), "동대문구": (7, 3),
                "종로구": (-14, -15), "서대문구": (-12, 8), "용산구": (8, -6), "강서구": (7, -3),
                "양천구": (-30, -3), "중랑구": (-6, -15), "동작구": (-36, -12), "광진구": (-2, 10),
                "송파구": (10, -6)}


def group_marker(gu):
    if gu in EARLY:
        return "s"
    if gu in SELF_PLAN:
        return "^"
    return "o"


def main():
    df = pd.read_csv(IN_FP, encoding="utf-8-sig")
    seoul_score_x = df["seoul_growth_x"].iloc[0]
    norm = TwoSlopeNorm(vmin=-360, vcenter=0, vmax=360)
    cmap = plt.get_cmap("RdBu_r")

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.axvline(SEOUL_SUPPLY_X, color=MUTED, lw=1, ls="--", zorder=1)
    ax.axhline(seoul_score_x, color=MUTED, lw=1, ls="--", zorder=1)
    ax.text(SEOUL_SUPPLY_X + 0.05, 2.35, f"서울 공급 {SEOUL_SUPPLY_X:.2f}×", color=MUTED, fontsize=9)
    ax.text(5.3, seoul_score_x + 0.08, f"서울 점수 {seoul_score_x:.2f}×", color=MUTED, fontsize=9)

    for _, r in df.iterrows():
        ax.scatter(r["eff_growth_x"], r["score_growth_x"], s=110, marker=group_marker(r["gu"]),
                   c=[cmap(norm(r["hot_change_21_24"]))], edgecolors=INK, linewidths=0.6, zorder=3)
        ax.annotate(r["gu"] if r["gu"] == "중구" else r["gu"][:-1],
                    (r["eff_growth_x"], r["score_growth_x"]), xytext=LABEL_OFFSET.get(r["gu"], (6, 4)),
                    textcoords="offset points", fontsize=9, color=INK)

    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cb.set_label("Hot Spot 집계구 수 증감 (2021–2024)", fontsize=10, color=INK)

    handles = [
        Line2D([], [], marker="s", ls="", mfc="white", mec=INK, ms=9, label="초기 시 집중투자(집중충전소 1차)"),
        Line2D([], [], marker="^", ls="", mfc="white", mec=INK, ms=9, label="2022~23 구 자체 확충계획"),
        Line2D([], [], marker="o", ls="", mfc="white", mec=INK, ms=9, label="기타"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=9)
    ax.set_xlabel("유효 급속충전기 증가율 (2024/2021, 배)", fontsize=11, color=INK)
    ax.set_ylabel("평균 접근성 점수 증가율 (2024/2021, 배)", fontsize=11, color=INK)
    ax.set_title("구별 공급 증가율 vs 접근성 증가율 — 서울 평균보다 덜 늘어난 구에서 핫스팟 소멸",
                 fontsize=12, color=INK, loc="left")
    ax.grid(color=GRID, lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.text(0.01, 0.005, "주: 유효 공급 = 급속·아파트 제외·평일 11–13시 운영. 비공용(이용제한·운수사 전용) 충전기 제외. Gi* KNN k=20.",
             fontsize=8, color=MUTED)
    fig.savefig(OUT_FP, dpi=150, facecolor="white", bbox_inches="tight")
    print(OUT_FP)
    print(df[["gu", "eff_growth_x", "score_growth_x", "hot_change_21_24"]]
          .corr(numeric_only=True).round(2))


if __name__ == "__main__":
    main()
