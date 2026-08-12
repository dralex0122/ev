"""집계구 생활인구 CSV를 도로망 시간대(오전/낮/밤/심야)에 맞춰 연도별로 집계.
- 오전: 07,08시 / 낮: 11,12시 / 밤: 17,18시 (도로망 그래프와 동일 정의)
- 심야: 02,03시 (도로망은 freeflow 근사, 인구는 실측 심야 시간대 사용)
- 도로망이 12개월 연평균이므로, 인구도 각 연도 12개월 전체 평일(월~금)을 표본으로 사용
"""
import zipfile
import io
import datetime
import calendar
import time
import pandas as pd

SRC_DIR = '/mnt/cowork/EV/input/raw/서울시_생활인구/집계구_생활인구_원본(OA-14979)'
OUT_CSV = '/mnt/cowork/EV/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)/oa_population_periods_2021_2024.csv'

PERIODS = {
    '오전': {'07', '08'},
    '낮': {'11', '12'},
    '밤': {'17', '18'},
    '심야': {'02', '03'},
}
YEARS = [2021, 2022, 2023, 2024]
TARGET_HOURS = set().union(*PERIODS.values())

def weekday_dates_in_month(year, month):
    dates = []
    last_day = calendar.monthrange(year, month)[1]
    for day in range(1, last_day + 1):
        d = datetime.date(year, month, day)
        if d.weekday() < 5:
            dates.append(d.strftime('%Y%m%d'))
    return dates

all_results = []
t0 = time.time()

for year in YEARS:
    accum = None
    day_count = 0

    for month in range(1, 13):
        zip_path = f'{SRC_DIR}/LOCAL_PEOPLE_{year}{month:02d}.zip'
        weekdays = weekday_dates_in_month(year, month)
        with zipfile.ZipFile(zip_path) as z:
            names = set(z.namelist())
            for wd in weekdays:
                fname = f'LOCAL_PEOPLE_{wd}.csv'
                if fname not in names:
                    continue
                with z.open(fname) as f:
                    raw = f.read()
                df = pd.read_csv(
                    io.BytesIO(raw), encoding='cp949',
                    usecols=['시간대구분', '집계구코드', '총생활인구수'],
                    dtype={'시간대구분': str, '집계구코드': str}, skipinitialspace=True
                )
                df['시간대구분'] = df['시간대구분'].str.zfill(2)
                df['집계구코드'] = df['집계구코드'].str.strip()
                df = df[df['시간대구분'].isin(TARGET_HOURS)]
                grouped = df.groupby(['집계구코드', '시간대구분'])['총생활인구수'].sum()
                accum = grouped if accum is None else accum.add(grouped, fill_value=0)
                day_count += 1
        print(f'  {year}-{month:02d} 완료 (누적 {day_count}일, {time.time()-t0:.0f}초 경과)', flush=True)

    accum = accum / day_count
    accum_df = accum.reset_index()
    pivot = accum_df.pivot(index='집계구코드', columns='시간대구분', values='총생활인구수')

    result = pd.DataFrame(index=pivot.index)
    for period, hours in PERIODS.items():
        cols = [h for h in hours if h in pivot.columns]
        result[f'{period}_avg'] = pivot[cols].mean(axis=1)
    result['year'] = year
    result = result.reset_index()
    all_results.append(result)
    print(f'{year}년: 집계구 {len(result)}개 처리 완료 (평일 {day_count}일 평균, 12개월 전체)', flush=True)

final = pd.concat(all_results, ignore_index=True)
final.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
print(f'저장 완료: {OUT_CSV} ({len(final)}행)')
print(final.head(8).to_string())
