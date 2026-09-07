"""
포스터 그림5(급증 원인) 본체 — 지금까지는 poster_draft artifact 안에
HTML/CSS로만 목업돼 있었는데, 실제 포스터엔 이미지 파일이 필요해서
matplotlib으로 다시 그림.

spike_cause_decomposition.py가 만든 spike_cause_decomposition_2021_2022.csv를
그대로 읽어서 왼쪽엔 판정 유형별 막대(도로망단독/계산이상치 0건도 명시적으로
표시), 오른쪽엔 상위 10개 동 표를 그림. 색은 poster_spike_dong_minimap.py와
동일하게 맞춤(같은 그림5 세트라 팔레트 통일).
"""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
SPIKE_FP = f"{NAS}/output/spike_cause_decomposition_2021_2022.csv"
OUT_PNG = f"{NAS}/output/maps/poster_spike_cause_summary.png"

# poster_spike_dong_minimap.py와 동일 팔레트
COLOR_SUPPLY = "#c0392b"
COLOR_MIXED = "#33586b"
COLOR_ZERO = "#d8d2c2"
INK = "#2b2b2b"
MUTED = "#7a7568"
BG = "#f2ede1"

VERDICT_COLOR = {"신규 공급형": COLOR_SUPPLY, "공급+도로망 복합": COLOR_MIXED}
VERDICT_LABEL = {"신규 공급형": "신규공급", "공급+도로망 복합": "복합"}


def main():
    spike = pd.read_csv(SPIKE_FP).sort_values("delta_score", ascending=False).reset_index(drop=True)
    spike["rank"] = spike.index + 1

    counts = spike["verdict"].value_counts()
    categories = ["신규 공급형", "공급+도로망 복합", "도로망 단독", "계산 이상치(600초 초과 급변)"]
    values = [counts.get(c, 0) for c in categories]
    colors = [COLOR_SUPPLY, COLOR_MIXED, COLOR_ZERO, COLOR_ZERO]

    fig = plt.figure(figsize=(11, 5.2))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.35], wspace=0.35)
    ax_bar = fig.add_subplot(gs[0])
    ax_tbl = fig.add_subplot(gs[1])

    # --- 왼쪽: 판정 유형별 막대 ---
    y = range(len(categories))
    ax_bar.barh(y, values, color=colors, height=0.55, edgecolor="none")
    ax_bar.set_yticks(list(y))
    ax_bar.set_yticklabels(categories, fontsize=10.5)
    ax_bar.invert_yaxis()
    for yi, v in zip(y, values):
        ax_bar.text(v + 0.15, yi, f"{v}개 동", va="center", fontsize=10.5,
                     color=INK if v > 0 else MUTED, fontweight="bold" if v > 0 else "normal")
    ax_bar.set_xlim(0, 9)
    ax_bar.set_xticks([])
    for spine in ["top", "right", "bottom"]:
        ax_bar.spines[spine].set_visible(False)
    ax_bar.spines["left"].set_color(MUTED)
    ax_bar.set_title("급증 상위 10개 동 — 원인 판정", fontsize=13, fontweight="bold", color=INK, pad=14, loc="left")

    # --- 오른쪽: 10개 동 표 ---
    ax_tbl.axis("off")
    ax_tbl.set_title("동별 상세", fontsize=13, fontweight="bold", color=INK, pad=14, loc="left")

    col_labels = ["순위", "자치구·동", "신규충전소", "판정"]
    cell_text = []
    cell_colors = []
    for _, r in spike.iterrows():
        cell_text.append([str(r["rank"]), f"{r['gu']} {r['dong']}", f"{r['n_new_stations']}개", VERDICT_LABEL[r["verdict"]]])
        c = VERDICT_COLOR[r["verdict"]]
        cell_colors.append(["white", "white", "white", c])

    tbl = ax_tbl.table(cellText=cell_text, colLabels=col_labels, cellColours=cell_colors,
                        colLoc="center", cellLoc="center", loc="upper center",
                        colWidths=[0.12, 0.42, 0.22, 0.24])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9.5)
    tbl.scale(1, 1.65)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#e5ddc9")
        if row == 0:
            cell.set_facecolor(BG)
            cell.set_text_props(fontweight="bold", color=INK)
        elif col == 3:
            cell.set_text_props(color="white", fontweight="bold")
        elif col == 1:
            cell.set_text_props(ha="left")

    fig.suptitle("2021→2022 접근성 급증, 왜 일어났는가", fontsize=15.5, fontweight="bold", color=INK, y=1.01)
    fig.text(0.5, -0.05,
             "Δ2SFCA score(week_낮_normal) 기준 상위 10개 동 · OD 원본(재계산 없음) 대비\n"
             "도로망 단독 개선·계산 이상치는 0건 — 급증이 계산 오류가 아니라 실제 신규 설치임을 뒷받침",
             ha="center", fontsize=9, color=MUTED)

    fig.savefig(OUT_PNG, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"saved {OUT_PNG}")


if __name__ == "__main__":
    main()
