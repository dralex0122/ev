"""
17시부터 24시간 동안, 매시간 정각(01분)에 district_availability_snapshot.py를
자동으로 실행하고, 끝날 때마다 그 시간대 결과를 NAS(cowork/EV/charger_accessibility)
까지 자동 업로드하는 자체 루프 스크립트.

- 서버에서 tmux로 띄워두면 이 스크립트 하나가 24시간 내내 스스로 시간을 재서
  수집 + NAS 업로드까지 반복함 (별도 세션/컴퓨터 불필요)
- district_availability_snapshot.py가 실행 시점의 실제 KST 날짜로 출력 폴더를
  자동 계산하므로(YYMMDD), 자정을 넘기면 다음날 폴더로 자연스럽게 넘어감
- NAS 비밀번호는 NAS_PASSWORD 환경변수에서 읽음 (하드코딩하지 않음)
- 총 24회 실행 후 자동 종료
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
TOTAL_RUNS = 24

NAS_SHARE = "//163.180.10.191/cowork"
NAS_USER = "dralex01"
NAS_REMOTE_ROOT = "EV/charger_accessibility"


def next_run_time(now):
    target = now.replace(minute=1, second=0, microsecond=0)
    if target <= now:
        target += timedelta(hours=1)
    return target


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
        date_folder = run_time.strftime("%y%m%d")
        hour_label = run_time.strftime("%H시")
        print(f"[{i}/{TOTAL_RUNS}] === {run_time.strftime('%Y-%m-%d %H:%M')} KST 실행 ===")
        sys.stdout.flush()
        result = subprocess.run(["python3", "-u", "district_availability_snapshot.py"])
        print(f"[{i}/{TOTAL_RUNS}] 종료 코드: {result.returncode}")
        sys.stdout.flush()

        if result.returncode == 0:
            print(f"[{i}/{TOTAL_RUNS}] NAS 업로드 시작: {date_folder}/{hour_label}")
            upload_hour_to_nas(date_folder, hour_label)
        else:
            print(f"[{i}/{TOTAL_RUNS}] 수집 실패로 NAS 업로드 건너뜀", file=sys.stderr)
        sys.stdout.flush()

    print(f"=== 24회 전부 완료 ({datetime.now(KST).isoformat()}) ===")


if __name__ == "__main__":
    main()
