#!/bin/bash
cd ~/ev-charger-accessibility
echo "[$(date)] S2(2.4배) 배치 완료 대기 시작" >> chain_s2park.log
while ! grep -q '전체 완료' g2sfca_run_all_s2.log 2>/dev/null; do
    sleep 60
done
echo "[$(date)] S2 배치 완료 감지, s2park(10배) 배치 시작" >> chain_s2park.log
python3 -u g2sfca_run_all.py --supply s2park > g2sfca_run_all_s2park.log 2>&1
echo "[$(date)] s2park 배치 완료" >> chain_s2park.log
