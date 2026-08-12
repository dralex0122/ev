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
    matched_bldg, total_bldg, fixed_count = 0, 0, 0
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

    print("\n=== [v4, housing 제거] night ~ pop+employ+floor_res+floor_nonres ===")
    r2, s, night_pred = fit_ols(np.column_stack([pop, employ, floor_res, floor_nonres]), night,
                                 ["pop", "employ", "floor_res", "floor_nonres"])
    print(f"R2={r2:.4f}  {s}")

    print("\n=== [v4, housing 제거] day ~ pop+employ+floor_res+floor_nonres ===")
    r2, s, day_pred = fit_ols(np.column_stack([pop, employ, floor_res, floor_nonres]), day,
                               ["pop", "employ", "floor_res", "floor_nonres"])
    print(f"R2={r2:.4f}  {s}")

    print("\n=== 상관계수 (보정 후) ===")
    import numpy as _np
    mat = _np.column_stack([pop, housing, employ, floor_res, floor_nonres, night, day])
    names = ["pop", "housing", "employ", "floor_res", "floor_nonres", "night", "day"]
    corr = _np.corrcoef(mat, rowvar=False)
    print("      " + " ".join(f"{n:>9}" for n in names))
    for i, n in enumerate(names):
        print(f"{n:>9} " + " ".join(f"{corr[i,j]:9.2f}" for j in range(len(names))))

    out_fp = os.path.join(BASE, "daynight_model", "seoul_daynight_model_v4_joined.csv")
    with open(out_fp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell250_id", "pop", "housing", "employ", "floor_res", "floor_nonres",
                    "night_avg", "day_avg", "night_pred", "day_pred"])
        for i, r in enumerate(rows):
            w.writerow(list(r) + [f"{night_pred[i]:.2f}", f"{day_pred[i]:.2f}"])
    print(f"\n조인 결과 저장: {out_fp}")


if __name__ == "__main__":
    main()
