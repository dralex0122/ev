"""
2026-08-26: 전기차 충전소 우선설치 후보지역 진단 — Getis-Ord Gi* 핫스팟/콜드스팟 분석.

배경: 박진우 교수님 논문(Leveraging temporal changes...)의 GitHub 공개 코드
(getis_ord_G_local 함수)를 그대로 재현. esda.getisord.G_Local(y, w, transform='B'),
p<0.05 단일 기준으로 Hot/Cold/Not Sig 판정 — 교수님 코드에도 FDR 등 다중검정
보정은 없어 동일하게 적용 안 함.

공간가중치는 교수님의 DistanceBand(900m, 균일 육각형 격자 기준) 대신 KNN(k=8)을
씀 — 우리 집계구는 크기가 불균일해서 900m를 그대로 쓰면 평균 122개 이웃이 잡혀
과도하게 평활화됨(집계구 중심점 기준 실측). KNN(k=8)은 중앙값 이웃거리 203m로
훨씬 국지적인 관계를 안정적으로 유지.

범위: 5개 확정 시나리오(week_오전_congested, week_낮_normal,
weekend_오전_freeflow, weekend_낮_normal, week_심야) x 2021~2024 = 20개 조합.
각 조합을 독립적으로 Gi* 검정한 뒤, 콜드스팟이면서 수요(생활인구)가 중위값
이상인 집계구를 "우선후보"로 표시하고, 20개 조합 중 몇 번 우선후보로 뽑혔는지
지속성(persistence)을 집계함 — 병합 분석이 아니라 사후 집계.

weekend_심야는 탐색적 검토용으로 별도 계산만 하고(평일/주말 심야 접근성
상관관계 Pearson r=0.95~0.96로 사실상 동일 확인) 지속성 집계에는 포함하지 않음
— 심야는 평일 단일 시나리오로 이미 확정.

결과: 20/20 전부에서 일관되게 우선후보로 나온 집계구 112개. 강동구 길동(20)·
천호1동(16)·천호2동(12), 관악구 난곡동(10)·난향동(6)이 최상위 — 노션 "🎯 우선설치
후보지역" 토글 및 발표자료에 반영 완료.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal
import esda

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
D1_FP = f"{NAS}/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)/d1_final_2021_2024.csv"
FINAL_GAUSSIAN_DIR = f"{NAS}/output/g2sfca_sfast_final_gaussian"
SIMYA_GAUSSIAN_DIR = f"{NAS}/output/g2sfca_sfast_simya_gaussian"
OUT_CSV = f"{NAS}/output/hotspot_persistence_final.csv"

K_NEIGHBORS = 8
P_THRESHOLD = 0.05
YEARS = [2021, 2022, 2023, 2024]

GU_MAP = {
    "11010": "종로구", "11020": "중구", "11030": "용산구", "11040": "성동구", "11050": "광진구",
    "11060": "동대문구", "11070": "중랑구", "11080": "성북구", "11090": "강북구", "11100": "도봉구",
    "11110": "노원구", "11120": "은평구", "11130": "서대문구", "11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구", "11180": "금천구", "11190": "영등포구", "11200": "동작구",
    "11210": "관악구", "11220": "서초구", "11230": "강남구", "11240": "송파구", "11250": "강동구",
}

# 확정 시나리오 5개 — 지속성 집계 대상
CONFIRMED_SCENARIOS = [
    (FINAL_GAUSSIAN_DIR, "week_오전_congested", "오전_avg", "평일오전(congested)"),
    (FINAL_GAUSSIAN_DIR, "week_낮_normal", "낮_avg", "평일낮(normal)"),
    (FINAL_GAUSSIAN_DIR, "weekend_오전_freeflow", "오전_avg", "주말오전(freeflow)"),
    (FINAL_GAUSSIAN_DIR, "weekend_낮_normal", "낮_avg", "주말낮(normal)"),
    (SIMYA_GAUSSIAN_DIR, "week_심야", "심야_avg", "심야"),
]

# 탐색적 검토용 — 지속성 집계에서 제외(심야 단일 시나리오 확정 근거 검증용)
EXPLORATORY_SCENARIOS = [
    (SIMYA_GAUSSIAN_DIR, "weekend_심야", "심야_avg", "주말 심야(탐색적)"),
]


def load_boundary():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy().reset_index(drop=True)
    return gdf


def build_knn_weights(gdf):
    points = np.array([[p.x, p.y] for p in gdf.geometry.centroid])
    return libpysal.weights.KNN.from_array(points, k=K_NEIGHBORS)


def gi_star_priority(gdf, w, base, suffix, demand_col, year, demand_all):
    """한 (연도, 시나리오) 조합에 대해 Gi* 계산 + 고수요 콜드스팟(우선후보) 판정."""
    acc = pd.read_csv(f"{base}/g2sfca_score_{year}_{suffix}.csv", dtype={"oa_code": str})
    acc = acc.set_index("oa_code").reindex(gdf["TOT_REG_CD"]).reset_index()
    y = acc["accessibility_score"].fillna(0).values

    lg = esda.getisord.G_Local(y, w, transform="B")
    coded = np.where((lg.Zs < 0) & (lg.p_norm < P_THRESHOLD), "Cold Spot",
             np.where((lg.Zs > 0) & (lg.p_norm < P_THRESHOLD), "Hot Spot", "Not Sig"))

    demand_y = demand_all[demand_all["year"] == year].set_index("집계구코드")[demand_col]
    demand_vals = gdf["TOT_REG_CD"].map(demand_y).fillna(0).values
    median_demand = np.median(demand_vals[demand_vals > 0])

    is_priority = (coded == "Cold Spot") & (demand_vals >= median_demand)
    return coded, is_priority


def main():
    gdf = load_boundary()
    w = build_knn_weights(gdf)
    demand_all = pd.read_csv(D1_FP, dtype={"집계구코드": str})

    persistence = pd.Series(0, index=gdf["TOT_REG_CD"])
    n_confirmed_combos = 0

    for base, suffix, demand_col, label in CONFIRMED_SCENARIOS:
        for year in YEARS:
            coded, is_priority = gi_star_priority(gdf, w, base, suffix, demand_col, year, demand_all)
            n_confirmed_combos += 1
            persistence.loc[is_priority] += 1
            n_cold = (coded == "Cold Spot").sum()
            n_hot = (coded == "Hot Spot").sum()
            print(f"[확정] {label} {year}: Cold {n_cold}, Hot {n_hot}, 우선후보 {is_priority.sum()}")

    print(f"\n총 확정 조합 수: {n_confirmed_combos} (5개 시나리오 x {len(YEARS)}개년)")

    for base, suffix, demand_col, label in EXPLORATORY_SCENARIOS:
        for year in YEARS:
            coded, is_priority = gi_star_priority(gdf, w, base, suffix, demand_col, year, demand_all)
            n_cold = (coded == "Cold Spot").sum()
            n_hot = (coded == "Hot Spot").sum()
            print(f"[탐색적, 집계 제외] {label} {year}: Cold {n_cold}, Hot {n_hot}, 우선후보 {is_priority.sum()}")

    result = pd.DataFrame({
        "oa_code": gdf["TOT_REG_CD"],
        "gu": gdf["TOT_REG_CD"].str[:5].map(GU_MAP),
        "dong": gdf["ADM_NM"],
        "persistence": persistence.values,
        "n_combos": n_confirmed_combos,
    })
    result.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {OUT_CSV} ({len(result)}행)")

    full_persistent = result[result["persistence"] == n_confirmed_combos]
    print(f"\n=== {n_confirmed_combos}/{n_confirmed_combos} 전부에서 우선후보인 집계구: {len(full_persistent)}개 ===")
    dong_counts = full_persistent.groupby(["gu", "dong"]).size().sort_values(ascending=False)
    print(dong_counts.head(15).to_string())


if __name__ == "__main__":
    main()
