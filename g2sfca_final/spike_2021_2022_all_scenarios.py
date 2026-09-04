"""
2021→2022 구 단위 집중도 재확인 — week_낮_normal 단일 시나리오(32.5%)가 어제 나온
40.8%와 안 맞아서, 5개 확정 시나리오(hotspot_gi_star.py와 동일 범위) 전부 합산해서
재계산. 2SFCA만 — Gravity는 week_낮만 계산돼 있어 5개 시나리오 비교 불가.
"""
import pandas as pd
import geopandas as gpd

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
FINAL_GAUSSIAN_DIR = f"{NAS}/output/g2sfca_sfast_final_gaussian"
SIMYA_GAUSSIAN_DIR = f"{NAS}/output/g2sfca_sfast_simya_gaussian"
TOP_N_GU = 5

CONFIRMED_SCENARIOS = [
    (FINAL_GAUSSIAN_DIR, "week_오전_congested"),
    (FINAL_GAUSSIAN_DIR, "week_낮_normal"),
    (FINAL_GAUSSIAN_DIR, "weekend_오전_freeflow"),
    (FINAL_GAUSSIAN_DIR, "weekend_낮_normal"),
    (SIMYA_GAUSSIAN_DIR, "week_심야"),
]

GU_MAP = {
    "11010": "종로구", "11020": "중구", "11030": "용산구", "11040": "성동구", "11050": "광진구",
    "11060": "동대문구", "11070": "중랑구", "11080": "성북구", "11090": "강북구", "11100": "도봉구",
    "11110": "노원구", "11120": "은평구", "11130": "서대문구", "11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구", "11180": "금천구", "11190": "영등포구", "11200": "동작구",
    "11210": "관악구", "11220": "서초구", "11230": "강남구", "11240": "송파구", "11250": "강동구",
}


def load_boundary():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")][["TOT_REG_CD", "ADM_NM"]].copy()
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)
    return gdf


def main():
    gdf = load_boundary()
    total_delta = pd.Series(0.0, index=gdf["TOT_REG_CD"])

    for base, suffix in CONFIRMED_SCENARIOS:
        s21 = pd.read_csv(f"{base}/g2sfca_score_2021_{suffix}.csv", dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"]
        s22 = pd.read_csv(f"{base}/g2sfca_score_2022_{suffix}.csv", dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"]
        d = (s22 - s21).reindex(gdf["TOT_REG_CD"]).fillna(0)
        total_delta += d.values
        gdf_tmp = gdf.copy()
        gdf_tmp["delta"] = d.values
        gu_sum = gdf_tmp.groupby("gu")["delta"].sum().sort_values(ascending=False)
        share = gu_sum / gu_sum.sum() * 100
        print(f"[{suffix}] 상위5구 집중도: {share.head(TOP_N_GU).sum():.1f}%  ({', '.join(share.head(TOP_N_GU).index)})")

    gdf["delta"] = total_delta.values
    gu_sum = gdf.groupby("gu")["delta"].sum().sort_values(ascending=False)
    share = gu_sum / gu_sum.sum() * 100
    cum = share.cumsum()
    print(f"\n=== 5개 시나리오 전부 합산 — 구 단위 Δscore(2022-2021) 순위 ===")
    for gu, v in share.head(10).items():
        print(f"  {gu}: {v:5.1f}%  (누적 {cum[gu]:5.1f}%)")
    print(f"\n상위{TOP_N_GU}구 집중도(5개 시나리오 합산): {share.head(TOP_N_GU).sum():.1f}%")


if __name__ == "__main__":
    main()
