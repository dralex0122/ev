import os

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

BASE = os.path.expanduser("~/ev-charger-accessibility")
TILE_LETTERS = "가나다라마바사아"
WGS84_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


def tile_origin(prefix):
    col = TILE_LETTERS.index(prefix[0]) + 1
    row = TILE_LETTERS.index(prefix[1]) + 1
    return 700000 + (col - 1) * 100000, 1300000 + (row - 1) * 100000


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


def fit_ols(X, y):
    Xb = np.column_stack([X, np.ones(len(y))])
    coef, *_ = np.linalg.lstsq(Xb, y, rcond=None)
    return coef


def r2_score(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - ss_res / ss_tot


# ============ 1) train/test 분할 검증 ============
print("=" * 20, "1) train/test 분할 검증", "=" * 20)
df = pd.read_csv(BASE + "/daynight_model/seoul_daynight_model_v6_joined.csv", encoding="utf-8-sig")
n = len(df)
print(f"전체 셀: {n}")

rng = np.random.default_rng(42)
idx = rng.permutation(n)
n_train = int(n * 0.8)
train_idx, test_idx = idx[:n_train], idx[n_train:]

X = df[["pop", "employ", "floor_res", "floor_nonres"]].values

for target in ["night_avg", "day_avg"]:
    y = df[target].values
    coef = fit_ols(X[train_idx], y[train_idx])
    pred_train = np.column_stack([X[train_idx], np.ones(len(train_idx))]) @ coef
    pred_test = np.column_stack([X[test_idx], np.ones(len(test_idx))]) @ coef
    r2_train = r2_score(y[train_idx], pred_train)
    r2_test = r2_score(y[test_idx], pred_test)
    print(f"[{target}] train(n={len(train_idx)}) R2={r2_train:.4f}  test(n={len(test_idx)}) R2={r2_test:.4f}")

# 5-fold 교차검증도 참고로
print()
print("--- 5-fold 교차검증 (더 안정적인 추정) ---")
folds = np.array_split(idx, 5)
for target in ["night_avg", "day_avg"]:
    y = df[target].values
    test_r2s = []
    for i in range(5):
        test_i = folds[i]
        train_i = np.concatenate([folds[j] for j in range(5) if j != i])
        coef = fit_ols(X[train_i], y[train_i])
        pred_test = np.column_stack([X[test_i], np.ones(len(test_i))]) @ coef
        test_r2s.append(r2_score(y[test_i], pred_test))
    print(f"[{target}] fold별 test R2: {[f'{r:.3f}' for r in test_r2s]}  평균={np.mean(test_r2s):.4f}")


# ============ 2) 스팟 체크 ============
print()
print("=" * 20, "2) 유명 지역 스팟 체크", "=" * 20)

api_key = os.environ.get("VWORLD_API_KEY")
VWORLD_URL = "http://api.vworld.kr/req/address"

def geocode(address, api_key):
    params = {
        "service": "address", "request": "getcoord", "version": "2.0",
        "crs": "epsg:4326", "address": address, "refine": "true", "simple": "false",
        "format": "json", "type": "ROAD", "key": api_key,
    }
    r = requests.get(VWORLD_URL, params=params, timeout=20)
    data = r.json()
    result = data.get("response", {}).get("result")
    if result and result.get("point"):
        return float(result["point"]["y"]), float(result["point"]["x"])
    return None


spots = {
    "강남역(업무/상업지구)": "서울특별시 강남구 강남대로 396",
    "여의도 IFC(업무지구)": "서울특별시 영등포구 국제금융로 10",
    "잠실 롯데월드타워(상업/업무)": "서울특별시 송파구 올림픽로 300",
    "홍대입구역(유흥/상업)": "서울특별시 마포구 양화로 160",
    "대치동 은마아파트(순수 주거지)": "서울특별시 강남구 삼성로 212",
    "helioCity 헬리오시티(순수 주거지)": "서울특별시 송파구 위례성대로 84",
}

df_idx = df.set_index("cell250_id")
for name, addr in spots.items():
    result = geocode(addr, api_key)
    if not result:
        print(f"{name}: 지오코딩 실패 ({addr})")
        continue
    lat, lon = result
    cell = latlon_to_cell250_id(lat, lon)
    if cell in df_idx.index:
        row = df_idx.loc[cell]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        print(f"{name} [{cell}]: 실제 night={row['night_avg']:.0f} day={row['day_avg']:.0f} | "
              f"예측 night={row['night_pred']:.0f} day={row['day_pred']:.0f} | "
              f"day/night 비율(실제)={row['day_avg']/max(row['night_avg'],1):.2f}")
    else:
        print(f"{name} [{cell}]: 회귀에 쓰인 6,941개 셀에 없음 (매칭 안 된 셀)")
