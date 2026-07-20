"""
duplicate_candidates_verified.csv의 "최종판단=가능성 높음" 그룹을 실시간 상태 동기화로 검증.

- 같은 물리적 충전기라면 "가용 대수"가 그룹 내 모든 station_id에서 항상 같이 움직여야 함
  (충전기 한 대는 동시에 한 곳에만 꽂혀있을 수 있으므로)
- statId 파라미터로 각 station을 개별 조회 (zcode/zscode 불필요)
- POLL_INTERVAL_SEC 간격으로 TOTAL_HOURS 동안 반복 수집, 매 폴링마다
  station_id별 (available_count, total_count)를 기록
- 종료 후 그룹별로 "모든 폴링에서 available_count가 그룹 내 전부 일치한 비율"(sync_rate) 계산
- API 서비스키는 EV_SERVICE_KEY 환경변수에서 읽음
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

BASE_URL = "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
INPUT_CSV = "duplicate_candidates_verified.csv"
LOG_FILE = "sync_verify_log.jsonl"
OUTPUT_CSV = "duplicate_candidates_sync_verified.csv"

POLL_INTERVAL_SEC = 15 * 60  # 15분
TOTAL_HOURS = 4

KST = timezone(timedelta(hours=9))


def load_target_ids():
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    groups = []
    all_ids = set()
    for row in rows:
        if row.get("최종판단") == "가능성 높음":
            ids = row["station_ids"].split(";")
            groups.append({"station_name": row["station_name"], "address": row["address"], "ids": ids})
            all_ids.update(ids)
    return groups, sorted(all_ids)


def fetch_station(sid, service_key):
    import requests

    url = f"{BASE_URL}?serviceKey={service_key}&pageNo=1&numOfRows=50&statId={sid}&dataType=JSON"
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                data = r.json()
                items_dict = data.get("items", {})
                items = items_dict.get("item", []) if items_dict else []
                if isinstance(items, dict):
                    items = [items]
                total = len(items)
                avail = sum(1 for it in items if it.get("stat") == "2")
                return {"total": total, "avail": avail}
            time.sleep(2)
        except Exception:
            time.sleep(3)
    return None


def main():
    service_key = os.environ.get("EV_SERVICE_KEY")
    if not service_key:
        print("EV_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    groups, all_ids = load_target_ids()
    print(f"대상 그룹: {len(groups)}개, 고유 station_id: {len(all_ids)}개")

    n_polls = int(TOTAL_HOURS * 3600 / POLL_INTERVAL_SEC)
    print(f"{POLL_INTERVAL_SEC//60}분 간격으로 {n_polls}회 폴링 ({TOTAL_HOURS}시간)")

    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        for poll_i in range(1, n_polls + 1):
            now = datetime.now(KST)
            snapshot = {}
            for sid in all_ids:
                result = fetch_station(sid, service_key)
                snapshot[sid] = result
                time.sleep(0.2)
            record = {"poll": poll_i, "time": now.isoformat(), "data": snapshot}
            logf.write(json.dumps(record, ensure_ascii=False) + "\n")
            logf.flush()
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] {poll_i}/{n_polls}회차 폴링 완료")

            if poll_i < n_polls:
                time.sleep(POLL_INTERVAL_SEC)

    # 분석
    print("\n=== 분석 시작 ===")
    all_records = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            all_records.append(json.loads(line))

    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    for row in rows:
        if row.get("최종판단") != "가능성 높음":
            row["sync_rate"] = ""
            row["sync_detail"] = ""
            continue
        ids = row["station_ids"].split(";")
        match_count = 0
        valid_polls = 0
        detail_snapshots = []
        for rec in all_records:
            snap = rec["data"]
            avails = []
            ok = True
            for sid in ids:
                v = snap.get(sid)
                if v is None:
                    ok = False
                    break
                avails.append(v["avail"])
            if not ok:
                continue
            valid_polls += 1
            if len(set(avails)) == 1:
                match_count += 1
            detail_snapshots.append(avails)
        sync_rate = round(match_count / valid_polls * 100, 1) if valid_polls else None
        row["sync_rate"] = f"{sync_rate}%" if sync_rate is not None else "데이터부족"
        row["sync_detail"] = str(detail_snapshots)

    new_fieldnames = fieldnames + ["sync_rate", "sync_detail"] if "sync_rate" not in fieldnames else fieldnames
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=new_fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"결과 -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
