"""
spike_cause_xy_quadrant.py 확장 — 급증 상위 10개 동만이 아니라 서울시 전체
행정동(gu+ADM_NM) 대상으로 같은 원인분해(신규 도달 충전소 수 vs 기존 충전소
이동시간 단축)를 계산해서, 상위 10개 동이 전체 분포에서 얼마나 튀는 값인지
배경으로 보여줌. 전체 동은 회색 무라벨 배경점, 상위 10개 동만 기존과 동일하게
색상+라벨(spike_cause_decomposition.py의 verdict 재사용).

spike_cause_decomposition.py와 동일 로직(OD 원본 재사용, 15분 컷오프, 유효공급
필터)이되 TOP_N_DONG 제한을 없애고 전체 동에 대해 벡터화 연산으로 계산.
"""
import json
import os
import re
import unicodedata
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
GAUSSIAN_OD_DIR = f"{NAS}/output/g2sfca_sfast_gaussian"
CHARGER_DIR_FASTONLY = f"{NAS}/input/processed/yearly_snapshots_fastonly"
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"
TOP10_FP = f"{NAS}/output/spike_cause_decomposition_2021_2022.csv"
OUT_CSV = f"{NAS}/output/spike_cause_decomposition_all_dong_2021_2022.csv"
OUT_PNG = f"{NAS}/output/maps/spike_cause_xy_quadrant_all_dong.png"

CUTOFF_SEC = 900
WINDOW_START, WINDOW_END = 11, 13
DAYTYPE = "week"

GU_MAP = {
    "11010": "종로구", "11020": "중구", "11030": "용산구", "11040": "성동구", "11050": "광진구",
    "11060": "동대문구", "11070": "중랑구", "11080": "성북구", "11090": "강북구", "11100": "도봉구",
    "11110": "노원구", "11120": "은평구", "11130": "서대문구", "11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구", "11180": "금천구", "11190": "영등포구", "11200": "동작구",
    "11210": "관악구", "11220": "서초구", "11230": "강남구", "11240": "송파구", "11250": "강동구",
}

TIME_RANGE_RE = re.compile(r"(\d{1,2})[:시](\d{2})?\s*[~-]\s*(\d{1,2})[:시](\d{2})?")

COLOR_SUPPLY = "#c0392b"
COLOR_MIXED = "#33586b"
COLOR_BG = "#c9c2ae"
INK = "#2b2b2b"
MUTED = "#7a7568"


def parse_open_window(text):
    if not text or not text.strip() or "24시간" in text or "24시" in text:
        return None
    m = TIME_RANGE_RE.search(text.strip())
    if not m:
        return None
    h1, _, h2, _ = m.groups()
    start, end = int(h1), int(h2)
    weekday_only = ("평일" in text) or ("주중" in text)
    return (start, end, weekday_only)


def is_open(parsed, window_start, window_end, daytype):
    if parsed is None:
        return True
    start, end, weekday_only = parsed
    if weekday_only and daytype == "weekend":
        return False
    if end <= start:
        return True
    return not (end <= window_start or start >= window_end)


def load_valid_stations(year, apt_set):
    fname = f"metro7_ev_chargers_{year}_fastonly.geojson"
    fp = unicodedata.normalize("NFD", os.path.join(CHARGER_DIR_FASTONLY, fname))
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    valid = set()
    for feat in data["features"]:
        p = feat["properties"]
        if p.get("city") != "서울특별시":
            continue
        sid = p["station_id"]
        if sid in apt_set:
            continue
        hours = parse_open_window(p.get("openinghour", ""))
        if is_open(hours, WINDOW_START, WINDOW_END, DAYTYPE):
            valid.add(sid)
    return valid


def load_reachable_od(year, valid_stations):
    od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{year}_week_낮_normal.csv", dtype={"station_id": str, "oa_code": str})
    od = od[od["travel_time_sec"] <= CUTOFF_SEC]
    od = od[od["station_id"].isin(valid_stations)]
    return od


