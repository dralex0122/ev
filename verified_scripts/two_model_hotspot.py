"""
2026-08-27 랩미팅 지시(2026-08-31 스코프 축소): Gaussian 2SFCA vs Gravity Model
2개 모형 비교용 Gi* 핫스팟/콜드스팟 분석. Cumulative Opportunity는 처음부터 제외
(2026-08-31 결정 — 3모형→2모형으로 최종 비교 범위 축소, 관련 코드는
archive/superseded/에 보존).

기존 three_model_hotspot.py + plot_two_model_hotspot.py(3모형 CSV에서 2개만 필터링)
조합을 대체 — 계산 단계부터 2개 모형만 돌려서 불필요한 CumOpp 계산을 안 함.

범위: 2021~2024년 평일 낮(week_낮_normal) 단일 시나리오, 2개 모형 x 4개년 = 8개 조합.
공간가중치는 이 비교 과제에 한해 KNN(k=30) 사용 — 기존 우선설치 후보지 분석
(hotspot_gi_star.py, k=8)과는 별개, 혼동 금지.

이번 분석은 "우선설치 후보지 진단"이 아니라 "모형 간 지역 패턴 비교"가 목적이라
고수요 교차필터(우선후보 판정)는 적용하지 않고, Hot/Cold/Not Sig 분류만 산출.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal
import esda

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
YEARS = [2021, 2022, 2023, 2024]
K_NEIGHBORS = 30
P_THRESHOLD = 0.05

MODELS = {
    "2SFCA": lambda year: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{year}_week_낮_normal.csv",
    "Gravity": lambda year: f"{NAS}/output/gravity_model_gaussian/gravity_score_{year}_week_낮_normal.csv",
}

OUT_FP = f"{NAS}/output/two_model_hotspot_k30.csv"


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
    return coded, y


def main():
    gdf = load_boundary()
    w = build_knn_weights(gdf, K_NEIGHBORS)
    print(f">> 집계구 {len(gdf):,}개, KNN(k={K_NEIGHBORS}) 공간가중치 구축 완료")

    records = []
    for model_name, path_fn in MODELS.items():
        for year in YEARS:
            fp = path_fn(year)
            coded, y = gi_star(gdf, w, fp)
            n_hot = (coded == "Hot Spot").sum()
            n_cold = (coded == "Cold Spot").sum()
            n_notsig = (coded == "Not Sig").sum()
            print(f"  [{model_name}] {year}: Hot {n_hot:5d} | Cold {n_cold:5d} | Not Sig {n_notsig:5d}")
            for oa, c in zip(gdf["TOT_REG_CD"], coded):
                records.append({"model": model_name, "year": year, "oa_code": oa, "gi_class": c})

    df = pd.DataFrame(records)
    df.to_csv(OUT_FP, index=False, encoding="utf-8-sig")
    print(f"\n>> 저장 완료: {OUT_FP} ({len(df):,}행 = 8개 조합 x {len(gdf):,}집계구)")


if __name__ == "__main__":
    main()
