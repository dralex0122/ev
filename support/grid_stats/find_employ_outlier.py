import glob
import os
import sys

from pyproj import Transformer

TILE_LETTERS = "가나다라마바사아"
BASE = os.path.expanduser("~/ev-charger-accessibility")


def tile_origin(prefix):
    col = TILE_LETTERS.index(prefix[0]) + 1
    row = TILE_LETTERS.index(prefix[1]) + 1
    return 700000 + (col - 1) * 100000, 1300000 + (row - 1) * 100000


def cell100_center_xy(grid_id):
    prefix = grid_id[:2]
    digits = grid_id[2:]
    x0, y0 = tile_origin(prefix)
    return x0 + int(digits[:3]) * 100 + 50, y0 + int(digits[3:]) * 100 + 50


rows = []
for fp in glob.glob(BASE + "/grid_stats/employ/*.csv"):
    with open(fp, encoding="cp949") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 4:
                try:
                    rows.append((parts[1], int(parts[3])))
                except ValueError:
                    pass

rows.sort(key=lambda x: -x[1])
transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

print("=== 종사자수 상위 10개 격자 ===")
for grid_id, val in rows[:10]:
    x, y = cell100_center_xy(grid_id)
    lon, lat = transformer.transform(x, y)
    print(f"{grid_id}: {val:,}명  -> lat={lat:.6f}, lon={lon:.6f}")
