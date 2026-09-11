"""
2026-09-09 개별미팅 피드백 대응 — 교수님 지적: KNN=30에서 비유의(회색) 지역이
거의 없고 거의 다 Hot/Cold로 나옴(표본이 많아지면 통계적으로 유의해지기 쉬움).
KNN을 15, 20으로 낮춰서 재실행하고 Hot/Cold/Not Sig 비율이 어떻게 바뀌는지
확인하는 민감도 분석.

기존 two_model_hotspot.py(K_NEIGHBORS=30)와 동일한 로직(2SFCA 모형, week_낮_normal,
4개년)을 재사용하되 모형은 2SFCA만(포스터가 2SFCA 단일모형 서사라 Gravity는 불필요).
기존 k=30 결과(two_model_hotspot_k30.csv)는 그대로 두고 새 k값만 별도 계산 —
원본 파일 덮어쓰지 않음.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal
import esda

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
YEARS = [2021, 2022, 2023, 2024]
K_LIST = [15, 20]
P_THRESHOLD = 0.05

SCORE_PATH = lambda year: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{year}_week_낮_normal.csv"
OUT_FP = f"{NAS}/output/gi_star_knn_sensitivity_2sfca.csv"
BASELINE_FP = f"{NAS}/output/two_model_hotspot_k30.csv"


def load_boundary():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)
    return gdf


def build_knn_weights(gdf, k):
    points = np.array([[p.x, p.y] for p in gdf.geometry.centroid])
    return libpysal.weights.KNN.from_array(points, k=k)


def gi_star(gdf, w, fp):
    acc = pd.read_csv(fp, dtype={"oa_code": str})
    acc = acc.set_index("oa_code").reindex(gdf["TOT_REG_CD"]).reset_index()
    y = acc["accessibility_score"].fillna(0).values
    lg = esda.getisord.G_Local(y, w, transform="B")
    coded = np.where((lg.Zs < 0) & (lg.p_norm < P_THRESHOLD), "Cold Spot",
             np.where((lg.Zs > 0) & (lg.p_norm < P_THRESHOLD), "Hot Spot", "Not Sig"))
    return coded


def main():
    gdf = load_boundary()
    n_total = len(gdf)
    print(f">> 집계구 {n_total:,}개")

    # 기존 k=30(2SFCA) 베이스라인 — 재계산 없이 그대로 로드해서 비교
    base = pd.read_csv(BASELINE_FP, dtype={"oa_code": str})
    base = base[base["model"] == "2SFCA"]

    records = []
    summary_rows = []

    for year in YEARS:
        b = base[base["year"] == year]["gi_class"]
        n_hot30 = (b == "Hot Spot").sum()
        n_cold30 = (b == "Cold Spot").sum()
        n_notsig30 = (b == "Not Sig").sum()
        summary_rows.append({"k": 30, "year": year, "n_hot": n_hot30, "n_cold": n_cold30,
                              "n_notsig": n_notsig30, "pct_notsig": round(100 * n_notsig30 / n_total, 1)})

    for k in K_LIST:
        w = build_knn_weights(gdf, k)
        print(f"\n>> KNN(k={k}) 공간가중치 구축 완료")
        for year in YEARS:
            coded = gi_star(gdf, w, SCORE_PATH(year))
            n_hot = (coded == "Hot Spot").sum()
            n_cold = (coded == "Cold Spot").sum()
            n_notsig = (coded == "Not Sig").sum()
            pct_notsig = round(100 * n_notsig / n_total, 1)
            print(f"  [k={k}] {year}: Hot {n_hot:5d} | Cold {n_cold:5d} | Not Sig {n_notsig:5d} ({pct_notsig}%)")
            summary_rows.append({"k": k, "year": year, "n_hot": n_hot, "n_cold": n_cold,
                                  "n_notsig": n_notsig, "pct_notsig": pct_notsig})
            for oa, c in zip(gdf["TOT_REG_CD"], coded):
                records.append({"model": "2SFCA", "k": k, "year": year, "oa_code": oa, "gi_class": c})

    df = pd.DataFrame(records)
    df.to_csv(OUT_FP, index=False, encoding="utf-8-sig")
    print(f"\n>> 저장 완료: {OUT_FP} ({len(df):,}행)")

    summary = pd.DataFrame(summary_rows).sort_values(["year", "k"])
    print("\n=== k별 Not Sig(회색) 비율 요약 ===")
    print(summary.to_string(index=False))
    summary_fp = f"{NAS}/output/gi_star_knn_sensitivity_summary.csv"
    summary.to_csv(summary_fp, index=False, encoding="utf-8-sig")
    print(f">> 요약 저장: {summary_fp}")


if __name__ == "__main__":
    main()
