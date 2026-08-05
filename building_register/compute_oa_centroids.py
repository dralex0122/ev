"""집계구(統計廳 Output Area) 경계 shapefile에서 중심점 좌표(WGS84) 산출."""
import geopandas as gpd

SRC = '/mnt/cowork/EV/집계구_2025_2Q/bnd_oa_11_2025_2Q.shp'
OUT_CSV = '/mnt/cowork/EV/집계구_2025_2Q/oa_centroids_wgs84.csv'

gdf = gpd.read_file(SRC)
print(f'원본 폴리곤 수: {len(gdf)}, CRS: {gdf.crs.to_string()[:60]}')

# 투영좌표계 상태에서 centroid 계산 (평면기하라 정확함)
gdf['centroid_proj'] = gdf.geometry.centroid

# WGS84(위경도)로 변환
centroids_wgs84 = gpd.GeoSeries(gdf['centroid_proj'], crs=gdf.crs).to_crs(epsg=4326)

out = gdf[['TOT_OA_CD', 'ADM_CD', 'BASE_DATE']].copy()
out['lon'] = centroids_wgs84.x
out['lat'] = centroids_wgs84.y

out.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
print(f'저장 완료: {OUT_CSV} ({len(out)}행)')
print(out.head(5).to_string())
print('좌표 범위: lon', out.lon.min(), '~', out.lon.max(), '/ lat', out.lat.min(), '~', out.lat.max())
