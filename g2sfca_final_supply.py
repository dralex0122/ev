"""
확정된 방법론 반영:
  1. 공급: 급속충전기(sfast)만 인정, 아파트 소재 충전소는 완전 제외(v3, 57.3%)
  2. 분석시간: 오전(7-8시 출근시간) & 낮(11-12시)만. 각 시간대에 실제로 운영 중인지
     openinghour 텍스트를 그 시간대(7-8시/11-12시) 및 요일유형(평일/주말)과 대조해 0/1 판정
  3. 거리조락함수: gaussian, exponential 둘 다 각각 따로 계산
기존 sfast_gaussian의 OD(이동시간) 데이터를 재사용(공급만 바뀌므로 이동시간 재계산 불필요).
"""
import json
import math
import os
import re
import unicodedata
import pandas as pd

NAS = "/mnt/cowork/EV"
GAUSSIAN_OD_DIR = f"{NAS}/output/g2sfca_sfast_gaussian"
D1_FP = f"{NAS}/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)/d1_final_2021_2024.csv"
CHARGER_DIR_FASTONLY = f"{NAS}/input/processed/yearly_snapshots_fastonly"
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"
CHARGER_2024_FP = f"{NAS}/input/processed/yearly_snapshots/metro7_ev_chargers_2024.geojson"  # openinghour 원본(연도별 파일엔 없어서 2024 기준 재사용)

CUTOFF_SEC = 900
EXP_BETA = 1.0 / 300  # 지수함수 반감기 약 300초(5분)대에서 절반 정도로 잡음(조정 가능)

PERIOD_WINDOW = {"오전": (7, 9), "낮": (11, 13)}  # [시작,끝) 시
COMBOS = [
    ("week", "오전", "congested"),
    ("week", "낮", "normal"),
    ("weekend", "오전", "freeflow"),
    ("weekend", "낮", "normal"),
]
YEARS = [2021, 2022, 2023, 2024]

TIME_RANGE_RE = re.compile(r"(\d{1,2})[:시](\d{2})?\s*[~-]\s*(\d{1,2})[:시](\d{2})?")


def parse_open_window(text):
    """openinghour 텍스트 -> (open_start_hr, open_end_hr, weekday_only) 또는 None(=24시간/판독불가->항상 열림)"""
    if not text or not text.strip() or "24시간" in text or "24시" in text:
        return None
    t = text.strip()
    m = TIME_RANGE_RE.search(t)
    if not m:
        return None  # 판독 불가 -> 과소평가 방지 위해 24시간으로 간주
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
    # 운영시간 [start,end)와 분석 시간창 [window_start,window_end) 겹치는지
    if end <= start:  # 자정 넘어가는 경우(예: 22~06) 등은 보수적으로 열림 처리
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

PERIOD_COL = {"오전": "오전_avg", "낮": "낮_avg"}


def load_demand(year, period):
    df = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    df = df[df["year"] == year]
    return dict(zip(df["집계구코드"], df[PERIOD_COL[period]].astype(float)))


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

    for decay_name, decay_fn in DECAY_FUNCS.items():
        out_dir = f"{NAS}/output/g2sfca_sfast_final_{decay_name}"
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n=== {decay_name} ===")

        for year in YEARS:
            supply, hours = load_supply_and_hours(year)
            for daytype, period, scenario in COMBOS:
                demand = load_demand(year, period)
                w_start, w_end = PERIOD_WINDOW[period]
                tag = f"{year}_{daytype}_{period}_{scenario}"
                od = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{tag}.csv", dtype={"station_id": str, "oa_code": str})

                # 유효 공급: 아파트 제외 + 이 시간창에 실제로 열려있는지
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

                out_fp = f"{out_dir}/g2sfca_score_{tag}.csv"
                pd.DataFrame({"oa_code": list(A.keys()), "accessibility_score": list(A.values())}).to_csv(
                    out_fp, index=False, encoding="utf-8-sig"
                )
                n_excluded_hours = sum(1 for sid in supply if sid not in apt_set and not is_open(hours.get(sid), w_start, w_end, daytype))
                print(f"  {tag}: 평균 {sum(A.values())/len(A)*1000:.4f}‰ (운영시간으로 추가 제외 {n_excluded_hours}개)")


if __name__ == "__main__":
    main()
