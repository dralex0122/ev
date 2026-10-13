"""
2026-10-07 랩미팅 지시 대응 — 이용제한 충전기(UseLimitation=Y, 버스·택시 차고지 등
비공용) 제외 + 입력 데이터(공급·수요·OD) 전수 재점검.

범위: week_낮_normal(11-13시), gaussian, 2021~2024, Gi* KNN k=20 (현재 확정 설정).
g2sfca_final_supply.py와 동일 로직(급속만, 아파트 v3 제외, 운영시간 판정)에
UseLimitation=Y 제외만 추가. 기존 결과(g2sfca_sfast_final_gaussian)는 덮어쓰지 않고
g2sfca_sfast_final_gaussian_nolimit에 따로 저장.

산출물(output/recheck_2026-10-13/):
  supply_audit.csv     연도별 충전소·충전기 수, 단계별 제외 내역
  demand_audit.csv     연도별 수요 집계구 매칭·결측·합계
  od_audit.csv         연도별 OD 행수·충전소/집계구 매칭·최대 이동시간
  hotspot_compare.csv  제외 전/후 Hot/Cold 개수(전체)
  hotspot_compare_gu.csv  제외 전/후 구별 Hot/Cold 개수
  gi_k20_before_after.csv 집계구별 제외 전/후 Gi* 분류
"""
import json
import os
import unicodedata

import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal
import esda

from g2sfca_final_supply import (
    NAS, D1_FP, CHARGER_DIR_FASTONLY, APT_FP, GAUSSIAN_OD_DIR, CUTOFF_SEC,
    parse_open_window, is_open, decay_gaussian,
)

BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
BEFORE_DIR = f"{NAS}/output/g2sfca_sfast_final_gaussian"
AFTER_DIR = f"{NAS}/output/g2sfca_sfast_final_gaussian_nolimit"
OUT_DIR = f"{NAS}/output/recheck_2026-10-13"
YEARS = [2021, 2022, 2023, 2024]
DAYTYPE, PERIOD, SCENARIO = "week", "낮", "normal"
W_START, W_END = 11, 13
K = 20
P_THRESHOLD = 0.05

GU_MAP = {
    "11010": "종로구", "11020": "중구", "11030": "용산구", "11040": "성동구", "11050": "광진구",
    "11060": "동대문구", "11070": "중랑구", "11080": "성북구", "11090": "강북구", "11100": "도봉구",
    "11110": "노원구", "11120": "은평구", "11130": "서대문구", "11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구", "11180": "금천구", "11190": "영등포구", "11200": "동작구",
    "11210": "관악구", "11220": "서초구", "11230": "강남구", "11240": "송파구", "11250": "강동구",
}


def load_stations(year):
    fname = f"metro7_ev_chargers_{year}_fastonly.geojson"
    fp = unicodedata.normalize("NFD", os.path.join(CHARGER_DIR_FASTONLY, fname))
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for feat in data["features"]:
        p = feat["properties"]
        if p.get("city") != "서울특별시":
            continue
        coords = (feat.get("geometry") or {}).get("coordinates") or [None, None]
        rows.append({
            "station_id": p["station_id"], "name": p.get("name"), "address": p.get("address"),
            "fast_count": p.get("fast_count") or 0, "openinghour": p.get("openinghour", ""),
            "UseLimitation": p.get("UseLimitation"), "lng": coords[0], "lat": coords[1],
        })
    df = pd.DataFrame(rows)
    df["open_parsed"] = df["openinghour"].apply(parse_open_window)
    df["is_open"] = df["open_parsed"].apply(lambda x: is_open(x, W_START, W_END, DAYTYPE))
    return df


