"""
4주간(2026-07-22~) 10분 주기 가용률 수집 결과 요약.
서울 데이터를 중심으로 전체/급속/완속 가용률을 평일/주말로 나눠 계산하고,
자치구별 최고/최저, 이상치 발생 현황, 일별 추이, 시간대별(4구간+0~23시 세분화)·
요일별(월~일) 패턴, 피크시간대(가용률 최저=충전 수요 최고 시간)까지 함께 정리한다.
"""
import json
import os
import glob
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser("~/ev-charger-accessibility/charger_accessibility")
DATE_START = "260722"
OUT_FP = os.path.expanduser("~/ev-charger-accessibility/support/daily_check/4week_scraping_summary.json")

PERIOD_OF = {}
for h in range(24):
    if 6 <= h < 12:
        PERIOD_OF[h] = "오전"
    elif 12 <= h < 18:
        PERIOD_OF[h] = "낮"
    elif 18 <= h < 24:
        PERIOD_OF[h] = "밤"
    else:
        PERIOD_OF[h] = "심야"


WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def is_weekend(date_str):
    dt = datetime.strptime("20" + date_str, "%Y%m%d")
    return dt.weekday() >= 5  # 5=토, 6=일


def weekday_kr(date_str):
    dt = datetime.strptime("20" + date_str, "%Y%m%d")
    return WEEKDAY_KR[dt.weekday()]


def new_bucket():
    return {"total": 0, "avail": 0, "fast_total": 0, "fast_avail": 0, "slow_total": 0, "slow_avail": 0}


def add_district(bucket, d):
    bucket["total"] += d.get("total_count", 0) or 0
    bucket["avail"] += d.get("available_count", 0) or 0
    bucket["fast_total"] += d.get("fast_total", 0) or 0
    bucket["fast_avail"] += d.get("fast_avail", 0) or 0
    bucket["slow_total"] += d.get("slow_total", 0) or 0
    bucket["slow_avail"] += d.get("slow_avail", 0) or 0


def rate(avail, total):
    return round(avail / total * 100, 2) if total else None


