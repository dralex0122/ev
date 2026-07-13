"""
서울시 25개 자치구 전기차 충전기 가용률 매시간 수집 스크립트.

- 실행 시점의 KST 시각을 파일명(예: 17시.json)으로 사용해 0713/<구>/<HH시>.json 에 저장
- WINDOW_START_UTC ~ WINDOW_END_UTC 범위 밖에서 실행되면 아무 것도 하지 않고 종료
  (하루 24회 범위를 벗어난 크론 실행을 안전하게 무시하기 위함)
- 저장이 끝나면 git add/commit/push까지 수행
- API 서비스키는 EV_SERVICE_KEY 환경변수에서 읽음 (레포에 하드코딩하지 않음)
"""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

MAX_WORKERS = 10

BASE_URL = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
NUM_OF_ROWS = 500
OUTPUT_ROOT = "0713"

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

# 2026-07-13 17:00 KST ~ 2026-07-14 16:00 KST (총 24회, 시 단위)
WINDOW_START_UTC = datetime(2026, 7, 13, 8, 0, 0, tzinfo=UTC)
WINDOW_END_UTC = datetime(2026, 7, 14, 7, 0, 0, tzinfo=UTC)

SEOUL_DISTRICTS = [
    ("종로구", "11110"), ("중구", "11140"), ("용산구", "11170"), ("성동구", "11200"),
    ("광진구", "11215"), ("동대문구", "11230"), ("중랑구", "11260"), ("성북구", "11290"),
    ("강북구", "11305"), ("도봉구", "11320"), ("노원구", "11350"), ("은평구", "11380"),
    ("서대문구", "11410"), ("마포구", "11440"), ("양천구", "11470"), ("강서구", "11500"),
    ("구로구", "11530"), ("금천구", "11545"), ("영등포구", "11560"), ("동작구", "11590"),
    ("관악구", "11620"), ("서초구", "11650"), ("강남구", "11680"), ("송파구", "11710"),
    ("강동구", "11740"),
]


