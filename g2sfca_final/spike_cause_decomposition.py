"""
9/2 랩미팅 반복 강조 피드백 대응 — "패턴 보여주기"에서 "왜 그런지 설명하기"로.
2021→2022 접근성 급증 상위 동에 대해, 증가 원인을 세 갈래로 분해:
  ① 신규 공급 — 그 동에서 새로 도달 가능해진(15분 이내) 급속충전소가 있는가
  ② 도로망 개선 — 기존에 이미 도달 가능하던 충전소까지의 이동시간이 단축됐는가
  ③ 계산 오류 — 이상치(음수/0초/급격한 값 변화) 없는지

방법: OD(이동시간) 원본을 그대로 써서(재계산 없음), 유효공급(아파트 제외+
운영시간 필터, g2sfca_final_supply.py와 동일 로직) 통과하는 15분 이내
충전소 집합을 연도별로 구성 — 신규/기존으로 나눠서 신규는 개수, 기존은
이동시간 변화(초)를 집계. 동 단위(ADM_NM)로 집계구를 묶어서 봄.
"""
import json
import os
import re
import unicodedata
import numpy as np
import pandas as pd
import geopandas as gpd

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
GAUSSIAN_OD_DIR = f"{NAS}/output/g2sfca_sfast_gaussian"
CHARGER_DIR_FASTONLY = f"{NAS}/input/processed/yearly_snapshots_fastonly"
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"
SCORE_PATH = lambda year: f"{NAS}/output/g2sfca_sfast_final_gaussian/g2sfca_score_{year}_week_낮_normal.csv"
OUT_CSV = f"{NAS}/output/spike_cause_decomposition_2021_2022.csv"

CUTOFF_SEC = 900  # 15분
WINDOW_START, WINDOW_END = 11, 13
DAYTYPE = "week"
TOP_N_DONG = 10

GU_MAP = {
    "11010": "종로구", "11020": "중구", "11030": "용산구", "11040": "성동구", "11050": "광진구",
    "11060": "동대문구", "11070": "중랑구", "11080": "성북구", "11090": "강북구", "11100": "도봉구",
    "11110": "노원구", "11120": "은평구", "11130": "서대문구", "11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구", "11180": "금천구", "11190": "영등포구", "11200": "동작구",
    "11210": "관악구", "11220": "서초구", "11230": "강남구", "11240": "송파구", "11250": "강동구",
}

TIME_RANGE_RE = re.compile(r"(\d{1,2})[:시](\d{2})?\s*[~-]\s*(\d{1,2})[:시](\d{2})?")


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
    """그 해 week_낮(11~13시) 기준 유효공급(아파트 제외+운영시간 통과) station_id 집합."""
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
    """연도별 OD에서 15분 이내 + 유효공급 통과하는 (oa_code, station_id, travel_time_sec)만."""
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
    print(f"   2021 유효충전소 {len(valid_2021)}개, 2022 유효충전소 {len(valid_2022)}개")

    od_2021 = load_reachable_od(2021, valid_2021)
    od_2022 = load_reachable_od(2022, valid_2022)

    # 상위 급증 동 재산출(2SFCA, week_낮_normal, Δscore 기준)
    s21 = pd.read_csv(SCORE_PATH(2021), dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"]
    s22 = pd.read_csv(SCORE_PATH(2022), dtype={"oa_code": str}).set_index("oa_code")["accessibility_score"]
    delta = (s22 - s21).to_frame("delta").join(oa_to_dong)
    dong_delta = delta.groupby(["gu", "ADM_NM"])["delta"].sum().sort_values(ascending=False)
    top_dongs = dong_delta.head(TOP_N_DONG)

    print(f"\n=== 상위 {TOP_N_DONG}개 급증 동 원인 분해 (2021→2022, week_낮_normal, 2SFCA) ===\n")

    records = []
    for (gu, dong), dscore in top_dongs.items():
        oa_codes = oa_to_dong[(oa_to_dong["gu"] == gu) & (oa_to_dong["ADM_NM"] == dong)].index.tolist()

        r21 = od_2021[od_2021["oa_code"].isin(oa_codes)]
        r22 = od_2022[od_2022["oa_code"].isin(oa_codes)]

        stations_21 = set(r21["station_id"])
        stations_22 = set(r22["station_id"])
        new_stations = stations_22 - stations_21
        common_stations = stations_22 & stations_21

        # 기존(공통) 충전소까지의 이동시간 변화 — (oa_code, station_id) 쌍 기준
        m21 = r21[r21["station_id"].isin(common_stations)].set_index(["oa_code", "station_id"])["travel_time_sec"]
        m22 = r22[r22["station_id"].isin(common_stations)].set_index(["oa_code", "station_id"])["travel_time_sec"]
        common_idx = m21.index.intersection(m22.index)
        tt_delta = (m22.loc[common_idx] - m21.loc[common_idx])
        mean_tt_delta = tt_delta.mean() if len(tt_delta) > 0 else np.nan

        # 이상치 점검: 음수 이동시간, 0초, 극단적 변화(>600초 단축/연장)
        anomaly = ((tt_delta.abs() > 600).sum() if len(tt_delta) > 0 else 0)

        # 판정
        has_new_supply = len(new_stations) > 0
        has_faster_road = (not np.isnan(mean_tt_delta)) and mean_tt_delta < -10  # 평균 10초 이상 단축
        if has_new_supply and has_faster_road:
            verdict = "공급+도로망 복합"
        elif has_new_supply:
            verdict = "신규 공급형"
        elif has_faster_road:
            verdict = "도로망 개선형"
        else:
            verdict = "원인 불명확(계산 재확인 필요)"

        print(f"[{gu} {dong}] Δscore={dscore:.6f}")
        print(f"  - 신규 도달 충전소: {len(new_stations)}개")
        print(f"  - 기존 충전소({len(common_stations)}개) 평균 이동시간 변화: {mean_tt_delta:+.1f}초" if not np.isnan(mean_tt_delta) else "  - 기존 충전소 없음(비교 불가)")
        print(f"  - 이상치(600초 초과 급변) 쌍: {anomaly}개")
        print(f"  - 판정: {verdict}\n")

        records.append({
            "gu": gu, "dong": dong, "delta_score": dscore,
            "n_new_stations": len(new_stations), "n_common_stations": len(common_stations),
            "mean_tt_delta_sec": mean_tt_delta, "n_anomaly_pairs": anomaly, "verdict": verdict,
        })

    pd.DataFrame(records).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {OUT_CSV}")


if __name__ == "__main__":
    main()
