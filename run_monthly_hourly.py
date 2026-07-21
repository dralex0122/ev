"""
2026-07-22 00시 ~ 2026-08-18 23시(KST) 동안, 매시간 정각(01분)에
district_availability_snapshot.py를 자동으로 실행하고, 끝날 때마다 그 시간대
결과를 NAS(cowork/EV/charger_accessibility)까지 자동 업로드하는 장기 자동 수집 루프.

- run_24h_hourly.py와 수집/저장 로직은 완전히 동일 (district_availability_snapshot.py
  호출 + smbclient NAS 업로드), 기간만 지정된 구간(총 672회)으로 확장
- district_availability_snapshot.py가 실행 시점의 실제 KST 날짜로 출력 폴더를
  자동 계산하므로(YYMMDD), 날짜가 바뀌면 자연스럽게 다음 폴더로 넘어감
- NAS 비밀번호는 NAS_PASSWORD 환경변수에서 읽음 (하드코딩하지 않음)
- 서버에서 tmux로 띄워두면 이 스크립트 하나가 기간 내내 스스로 시간을 재서
  수집 + NAS 업로드까지 반복함 (별도 세션/컴퓨터 불필요)
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

WINDOW_START = datetime(2026, 7, 22, 0, 1, 0, tzinfo=KST)
WINDOW_END = datetime(2026, 8, 18, 23, 1, 0, tzinfo=KST)  # 이 시각(23시 수집)까지 포함

NAS_SHARE = "//163.180.10.191/cowork"
NAS_USER = "dralex01"
NAS_REMOTE_ROOT = "EV/charger_accessibility"


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
    total_runs = int((WINDOW_END - WINDOW_START).total_seconds() // 3600) + 1
    print(f"=== 장기 수집 루프 시작 ({datetime.now(KST).isoformat()}) ===")
    print(f"=== 수집 구간: {WINDOW_START.strftime('%Y-%m-%d %H:%M')} ~ {WINDOW_END.strftime('%Y-%m-%d %H:%M')} KST, 총 {total_runs}회 ===")
    sys.stdout.flush()

    run_time = WINDOW_START
    run_no = 0

    while run_time <= WINDOW_END:
        run_no += 1
        now = datetime.now(KST)
        wait_sec = (run_time - now).total_seconds()
        print(f"[{run_no}/{total_runs}] 다음 실행 예정: {run_time.strftime('%Y-%m-%d %H:%M')} KST ({wait_sec:.0f}초 대기)")
        sys.stdout.flush()
        if wait_sec > 0:
            time.sleep(wait_sec)

        actual_run_time = datetime.now(KST)
        date_folder = actual_run_time.strftime("%y%m%d")
        hour_label = actual_run_time.strftime("%H시")
        print(f"[{run_no}/{total_runs}] === {actual_run_time.strftime('%Y-%m-%d %H:%M')} KST 실행 ===")
        sys.stdout.flush()
        result = subprocess.run(["python3", "-u", "district_availability_snapshot.py"])
        print(f"[{run_no}/{total_runs}] 종료 코드: {result.returncode}")
        sys.stdout.flush()

        if result.returncode == 0:
            print(f"[{run_no}/{total_runs}] NAS 업로드 시작: {date_folder}/{hour_label}")
            upload_hour_to_nas(date_folder, hour_label)
        else:
            print(f"[{run_no}/{total_runs}] 수집 실패로 NAS 업로드 건너뜀", file=sys.stderr)
        sys.stdout.flush()

        run_time += timedelta(hours=1)

    print(f"=== 전체 {total_runs}회 완료 ({datetime.now(KST).isoformat()}) ===")


if __name__ == "__main__":
    main()
