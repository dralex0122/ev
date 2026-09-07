"""
포스터 필수 콘텐츠 "충전소 시계열 증가 그래프" — week_낮(평일 11~13시) 단일 기준으로
재계산. g2sfca_final_supply.py의 유효공급 판정 로직(아파트 제외 + 그 시간창에
실제 운영 중인지)을 그대로 재사용해서 "이 시나리오에서 실제로 셀 수 있는" 충전소/
충전기 수를 연도별로 집계 — 그냥 전체 등록 대수가 아니라 최종 방법론이 실제로 쓰는
유효공급 기준.

2SFCA 접근성 점수 인덱스(2021=100)는 이미 계산된 week_낮_normal 결과 재사용.

배경: 시계열 변화를 다룰 때도(모형 비교 아니라 시간축 비교) week_낮 단일 시나리오로
통일 — [[scenario_scope_week_day_only]] 결정 반영.
"""
import json
import os
import re
import unicodedata
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
CHARGER_DIR_FASTONLY = f"{NAS}/input/processed/yearly_snapshots_fastonly"
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"
SCORE_FP = lambda year: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{year}_week_낮_normal.csv"
OUT_PNG = f"{NAS}/output/maps/poster_timeseries_week_day.png"

YEARS = [2021, 2022, 2023, 2024]
WINDOW_START, WINDOW_END = 11, 13  # 낮 11~13시
DAYTYPE = "week"  # 평일

TIME_RANGE_RE = re.compile(r"(\d{1,2})[:시](\d{2})?\s*[~-]\s*(\d{1,2})[:시](\d{2})?")

INK = "#2b2b2b"
MUTED = "#7a7568"
BAR_COLOR = "#0047ab"
LINE_COLOR = "#e60000"


def parse_open_window(text):
    if not text or not text.strip() or "24시간" in text or "24시" in text:
        return None
    m = TIME_RANGE_RE.search(text.strip())
    if not m:
        return None
    h1, _, h2, _ = m.groups()
    start, end = int(h1), int(h2)
    weekday_only = ("평일" in text) or ("주중" in text)
    return (start, end, weekday_only)


def is_open(parsed, window_start, window_end, daytype):
    if parsed is None:
        return True
    start, end, weekday_only = parsed
    if weekday_only and daytype == "weekend":
        return False
    if end <= start:
        return True
    return not (end <= window_start or start >= window_end)


def load_supply_and_hours(year):
    fname = f"metro7_ev_chargers_{year}_fastonly.geojson"
    fp = unicodedata.normalize("NFD", os.path.join(CHARGER_DIR_FASTONLY, fname))
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    supply, hours = {}, {}
    for feat in data["features"]:
        p = feat["properties"]
        if p.get("city") == "서울특별시":
            sid = p["station_id"]
            supply[sid] = p.get("fast_count", 0) or 0
            hours[sid] = parse_open_window(p.get("openinghour", ""))
    return supply, hours


def main():
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])

    n_stations, n_chargers = [], []
    for year in YEARS:
        supply, hours = load_supply_and_hours(year)
        valid_sids = [
            sid for sid in supply
            if sid not in apt_set and is_open(hours.get(sid), WINDOW_START, WINDOW_END, DAYTYPE)
        ]
        n_stations.append(len(valid_sids))
        n_chargers.append(sum(supply[sid] for sid in valid_sids))
        print(f"{year}: 유효 충전소 {len(valid_sids)}개, 급속충전기 {sum(supply[sid] for sid in valid_sids)}대 "
              f"(week_낮 11~13시 기준, 아파트 제외)")

    # 2SFCA 접근성 인덱스(2021=100, 중위값) — week_낮_normal
    scores_by_year = {}
    for year in YEARS:
        s = pd.read_csv(SCORE_FP(year), dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"]
        scores_by_year[year] = s
    base = scores_by_year[2021]
    valid = base > 0
    index_median = []
    for year in YEARS:
        idx = (scores_by_year[year][valid] / base[valid]) * 100
        index_median.append(idx.median())

    print("\n접근성 인덱스(2021=100, 중위값):", {y: round(v) for y, v in zip(YEARS, index_median)})

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    bars = ax.bar([str(y) for y in YEARS], n_chargers, color=BAR_COLOR, alpha=0.85, width=0.6)
    for b, n_s, n_c in zip(bars, n_stations, n_chargers):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(n_chargers) * 0.015,
                f"{n_c:,}대\n({n_s:,}개소)", ha="center", va="bottom", fontsize=10, color=INK)
    ax.set_ylabel("유효 급속충전기 수 (대)", fontsize=11)
    ax.set_title("연도별 급속충전기 증가 — 평일 낮(11~13시) 기준", fontsize=13, color=INK, fontweight="bold")
    ax.set_ylim(0, max(n_chargers) * 1.18)
    ax.spines[["top", "right"]].set_visible(False)

    ax = axes[1]
    ax.plot(YEARS, index_median, marker="o", color=LINE_COLOR, linewidth=2.2, markersize=7)
    for x, y in zip(YEARS, index_median):
        ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=10.5, color=LINE_COLOR, fontweight="bold")
    ax.axhline(100, color=MUTED, linewidth=0.7, linestyle="--")
    ax.set_ylabel("접근성 점수 인덱스 (2021=100, 중위값)", fontsize=11)
    ax.set_title("2SFCA 접근성 개선 — 평일 낮(week_낮_normal) 기준", fontsize=13, color=INK, fontweight="bold")
    ax.set_xticks(YEARS)
    ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle("충전소 공급 및 접근성 시계열 변화 (2021~2024, 평일 낮만)", fontsize=15.5, color=INK, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"\nsaved {OUT_PNG}")


if __name__ == "__main__":
    main()
