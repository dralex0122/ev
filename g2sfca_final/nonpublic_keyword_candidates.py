"""
2026-10-13: UseLimitation=N인데 실제로는 운수사·회사 전용으로 보이는 충전소 후보 정리.

UseLimitation 필드만으로는 택시회사 등 차고지 충전기가 다 걸러지지 않음
(예: 서울강서 영풍콜택시 = N). 충전소명 키워드로 후보를 뽑고 규칙으로 1차 판정만
붙임 — 키워드 매칭은 오탐이 많아(교통안전공단 검사소, 시민개방 충전소 등) 최종 제외는
final_label 수기 검토 후 결정.

대상: 연도별 유효 공급(급속, 아파트 v3 제외, 평일 11-13시 운영, UseLimitation!=Y)
판정 규칙:
  - 제외 키워드와 유지 키워드가 함께 있으면 → 검토필요
  - 제외 키워드만 → 제외
  - 유지 키워드만 → 유지
  - 둘 다 없음(후보 키워드에만 걸림) → 검토필요
"""
import re

import pandas as pd

from g2sfca_final_supply import APT_FP
from recheck_uselimitation_week_day import load_stations, OUT_DIR, YEARS

CANDIDATE_RE = r"차고지|운수|여객|교통|통운|버스|택시|콜|화물|물류|운송|렌터카|렌트카|관용|전용|직원|사옥"
EXCLUDE_RE = r"차고지|운수|여객|통운|택시|콜택시|화물|물류|운송|렌터카|렌트카|관용|전용"
KEEP_RE = r"개방|시민|공영|가로등|검사소|터미널|24시간이용가능|교통공원|면허시험장"

OUT_FP = f"{OUT_DIR}/nonpublic_keyword_candidates.csv"


def judge(name):
    ex = sorted(set(re.findall(EXCLUDE_RE, name)))
    kp = sorted(set(re.findall(KEEP_RE, name)))
    if ex and kp:
        return "검토필요", f"제외({','.join(ex)}) + 유지({','.join(kp)}) 키워드 동시"
    if ex:
        return "제외", f"제외 키워드: {','.join(ex)}"
    if kp:
        return "유지", f"유지 키워드: {','.join(kp)}"
    return "검토필요", f"후보 키워드만: {','.join(sorted(set(re.findall(CANDIDATE_RE, name))))}"


def main():
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])

    frames = []
    for year in YEARS:
        st = load_stations(year)
        eff = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y")]
        cand = eff[eff.name.str.contains(CANDIDATE_RE, na=False)]
        frames.append(cand.assign(year=year)[["station_id", "name", "address", "fast_count", "year"]])
    allc = pd.concat(frames)

    fc = allc.pivot_table(index="station_id", columns="year", values="fast_count", aggfunc="first")
    fc.columns = [f"fast_{y}" for y in fc.columns]
    info = allc.sort_values("year").groupby("station_id").last()[["name", "address"]]
    df = info.join(fc).reset_index()
    df["gu"] = df.address.str.split().str[1]
    df[["rule_label", "reason"]] = df.name.apply(lambda n: pd.Series(judge(n)))
    df["final_label"] = ""  # 수기 검토 후 기입(제외/유지)

    order = {"제외": 0, "검토필요": 1, "유지": 2}
    df = df.sort_values(["rule_label", "fast_2024"], key=lambda s: s.map(order) if s.name == "rule_label" else -s.fillna(0))
    cols = ["station_id", "name", "address", "gu", "rule_label", "reason", "final_label"] + \
           [c for c in df.columns if c.startswith("fast_")]
    df[cols].to_csv(OUT_FP, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print(f">> 저장: {OUT_FP} ({len(df)}곳)\n")
    for lab in ["제외", "검토필요", "유지"]:
        sub = df[df.rule_label == lab]
        by_year = {c: int(sub[c].sum()) for c in cols if c.startswith("fast_")}
        print(f"=== {lab}: {len(sub)}곳, 충전기 {by_year} ===")
        print(sub[["name", "gu", "fast_2024", "reason"]].to_string(index=False), "\n")


if __name__ == "__main__":
    main()
