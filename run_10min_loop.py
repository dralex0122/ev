"""
2026-08-18 23:50(KST)까지, 10분마다 district_availability_snapshot.py를
실행하고 NAS에 자동 업로드하는 루프. run_monthly_hourly.py(1시간 간격)를
대체해서 더 촘촘한 간격으로 전환.

- district_availability_snapshot.py의 저장 폴더명은 "HH시MM분"(분 단위 포함)으로
  이미 수정되어 있어, 10분마다 실행해도 서로 덮어쓰지 않고 다 남음
- NAS 업로드 로직은 기존과 동일
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
INTERVAL_MINUTES = 10

WINDOW_END = datetime(2026, 8, 18, 23, 50, 0, tzinfo=KST)

NAS_SHARE = "//163.180.10.191/cowork"
NAS_USER = "dralex01"
NAS_REMOTE_ROOT = "EV/charger_accessibility"


def next_run_time(now):
    minute = (now.minute // INTERVAL_MINUTES + 1) * INTERVAL_MINUTES
    base = now.replace(second=0, microsecond=0)
    if minute >= 60:
        base = base.replace(minute=0) + timedelta(hours=1)
    else:
        base = base.replace(minute=minute)
    return base


def upload_hour_to_nas(date_folder, hour_label):
    """<date_folder>/<도시>/<hour_label>/*.json 과 anomalies_<hour_label>.json 을 NAS로 업로드."""
    nas_password = os.environ.get("NAS_PASSWORD")
    if not nas_password:
        print("  NAS_PASSWORD 환경변수가 없어 NAS 업로드를 건너뜁니다.", file=sys.stderr)
        return

    local_root = os.path.abspath(date_folder)
    if not os.path.isdir(local_root):
        print(f"  {local_root} 없음, NAS 업로드 건너뜀", file=sys.stderr)
        return

    cmds = [f"cd {NAS_REMOTE_ROOT}", f"mkdir {date_folder}"]
    found_any = False

    for city in sorted(os.listdir(local_root)):
        hour_dir = os.path.join(local_root, city, hour_label)
        if not os.path.isdir(hour_dir):
            continue
        cmds.append(f"mkdir {date_folder}/{city}")
        cmds.append(f"mkdir {date_folder}/{city}/{hour_label}")
        for fn in sorted(os.listdir(hour_dir)):
            local_path = os.path.join(hour_dir, fn)
            remote_path = f"{date_folder}/{city}/{hour_label}/{fn}"
            cmds.append(f"put {local_path} {remote_path}")
            found_any = True

    anomalies_path = os.path.join(local_root, f"anomalies_{hour_label}.json")
    if os.path.isfile(anomalies_path):
        cmds.append(f"put {anomalies_path} {date_folder}/anomalies_{hour_label}.json")
        found_any = True

    if not found_any:
        print(f"  {hour_label} 관련 파일이 없어 NAS 업로드 건너뜀", file=sys.stderr)
        return

    cmd_str = "; ".join(cmds)
    env = os.environ.copy()
    env["PASSWD"] = nas_password
    result = subprocess.run(
        ["smbclient", NAS_SHARE, "-U", NAS_USER, "-c", cmd_str],
        env=env, capture_output=True, text=True,
    )
    if result.returncode != 0 or "NT_STATUS" in (result.stdout + result.stderr):
        print(f"  NAS 업로드 중 문제 발생:\n{result.stdout}\n{result.stderr}", file=sys.stderr)
    else:
        print(f"  NAS 업로드 완료: {NAS_REMOTE_ROOT}/{date_folder}/*/{hour_label}/")


def main():
    print(f"=== 10분 간격 수집 루프 시작 ({datetime.now(KST).isoformat()}) ===")
    print(f"=== 종료 시각: {WINDOW_END.strftime('%Y-%m-%d %H:%M')} KST ===")
    sys.stdout.flush()

    run_no = 0
    while True:
        now = datetime.now(KST)
        if now >= WINDOW_END:
            break
        run_time = next_run_time(now)
        if run_time > WINDOW_END:
            break

        run_no += 1
        wait_sec = (run_time - now).total_seconds()
        print(f"[{run_no}] 다음 실행 예정: {run_time.strftime('%Y-%m-%d %H:%M')} KST ({wait_sec:.0f}초 대기)")
        sys.stdout.flush()
        if wait_sec > 0:
            time.sleep(wait_sec)

        actual_run_time = datetime.now(KST)
        date_folder = actual_run_time.strftime("%y%m%d")
        hour_label = actual_run_time.strftime("%H시%M분")
        print(f"[{run_no}] === {actual_run_time.strftime('%Y-%m-%d %H:%M')} KST 실행 ===")
        sys.stdout.flush()
        result = subprocess.run(["python3", "-u", "district_availability_snapshot.py"])
        print(f"[{run_no}] 종료 코드: {result.returncode}")
        sys.stdout.flush()

        if result.returncode == 0:
            print(f"[{run_no}] NAS 업로드 시작: {date_folder}/{hour_label}")
            upload_hour_to_nas(date_folder, hour_label)
        else:
            print(f"[{run_no}] 수집 실패로 NAS 업로드 건너뜀", file=sys.stderr)
        sys.stdout.flush()

    print(f"=== 전체 종료 ({datetime.now(KST).isoformat()}) ===")


if __name__ == "__main__":
    main()
