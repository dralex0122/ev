"""
서울시 주/야간 인구 회귀분석 v3: v2에서 발견된 건축물대장 연면적 이상치
(원본 정부 데이터 자체의 단위 오류, 5건, x1000 배 부풀려짐)를 보정 후 재적합.

v2 대비 변경점: building_register_seoul_geocoded.csv 로드 직후,
5건의 확정된 이상치(gu+주용도+세대수+원래연면적으로 식별)의 floor_area_m2를
1000으로 나눠서 보정.
"""
import csv
import glob
import os
import numpy as np
import requests
from pyproj import Transformer

TILE_LETTERS = "가나다라마바사아"
BASE = os.path.expanduser("~/ev-charger-accessibility")

WGS84_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

RESIDENTIAL_KEYWORDS = ["단독주택", "공동주택", "아파트", "연립주택", "다세대주택", "다가구주택"]

# (gu, main_use, units, 원래floor_area_m2) -> 보정된 floor_area_m2
# 3가지 독립적 교차검증(세대수 대비, 대지면적 대비 용적률, 사용자 실측 확인)으로 확정된 5건
OUTLIER_FIXES = {
    ("강남구", "", 0, 2992344.0): 2992.344,
    ("강서구", "공동주택", 65, 7900688.0): 7900.688,
    ("도봉구", "공동주택", 347, 36992865.0): 36992.865,
    ("송파구", "공동주택", 5540, 851634243.0): 851634.243,
    ("용산구", "판매및영업시설", 0, 50222615.0): 50222.615,
}

# (gu, main_use, units, floor_area_m2) -> 보정된 (lat, lon)
# 도로명주소를 3개 이상 서로 다른 지번이 공유하는 "대형/복합시설" 80건을 지번(파셀) 주소로
# 재지오코딩해서, 기존 결과와 150m 이상 차이나는 29건만 교체 (지번 주소가 더 정밀함)
COORD_FIXES = {
    ("강남구", "공동주택", 765, 117068.12): (37.52906691837889, 127.02457688294558),
    ("강동구", "공동주택", 1667, 174673.41): (37.55323080358761, 127.14869041104194),
    ("강동구", "공동주택", 630, 62855.57): (37.550958216732596, 127.14849790561227),
    ("강동구", "공동주택", 150, 20181.45): (37.549911438811364, 127.14875477046385),
    ("강서구", "자원순환관련시설", 0, 62995.18): (37.58037850430485, 126.8282027978936),
    ("강서구", "제1종근린생활시설", 0, 15049.88): (37.576690705057075, 126.82482869556398),
    ("구로구", "제2종근린생활시설", 0, 116.16): (37.491442522610285, 126.84526268707565),
    ("구로구", "제2종근린생활시설", 0, 692.89): (37.490874543509264, 126.84461318276325),
    ("구로구", "종교시설", 0, 1050.36): (37.491442522610285, 126.84667719321294),
    ("노원구", "교육연구시설", 0, 110212.76): (37.64272197440637, 127.1058682559679),
    ("노원구", "교육연구및복지시설", 0, 16894.19): (37.6407370406762, 127.1078530479758),
    ("노원구", "교육연구및복지시설", 0, 7170.88): (37.641871078096585, 127.11065782682786),
    ("노원구", "교육연구시설", 0, 4634.99): (37.63640005794957, 127.08353031068859),
    ("노원구", "교육연구시설", 0, 1583.9): (37.633727626904644, 127.08342318695398),
    ("노원구", "교육연구시설", 0, 20319.02): (37.633560963592906, 127.08494405246265),
    ("노원구", "공동주택", 0, 5886.48): (37.63025513005313, 127.08554930040756),
    ("노원구", "교육연구시설", 0, 127.5): (37.63432239117829, 127.08285333931529),
    ("도봉구", "공동주택", 604, 44520.93): (37.66093486041266, 127.02672601453949),
    ("동대문구", "공동주택", 7, 2421.21): (37.58934260392357, 127.06418214958845),
    ("동대문구", "노유자시설", 0, 23046.66): (37.58934260392357, 127.06418214958845),
    ("동작구", "묘지관련시설", 0, 1140.41): (37.503723057791774, 126.97455236377101),
    ("동작구", "국방,군사시설", 0, 686.6): (37.50280056421809, 126.9731745052847),
    ("동작구", "묘지관련시설", 0, 11080.63): (37.49897503700389, 126.96779172596018),
    ("성북구", "교육연구시설", 0, 310130.08): (37.58361996842272, 127.02634491570063),
    ("성북구", "교육연구시설", 0, 10630.51): (37.59089143240938, 127.02589516074545),
    ("송파구", "숙박시설", 0, 86948.05): (37.5214533856544, 127.1163892266859),
    ("송파구", "문화및집회시설", 0, 163178.96): (37.51775414198252, 127.12560398508126),
    ("송파구", "문화및집회시설", 0, 4050.87): (37.520780147698616, 127.12128316439252),
    ("송파구", "문화및집회시설", 0, 14206.44): (37.51774868851548, 127.11441541406916),
}


