import csv
import glob
from collections import defaultdict

import numpy as np
import pandas as pd

BASE = "/home/jmw/ev-charger-accessibility"

print("=== 1) COORD_FIXES 키 충돌 확인 ===")
import sys
sys.path.insert(0, BASE + "/daynight_model")
from seoul_daynight_model_v6 import COORD_FIXES, OUTLIER_FIXES  # noqa

key_counts = defaultdict(int)
with open(BASE + "/building_register/building_register_seoul_geocoded.csv", encoding="utf-8-sig") as f:
    r = csv.DictReader(f)
    for row in r:
        try:
            area = float(row["floor_area_m2"])
        except ValueError:
            continue
        units = int(row["units"]) if row["units"] else 0
        key = (row["gu"], row["main_use"], units, area)
        key_counts[key] += 1

collisions = [(k, key_counts[k]) for k in COORD_FIXES if key_counts.get(k, 0) != 1]
print(f"COORD_FIXES 29건 중 지오코딩 파일에서 정확히 1건과 매칭 안 되는 키: {len(collisions)}건")
for k, c in collisions:
    print(f"  {k} -> 매칭 {c}건")

collisions2 = [(k, key_counts[k]) for k in OUTLIER_FIXES if key_counts.get(k, 0) != 1]
print(f"OUTLIER_FIXES 5건 중 정확히 1건과 매칭 안 되는 키: {len(collisions2)}건")
for k, c in collisions2:
    print(f"  {k} -> 매칭 {c}건")

print()
print("=== 2) employ/housing 100m 격자 이상치 확인 ===")
def load_grid_values(pattern):
    values = []
    for fp in glob.glob(pattern):
        with open(fp, encoding="cp949") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4:
                    try:
                        values.append(int(parts[3]))
                    except ValueError:
                        pass
    return values

housing_vals = load_grid_values(BASE + "/grid_stats/housing/*.csv")
employ_vals = load_grid_values(BASE + "/grid_stats/employ/*.csv")

for name, vals in [("housing(100m 격자당 총주택수)", housing_vals), ("employ(100m 격자당 총종사자수)", employ_vals)]:
    arr = np.array(vals)
    print(f"{name}: n={len(arr)}, min={arr.min()}, max={arr.max()}, mean={arr.mean():.1f}, "
          f"99.9%ile={np.percentile(arr, 99.9):.1f}, 상위5개={sorted(arr)[-5:]}")

print()
print("=== 3) v6 joined CSV 최종 결과물 점검 ===")
df = pd.read_csv(BASE + "/daynight_model/seoul_daynight_model_v6_joined.csv", encoding="utf-8-sig")
print("행 수:", len(df))
print("NaN/inf 존재 여부:", df.isna().any().any(), np.isinf(df.select_dtypes(include=[np.number])).any().any())
print()
print("음수 예측값 있는지 (night_pred/day_pred):")
print("night_pred < 0:", (df["night_pred"] < 0).sum())
print("day_pred < 0:", (df["day_pred"] < 0).sum())
print()
resid_night = df["night_avg"] - df["night_pred"]
resid_day = df["day_avg"] - df["day_pred"]
print("night 잔차: min=%.1f max=%.1f std=%.1f" % (resid_night.min(), resid_night.max(), resid_night.std()))
print("day 잔차: min=%.1f max=%.1f std=%.1f" % (resid_day.min(), resid_day.max(), resid_day.std()))
