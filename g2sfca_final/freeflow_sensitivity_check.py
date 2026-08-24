"""
2026-08-24: weekend_오전_freeflow·심야의 Gini가 다른 조합보다 유독 낮게 나온 원인 규명용
민감도(robustness) 체크 스크립트.

배경: congested/normal/freeflow는 실측 혼잡도가 아니라 도로구간별 속도 백분위수
(15%/30%/85%)로 정의됨(graph_years/build_seoul_network_years.py 참고). 속도가
빠를수록 15분 컷오프 내 도달 가능 충전소 수(catchment)가 커져서, Gini가 실제
형평성 효과가 아니라 catchment 확대에 따른 방법론적 압축 효과로 낮아질 수 있다는
가설을 세우고, 인구·요일·연도를 고정한 채 교통 시나리오만 바꿔가며 통제실험으로
검증함.

결과(4개년 x 오전/낮 = 8개 조합 전부): congested > normal > freeflow 순으로
Gini가 예외 없이 감소, reach_per_oa(도달 충전소 수)와 Gini의 상관계수
Pearson r=-0.78 / Spearman r=-0.89 (24개 조합 전체) — 강한 반비례.
=> 결론: catchment 반경 민감도에 의한 압축 효과로 확인, 노션 "⚖️ 지니계수·팔마비율"
토글에 반영 완료.
"""
import json, math, os, re, unicodedata
import pandas as pd
import numpy as np

NAS = "/mnt/cowork/EV"
GAUSSIAN_OD_DIR = f"{NAS}/output/g2sfca_sfast_gaussian"
D1_FP = f"{NAS}/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)/d1_final_2021_2024.csv"
CHARGER_DIR_FASTONLY = f"{NAS}/input/processed/yearly_snapshots_fastonly"
APT_FP = f"{NAS}/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"

CUTOFF_SEC = 900
PERIOD_WINDOW = {"오전": (7, 9), "낮": (11, 13)}
PERIOD_COL = {"오전": "오전_avg", "낮": "낮_avg"}
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

def decay_gaussian(tt, d0=CUTOFF_SEC):
    if tt > d0:
        return 0.0
    ratio = tt / d0
    return (math.exp(-0.5 * ratio**2) - math.exp(-0.5)) / (1 - math.exp(-0.5))

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

def weighted_gini(score, weight):
    df = pd.DataFrame({"score": score, "weight": weight})
    df = df[df["weight"] > 0].copy()
    if len(df) == 0 or df["weight"].sum() == 0:
        return np.nan
    df = df.sort_values("score")
    df["mass"] = df["score"] * df["weight"]
    total_w = df["weight"].sum()
    total_mass = df["mass"].sum()
    if total_mass <= 0:
        return np.nan
    cum_w = df["weight"].cumsum() / total_w
    cum_mass = df["mass"].cumsum() / total_mass
    X = np.concatenate([[0.0], cum_w.values])
    Y = np.concatenate([[0.0], cum_mass.values])
    return 1.0 - np.sum((X[1:] - X[:-1]) * (Y[1:] + Y[:-1]))

apt = pd.read_csv(APT_FP, dtype={"station_id": str})
apt_set = set(apt[apt.is_apt_v3]["station_id"])

results = []
for year in [2021, 2022, 2023, 2024]:
    supply, hours = load_supply_and_hours(year)
    for daytype in ["week"]:  # OD 파일이 week만 3시나리오 다 있음(weekend는 freeflow만 존재)
        for period in ["오전", "낮"]:
            demand = load_demand(year, period)
            w_start, w_end = PERIOD_WINDOW[period]
            for scenario in ["congested", "normal", "freeflow"]:
                tag = f"{year}_{daytype}_{period}_{scenario}"
                fp = f"{GAUSSIAN_OD_DIR}/od_{tag}.csv"
                if not os.path.exists(fp):
                    continue
                od = pd.read_csv(fp, dtype={"station_id": str, "oa_code": str})

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
                    D_sum = sum(demand.get(oa, 0) * decay_gaussian(tt) for oa, tt in zip(grp.oa_code, grp.travel_time_sec))
                    R[sid] = S_j / D_sum if D_sum > 0 else 0.0

                oa_catchment = {}
                for sid, oa, tt in zip(od.station_id, od.oa_code, od.travel_time_sec):
                    oa_catchment.setdefault(oa, []).append((sid, tt))

                A = {oa: sum(R[sid] * decay_gaussian(tt) for sid, tt in oa_catchment.get(oa, [])) for oa in demand}

                scores = pd.Series(A)
                weights = pd.Series(demand)
                common = scores.index.intersection(weights.index)
                g = weighted_gini(scores[common].values, weights[common].values)
                reach = len(od) / od.oa_code.nunique()
                results.append((year, period, scenario, reach, g))
                print(f"{year} {period:2s} {scenario:10s}: reach={reach:6.1f}  gini={g:.4f}")

print()
print("=== 상관관계 (reach_per_oa vs gini, 전체) ===")
df = pd.DataFrame(results, columns=["year","period","scenario","reach","gini"])
print("Pearson r =", df["reach"].corr(df["gini"]))
print("Spearman r =", df["reach"].corr(df["gini"], method="spearman"))
df.to_csv(f"{NAS}/output/freeflow_sensitivity_check.csv", index=False)
