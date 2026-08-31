"""
2026-08-27 랩미팅 지시: Gaussian 2SFCA·Gravity Model과 비교할 Cumulative Opportunity
(누적기회모형) 계산.

Cumulative Opportunity = 거리조락도 없고 수요(경쟁)도 없는 가장 단순한 접근성 측정:
t0(15분) 이내면 거리 상관없이 동일 가중치(1)로 유효 공급을 그대로 합산.
A_i = sum_j(S_j_eff) for all j where t_ij <= 900초.
(2026-08-28 명확화: 거리조락을 넣으면 Gravity Model과 공식이 같아져 구분이 안
되므로 반드시 이진 컷오프로 구현 — gravity_model_supply.py 참고)

범위: 2021~2024년 평일 낮(week_낮_normal) 단일 시나리오, t0=15분(900초) —
g2sfca_final_supply.py / gravity_model_supply.py와 동일 공급 정의(sfast +
아파트 완전제외 + 운영시간 실측 반영) 및 동일 OD(이동시간) 재사용.
"""
import json
import os
import re
import unicodedata
import pandas as pd

NAS = "/mnt/cowork/EV"
GAUSSIAN_OD_DIR = f"{NAS}/output/g2sfca_sfast_gaussian"
CHARGER_DIR_FASTONLY = f"{NAS}/input/processed/yearly_snapshots_fastonly"
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"
OUT_DIR = f"{NAS}/output/cumulative_opportunity"

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
    print(f"\n=== Cumulative Opportunity (이진 컷오프, t0=15분, {DAYTYPE}_{PERIOD}_{SCENARIO}) ===")

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

        # od 파일 자체가 이미 15분 이내 조합만 담고 있는지 확인 위해 컷오프 재적용(방어적)
        od_within = od[od["travel_time_sec"] <= CUTOFF_SEC]

        A = {}
        for oa, grp in od_within.groupby("oa_code"):
            A[oa] = sum(eff_supply(sid) for sid in grp.station_id)

        out_fp = f"{OUT_DIR}/cumopp_score_{tag}.csv"
        pd.DataFrame({"oa_code": list(A.keys()), "accessibility_score": list(A.values())}).to_csv(
            out_fp, index=False, encoding="utf-8-sig"
        )
        n_excluded_hours = sum(1 for sid in supply if sid not in apt_set and not is_open(hours.get(sid), WINDOW_START, WINDOW_END, DAYTYPE))
        print(f"  {tag}: 평균 {sum(A.values())/len(A):.4f} (운영시간으로 추가 제외 {n_excluded_hours}개) -> {out_fp}")


if __name__ == "__main__":
    main()
