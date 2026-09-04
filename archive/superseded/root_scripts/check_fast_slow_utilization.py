"""급속/완속 충전기의 실측 가동률·세션수를 10분 루프 데이터로 계산 (S2 가중치 검증용, 확정 아님)."""
import json
import glob
from collections import defaultdict

ROOT = '/home/jmw/ev-charger-accessibility/charger_accessibility'

files = sorted(glob.glob(f'{ROOT}/*/서울특별시/*시/*분/*.json'))
print(f'총 파일 수: {len(files)}')

# 1차: 가동률 계산용 누적
fast_total_sum = 0
fast_busy_sum = 0
slow_total_sum = 0
slow_busy_sum = 0

# 2차: 단일충전기 스테이션 세션 카운팅용
# station_id -> list of (timestamp_str, avail) for stations that are single-charger
single_fast_series = defaultdict(list)
single_slow_series = defaultdict(list)

for i, fp in enumerate(files):
    # 경로에서 타임스탬프 추출: .../YYMMDD/서울특별시/HH시/MM분/구.json
    parts = fp.split('/')
    ymd = parts[-5]
    hh = parts[-3].replace('시','')
    mm = parts[-2].replace('분','')
    ts = f'{ymd}{hh}{mm}'
    try:
        with open(fp) as f:
            d = json.load(f)
    except Exception:
        continue
    for st in d.get('stations', []):
        ft, fa = st.get('fast_total', 0), st.get('fast_avail', 0)
        stt, sa = st.get('slow_total', 0), st.get('slow_avail', 0)
        fast_total_sum += ft
        fast_busy_sum += (ft - fa)
        slow_total_sum += stt
        slow_busy_sum += (sa if False else (stt - sa))
        sid = st.get('station_id')
        if ft == 1:
            single_fast_series[sid].append((ts, fa))
        if stt == 1:
            single_slow_series[sid].append((ts, sa))
    if (i+1) % 5000 == 0:
        print(f'  진행: {i+1}/{len(files)}')

print()
print('=== 1차: 평균 가동률 ===')
print(f'급속: total_charger_snapshots={fast_total_sum}, busy={fast_busy_sum}, 가동률={fast_busy_sum/fast_total_sum*100:.2f}%')
print(f'완속: total_charger_snapshots={slow_total_sum}, busy={slow_busy_sum}, 가동률={slow_busy_sum/slow_total_sum*100:.2f}%')

def count_sessions(series_dict):
    total_sessions = 0
    total_charger_days = 0
    dates_seen = set()
    for sid, series in series_dict.items():
        series.sort()
        prev_avail = None
        for ts, avail in series:
            date = ts[:6]
            dates_seen.add(date)
            busy = (avail == 0)
            if prev_avail is not None:
                was_busy = (prev_avail == 0)
                if busy and not was_busy:
                    total_sessions += 1
            prev_avail = avail
    n_chargers = len(series_dict)
    n_days = len(dates_seen)
    return total_sessions, n_chargers, n_days

fs, fn, fd = count_sessions(single_fast_series)
ss, sn, sd = count_sessions(single_slow_series)

print()
print('=== 2차: 단일충전기 스테이션 세션 카운트 ===')
print(f'급속 단일충전기 스테이션 수: {fn}, 관측일수(연인원): {fd}')
print(f'  총 세션 시작 감지: {fs}건 -> 충전기 1대당 하루 평균 {fs/(fn*fd)*1 if fn*fd>0 else 0:.3f}회 (단, fd는 전체기간 고유일수라 근사치)')
print(f'완속 단일충전기 스테이션 수: {sn}, 관측일수(연인원): {sd}')
print(f'  총 세션 시작 감지: {ss}건 -> 충전기 1대당 하루 평균 {ss/(sn*sd)*1 if sn*sd>0 else 0:.3f}회 (단, fd는 전체기간 고유일수라 근사치)')

if sn>0 and sd>0 and ss>0:
    fast_per_day = fs/(fn*fd) if fn*fd>0 else 0
    slow_per_day = ss/(sn*sd) if sn*sd>0 else 0
    if slow_per_day>0:
        print()
        print(f'실측 비율(급속/완속): {fast_per_day/slow_per_day:.2f}배  (논문 인용값: 12배)')
