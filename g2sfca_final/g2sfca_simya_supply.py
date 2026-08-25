"""
심야(00~05시, 6시간) 접근성 분석.
공급: sfast(급속충전기만) + 아파트 소재 완전 제외(v3, 57.3%) — 오전/낮 최종 방법론과 동일 기준.
운영시간: 00~06시 창과 대조해 실제 운영 여부 0/1 반영.
거리조락함수: gaussian, exponential 각각 따로 계산.
평일/주말 모두 계산해서 비교(심야도 나눠야 하는지 확인 목적).
기존 캐시된 OD(od_{year}_{week/weekend}_심야_freeflow.csv) 재사용.
"""
import json
import math
import os
import re
import unicodedata
import pandas as pd

NAS = "/mnt/cowork/EV"
OD_DIR = f"{NAS}/output/g2sfca_sfast_gaussian"
D1_FP = f"{NAS}/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)/d1_final_2021_2024.csv"
CHARGER_DIR_FASTONLY = f"{NAS}/input/processed/yearly_snapshots_fastonly"
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"

CUTOFF_SEC = 900
EXP_BETA = 1.0 / 300

WINDOW = (0, 6)  # 00~06시 (6시간, 2026-08-21 확장분과 동일 정의)
YEARS = [2021, 2022, 2023, 2024]
DAYTYPES = ["week", "weekend"]

TIME_RANGE_RE = re.compile(r"(\d{1,2})[:시](\d{2})?\s*[~-]\s*(\d{1,2})[:시](\d{2})?")


def parse_open_window(text):
    if not text or not text.strip() or "24시간" in text or "24시" in text:
        return None
    t = text.strip()
    m = TIME_RANGE_RE.search(t)
    if not m:
        return None
    h1, _, h2, _ = m.groups()
    start, end = int(h1), int(h2)
    weekday_only = ("평일" in t) or ("주중" in t)
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


def decay_gaussian(tt, d0=CUTOFF_SEC):
    if tt > d0:
        return 0.0
    ratio = tt / d0
    return (math.exp(-0.5 * ratio**2) - math.exp(-0.5)) / (1 - math.exp(-0.5))


def decay_exponential(tt, d0=CUTOFF_SEC, beta=EXP_BETA):
    if tt > d0:
        return 0.0
    return math.exp(-beta * tt)


DECAY_FUNCS = {"gaussian": decay_gaussian, "exponential": decay_exponential}


def load_demand(year):
    df = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    df = df[df["year"] == year]
    return dict(zip(df["집계구코드"], df["심야_avg"].astype(float)))


def load_supply_and_hours(year):
    fname = f"metro7_ev_chargers_{year}_fastonly.geojson"
    fp = unicodedata.normalize("NFD", os.path.join(CHARGER_DIR_FASTONLY, fname))
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    supply, hours = {}, {}
    for feat in data["features"]:
        p = feat["properties"]
        if p.get("city") == "서울특별시":
            sid = p["station_id"]
            supply[sid] = p.get("fast_count", 0) or 0
            hours[sid] = parse_open_window(p.get("openinghour", ""))
    return supply, hours


def main():
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    print(f"아파트 제외 대상: {len(apt_set)}개")

    w_start, w_end = WINDOW
    results_summary = []

    for decay_name, decay_fn in DECAY_FUNCS.items():
        out_dir = f"{NAS}/output/g2sfca_sfast_simya_{decay_name}"
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n=== {decay_name} ===")

        for year in YEARS:
            supply, hours = load_supply_and_hours(year)
            demand = load_demand(year)

            for daytype in DAYTYPES:
                tag = f"{year}_{daytype}_심야_freeflow"
                od = pd.read_csv(f"{OD_DIR}/od_{tag}.csv", dtype={"station_id": str, "oa_code": str})

                def eff_supply(sid):
                    if sid in apt_set:
                        return 0
                    if not is_open(hours.get(sid), w_start, w_end, daytype):
                        return 0
                    return supply.get(sid, 0)

                R = {}
                for sid, grp in od.groupby("station_id"):
                    S_j = eff_supply(sid)
                    if S_j == 0:
                        R[sid] = 0.0
                        continue
                    D_sum = sum(demand.get(oa, 0) * decay_fn(tt) for oa, tt in zip(grp.oa_code, grp.travel_time_sec))
                    R[sid] = S_j / D_sum if D_sum > 0 else 0.0

                oa_catchment = {}
                for sid, oa, tt in zip(od.station_id, od.oa_code, od.travel_time_sec):
                    oa_catchment.setdefault(oa, []).append((sid, tt))

                A = {oa: sum(R[sid] * decay_fn(tt) for sid, tt in oa_catchment.get(oa, [])) for oa in demand}

                out_fp = f"{out_dir}/g2sfca_score_{year}_{daytype}_심야.csv"
                pd.DataFrame({"oa_code": list(A.keys()), "accessibility_score": list(A.values())}).to_csv(
                    out_fp, index=False, encoding="utf-8-sig"
                )
                n_excluded_hours = sum(1 for sid in supply if sid not in apt_set and not is_open(hours.get(sid), w_start, w_end, daytype))
                mean_score = sum(A.values()) / len(A) * 1000
                print(f"  {year}_{daytype}_심야: 평균 {mean_score:.4f}‰ (운영시간으로 추가 제외 {n_excluded_hours}개, 비아파트 {sum(1 for s in supply if s not in apt_set)}개 중)")
                results_summary.append((decay_name, year, daytype, mean_score))

    print("\n=== week vs weekend 비교 ===")
    df = pd.DataFrame(results_summary, columns=["decay", "year", "daytype", "mean_permille"])
    piv = df.pivot_table(index=["decay", "year"], columns="daytype", values="mean_permille")
    piv["차이(%)"] = (piv["weekend"] / piv["week"] - 1) * 100
    print(piv.to_string())


if __name__ == "__main__":
    main()
