"""2019년(코로나 이전 기준선) 집계구 생활인구를 2021~2024와 같은 정의로 집계.
- aggregate_oa_population_periods.py와 동일: 12개월 전체 평일(월~금) 평균, 낮=11·12시, 심야=00~05시 등
- 차이: 2019 원본은 대부분 UTF-8(BOM), 6일(9/2~4, 10/28~30)만 cp949+행 끝 빈 칸 → 인코딩 자동 판별, index_col=False
- 원본 결측: 10/15~27(13일, 평일 9일) 파일이 제공 zip에 없음 → 평일 252일 평균
- 용도: 2021년(코로나 시기) 업무지구 낮 인구 감소 여부 확인용 기준선. 접근성 계산 입력 아님.
"""
import zipfile
import io
import datetime
import calendar
import time
import pandas as pd

SRC_DIR = '/mnt/cowork/EV/input/raw/서울시_생활인구/집계구_생활인구_원본(OA-14979)'
OUT_CSV = '/mnt/cowork/EV/input/processed/서울시_생활인구/집계구_생활인구_원본(OA-14979)/oa_population_periods_2019.csv'

PERIODS = {
    '오전': {'07', '08'},
    '낮': {'11', '12'},
    '밤': {'17', '18'},
    '심야': {'00', '01', '02', '03', '04', '05'},
}
YEAR = 2019
TARGET_HOURS = set().union(*PERIODS.values())


def read_day(raw):
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc,
                               usecols=['시간대구분', '집계구코드', '총생활인구수'],
                               dtype={'시간대구분': str, '집계구코드': str}, skipinitialspace=True,
                               index_col=False)  # 9/2~4·10/28~30 cp949 파일은 행 끝 빈 칸 5개 → 열 밀림 방지
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError('인코딩 판별 실패')


accum, day_count, masked = None, 0, 0
t0 = time.time()
for month in range(1, 13):
    last_day = calendar.monthrange(YEAR, month)[1]
    weekdays = [datetime.date(YEAR, month, d).strftime('%Y%m%d') for d in range(1, last_day + 1)
                if datetime.date(YEAR, month, d).weekday() < 5]
    with zipfile.ZipFile(f'{SRC_DIR}/LOCAL_PEOPLE_{YEAR}{month:02d}.zip') as z:
        names = set(z.namelist())
        for wd in weekdays:
            fname = f'LOCAL_PEOPLE_{wd}.csv'
            if fname not in names:
                print(f'  [누락] {fname}', flush=True)
                continue
            df = read_day(z.read(fname))
            df['시간대구분'] = df['시간대구분'].str.zfill(2)
            df['집계구코드'] = df['집계구코드'].str.strip()
            df = df[df['시간대구분'].isin(TARGET_HOURS)]
            v = pd.to_numeric(df['총생활인구수'], errors='coerce')
            masked += int(v.isna().sum())
            df = df.assign(총생활인구수=v.fillna(0))
            g = df.groupby(['집계구코드', '시간대구분'])['총생활인구수'].sum()
            accum = g if accum is None else accum.add(g, fill_value=0)
            day_count += 1
    print(f'  {YEAR}-{month:02d} 완료 (누적 {day_count}일, {time.time()-t0:.0f}초)', flush=True)

pivot = (accum / day_count).reset_index().pivot(index='집계구코드', columns='시간대구분', values='총생활인구수')
result = pd.DataFrame(index=pivot.index)
for period, hours in PERIODS.items():
    result[f'{period}_avg'] = pivot[[h for h in hours if h in pivot.columns]].mean(axis=1)
result['year'] = YEAR
result = result.reset_index()
result.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
print(f'{YEAR}년: 집계구 {len(result)}개, 평일 {day_count}일 평균, 총생활인구수 비숫자(*) {masked}건')
print(f'저장 완료: {OUT_CSV}')
