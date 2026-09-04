"""
포스터 필수 콘텐츠 "연구지역 지도(충전소 포인트 포함)" — 9/2 랩미팅 원본 전사 확인
(2026-09-04) 기준: "연구지역을 보여주는 지도... 충전소의 포인트[를] 넣어라".
Figure4/Gi* 지도와는 별개의 산출물.

서울 25개 자치구 경계(집계구를 자치구 단위로 dissolve) + 2024년 기준 급속충전소
포인트(최종 방법론과 동일하게 아파트 소재 제외) 오버레이. 자치구 이름 라벨 포함.
"""
import json
import os
import unicodedata
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
CHARGER_FP = unicodedata.normalize(
    "NFD", f"{NAS}/input/processed/yearly_snapshots_fastonly/metro7_ev_chargers_2024_fastonly.geojson"
)
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"
OUT_PNG = f"{NAS}/output/maps/poster_study_area_map.png"

GU_MAP = {
    "11010": "종로구", "11020": "중구", "11030": "용산구", "11040": "성동구", "11050": "광진구",
    "11060": "동대문구", "11070": "중랑구", "11080": "성북구", "11090": "강북구", "11100": "도봉구",
    "11110": "노원구", "11120": "은평구", "11130": "서대문구", "11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구", "11180": "금천구", "11190": "영등포구", "11200": "동작구",
    "11210": "관악구", "11220": "서초구", "11230": "강남구", "11240": "송파구", "11250": "강동구",
}

GU_FILL = "#f2ede1"
GU_BORDER = "#a89f8a"
PT_COLOR = "#c0392b"
INK = "#2b2b2b"
MUTED = "#7a7568"


def load_gu_boundary():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy()
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)
    gu = gdf.dissolve(by="gu").reset_index()
    # dissolve 후에도 집계구 세부 경계(도로/하천 등 미세 틈)가 남아 지저분해 보여서
    # 살짝 buffer(+)-buffer(-)로 틈을 메운 뒤 simplify로 정리
    gu["geometry"] = gu.geometry.buffer(15).buffer(-15).simplify(20)
    return gu


def load_chargers():
    with open(CHARGER_FP, encoding="utf-8") as f:
        data = json.load(f)
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])

    rows = []
    for feat in data["features"]:
        p = feat["properties"]
        if p.get("city") != "서울특별시":
            continue
        if p["station_id"] in apt_set:
            continue
        lon, lat = feat["geometry"]["coordinates"]
        rows.append({"station_id": p["station_id"], "fast_count": p.get("fast_count", 0) or 0,
                     "geometry": Point(lon, lat)})
    pts = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return pts.to_crs(epsg=5179)


def main():
    gu = load_gu_boundary()
    pts = load_chargers()
    print(f"자치구 {len(gu)}개, 충전소(아파트 제외) {len(pts)}개, 급속충전기 총 {pts['fast_count'].sum():,}대")

    fig, ax = plt.subplots(figsize=(10, 10.5))
    gu.plot(ax=ax, color=GU_FILL, edgecolor=GU_BORDER, linewidth=0.9)
    pts.plot(ax=ax, color=PT_COLOR, markersize=6, alpha=0.55, linewidth=0)

    for _, row in gu.iterrows():
        c = row.geometry.representative_point()
        ax.text(c.x, c.y, row["gu"], fontsize=7.5, color=INK, ha="center", va="center",
                fontweight="medium")

    ax.set_axis_off()
    ax.set_title("연구지역 — 서울시 25개 자치구 및 급속충전소 위치", fontsize=16, color=INK, fontweight="bold", pad=14)
    fig.text(0.5, 0.045, f"2024년 기준, 급속충전소 {len(pts):,}개소(아파트 소재 제외) · 집계구(2016년 경계) 자치구 단위 병합",
              ha="center", fontsize=10, color=MUTED)

    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(OUT_PNG, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"saved {OUT_PNG}")


if __name__ == "__main__":
    main()
