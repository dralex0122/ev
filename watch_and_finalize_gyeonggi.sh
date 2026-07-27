#!/bin/bash
# gyeonggi_boundary tmux 세션이 끝날 때까지 기다렸다가, 자동으로
# finalize_gyeonggi.py(교차검증+수정+23/24년 스냅샷)를 실행하고 NAS에 업로드.
cd ~/ev-charger-accessibility || exit 1

echo "=== $(date) finalize watcher 시작, gyeonggi_boundary 종료 대기 중 ===" >> gyeonggi_finalize_log.txt

while tmux has-session -t gyeonggi_boundary 2>/dev/null; do
  sleep 30
done

echo "=== $(date) gyeonggi_boundary 종료 감지, finalize 시작 ===" >> gyeonggi_finalize_log.txt
python3 -u finalize_gyeonggi.py >> gyeonggi_finalize_log.txt 2>&1

echo "=== $(date) NAS 업로드 ===" >> gyeonggi_finalize_log.txt
python3 - <<'PYEOF' >> gyeonggi_finalize_log.txt 2>&1
import os
import subprocess

nas_password = os.environ.get("NAS_PASSWORD")
if not nas_password:
    print("NAS_PASSWORD 없음, NAS 업로드 건너뜀")
else:
    cmds = [
        "cd EV",
        "put gyeonggi_ev_chargers.geojson gyeonggi_ev_chargers.geojson",
        "mkdir yearly_snapshots",
        "cd yearly_snapshots",
        "put yearly_snapshots/gyeonggi_ev_chargers_2023.geojson gyeonggi_ev_chargers_2023.geojson",
        "put yearly_snapshots/gyeonggi_ev_chargers_2024.geojson gyeonggi_ev_chargers_2024.geojson",
    ]
    env = os.environ.copy()
    env["PASSWD"] = nas_password
    r = subprocess.run(
        ["smbclient", "//163.180.10.191/cowork", "-U", "dralex01", "-c", "; ".join(cmds)],
        env=env, capture_output=True, text=True,
    )
    print(r.stdout)
    print(r.stderr)
PYEOF

echo "=== $(date) 전체 완료 ===" >> gyeonggi_finalize_log.txt
