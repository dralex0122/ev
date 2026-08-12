"""2016년 집계구(서울 열린데이터광장 제공) 경계 shapefile에서 중심점 좌표(WGS84) 산출.
인구 데이터의 집계구코드(TOT_REG_CD)와 100% 일치 확인됨 - 2025년 SGIS 버전 대신 이 파일 사용.
"""
import geopandas as gpd

SRC = '/mnt/cowork/EV/input/raw/집계구_2016/집계구.shp'
OUT_CSV = '/mnt/cowork/EV/input/raw/집계구_2016/oa_centroids_2016_wgs84.csv'

gdf = gpd.read_file(SRC, encoding='cp949')
gdf = gdf.set_crs(epsg=5179, allow_override=True)
print(f'원본 폴리곤 수: {len(gdf)}, CRS 설정: {gdf.crs.to_string()[:50]}')

gdf['centroid_proj'] = gdf.geometry.centroid
centroids_wgs84 = gpd.GeoSeries(gdf['centroid_proj'], crs=gdf.crs).to_crs(epsg=4326)

out = gdf[['TOT_REG_CD', 'ADM_CD', 'ADM_NM']].copy()
out['lon'] = centroids_wgs84.x
out['lat'] = centroids_wgs84.y

out.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
print(f'저장 완료: {OUT_CSV} ({len(out)}행)')
print(out.head(5).to_string())
print('좌표 범위: lon', out.lon.min(), '~', out.lon.max(), '/ lat', out.lat.min(), '~', out.lat.max())