def main():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")][["TOT_REG_CD", "ADM_NM"]].copy()
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)
    oa_to_dong = gdf.set_index("TOT_REG_CD")[["gu", "ADM_NM"]]

    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])

    print(">> 유효공급 충전소 집합 로딩 중...")
    valid_2021 = load_valid_stations(2021, apt_set)
    valid_2022 = load_valid_stations(2022, apt_set)

    od_2021 = load_reachable_od(2021, valid_2021).join(oa_to_dong, on="oa_code")
    od_2022 = load_reachable_od(2022, valid_2022).join(oa_to_dong, on="oa_code")
    print(f">> 2021 도달쌍 {len(od_2021):,} / 2022 도달쌍 {len(od_2022):,}")

    # --- 동별 신규 도달 충전소 수: 동 단위로 station_id 집합 차집합 ---
    st21 = od_2021.groupby(["gu", "ADM_NM"])["station_id"].apply(set)
    st22 = od_2022.groupby(["gu", "ADM_NM"])["station_id"].apply(set)
    all_dong = st21.index.union(st22.index)
    st21 = st21.reindex(all_dong, fill_value=set())
    st22 = st22.reindex(all_dong, fill_value=set())
    n_new = (st22 - st21).apply(len)

    # --- 동별 기존(공통) 충전소까지 평균 이동시간 변화: 전역 merge 후 동별 groupby ---
    m21 = od_2021[["oa_code", "station_id", "travel_time_sec", "gu", "ADM_NM"]]
    m22 = od_2022[["oa_code", "station_id", "travel_time_sec"]]
    merged = m21.merge(m22, on=["oa_code", "station_id"], suffixes=("_21", "_22"), how="inner")
    merged["tt_delta"] = merged["travel_time_sec_22"] - merged["travel_time_sec_21"]
    mean_tt_delta = merged.groupby(["gu", "ADM_NM"])["tt_delta"].mean()
    mean_tt_delta = mean_tt_delta.reindex(all_dong)

    df = pd.DataFrame({"n_new_stations": n_new, "mean_tt_delta_sec": mean_tt_delta}).reindex(all_dong)
    df.index = pd.MultiIndex.from_tuples(all_dong, names=["gu", "dong"])
    df = df.reset_index()
    df["tt_shortened_sec"] = -df["mean_tt_delta_sec"].fillna(0)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f">> 전체 {len(df):,}개 동 계산 완료, 저장: {OUT_CSV}")

    # --- 상위 10개 동(기존 계산 재사용, verdict·라벨용) ---
    top10 = pd.read_csv(TOP10_FP)
    top10["tt_shortened_sec"] = -top10["mean_tt_delta_sec"].fillna(0)
    top10_keys = set(zip(top10["gu"], top10["dong"]))

    bg = df[~df.apply(lambda r: (r["gu"], r["dong"]) in top10_keys, axis=1)]

    fig, ax = plt.subplots(figsize=(9.5, 8))
    ax.scatter(bg["n_new_stations"], bg["tt_shortened_sec"], s=18, color=COLOR_BG, alpha=0.55,
               linewidth=0, zorder=2, label=f"나머지 {len(bg):,}개 동")

    verdict_color = {"신규 공급형": COLOR_SUPPLY, "공급+도로망 복합": COLOR_MIXED}
    verdict_label = {"신규 공급형": "신규공급형(상위10)", "공급+도로망 복합": "공급+도로망 복합(상위10)"}
    for verdict, sub in top10.groupby("verdict"):
        ax.scatter(sub["n_new_stations"], sub["tt_shortened_sec"], s=120,
                   color=verdict_color[verdict], edgecolor="white", linewidth=0.9,
                   zorder=4, label=verdict_label[verdict])
    for _, r in top10.iterrows():
        ax.annotate(f"{r['gu']} {r['dong']}", (r["n_new_stations"], r["tt_shortened_sec"]),
                    textcoords="offset points", xytext=(7, 5), fontsize=8.5, color=INK, zorder=5)

    ax.axhline(0, color=MUTED, linewidth=0.7, zorder=1)
    ax.axvline(0, color=MUTED, linewidth=0.7, zorder=1)

    ax.set_xlabel("신규 도달 급속충전소 수 (개, 2021→2022)", fontsize=11)
    ax.set_ylabel("기존 충전소까지 평균 이동시간 단축 (초, 2021→2022)", fontsize=11)
    ax.set_title("서울시 전체 동 — 공급 변화 vs 이동성 변화\n(급증 상위 10개 동 강조 표시)", fontsize=14.5, fontweight="bold", color=INK, pad=14)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)

    n_bg_at_origin = ((bg["n_new_stations"] == 0) & (bg["tt_shortened_sec"] == 0)).sum()
    fig.text(0.5, -0.02,
              f"Δ2SFCA score(week_낮_normal) 상위 10개 동 강조 · 나머지 동 중 {n_bg_at_origin:,}개는 공급·이동시간 변화 전혀 없음(원점 밀집)",
              ha="center", fontsize=8.5, color=MUTED)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"saved {OUT_PNG}")


if __name__ == "__main__":
    main()