def audit_supply(year, st, apt_set, od_sids):
    st = st.copy()
    st["is_apt"] = st["station_id"].isin(apt_set)
    st["is_limit"] = st["UseLimitation"] == "Y"
    base = st[~st.is_apt & st.is_open]                      # 기존 유효 공급
    after = base[~base.is_limit]                             # 이용제한 제외 후
    in_seoul_box = st.lat.between(37.41, 37.72) & st.lng.between(126.76, 127.19)
    return {
        "year": year,
        "stations_raw": len(st),
        "chargers_raw": int(st.fast_count.sum()),
        "dup_station_id": int(st.station_id.duplicated().sum()),
        "dup_coord_diff_id": int(st.duplicated(["lat", "lng"]).sum()),
        "coord_missing_or_outside_seoul": int((~in_seoul_box).sum()),
        "fast_count_zero": int((st.fast_count <= 0).sum()),
        "apt_excluded_stations": int(st.is_apt.sum()),
        "apt_excluded_chargers": int(st[st.is_apt].fast_count.sum()),
        "closed_11_13_stations": int((~st.is_apt & ~st.is_open).sum()),
        "closed_11_13_chargers": int(st[~st.is_apt & ~st.is_open].fast_count.sum()),
        "before_stations": len(base),
        "before_chargers": int(base.fast_count.sum()),
        "limitY_stations": int(base.is_limit.sum()),
        "limitY_chargers": int(base[base.is_limit].fast_count.sum()),
        "limitY_pct_chargers": round(100 * base[base.is_limit].fast_count.sum() / base.fast_count.sum(), 1),
        "after_stations": len(after),
        "after_chargers": int(after.fast_count.sum()),
        "eff_stations_missing_in_od": int((~base.station_id.isin(od_sids)).sum()),
    }


def audit_demand(year, d1, oa_set):
    d = d1[d1.year == year]
    v = d["낮_avg"]
    return {
        "year": year,
        "rows": len(d),
        "unique_oa": d["집계구코드"].nunique(),
        "dup_oa": int(d["집계구코드"].duplicated().sum()),
        "oa_not_in_boundary": int((~d["집계구코드"].isin(oa_set)).sum()),
        "boundary_oa_missing": len(oa_set - set(d["집계구코드"])),
        "nan": int(v.isna().sum()),
        "zero": int((v == 0).sum()),
        "negative": int((v < 0).sum()),
        "sum_낮_avg": round(float(v.sum()), 0),
        "median_낮_avg": round(float(v.median()), 1),
    }


def audit_od(year, od, st_sids, oa_set):
    return {
        "year": year,
        "rows": len(od),
        "stations": od.station_id.nunique(),
        "oa": od.oa_code.nunique(),
        "od_station_not_in_supply_file": len(set(od.station_id) - st_sids),
        "od_oa_not_in_boundary": len(set(od.oa_code) - oa_set),
        "dup_pairs": int(od.duplicated(["station_id", "oa_code"]).sum()),
        "max_tt_sec": round(float(od.travel_time_sec.max()), 1),
        "over_cutoff_rows": int((od.travel_time_sec > CUTOFF_SEC).sum()),
        "negative_or_nan_tt": int((od.travel_time_sec.isna() | (od.travel_time_sec < 0)).sum()),
        "median_tt_sec": round(float(od.travel_time_sec.median()), 1),
    }


def g2sfca(supply, demand, od):
    """g2sfca_final_supply.main()의 gaussian 계산과 동일."""
    od = od.copy()
    od["w"] = od.travel_time_sec.apply(decay_gaussian)
    od["dem"] = od.oa_code.map(demand).fillna(0)
    d_sum = (od.dem * od.w).groupby(od.station_id).sum()
    s = pd.Series(supply).reindex(d_sum.index).fillna(0)
    R = (s / d_sum).where(d_sum > 0, 0.0).fillna(0.0)
    od["Rw"] = od.station_id.map(R) * od.w
    A = od.groupby("oa_code").Rw.sum()
    return pd.Series(demand).index.to_series().map(A).fillna(0.0)


