import csv
from collections import defaultdict

fp = "/home/jmw/ev-charger-accessibility/building_register/building_register_seoul_geocoded.csv"

groups = defaultdict(list)
with open(fp, encoding="utf-8-sig") as f:
    r = csv.DictReader(f)
    for row in r:
        key = (row["lat"], row["lon"])
        groups[key].append(row)

sizes = sorted(groups.items(), key=lambda kv: -len(kv[1]))
big = [(k, v) for k, v in sizes if len(v) >= 5]
print(f"같은 좌표(소수점 6자리까지 동일)를 공유하는 그룹 중 5건 이상인 그룹: {len(big)}개")
total_in_big = sum(len(v) for _, v in big)
print(f"그런 그룹에 속한 건물 총합: {total_in_big}건 / 전체 {sum(len(v) for v in groups.values())}건")
print()
print("=== 상위 15개 그룹 ===")
for (lat, lon), rows in big[:15]:
    uses = {}
    for r in rows:
        uses[r["main_use"]] = uses.get(r["main_use"], 0) + 1
    print(f"({lat}, {lon}) - {len(rows)}건, 용도분포: {uses}, gu={rows[0]['gu']}")
