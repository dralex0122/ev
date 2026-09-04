import csv
from collections import Counter

rows = []
with open("/home/jmw/ev-charger-accessibility/grid_population/unmatched_cells_reverse_geocoded.csv", encoding="utf-8-sig") as f:
    r = csv.DictReader(f)
    for row in r:
        row["night_avg"] = float(row["night_avg"])
        row["day_avg"] = float(row["day_avg"])
        rows.append(row)

print("전체:", len(rows))

no_addr = [r for r in rows if not r["address"]]
print("주소 없는 셀:", no_addr)
print()

keywords = {
    "산/임야": ["산", "임야"],
    "공원/녹지": ["공원", "유원지", "근린공원"],
    "하천/강": ["하천", "강", "천"],
    "학교(운동장 등)": ["학교"],
    "도로/철도": ["고속도로", "철도", "IC", "나들목"],
    "묘지": ["묘지", "공동묘지"],
}


def classify(addr):
    for cat, kws in keywords.items():
        for kw in kws:
            if kw in addr:
                return cat
    return "기타(일반 주소지)"


cat_counter = Counter()
cat_night_sum = {}
for row in rows:
    cat = classify(row["address"])
    cat_counter[cat] += 1
    cat_night_sum.setdefault(cat, []).append(row["night_avg"])

print("카테고리별 개수 및 평균 night_avg:")
for cat, cnt in cat_counter.most_common():
    nights = cat_night_sum[cat]
    print(f"{cat}: {cnt}건, 평균night={sum(nights)/len(nights):.1f}, 중앙값={sorted(nights)[len(nights)//2]:.1f}")

print()
print("=== night_avg 높은데(>100) 기타(일반 주소지)로 분류된 샘플 20개 ===")
high_normal = [r for r in rows if classify(r["address"]) == "기타(일반 주소지)" and r["night_avg"] > 100]
print("해당 건수:", len(high_normal))
for r in sorted(high_normal, key=lambda x: -x["night_avg"])[:20]:
    print(f"{r['address']}  night={r['night_avg']:.1f} day={r['day_avg']:.1f}")
