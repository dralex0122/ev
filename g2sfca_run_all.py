"""G2SFCA 전체 96개 조합(4개년×2요일유형×4시간대×3시나리오) 순차 실행.
개별 조합 실패해도 계속 진행, 실패 목록은 마지막에 요약.
"""
import time
import traceback

import g2sfca_run

YEARS = [2021, 2022, 2023, 2024]
DAYTYPES = ["week", "weekend"]
PERIODS = ["오전", "낮", "밤", "심야"]
SCENARIOS = ["normal", "congested", "freeflow"]

combos = [(y, d, p, s) for y in YEARS for d in DAYTYPES for p in PERIODS for s in SCENARIOS]
print(f"총 {len(combos)}개 조합 실행 시작", flush=True)

t_start = time.time()
failed = []
for i, (year, daytype, period, scenario) in enumerate(combos, 1):
    tag = f"{year}_{daytype}_{period}_{scenario}"
    print(f"\n===== [{i}/{len(combos)}] {tag} 시작 ({time.time()-t_start:.0f}초 경과) =====", flush=True)
    try:
        g2sfca_run.main(year, daytype, period, scenario)
    except Exception:
        print(f"!!! {tag} 실패:", flush=True)
        traceback.print_exc()
        failed.append(tag)

print(f"\n\n전체 완료: {len(combos)}개 중 {len(combos)-len(failed)}개 성공, {len(failed)}개 실패", flush=True)
print(f"총 소요시간: {(time.time()-t_start)/60:.1f}분", flush=True)
if failed:
    print("실패 목록:", failed, flush=True)
