"""
2026-10-24 — 원인 분해(local_change_decomposition.py) 결과를 논문용 Shapley 기여 표로 저장.
재계산 없이 저장된 반사실 CSV만 읽음.
  T·D 기여 = 두 순서 평균(Shapley), S 기여 = actual − TD (신규 충전소는 y0 OD에 없어 S는 항상 마지막).
출력:
  local_change_shapley_long.csv  — 전환 × 지표 전체(base, T, D, S, actual, change, 기여 비중)
  local_change_shapley_paper.csv — 논문 표: 핵심 지표만, 표시용 반올림
"""
import pandas as pd

from local_change_decomposition import OUT_FP, GROUP_FP, OUT_DIR

LONG_FP = f"{OUT_DIR}/local_change_shapley_long.csv"
PAPER_FP = f"{OUT_DIR}/local_change_shapley_paper.csv"
PAPER_METRICS = {  # 지표 컬럼 → (표시명, 소수 자리)
    "mean_x1000": ("평균 접근성(×1000, 낮인구 가중)", 4),
    "grp_하위40": ("하위 40% 집단 평균(×1000)", 4),
    "grp_상위10": ("상위 10% 집단 평균(×1000)", 4),
    "gini": ("지니계수", 4),
    "palma": ("Palma 비", 3),
    "hot_seoul": ("Hot Spot 수(서울)", 0),
    "hot_종로·중구": ("Hot Spot 수(종로·중구)", 0),
}


def shapley(v):
    return pd.DataFrame({
        "base": v.loc["base"],
        "T": ((v.loc["T"] - v.loc["base"]) + (v.loc["TD"] - v.loc["D"])) / 2,
        "D": ((v.loc["D"] - v.loc["base"]) + (v.loc["TD"] - v.loc["T"])) / 2,
        "S": v.loc["actual"] - v.loc["TD"],
        "actual": v.loc["actual"],
    })


def main():
    out = pd.read_csv(OUT_FP)
    grp = pd.read_csv(GROUP_FP)
    # 집단 평균을 지표 컬럼으로 붙임
    g = grp.pivot_table(index=["transition", "combo"], columns="group", values="mean_x1000")
    g.columns = [f"grp_{c}" for c in g.columns]
    out = out.merge(g.reset_index(), on=["transition", "combo"])
    metrics = [c for c in out.columns if c not in ("transition", "combo")]

    rows = []
    for tr, sub in out.groupby("transition", sort=False):
        c = shapley(sub.set_index("combo")[metrics])
        c["change"] = c["actual"] - c["base"]
        assert (c[["T", "D", "S"]].sum(axis=1) - c["change"]).abs().max() < 1e-6
        for f in ["T", "D", "S"]:
            c[f"{f}_share"] = (c[f] / c["change"]).where(c["change"].abs() > 1e-12)
        rows.append(c.rename_axis("metric").reset_index().assign(transition=tr))
    long = pd.concat(rows, ignore_index=True)
    long = long[["transition", "metric", "base", "actual", "change", "T", "D", "S", "T_share", "D_share", "S_share"]]
    long.to_csv(LONG_FP, index=False, encoding="utf-8-sig")

    paper = long[long.metric.isin(PAPER_METRICS)].copy()
    paper["order"] = paper.metric.map(list(PAPER_METRICS).index)
    paper["tr_order"] = paper.transition.map(list(out.transition.unique()).index)
    for col in ["base", "actual", "change", "T", "D", "S"]:
        paper[col] = [f"{x:.{PAPER_METRICS[m][1]}f}" for x, m in zip(paper[col], paper.metric)]
    paper["지표"] = paper.metric.map(lambda m: PAPER_METRICS[m][0])
    paper = paper.sort_values(["tr_order", "order"])[["transition", "지표", "base", "actual", "change", "T", "D", "S"]]
    paper.columns = ["전환", "지표", "y0", "y1", "변화", "통행시간(T)", "수요(D)", "공급(S)"]
    paper.to_csv(PAPER_FP, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print(paper.to_string(index=False))
    print(f"\n>> 저장: {LONG_FP}\n         {PAPER_FP}")


if __name__ == "__main__":
    main()
