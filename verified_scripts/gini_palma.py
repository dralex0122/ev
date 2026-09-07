"""
집계구별 EV 충전소 접근성(G2SFCA 점수)의 인구가중 Gini 계수 + Palma 비율.
5개 조합(week_오전, week_낮, weekend_오전, weekend_낮, 심야) x gaussian/exponential x 2021~2024,
합치지 않고 각각 따로 계산 (선행논문 관례: Cai et al./제주EV/Park ICU 전부 시나리오별 병렬 제시).
"""
import pandas as pd
import numpy as np

NAS = "/mnt/cowork/EV"
D1_FP = f"{NAS}/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)/d1_final_2021_2024.csv"
YEARS = [2021, 2022, 2023, 2024]
DECAYS = ["gaussian", "exponential"]

# (콤보 라벨, 파일 패턴, 인구가중치로 쓸 D1 컬럼)
COMBOS = [
    ("week_오전_congested", "g2sfca_score_{year}_week_오전_congested.csv", "오전_avg"),
    ("week_낮_normal", "g2sfca_score_{year}_week_낮_normal.csv", "낮_avg"),
    ("weekend_오전_freeflow", "g2sfca_score_{year}_weekend_오전_freeflow.csv", "오전_avg"),
    ("weekend_낮_normal", "g2sfca_score_{year}_weekend_낮_normal.csv", "낮_avg"),
    ("심야", "g2sfca_score_{year}_week_심야.csv", "심야_avg"),
]


def combo_dir(decay, combo_label):
    suffix = "simya" if combo_label == "심야" else "final"
    return f"{NAS}/output/g2sfca_sfast_{suffix}_{decay}"


def weighted_gini(score, weight):
    """인구가중 Gini (Lorenz curve 기반). score=1인당 접근성, weight=인구."""
    df = pd.DataFrame({"score": score, "weight": weight})
    df = df[df["weight"] > 0].copy()
    if len(df) == 0 or df["weight"].sum() == 0:
        return np.nan
    df = df.sort_values("score")
    df["mass"] = df["score"] * df["weight"]  # 총 접근가능량(인구 x 1인당 접근성)
    total_w = df["weight"].sum()
    total_mass = df["mass"].sum()
    if total_mass <= 0:
        return np.nan
    cum_w = df["weight"].cumsum() / total_w
    cum_mass = df["mass"].cumsum() / total_mass
    X = np.concatenate([[0.0], cum_w.values])
    Y = np.concatenate([[0.0], cum_mass.values])
    gini = 1.0 - np.sum((X[1:] - X[:-1]) * (Y[1:] + Y[:-1]))
    return gini


def weighted_palma(score, weight):
    """인구가중 Palma = (상위10% 인구가 가진 접근가능량 점유율) / (하위40% 인구가 가진 점유율).
    score 오름차순 정렬 기준으로 하위40% = 정렬 앞부분, 상위10% = 정렬 뒷부분.
    경계에 걸친 집계구는 인구를 선형보간해서 부분 포함."""
    df = pd.DataFrame({"score": score, "weight": weight})
    df = df[df["weight"] > 0].copy()
    if len(df) == 0:
        return np.nan
    df = df.sort_values("score").reset_index(drop=True)
    df["mass"] = df["score"] * df["weight"]
    total_w = df["weight"].sum()
    total_mass = df["mass"].sum()
    if total_mass <= 0 or total_w <= 0:
        return np.nan

    df["cum_w_start"] = df["weight"].cumsum() - df["weight"]
    df["cum_w_end"] = df["weight"].cumsum()
    df["w_share_start"] = df["cum_w_start"] / total_w
    df["w_share_end"] = df["cum_w_end"] / total_w

    def mass_in_population_range(lo, hi):
        # lo, hi: 인구 누적비율 구간 [0,1]. 각 행이 그 구간과 겹치는 만큼 mass를 선형보간해서 더함.
        overlap_lo = df["w_share_start"].clip(lower=lo)
        overlap_hi = df["w_share_end"].clip(upper=hi)
        overlap = (overlap_hi - overlap_lo).clip(lower=0)
        frac = np.where(df["w_share_end"] > df["w_share_start"],
                         overlap / (df["w_share_end"] - df["w_share_start"]), 0)
        return (frac * df["mass"]).sum()

    bottom40_mass = mass_in_population_range(0.0, 0.40)
    top10_mass = mass_in_population_range(0.90, 1.00)
    bottom40_share = bottom40_mass / total_mass
    top10_share = top10_mass / total_mass
    if bottom40_share <= 0:
        return np.nan
    return top10_share / bottom40_share


def main():
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    rows = []

    for decay in DECAYS:
        for year in YEARS:
            demand_year = d1[d1["year"] == year]
            for combo_label, fname_tmpl, pop_col in COMBOS:
                fp = f"{combo_dir(decay, combo_label)}/{fname_tmpl.format(year=year)}"
                score_df = pd.read_csv(fp, dtype={"oa_code": str})
                pop_map = dict(zip(demand_year["집계구코드"], demand_year[pop_col].astype(float)))
                score_df["pop"] = score_df["oa_code"].map(pop_map)
                n_missing_pop = score_df["pop"].isna().sum()
                score_df = score_df.dropna(subset=["pop"])

                total_pop = score_df["pop"].sum()
                gini = weighted_gini(score_df["accessibility_score"].values, score_df["pop"].values)
                palma = weighted_palma(score_df["accessibility_score"].values, score_df["pop"].values)

                rows.append({
                    "year": year, "combo": combo_label, "decay": decay,
                    "gini": gini, "palma": palma,
                    "n_oa": len(score_df), "n_missing_pop": n_missing_pop,
                    "total_pop": total_pop,
                })

    result = pd.DataFrame(rows)
    out_fp = f"{NAS}/output/gini_palma_2021_2024.csv"
    result[["year", "combo", "decay", "gini", "palma"]].to_csv(out_fp, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 100)
    print("=== 전체 결과 ===")
    print(result[["year", "combo", "decay", "gini", "palma", "n_oa", "n_missing_pop", "total_pop"]].to_string(index=False))

    print("\n=== sanity check ===")
    print("Gini 범위:", result["gini"].min(), "~", result["gini"].max())
    print("Palma 범위:", result["palma"].min(), "~", result["palma"].max())
    print("total_pop 요약 (연도x콤보):")
    print(result.pivot_table(index="year", columns="combo", values="total_pop", aggfunc="first").to_string())

    print("\n=== 콤보별 2021->2024 추이 (gaussian) ===")
    piv_g = result[result.decay == "gaussian"].pivot(index="combo", columns="year", values="gini")
    print(piv_g.to_string())
    print("\n=== 콤보별 2021->2024 추이 (exponential) ===")
    piv_e = result[result.decay == "exponential"].pivot(index="combo", columns="year", values="gini")
    print(piv_e.to_string())

    print("\n저장 완료:", out_fp)


if __name__ == "__main__":
    main()
