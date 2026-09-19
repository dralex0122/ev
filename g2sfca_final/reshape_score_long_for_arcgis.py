"""
ArcGIS Pro "Create Space Time Cube From Defined Locations"가 wide-format
(score_2021~2024 컬럼)을 못 받고 실제 Time Field(날짜형)가 있는 long-format만
받아서, 사용자가 GUI에서 "Table To Time Series"로 직접 변환하기 어렵다고 해서
대신 파이썬으로 reshape. 필드명은 shapefile(DBF) 10자 제한 준수.

wide g2sfca_score_wide_2021_2024_week_낮_normal.shp(19,153행) ->
long g2sfca_score_long_2021_2024.shp(19,153*4=76,612행), 위치당 연도별 1행 +
TIME_STEP(날짜형 필드).
"""
import geopandas as gpd
import pandas as pd

NAS = "/mnt/cowork/EV"
IN_FP = f"{NAS}/output/arcgis_spacetimecube/g2sfca_score_wide_2021_2024_week_낮_normal.shp"
OUT_FP = f"{NAS}/output/arcgis_spacetimecube/g2sfca_score_long_2021_2024.shp"

YEARS = [2021, 2022, 2023, 2024]


def main():
    gdf = gpd.read_file(IN_FP)
    print(f">> 원본 wide: {len(gdf):,}행, 필드 {list(gdf.columns)}")

    rows = []
    for year in YEARS:
        sub = gdf[["TOT_REG_CD", "ADM_NM", f"score_{year}", "geometry"]].copy()
        sub = sub.rename(columns={f"score_{year}": "score"})
        sub["TIME_STEP"] = pd.Timestamp(f"{year}-01-01")
        rows.append(sub)

    long_gdf = gpd.GeoDataFrame(pd.concat(rows, ignore_index=True), geometry="geometry", crs=gdf.crs)
    long_gdf = long_gdf[["TOT_REG_CD", "ADM_NM", "TIME_STEP", "score", "geometry"]]

    long_gdf.to_file(OUT_FP)
    print(f">> long 저장: {OUT_FP} ({len(long_gdf):,}행 = {len(gdf):,}위치 x {len(YEARS)}개년)")
    print(long_gdf.dtypes)
    print(long_gdf.head(8)[["TOT_REG_CD", "ADM_NM", "TIME_STEP", "score"]])


if __name__ == "__main__":
    main()