def tile_origin(prefix):
    col = TILE_LETTERS.index(prefix[0]) + 1
    row = TILE_LETTERS.index(prefix[1]) + 1
    return 700000 + (col - 1) * 100000, 1300000 + (row - 1) * 100000


def cell100_center_xy(grid_id):
    prefix = grid_id[:2]
    digits = grid_id[2:]
    x0, y0 = tile_origin(prefix)
    return x0 + int(digits[:3]) * 100 + 50, y0 + int(digits[3:]) * 100 + 50


def cell100_to_cell250_id(grid_id):
    prefix = grid_id[:2]
    x, y = cell100_center_xy(grid_id)
    x0, y0 = tile_origin(prefix)
    bin_x_10m = int((x - x0) // 250) * 25
    bin_y_10m = int((y - y0) // 250) * 25
    return f"{prefix}{bin_x_10m:04d}{bin_y_10m:04d}"


def latlon_to_cell250_id(lat, lon):
    x, y = WGS84_TO_5179.transform(lon, lat)
    for col_letter in TILE_LETTERS:
        for row_letter in TILE_LETTERS:
            prefix = col_letter + row_letter
            x0, y0 = tile_origin(prefix)
            rel_x, rel_y = x - x0, y - y0
            if 0 <= rel_x < 100000 and 0 <= rel_y < 100000:
                bin_x_10m = int(rel_x // 250) * 25
                bin_y_10m = int(rel_y // 250) * 25
                return f"{prefix}{bin_x_10m:04d}{bin_y_10m:04d}"
    return None


def load_grid_value_files(pattern, field_code_hint):
    values = {}
    for fp in glob.glob(pattern):
        with open(fp, encoding="cp949") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4:
                    values[parts[1]] = int(parts[3])
    return values


def main():
    pop_by_grid = {}
    with open(os.path.join(BASE, "grid_population", "gridpop_7cities_verified.csv"), encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            if row["city"] == "서울특별시":
                pop_by_grid[row["grid_id"]] = float(row["total_population"])
    seoul_grid_ids = list(pop_by_grid.keys())
    print(f"서울 100m 인구 격자: {len(seoul_grid_ids):,}")

    housing_by_grid = load_grid_value_files(os.path.join(BASE, "grid_stats/housing/*.csv"), "to_ho_001")
    employ_by_grid = load_grid_value_files(os.path.join(BASE, "grid_stats/employ/*.csv"), "to_em_020")
    print(f"전국 주택 격자: {len(housing_by_grid):,}, 전국 종사자 격자: {len(employ_by_grid):,}")

    pop250_fp = glob.glob(os.path.join(BASE, "grid_stats/seoul_250m_생활인구_평일평균프로파일*.csv"))[0]
    night_by_250, day_by_250 = {}, {}
    with open(pop250_fp, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            night_by_250[row["grid_id"]] = float(row["night_avg_00_05"])
            day_by_250[row["grid_id"]] = float(row["day_avg_12_16"])
    print(f"250m 생활인구 격자: {len(night_by_250):,}")

    agg = {}
    for gid in seoul_grid_ids:
        cell250 = cell100_to_cell250_id(gid)
        e = agg.setdefault(cell250, {"pop": 0.0, "housing": 0.0, "employ": 0.0,
                                      "floor_res": 0.0, "floor_nonres": 0.0})
        e["pop"] += pop_by_grid.get(gid, 0.0)
        e["housing"] += housing_by_grid.get(gid, 0)
        e["employ"] += employ_by_grid.get(gid, 0)

    bldg_fp = os.path.join(BASE, "building_register/building_register_seoul_geocoded.csv")
    matched_bldg, total_bldg, fixed_count, coord_fixed_count = 0, 0, 0, 0
    with open(bldg_fp, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            total_bldg += 1
            try:
                lat, lon = float(row["lat"]), float(row["lon"])
                area = float(row["floor_area_m2"]) if row["floor_area_m2"] else 0.0
            except ValueError:
                continue

            units = int(row["units"]) if row["units"] else 0
            key = (row["gu"], row["main_use"], units, area)
            if key in OUTLIER_FIXES:
                area = OUTLIER_FIXES[key]
                fixed_count += 1
            if key in COORD_FIXES:
                lat, lon = COORD_FIXES[key]
                coord_fixed_count += 1

            cell250 = latlon_to_cell250_id(lat, lon)
            if cell250 is None:
                continue
            e = agg.setdefault(cell250, {"pop": 0.0, "housing": 0.0, "employ": 0.0,
                                          "floor_res": 0.0, "floor_nonres": 0.0})
            is_res = any(k in row["main_use"] for k in RESIDENTIAL_KEYWORDS)
            if is_res:
                e["floor_res"] += area
            else:
                e["floor_nonres"] += area
            matched_bldg += 1
    print(f"건축물대장 {total_bldg:,}건 중 {matched_bldg:,}건 250m 격자에 매칭")
    print(f"이상치 보정 적용된 건수: {fixed_count} / {len(OUTLIER_FIXES)}건 확정 목록")
    print(f"좌표 보정 적용된 건수: {coord_fixed_count} / {len(COORD_FIXES)}건 확정 목록")

    rows = []
    for cell250, e in agg.items():
        if cell250 in night_by_250:
            rows.append((cell250, e["pop"], e["housing"], e["employ"], e["floor_res"], e["floor_nonres"],
                         night_by_250[cell250], day_by_250[cell250]))
    print(f"생활인구와 매칭된 250m 셀: {len(rows):,} / {len(night_by_250):,}")

    pop = np.array([r[1] for r in rows])
    housing = np.array([r[2] for r in rows])
    employ = np.array([r[3] for r in rows])
    floor_res = np.array([r[4] for r in rows])
    floor_nonres = np.array([r[5] for r in rows])
    night = np.array([r[6] for r in rows])
    day = np.array([r[7] for r in rows])

    def fit_ols(X, y, names):
        Xb = np.column_stack([X, np.ones(len(y))])
        coef, *_ = np.linalg.lstsq(Xb, y, rcond=None)
        pred = Xb @ coef
        ss_res = np.sum((y - pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot
        coef_str = ", ".join(f"{n}={c:.5f}" for n, c in zip(names, coef[:-1]))
        return r2, coef_str, pred

    print("\n=== [참고] night ~ pop+employ (housing 제외) ===")
    r2, s, _ = fit_ols(np.column_stack([pop, employ]), night, ["pop", "employ"])
    print(f"R2={r2:.4f}  {s}")

    print("\n=== [참고] day ~ pop+employ (housing 제외) ===")
    r2, s, _ = fit_ols(np.column_stack([pop, employ]), day, ["pop", "employ"])
    print(f"R2={r2:.4f}  {s}")

    print("\n=== [v6 기준] night ~ pop+employ+floor_res+floor_nonres (선형) ===")
    r2, s, night_pred_lin = fit_ols(np.column_stack([pop, employ, floor_res, floor_nonres]), night,
                                     ["pop", "employ", "floor_res", "floor_nonres"])
    print(f"R2={r2:.4f}  {s}")

    print("\n=== [v6 기준] day ~ pop+employ+floor_res+floor_nonres (선형) ===")
    r2, s, day_pred_lin = fit_ols(np.column_stack([pop, employ, floor_res, floor_nonres]), day,
                                   ["pop", "employ", "floor_res", "floor_nonres"])
    print(f"R2={r2:.4f}  {s}")

    def r2_score(y_true, y_pred):
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        return 1 - ss_res / ss_tot

    def fit_log_smear(Xtr, ytr, Xte=None):
        """log1p 회귀 적합 + Duan's smearing 보정. 반환: (train 보정예측, test 보정예측 또는 None, smear factor)"""
        Xtr_log = np.log1p(Xtr)
        ytr_log = np.log1p(ytr)
        Xb = np.column_stack([Xtr_log, np.ones(len(ytr_log))])
        coef, *_ = np.linalg.lstsq(Xb, ytr_log, rcond=None)
        fitted_log = Xb @ coef
        resid = ytr_log - fitted_log
        smear = np.mean(np.exp(resid))  # Duan's smearing estimator

        train_pred = np.exp(fitted_log) * smear - 1
        test_pred = None
        if Xte is not None:
            Xte_log = np.log1p(Xte)
            Xbte = np.column_stack([Xte_log, np.ones(len(Xte_log))])
            fitted_log_te = Xbte @ coef
            test_pred = np.exp(fitted_log_te) * smear - 1
        return train_pred, test_pred, smear, coef

    X = np.column_stack([pop, employ, floor_res, floor_nonres])

    print("\n=== [v7, 로그+smearing] night ===")
    night_pred_smear, _, smear_night, coef_night = fit_log_smear(X, night)
    r2_smear_night = r2_score(night, night_pred_smear)
    print(f"smearing factor={smear_night:.4f}  R2(원래 스케일, in-sample)={r2_smear_night:.4f}  "
          f"(참고: 선형모델 R2={r2_score(night, night_pred_lin):.4f})")

    print("\n=== [v7, 로그+smearing] day ===")
    day_pred_smear, _, smear_day, coef_day = fit_log_smear(X, day)
    r2_smear_day = r2_score(day, day_pred_smear)
    print(f"smearing factor={smear_day:.4f}  R2(원래 스케일, in-sample)={r2_smear_day:.4f}  "
          f"(참고: 선형모델 R2={r2_score(day, day_pred_lin):.4f})")

    # ---- train/test 분할 검증 (선형 vs 로그+smearing) ----
    print("\n=== train/test 분할 검증 (80/20, seed=42) ===")
    n = len(rows)
    rng = np.random.default_rng(42)
    idx = rng.permutation(n)
    n_train = int(n * 0.8)
    train_idx, test_idx = idx[:n_train], idx[n_train:]

    for name, y in [("night", night), ("day", day)]:
        # 선형모델
        Xb_train = np.column_stack([X[train_idx], np.ones(len(train_idx))])
        coef_lin, *_ = np.linalg.lstsq(Xb_train, y[train_idx], rcond=None)
        Xb_test = np.column_stack([X[test_idx], np.ones(len(test_idx))])
        pred_lin_test = Xb_test @ coef_lin
        r2_lin_test = r2_score(y[test_idx], pred_lin_test)

        # 로그+smearing (smearing factor는 train 잔차로만 계산 -> test에 적용)
        _, pred_smear_test, smear_f, _ = fit_log_smear(X[train_idx], y[train_idx], X[test_idx])
        r2_smear_test = r2_score(y[test_idx], pred_smear_test)

        print(f"[{name}] test R2 - 선형: {r2_lin_test:.4f}   로그+smearing: {r2_smear_test:.4f}")

    # ---- 스팟 체크 (로그+smearing 예측으로) ----
    print("\n=== 스팟 체크 (로그+smearing vs 선형 vs 실제) ===")
    cell_to_idx = {r[0]: i for i, r in enumerate(rows)}
    api_key = os.environ.get("VWORLD_API_KEY")
    VWORLD_URL = "http://api.vworld.kr/req/address"

    def geocode_road(address, api_key):
        params = {
            "service": "address", "request": "getcoord", "version": "2.0",
            "crs": "epsg:4326", "address": address, "refine": "true", "simple": "false",
            "format": "json", "type": "ROAD", "key": api_key,
        }
        resp = requests.get(VWORLD_URL, params=params, timeout=20)
        data = resp.json()
        result = data.get("response", {}).get("result")
        if result and result.get("point"):
            return float(result["point"]["y"]), float(result["point"]["x"])
        return None

    spots = {
        "강남역(업무)": "서울특별시 강남구 강남대로 396",
        "여의도 IFC(업무)": "서울특별시 영등포구 국제금융로 10",
        "잠실 롯데월드타워(상업)": "서울특별시 송파구 올림픽로 300",
        "홍대입구역(유흥)": "서울특별시 마포구 양화로 160",
        "대치동 은마아파트(주거)": "서울특별시 강남구 삼성로 212",
    }
    for name, addr in spots.items():
        result = geocode_road(addr, api_key)
        if not result:
            print(f"{name}: 지오코딩 실패")
            continue
        lat, lon = result
        cell = latlon_to_cell250_id(lat, lon)
        if cell not in cell_to_idx:
            print(f"{name} [{cell}]: 회귀 대상 셀에 없음")
            continue
        i = cell_to_idx[cell]
        print(f"{name}: 실제 night={night[i]:.0f} day={day[i]:.0f} | "
              f"선형예측 night={night_pred_lin[i]:.0f} day={day_pred_lin[i]:.0f} | "
              f"로그+smearing예측 night={night_pred_smear[i]:.0f} day={day_pred_smear[i]:.0f}")

    out_fp = os.path.join(BASE, "daynight_model", "seoul_daynight_model_v7_joined.csv")
    with open(out_fp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell250_id", "pop", "housing", "employ", "floor_res", "floor_nonres",
                    "night_avg", "day_avg", "night_pred_linear", "day_pred_linear",
                    "night_pred_smear", "day_pred_smear"])
        for i, r in enumerate(rows):
            w.writerow(list(r) + [f"{night_pred_lin[i]:.2f}", f"{day_pred_lin[i]:.2f}",
                                   f"{night_pred_smear[i]:.2f}", f"{day_pred_smear[i]:.2f}"])
    print(f"\n조인 결과 저장: {out_fp}")



if __name__ == "__main__":
    main()