def fetch_district_items(zscode, service_key):
    import requests

    page_no = 1
    all_items = []

    while True:
        full_url = (
            f"{BASE_URL}?"
            f"serviceKey={service_key}"
            f"&pageNo={page_no}"
            f"&numOfRows={NUM_OF_ROWS}"
            f"&zcode=11"
            f"&zscode={zscode}"
            f"&dataType=JSON"
        )

        page_success = False
        items = []
        total_count = 0

        for attempt in range(1, 4):
            try:
                response = requests.get(full_url, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    items_dict = data.get("items", {})
                    if not items_dict or "item" not in items_dict:
                        page_success = True
                        break
                    items = items_dict["item"]
                    if not items:
                        page_success = True
                        break
                    all_items.extend(items)
                    total_count = int(data.get("totalCount", 0))
                    page_success = True
                    break
                else:
                    time.sleep(3)
            except Exception:
                time.sleep(5)

        if not page_success or not items or len(all_items) >= total_count:
            break

        page_no += 1
        time.sleep(0.3)

    return all_items


def analyze_district(gu_name, zscode, service_key):
    all_items = fetch_district_items(zscode, service_key)

    dist_total = dist_avail = 0
    dist_slow_total = dist_slow_avail = 0
    dist_fast_total = dist_fast_avail = 0
    station_counts = {}

    for item in all_items:
        stat_id = item.get("statId")
        if not stat_id:
            continue
        stat_nm = item.get("statNm")
        addr = item.get("addr", "")
        lat = item.get("lat", "-")
        lng = item.get("lng", "-")
        stat_code = item.get("stat", "0")
        stat_upd_dt = item.get("statUpdDt", "")
        output_val = item.get("output")

        is_available = 1 if stat_code == "2" else 0
        try:
            kw = float(output_val) if output_val else 0.0
        except ValueError:
            kw = 7.0
        is_slow = kw < 50.0

        dist_total += 1
        dist_avail += is_available
        if is_slow:
            dist_slow_total += 1
            dist_slow_avail += is_available
        else:
            dist_fast_total += 1
            dist_fast_avail += is_available

        s = station_counts.setdefault(stat_id, {
            "name": stat_nm, "address": addr, "lat": lat, "lng": lng,
            "total_count": 0, "available_count": 0,
            "slow_total": 0, "slow_avail": 0,
            "fast_total": 0, "fast_avail": 0,
            "latest_update": "",
        })
        s["total_count"] += 1
        s["available_count"] += is_available
        if is_slow:
            s["slow_total"] += 1
            s["slow_avail"] += is_available
        else:
            s["fast_total"] += 1
            s["fast_avail"] += is_available
        if stat_upd_dt and stat_upd_dt > s["latest_update"]:
            s["latest_update"] = stat_upd_dt

    def pct(n, d):
        return round((n / d) * 100, 1) if d else 0.0

    stations = []
    for stat_id, info in sorted(station_counts.items(), key=lambda x: x[1]["total_count"], reverse=True):
        stations.append({
            "station_id": stat_id,
            "name": info["name"],
            "address": info["address"],
            "lat": info["lat"],
            "lng": info["lng"],
            "total_count": info["total_count"],
            "available_count": info["available_count"],
            "total_percent": pct(info["available_count"], info["total_count"]),
            "slow_total": info["slow_total"],
            "slow_avail": info["slow_avail"],
            "slow_percent": pct(info["slow_avail"], info["slow_total"]),
            "fast_total": info["fast_total"],
            "fast_avail": info["fast_avail"],
            "fast_percent": pct(info["fast_avail"], info["fast_total"]),
            "latest_update": info["latest_update"],
        })

    return {
        "district": gu_name,
        "zscode": zscode,
        "summary": {
            "total_count": dist_total,
            "available_count": dist_avail,
            "total_percent": pct(dist_avail, dist_total),
            "slow_total": dist_slow_total,
            "slow_avail": dist_slow_avail,
            "slow_percent": pct(dist_slow_avail, dist_slow_total),
            "fast_total": dist_fast_total,
            "fast_avail": dist_fast_avail,
            "fast_percent": pct(dist_fast_avail, dist_fast_total),
            "station_count": len(station_counts),
        },
        "stations": stations,
    }


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    repo_dir = os.path.dirname(os.path.abspath(__file__)) or "."

    now_utc = datetime.now(UTC)
    now_hour_utc = now_utc.replace(minute=0, second=0, microsecond=0)

    if not (WINDOW_START_UTC <= now_hour_utc <= WINDOW_END_UTC):
        print(f"현재 시각({now_utc.isoformat()})은 수집 대상 24시간 구간을 벗어났습니다. 아무 작업도 하지 않습니다.")
        return

    now_kst = now_utc.astimezone(KST)
    hour_label = now_kst.strftime("%H시")

    print(f"=== {now_kst.strftime('%Y-%m-%d %H:%M')} KST 서울시 25개구 수집 시작 (병렬 {MAX_WORKERS}) ===")

    written_files = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(analyze_district, gu_name, zscode, service_key): gu_name
            for gu_name, zscode in SEOUL_DISTRICTS
        }
        for future in as_completed(futures):
            gu_name = futures[future]
            try:
                result = future.result()
            except Exception as e:
                print(f"  {gu_name} 수집 실패: {e}", file=sys.stderr)
                continue

            result["collected_at_kst"] = now_kst.isoformat()
            result["collected_at_utc"] = now_utc.isoformat()

            gu_dir = os.path.join(repo_dir, OUTPUT_ROOT, gu_name)
            os.makedirs(gu_dir, exist_ok=True)
            file_path = os.path.join(gu_dir, f"{hour_label}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            written_files.append(os.path.join(OUTPUT_ROOT, gu_name, f"{hour_label}.json"))
            print(f"- {gu_name} 완료 (가용률 {result['summary']['total_percent']}%) -> {file_path}")

    if not written_files:
        print("저장된 파일이 없어 커밋을 건너뜁니다.", file=sys.stderr)
        sys.exit(1)

    run(["git", "add", OUTPUT_ROOT], repo_dir)
    commit = run(["git", "commit", "-m", f"Seoul EV charger availability: {now_kst.strftime('%Y-%m-%d %H:%M')} KST"], repo_dir)
    print(commit.stdout, commit.stderr)
    push = run(["git", "push", "origin", "main"], repo_dir)
    print(push.stdout, push.stderr)
    if push.returncode != 0:
        sys.exit(1)

    print(f"=== 완료: {len(written_files)}개 구 데이터 커밋 & push ===")


if __name__ == "__main__":
    main()