def gi_classes(gdf, w, scores):
    y = scores.reindex(gdf["TOT_REG_CD"]).fillna(0).values
    lg = esda.getisord.G_Local(y, w, transform="B")
    return np.where((lg.Zs < 0) & (lg.p_norm < P_THRESHOLD), "Cold Spot",
           np.where((lg.Zs > 0) & (lg.p_norm < P_THRESHOLD), "Hot Spot", "Not Sig"))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(AFTER_DIR, exist_ok=True)

    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)
    oa_set = set(gdf["TOT_REG_CD"])
    w = libpysal.weights.KNN.from_array(np.array([[p.x, p.y] for p in gdf.geometry.centroid]), k=K)
    gu = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)

    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})

    sup_rows, dem_rows, od_rows, cmp_rows, gu_rows, cls_rows = [], [], [], [], [], []
    for year in YEARS:
        tag = f"{year}_{DAYTYPE}_{PERIOD}_{SCENARIO}"
        st = load_stations(year)
        od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{tag}.csv", dtype={"station_id": str, "oa_code": str})

        sup_rows.append(audit_supply(year, st, apt_set, set(od.station_id)))
        dem_rows.append(audit_demand(year, d1, oa_set))
        od_rows.append(audit_od(year, od, set(st.station_id), oa_set))

        d = d1[d1.year == year]
        demand = dict(zip(d["집계구코드"], d["낮_avg"].astype(float)))
        eff = st[~st.station_id.isin(apt_set) & st.is_open]
        sup_before = dict(zip(eff.station_id, eff.fast_count))
        sup_after = dict(zip(eff[eff.UseLimitation != "Y"].station_id, eff[eff.UseLimitation != "Y"].fast_count))

        # 재현 검증: 기존 파일과 동일 로직으로 다시 계산한 값이 일치하는지
        before = pd.read_csv(f"{BEFORE_DIR}/g2sfca_score_{tag}.csv", dtype={"oa_code": str}).set_index("oa_code").accessibility_score
        recomputed = g2sfca(sup_before, demand, od)
        max_diff = float((recomputed.reindex(before.index) - before).abs().max())

        after = g2sfca(sup_after, demand, od)
        pd.DataFrame({"oa_code": after.index, "accessibility_score": after.values}).to_csv(
            f"{AFTER_DIR}/g2sfca_score_{tag}.csv", index=False, encoding="utf-8-sig")

        cb, ca = gi_classes(gdf, w, before), gi_classes(gdf, w, after)
        for label, c, s in [("before", cb, before), ("after", ca, after)]:
            cmp_rows.append({"year": year, "version": label,
                             "hot": int((c == "Hot Spot").sum()), "cold": int((c == "Cold Spot").sum()),
                             "notsig": int((c == "Not Sig").sum()),
                             "mean_score_x1000": round(float(s.mean()) * 1000, 4),
                             "reproduce_max_abs_diff": max_diff if label == "before" else None})
            t = pd.DataFrame({"gu": gu, "c": c}).groupby("gu").c.value_counts().unstack(fill_value=0)
            for g, r in t.iterrows():
                gu_rows.append({"year": year, "version": label, "gu": g,
                                "hot": int(r.get("Hot Spot", 0)), "cold": int(r.get("Cold Spot", 0))})
        cls_rows.append(pd.DataFrame({"year": year, "oa_code": gdf["TOT_REG_CD"], "gu": gu,
                                      "before": cb, "after": ca}))
        print(f"[{year}] 완료 (재현 오차 max {max_diff:.2e})", flush=True)

    out = {
        "supply_audit": pd.DataFrame(sup_rows), "demand_audit": pd.DataFrame(dem_rows),
        "od_audit": pd.DataFrame(od_rows), "hotspot_compare": pd.DataFrame(cmp_rows),
        "hotspot_compare_gu": pd.DataFrame(gu_rows), "gi_k20_before_after": pd.concat(cls_rows),
    }
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    for name, df in out.items():
        df.to_csv(f"{OUT_DIR}/{name}.csv", index=False, encoding="utf-8-sig")
        if name != "gi_k20_before_after":
            print(f"\n=== {name} ===\n{df.to_string(index=False)}")


if __name__ == "__main__":
    main()
