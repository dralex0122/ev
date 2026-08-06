#!/bin/bash
# 서버 재부팅(정전 복구 등) 시 10분 수집 루프를 자동으로 다시 시작.
# crontab @reboot 항목에 등록해서 사용. 이미 세션이 돌고 있으면 중복 실행하지 않음.
sleep 30
source ~/.bashrc

if tmux has-session -t loop_10min 2>/dev/null; then
    echo "[$(date)] loop_10min 세션이 이미 존재, 건너뜀" >> ~/ev-charger-accessibility/boot_restart_log.txt
    exit 0
fi

cd ~/ev-charger-accessibility
tmux new-session -d -s loop_10min 'cd ~/ev-charger-accessibility && python3 -u availability_loops/run_10min_loop.py >> loop_10min_log.txt 2>&1'
echo "[$(date)] loop_10min 세션 자동 재시작 완료" >> ~/ev-charger-accessibility/boot_restart_log.txt
