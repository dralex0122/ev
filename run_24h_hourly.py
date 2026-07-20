"""
17시부터 24시간 동안, 매시간 정각(01분)에 district_availability_snapshot.py를
자동으로 실행하는 자체 루프 스크립트.

- 서버에서 tmux로 띄워두면 이 스크립트 하나가 24시간 내내 스스로 시간을 재서
  district_availability_snapshot.py를 반복 실행함 (별도 세션/컴퓨터 불필요)
- district_availability_snapshot.py가 실행 시점의 실제 KST 날짜로 출력 폴더를
  자동 계산하므로(YYMMDD), 자정을 넘기면 다음날 폴더로 자연스럽게 넘어감
- 총 24회 실행 후 자동 종료
"""

import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
TOTAL_RUNS = 24


def next_run_time(now):
    target = now.replace(minute=1, second=0, microsecond=0)
    if target <= now:
        target += timedelta(hours=1)
    return target


def main():
    print(f"=== 24시간 매시간 수집 루프 시작 ({datetime.now(KST).isoformat()}) ===")
    for i in range(1, TOTAL_RUNS + 1):
        now = datetime.now(KST)
        nxt = next_run_time(now)
        wait_sec = (nxt - now).total_seconds()
        print(f"[{i}/{TOTAL_RUNS}] 다음 실행 예정: {nxt.strftime('%Y-%m-%d %H:%M')} KST ({wait_sec:.0f}초 대기)")
        sys.stdout.flush()
        if wait_sec > 0:
            time.sleep(wait_sec)

        run_time = datetime.now(KST)
        print(f"[{i}/{TOTAL_RUNS}] === {run_time.strftime('%Y-%m-%d %H:%M')} KST 실행 ===")
        sys.stdout.flush()
        result = subprocess.run(["python3", "-u", "district_availability_snapshot.py"])
        print(f"[{i}/{TOTAL_RUNS}] 종료 코드: {result.returncode}")
        sys.stdout.flush()

    print(f"=== 24회 전부 완료 ({datetime.now(KST).isoformat()}) ===")


if __name__ == "__main__":
    main()
