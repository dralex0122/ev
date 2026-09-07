"""
2021년 vs 2024년 Gi* 핫스팟/콜드스팟 전이(transition) 분석 — 2SFCA, Gravity 각각.
two_model_hotspot.py가 계산 단계부터 2개 모형만 돌려 저장한
two_model_hotspot_k30.csv(재계산 불필요) 활용.
"""
import pandas as pd
import geopandas as gpd

NAS = "/mnt/cowork/EV"
HOTSPOT_FP = f"{NAS}/output/two_model_hotspot_k30.csv"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
OUT_FP = f"{NAS}/output/hotspot_transition_2021_2024.csv"

GU_MAP = {
    "11010":"종로구","11020":"중구","11030":"용산구","11040":"성동구","11050":"광진구",
    "11060":"동대문구","11070":"중랑구","11080":"성북구","11090":"강북구","11100":"도봉구",
    "11110":"노원구","11120":"은평구","11130":"서대문구","11140":"마포구","11150":"양천구",
    "11160":"강서구","11170":"구로구","11180":"금천구","11190":"영등포구","11200":"동작구",
    "11210":"관악구","11220":"서초구","11230":"강남구","11240":"송파구","11250":"강동구",
}

def classify_transition(row):
    a, b = row["2021"], row["2024"]
    simple = lambda x: "Hot" if x == "Hot Spot" else ("Cold" if x == "Cold Spot" else "NotSig")
    a, b = simple(a), simple(b)
    if a == "Cold" and b == "Cold":
        return "지속콜드"
    if a == "Hot" and b == "Cold":
        return "신규악화(Hot->Cold)"
    if a == "Cold" and b == "Hot":
        return "개선(Cold->Hot)"
    if a == "Hot" and b == "Hot":
        return "지속핫"
    if a == "NotSig" and b == "Cold":
        return "신규콜드(NotSig->Cold)"
    if a == "Cold" and b == "NotSig":
        return "콜드탈출(Cold->NotSig)"
    return f"{a}->{b}"

def main():
    hs = pd.read_csv(HOTSPOT_FP, dtype={"oa_code": str})
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")][["TOT_REG_CD", "ADM_NM"]].rename(columns={"TOT_REG_CD": "oa_code"})
    gdf["gu"] = gdf["oa_code"].str[:5].map(GU_MAP)

    all_results = []
    for model in ["2SFCA", "Gravity"]:
        sub = hs[hs["model"] == model]
        piv = sub[sub["year"].isin([2021, 2024])].pivot(index="oa_code", columns="year", values="gi_class")
        piv.columns = [str(c) for c in piv.columns]
        piv = piv.reset_index()
        piv["transition"] = piv.apply(classify_transition, axis=1)
        piv["model"] = model
        all_results.append(piv)
        print(f"\n=== {model} 전이 유형별 집계구 수 ===")
        print(piv["transition"].value_counts())

    result = pd.concat(all_results, ignore_index=True)
    result = result.merge(gdf, on="oa_code", how="left")
    result.to_csv(OUT_FP, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {OUT_FP}")

    # 지속콜드 상위 동 (모형별)
    for model in ["2SFCA", "Gravity"]:
        sub = result[(result.model == model) & (result.transition == "지속콜드")]
        print(f"\n=== {model} 지속콜드 상위 동 ===")
        print(sub.groupby(["gu", "ADM_NM"]).size().sort_values(ascending=False).head(10))

    # 신규악화 상위 동 (모형별)
    for model in ["2SFCA", "Gravity"]:
        sub = result[(result.model == model) & (result.transition == "신규악화(Hot->Cold)")]
        print(f"\n=== {model} 신규악화(Hot->Cold) 상위 동 ===")
        print(sub.groupby(["gu", "ADM_NM"]).size().sort_values(ascending=False).head(10))

    # 두 모형 다 지속콜드인 집계구 (교차 검증)
    c2s = set(result[(result.model=="2SFCA") & (result.transition=="지속콜드")]["oa_code"])
    cgr = set(result[(result.model=="Gravity") & (result.transition=="지속콜드")]["oa_code"])
    both = c2s & cgr
    only2s = c2s - cgr
    print(f"\n=== 교차검증 ===")
    print(f"2SFCA만 지속콜드: {len(c2s)}개 / Gravity만 지속콜드: {len(cgr)}개")
    print(f"둘 다 지속콜드(진짜 구조적 문제): {len(both)}개")
    print(f"2SFCA만 지속콜드, Gravity는 아님(수요압박형): {len(only2s)}개")

if __name__ == "__main__":
    main()
