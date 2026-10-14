"""
2026-10-14 랩미팅 과제: 2021~2024 접근성 불평등 시계열 — 지니계수·Palma ratio.

입력: 최종(nonpublic) week_낮_normal 2SFCA 점수, 집계구 생활인구(d1).
가중치:
  - 낮인구(주): 모형 수요와 동일한 낮_avg — "낮 시간 서울에 있는 사람 기준" 불평등
  - 심야인구(민감도): 거주인구 근사
  - 없음(민감도): 집계구 단위
Palma = 점수 상위 10%(가중치 누적 기준)가 가진 점수 총량 / 하위 40%가 가진 점수 총량.
지니·Palma 모두 척도 불변이라 연도 간 점수 수준 차이(공급 증가)에 영향받지 않음.
"""
import numpy as np
import pandas as pd

from g2sfca_final_supply import D1_FP
from recheck_uselimitation_week_day import OUT_DIR, YEARS, DAYTYPE, PERIOD, SCENARIO
from recompute_exclude_nonpublic import NONPUBLIC_DIR

OUT_FP = f"{OUT_DIR}/inequality_gini_palma.csv"


def weighted_gini(x, w):
    o = np.argsort(x)
    x, w = x[o], w[o]
    cw = np.cumsum(w) / w.sum()
    cxw = np.cumsum(x * w) / (x * w).sum()
    # 로렌츠 곡선 아래 면적(사다리꼴), G = 1 − 2·면적
    area = np.sum(np.diff(np.concatenate([[0], cw])) * (cxw + np.concatenate([[0], cxw[:-1]])) / 2)
    return 1 - 2 * area


def weighted_share(x, w, lo, hi):
    """가중치 누적 분위 [lo, hi) 구간이 가진 x·w 총량 비중. 경계 집계구는 비율로 나눔."""
    o = np.argsort(x)
    x, w = x[o], w[o] / w.sum()
    end = np.cumsum(w)
    start = end - w
    frac = np.clip((np.minimum(end, hi) - np.maximum(start, lo)) / np.where(w > 0, w, 1), 0, 1)
    return np.sum(x * w * frac) / np.sum(x * w)


def main():
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    rows = []
    for year in YEARS:
        tag = f"{year}_{DAYTYPE}_{PERIOD}_{SCENARIO}"
        s = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{tag}.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score
        d = d1[d1.year == year].set_index("집계구코드")
        df = pd.DataFrame({"score": s}).join(d[["낮_avg", "심야_avg"]].astype(float))
        df = df[df.score.notna()]
        for wname, w in [("낮인구", df["낮_avg"].fillna(0).values), ("심야인구", df["심야_avg"].fillna(0).values),
                         ("집계구", np.ones(len(df)))]:
            x = df.score.values
            top10, bot40 = weighted_share(x, w, 0.9, 1.0), weighted_share(x, w, 0.0, 0.4)
            rows.append({"year": year, "weight": wname, "n_oa": len(df),
                         "zero_score_pct": round(float((x == 0).mean() * 100), 2),
                         "gini": round(weighted_gini(x, w), 4),
                         "top10_share": round(top10, 4), "bottom40_share": round(bot40, 4),
                         "palma": round(top10 / bot40, 3)})
    out = pd.DataFrame(rows)
    out.to_csv(OUT_FP, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    for wname, g in out.groupby("weight", sort=False):
        print(f"\n=== 가중치: {wname} ===\n{g.drop(columns='weight').to_string(index=False)}")
    print(f"\n>> 저장: {OUT_FP}")


if __name__ == "__main__":
    main()
