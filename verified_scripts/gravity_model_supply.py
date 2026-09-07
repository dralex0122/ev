"""
2026-08-27 랩미팅 지시: Gaussian 2SFCA와 비교할 Gravity Model(중력모형) 계산.

Gravity Model = 2SFCA에서 수요(경쟁) 정규화(Step 1, R_j = S_j / 가중수요합) 없이,
공급(S_j)을 거리조락으로 바로 가중합산: A_i = sum_j(S_j_eff * decay(t_ij)).
Cumulative Opportunity(거리조락 없는 이진 컷오프)와 구분하기 위해 거리조락은 유지
(2026-08-28 명확화 — decay를 빼면 Cumulative Opportunity와 같아지고, decay를
넣으면 Gravity가 됨. 수요 항만 빼는 게 Gravity의 정의).

범위: 랩미팅에서 지시한 대로 2021~2024년 **평일 낮(week_낮_normal)** 단일 시나리오만,
gaussian 거리조락, t0=15분(900초) — g2sfca_final_supply.py와 동일 공급 정의
(sfast + 아파트 완전제외 + 운영시간 실측 반영) 및 동일 OD(이동시간) 재사용.
"""
import json
import math
import os
import re
import unicodedata
import pandas as pd

NAS = "/mnt/cowork/EV"
GAUSSIAN_OD_DIR = f"{NAS}/output/g2sfca_sfast_gaussian"
CHARGER_DIR_FASTONLY = f"{NAS}/input/processed/yearly_snapshots_fastonly"
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"
OUT_DIR = f"{NAS}/output/gravity_model_gaussian"

CUTOFF_SEC = 900  # 15분

YEARS = [2021, 2022, 2023, 2024]
DAYTYPE, PERIOD, SCENARIO = "week", "낮", "normal"
WINDOW_START, WINDOW_END = 11, 13

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
    os.makedirs(OUT_DIR, exist_ok=True)
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    print(f"아파트 제외 대상: {len(apt_set)}개")
    print(f"\n=== Gravity Model (gaussian, t0=15분, {DAYTYPE}_{PERIOD}_{SCENARIO}) ===")

    for year in YEARS:
        supply, hours = load_supply_and_hours(year)
        tag = f"{year}_{DAYTYPE}_{PERIOD}_{SCENARIO}"
        od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{tag}.csv", dtype={"station_id": str, "oa_code": str})

        def eff_supply(sid):
            if sid in apt_set:
                return 0
            if not is_open(hours.get(sid), WINDOW_START, WINDOW_END, DAYTYPE):
                return 0
            return supply.get(sid, 0)

        A = {}
        for oa, grp in od.groupby("oa_code"):
            A[oa] = sum(eff_supply(sid) * decay_gaussian(tt) for sid, tt in zip(grp.station_id, grp.travel_time_sec))

        out_fp = f"{OUT_DIR}/gravity_score_{tag}.csv"
        pd.DataFrame({"oa_code": list(A.keys()), "accessibility_score": list(A.values())}).to_csv(
            out_fp, index=False, encoding="utf-8-sig"
        )
        n_excluded_hours = sum(1 for sid in supply if sid not in apt_set and not is_open(hours.get(sid), WINDOW_START, WINDOW_END, DAYTYPE))
        print(f"  {tag}: 평균 {sum(A.values())/len(A):.4f} (운영시간으로 추가 제외 {n_excluded_hours}개) -> {out_fp}")


if __name__ == "__main__":
    main()
