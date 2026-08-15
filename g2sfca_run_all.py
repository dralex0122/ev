"""G2SFCA 전체 조합 순차 실행 (연도x요일유형x시간대x시나리오, --supply로 S1/S2 선택).
심야는 freeflow 근사 그래프만 존재하므로 심야+normal/congested는 애초에 생성하지 않음
(2026-08-07 배치 실행에서 이 조합들이 '실패'로 잘못 표시됐던 것 수정).
개별 조합 실패해도 계속 진행, 실패 목록은 마지막에 요약.
"""
import argparse
import time
import traceback

import g2sfca_run

YEARS = [2021, 2022, 2023, 2024]
DAYTYPES = ["week", "weekend"]
PERIODS = ["오전", "낮", "밤", "심야"]
SCENARIOS = ["normal", "congested", "freeflow"]


def build_combos():
    combos = []
    for y in YEARS:
        for d in DAYTYPES:
            for p in PERIODS:
                if p == "심야":
                    combos.append((y, d, p, "freeflow"))
                else:
                    for s in SCENARIOS:
                        combos.append((y, d, p, s))
    return combos


def main(supply, decay="binary"):
    combos = build_combos()
    print(f"총 {len(combos)}개 조합 실행 시작 (supply={supply}, decay={decay})", flush=True)

    t_start = time.time()
    failed = []
    for i, (year, daytype, period, scenario) in enumerate(combos, 1):
        tag = f"{year}_{daytype}_{period}_{scenario}"
        print(f"\n===== [{i}/{len(combos)}] {tag} 시작 ({time.time()-t_start:.0f}초 경과) =====", flush=True)
        try:
            g2sfca_run.main(year, daytype, period, scenario, supply, decay)
        except Exception:
            print(f"!!! {tag} 실패:", flush=True)
            traceback.print_exc()
            failed.append(tag)

    print(f"\n\n전체 완료: {len(combos)}개 중 {len(combos)-len(failed)}개 성공, {len(failed)}개 실패", flush=True)
    print(f"총 소요시간: {(time.time()-t_start)/60:.1f}분", flush=True)
    if failed:
        print("실패 목록:", failed, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--supply", default="s1", choices=["s1", "s2", "s2park", "sfast"])
    parser.add_argument("--decay", default="binary", choices=["binary", "gaussian"])
    args = parser.parse_args()
    main(args.supply, args.decay)
