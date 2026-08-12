#!/bin/bash
# boundary_all tmux 세션이 끝날 때까지 기다렸다가, 자동으로
# patch_city_labels.py -> git commit/push -> NAS 업로드까지 이어서 수행.
cd ~/ev-charger-accessibility || exit 1

echo "=== $(date) finalize watcher 시작, boundary_all 종료 대기 중 ===" >> finalize_log.txt

while tmux has-session -t boundary_all 2>/dev/null; do
  sleep 30
done

echo "=== $(date) boundary_all 종료 감지, patch 시작 ===" >> finalize_log.txt
python3 -u patch_city_labels.py >> finalize_log.txt 2>&1

echo "=== $(date) git commit/push ===" >> finalize_log.txt
git add metro7_ev_chargers_new.geojson metropolitan_ev_stations.geojson >> finalize_log.txt 2>&1
git commit -m "Patch city labels using VWorld reverse-geocoding boundary check results" >> finalize_log.txt 2>&1
git push >> finalize_log.txt 2>&1

echo "=== $(date) NAS 업로드 ===" >> finalize_log.txt
python3 - <<'PYEOF' >> finalize_log.txt 2>&1
import os
import subprocess

nas_password = os.environ.get("NAS_PASSWORD")
if not nas_password:
    print("NAS_PASSWORD 없음, NAS 업로드 건너뜀")
else:
    cmds = [
        "cd EV",
        "put metro7_ev_chargers_new.geojson metro7_ev_chargers_new.geojson",
        "put metropolitan_ev_stations.geojson metropolitan_ev_stations.geojson",
        "mkdir boundary_check",
        "cd boundary_check",
    ]
    for path in sorted(__import__("glob").glob("boundary_check_*.csv")):
        cmds.append(f"put {path} {path}")
    env = os.environ.copy()
    env["PASSWD"] = nas_password
    r = subprocess.run(
        ["smbclient", "//163.180.10.191/cowork", "-U", "dralex01", "-c", "; ".join(cmds)],
        env=env, capture_output=True, text=True,
    )
    print(r.stdout)
    print(r.stderr)
PYEOF

echo "=== $(date) 전체 완료 ===" >> finalize_log.txt
