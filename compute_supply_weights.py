"""
충전소별 '실제 접근 가능성' 가중치 계산.

세 가지 신호를 결합:
  1. 아파트 소재 여부 (apt_charger_flags v3) -> 아파트면 공급에서 완전 제외(가중치 0)
  2. 운영시간(openinghour 자유텍스트 파싱) -> 24시간 대비 실제 열려있는 시간 비율
  3. 유료주차 여부(parking_free) -> 유료(N)면 할인 계수 적용(PAID_PARKING_DISCOUNT, 조정 가능)

PAID_PARKING_DISCOUNT 값은 데이터에서 도출한 게 아니라 임의로 잡은 기본값(0.85)이라
확정 전 조정 필요 - 이 스크립트 상단에서 바로 바꿀 수 있게 상수로 분리해둠.
"""
import json
import re
import pandas as pd

PAID_PARKING_DISCOUNT = 0.85  # TODO: 확정 필요, 지금은 임의값

APT_FLAG_FP = "/mnt/cowork/EV/output/apt_charger_flags/seoul_chargers_2024_apt_v3_final.csv"
CHARGER_FP = "/mnt/cowork/EV/input/processed/yearly_snapshots/metro7_ev_chargers_2024.geojson"
OUT_FP = "/mnt/cowork/EV/output/apt_charger_flags/seoul_chargers_2024_supply_weights.csv"

TIME_RANGE_RE = re.compile(r"(\d{1,2})[:시](\d{2})?\s*[~-]\s*(\d{1,2})[:시](\d{2})?")


def parse_hours_fraction(text):
    """openinghour 텍스트 -> (하루 중 열려있는 시간 비율 0~1, 파싱성공여부)"""
    if not text or not text.strip():
        return 1.0, False  # 빈 값은 정보 없음 -> 24시간으로 간주(과소평가 방지)
    t = text.strip()

    if "24시간" in t or "24시" in t:
        return 1.0, True
    if t in ("~", "0000~0000"):
        return 1.0, False  # 판독 불가 패턴 -> 기본값

    m = TIME_RANGE_RE.search(t)
    if m:
        h1, m1, h2, m2 = m.groups()
        start = int(h1) + (int(m1) / 60 if m1 else 0)
        end = int(h2) + (int(m2) / 60 if m2 else 0)
        span = (end - start) % 24
        if span == 0:
            span = 24
        # "평일만" 언급되면 주 5/7일만 여는 것도 감안해 시간비율에 곱해줌
        if "평일" in t or "주중" in t:
            span *= 5 / 7
        return round(span / 24, 4), True

    return 1.0, False  # 그 외 판독 불가 -> 기본값(24시간 가정), 파싱실패로 표시


def main():
    apt = pd.read_csv(APT_FLAG_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])

    with open(CHARGER_FP, encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for feat in data["features"]:
        p = feat["properties"]
        if p.get("city") != "서울특별시":
            continue
        sid = p["station_id"]
        hours_frac, parsed_ok = parse_hours_fraction(p.get("openinghour", ""))
        parking_free = p.get("parking_free")
        is_apt = sid in apt_set

        if is_apt:
            weight = 0.0
        else:
            paid_factor = PAID_PARKING_DISCOUNT if parking_free == "N" else 1.0
            weight = round(hours_frac * paid_factor, 4)

        rows.append({
            "station_id": sid, "name": p["name"], "total_count": p["total_count"],
            "is_apt": is_apt, "parking_free": parking_free, "openinghour": p.get("openinghour", ""),
            "hours_fraction": hours_frac, "hours_parsed_ok": parsed_ok,
            "supply_weight": weight,
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_FP, index=False, encoding="utf-8-sig")

    print(f"총 충전소: {len(df)}")
    print(f"아파트 제외(가중치 0): {(df.supply_weight == 0).sum()}")
    print(f"가중치 1.0(풀 웨이트): {(df.supply_weight == 1.0).sum()}")
    print(f"가중치 0 초과 1 미만(부분 할인): {((df.supply_weight > 0) & (df.supply_weight < 1.0)).sum()}")
    print(f"운영시간 텍스트 파싱 실패(기본값 1.0 적용): {(~df.hours_parsed_ok).sum()}")
    print()
    print("가중치 분포 요약:")
    print(df.supply_weight.describe())
    print()
    print("=== 부분 할인된 충전소 예시 10개 ===")
    print(df[(df.supply_weight > 0) & (df.supply_weight < 1.0)][
        ["name", "parking_free", "openinghour", "hours_fraction", "supply_weight"]
    ].head(10).to_string(index=False))
    print(f"\n저장: {OUT_FP}")


if __name__ == "__main__":
    main()
