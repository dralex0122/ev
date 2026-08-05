"""연도별 충전소 스냅샷에서 S2(급속:완속=12:1 가중 대수) 산출. 근거: Zhang&Cao(2025) 런던 EV 논문."""
import json
import csv

FAST_WEIGHT = 12
SLOW_WEIGHT = 1

for year in [2021, 2022, 2023, 2024]:
    src = f'/mnt/cowork/EV/yearly_snapshots/metro7_ev_chargers_{year}.geojson'
    out_csv = f'/mnt/cowork/EV/yearly_snapshots/seoul_s2_weighted_{year}.csv'

    with open(src) as f:
        data = json.load(f)

    rows = []
    for feat in data['features']:
        p = feat['properties']
        if p.get('zcode') != '11':
            continue
        lon, lat = feat['geometry']['coordinates']
        fast = p.get('fast_count', 0) or 0
        slow = p.get('slow_count', 0) or 0
        total = p.get('total_count', 0) or 0
        s2 = fast * FAST_WEIGHT + slow * SLOW_WEIGHT
        rows.append({
            'station_id': p.get('station_id'),
            'lon': lon, 'lat': lat,
            'fast_count': fast, 'slow_count': slow,
            's1_total_count': total,
            's2_weighted': s2,
        })

    with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['station_id','lon','lat','fast_count','slow_count','s1_total_count','s2_weighted'])
        writer.writeheader()
        writer.writerows(rows)

    s1_sum = sum(r['s1_total_count'] for r in rows)
    s2_sum = sum(r['s2_weighted'] for r in rows)
    print(f'{year}년: 서울 {len(rows)}개 충전소 -> {out_csv}')
    print(f'  S1 합계(단순대수): {s1_sum}, S2 합계(가중): {s2_sum}')
