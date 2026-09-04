import glob
from collections import defaultdict

import pandas as pd

BASE = "/home/jmw/ev-charger-accessibility/building_register/building_register_seoul"

rows = []
for f in glob.glob(BASE + "/*.csv"):
    df = pd.read_csv(
        f, encoding="utf-8-sig",
        usecols=["대지위치", "도로명대지위치", "건물명", "연면적(㎡)", "주용도코드명", "세대수(세대)"],
    )
    df["__file"] = f.split("/")[-1]
    rows.append(df)

full = pd.concat(rows, ignore_index=True)
full["gu"] = full["__file"].str.split(" ").str[0]
full["연면적(㎡)"] = pd.to_numeric(full["연면적(㎡)"], errors="coerce")

# 도로명대지위치가 비어있지 않은 것만
has_road = full[full["도로명대지위치"].notna() & (full["도로명대지위치"].str.strip() != "")]

group_lots = has_road.groupby("도로명대지위치")["대지위치"].nunique()
shared = group_lots[group_lots >= 3].sort_values(ascending=False)
print(f"3개 이상 서로 다른 지번이 같은 도로명주소를 공유하는 그룹: {len(shared)}개")
total_bldg_in_shared = has_road[has_road["도로명대지위치"].isin(shared.index)].shape[0]
print(f"거기 속한 건물 총 건수: {total_bldg_in_shared}건")
print()
print("=== 상위 20개 그룹 (지번 개수 기준) ===")
for addr, cnt in shared.head(20).items():
    print(f"{addr}: 서로 다른 지번 {cnt}개")