def main():
    date_folders = sorted(
        d for d in os.listdir(BASE)
        if d.isdigit() and len(d) == 6 and d >= DATE_START and os.path.isdir(os.path.join(BASE, d))
    )
    print(f"대상 날짜: {date_folders[0]} ~ {date_folders[-1]} ({len(date_folders)}일)", flush=True)

    seoul_weekday = new_bucket()
    seoul_weekend = new_bucket()
    seoul_all = new_bucket()
    all_cities_all = new_bucket()

    seoul_by_district = defaultdict(new_bucket)
    seoul_by_period = defaultdict(new_bucket)
    seoul_daily = defaultdict(new_bucket)
    seoul_by_hour = defaultdict(new_bucket)  # 0~23시, 전체
    seoul_by_hour_weekday = defaultdict(new_bucket)
    seoul_by_hour_weekend = defaultdict(new_bucket)
    seoul_by_dow = defaultdict(new_bucket)  # 월~일

    anomaly_days_with_issue = 0
    anomaly_total_files = 0
    n_files = 0

    for date_folder in date_folders:
        date_path = os.path.join(BASE, date_folder)
        weekend = is_weekend(date_folder)

        # 이상치 집계
        anomalies_dir = os.path.join(date_path, "anomalies")
        if os.path.isdir(anomalies_dir):
            for fp in glob.glob(os.path.join(anomalies_dir, "*.json")):
                anomaly_total_files += 1
                try:
                    with open(fp, encoding="utf-8") as f:
                        data = json.load(f)
                    if data and (not isinstance(data, list) or len(data) > 0) and (not isinstance(data, dict) or len(data) > 0):
                        anomaly_days_with_issue += 1
                except Exception:
                    pass

        for city in os.listdir(date_path):
            if city == "anomalies":
                continue
            city_path = os.path.join(date_path, city)
            if not os.path.isdir(city_path):
                continue
            is_seoul = city == "서울특별시"

            for hour_label in os.listdir(city_path):
                hour_path = os.path.join(city_path, hour_label)
                if not os.path.isdir(hour_path):
                    continue
                try:
                    hour = int(hour_label.replace("시", ""))
                except ValueError:
                    continue
                period = PERIOD_OF[hour]

                for minute_label in os.listdir(hour_path):
                    minute_path = os.path.join(hour_path, minute_label)
                    if not os.path.isdir(minute_path):
                        continue

                    for fn in os.listdir(minute_path):
                        if not fn.endswith(".json"):
                            continue
                        fp = os.path.join(minute_path, fn)
                        try:
                            with open(fp, encoding="utf-8") as f:
                                data = json.load(f)
                        except Exception:
                            continue
                        summary = data.get("summary")
                        if not summary:
                            continue
                        n_files += 1

                        add_district(all_cities_all, summary)
                        if is_seoul:
                            add_district(seoul_all, summary)
                            add_district(seoul_weekend if weekend else seoul_weekday, summary)
                            gu = fn.replace(".json", "")
                            add_district(seoul_by_district[gu], summary)
                            add_district(seoul_by_period[period], summary)
                            add_district(seoul_daily[date_folder], summary)
                            add_district(seoul_by_hour[hour], summary)
                            add_district(seoul_by_hour_weekend[hour] if weekend else seoul_by_hour_weekday[hour], summary)
                            add_district(seoul_by_dow[weekday_kr(date_folder)], summary)

        if date_folders.index(date_folder) % 5 == 0:
            print(f"  ...{date_folder} 처리 중 (누적 파일 {n_files:,}개)", flush=True)

    def summarize(b):
        return {
            "전체_가용률": rate(b["avail"], b["total"]),
            "급속_가용률": rate(b["fast_avail"], b["fast_total"]),
            "완속_가용률": rate(b["slow_avail"], b["slow_total"]),
            "표본_충전기_레코드수": b["total"],
        }

    result = {
        "대상_기간": f"{date_folders[0]} ~ {date_folders[-1]}",
        "처리_파일수": n_files,
        "서울_전체": summarize(seoul_all),
        "서울_평일": summarize(seoul_weekday),
        "서울_주말": summarize(seoul_weekend),
        "서울+6대광역시_전체": summarize(all_cities_all),
        "서울_시간대별": {p: summarize(b) for p, b in seoul_by_period.items()},
        "서울_자치구별": {gu: summarize(b) for gu, b in sorted(seoul_by_district.items())},
        "서울_일별추이": {d: summarize(b) for d, b in sorted(seoul_daily.items())},
        "서울_시간별(0~23시)_전체": {f"{h:02d}시": summarize(seoul_by_hour[h]) for h in sorted(seoul_by_hour)},
        "서울_시간별_평일": {f"{h:02d}시": summarize(seoul_by_hour_weekday[h]) for h in sorted(seoul_by_hour_weekday)},
        "서울_시간별_주말": {f"{h:02d}시": summarize(seoul_by_hour_weekend[h]) for h in sorted(seoul_by_hour_weekend)},
        "서울_요일별": {d: summarize(seoul_by_dow[d]) for d in WEEKDAY_KR if d in seoul_by_dow},
        "이상치": {
            "체크된_스냅샷수": anomaly_total_files,
            "이상치_발견된_스냅샷수": anomaly_days_with_issue,
        },
    }

    # 자치구 최고/최저
    district_rates = {gu: v["전체_가용률"] for gu, v in result["서울_자치구별"].items() if v["전체_가용률"] is not None}
    if district_rates:
        best = max(district_rates.items(), key=lambda x: x[1])
        worst = min(district_rates.items(), key=lambda x: x[1])
        result["서울_자치구_최고최저"] = {"최고": {"구": best[0], "가용률": best[1]}, "최저": {"구": worst[0], "가용률": worst[1]}}

    # 피크 시간대(가용률이 가장 낮음 = 충전 수요가 가장 높은 시간) / 한산한 시간(가용률 가장 높음)
    def find_peak(hourly_dict, key="전체_가용률"):
        rates = {h: v[key] for h, v in hourly_dict.items() if v[key] is not None}
        if not rates:
            return None
        peak_hour = min(rates.items(), key=lambda x: x[1])
        quiet_hour = max(rates.items(), key=lambda x: x[1])
        return {
            "피크시간(가용률 최저=수요 최고)": {"시간": peak_hour[0], "가용률": peak_hour[1]},
            "한산시간(가용률 최고=수요 최저)": {"시간": quiet_hour[0], "가용률": quiet_hour[1]},
        }

    result["피크시간대"] = {
        "전체": find_peak(result["서울_시간별(0~23시)_전체"]),
        "전체_급속기준": find_peak(result["서울_시간별(0~23시)_전체"], "급속_가용률"),
        "전체_완속기준": find_peak(result["서울_시간별(0~23시)_전체"], "완속_가용률"),
        "평일": find_peak(result["서울_시간별_평일"]),
        "주말": find_peak(result["서울_시간별_주말"]),
    }

    with open(OUT_FP, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    console_skip = ("서울_자치구별", "서울_일별추이", "서울_시간별(0~23시)_전체", "서울_시간별_평일", "서울_시간별_주말")
    print("\n=== 요약 ===")
    print(json.dumps({k: v for k, v in result.items() if k not in console_skip}, ensure_ascii=False, indent=2))
    print(f"\n저장: {OUT_FP}")


if __name__ == "__main__":
    main()
