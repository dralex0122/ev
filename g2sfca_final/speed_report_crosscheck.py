"""
2026-10-24 — OD 링크 속도를 서울시 「차량통행속도 보고서」(2021~2024, TOPIS 택시 GPS)와 대조.
목적: 2023년 9·11·12월 속도 급락(조화평균 약 15 → 10.5 km/h)이 실제 혼잡인지 자료 이상인지 판단.

보고서(각 연도판 Ⅲ장 총괄분석): 평일 낮(12–14시) 연평균, 월별 낮(전 요일), 도로기능별·도심 낮.
우리 그래프: week_normal, 실측 링크만(등급별 기본값으로 채운 링크 제외), 공간평균속도 = Σ길이 / Σ(길이/속도).
  - 연간: OD에 쓴 연평균 그래프(11·12시 평균)
  - 월별: 12시 그래프(보고서 낮 12–14시와 겹치는 시간), 11·12시 평균(우리 시나리오)
보고서는 간선 위주 약 1,500km, 집계 방식도 달라 절대 수준보다 변화율(2022=1, 월/연평균)로 비교.
"""
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor

import networkx as nx
import numpy as np
import pandas as pd

from recheck_uselimitation_week_day import OUT_DIR

NAS = "/mnt/cowork/EV"
REPORT_FP = f"{NAS}/reference/서울시_차량통행속도_보고서/{{y}}년_서울시_차량통행속도_보고서.pdf"
MONTHLY_FP = f"{NAS}/input/processed/도로망_그래프/서울_연도별/{{y}}/seoul_{{y}}{{m:02d}}_week_{{h}}시_normal.graphml"
ANNUAL_FP = f"{NAS}/input/processed/도로망_그래프/서울_연도별_시간대통합/{{y}}/seoul_{{y}}_week_낮_normal_연평균.graphml"
YEARS = [2021, 2022, 2023, 2024]
HOURS = ["11", "12"]
RANK_DEFAULT = {"101": 100, "102": 80, "103": 50, "104": 50, "105": 50, "106": 50, "107": 50, "108": 40}
EXPRESS = {"101", "102"}  # 고속국도·도시고속도로 ↔ 보고서 '도시고속도로'
ROW_LABELS = ["전체", "도시고속도로", "주간선도로", "보조간선도로", "기타도로", "도심평균", "외곽평균"]
NUM = r"-?\d+\.\d"

ANNUAL_OUT = f"{OUT_DIR}/speed_report_crosscheck_annual.csv"
MONTHLY_OUT = f"{OUT_DIR}/speed_report_crosscheck_monthly.csv"


# --- 보고서 표 추출
def report_tables(y):
    txt = subprocess.run(["pdftotext", "-layout", "-f", "1", "-l", "80", REPORT_FP.format(y=y), "-"],
                         capture_output=True, text=True, check=True).stdout
    pages = txt.split("\f")
    start = next(i for i, p in enumerate(pages) if "총괄분석" in p and "12:00-14:00" in p)  # 목차 제외

    def row(page, label):
        m = re.search(rf"^\s*{label}\s+(.*)$", page, re.M)
        return [float(x) for x in re.findall(NUM, m.group(1))] if m else None

    weekday = row(pages[start], "낮")              # 월~일, 평일, 주말, 전년 평일·주말, 전년 대비
    monthly_pg = next(p for p in pages[start:] if re.search(r"나\) 월별\s*통행속도\s*\n", p))
    monthly = row(monthly_pg, "낮")[:12]           # 1~12월 (+평균)
    band = {}
    for p in pages[start:start + 12]:
        if not re.search(r"시간대별\s*통행속도", p):
            continue
        for lab in ROW_LABELS:
            r = row(p, lab)
            if lab not in band and r and len(r) >= 4:
                band[lab] = r[1]                   # 오전, 낮, 오후, 전일 순
    assert len(weekday) >= 9 and len(monthly) == 12, y
    return {"weekday_noon": weekday[7], "monthly": monthly, "band": band}


# --- 우리 그래프 속도
def sm(x):
    return x.len.sum() / (x.len / x.spd).sum()


def measured(fp):
    G = nx.read_graphml(fp)
    d = pd.DataFrame([(a.get("link_id"), str(a.get("road_rank")), float(a["length"]), float(a["speed"]))
                      for _, _, a in G.edges(data=True)], columns=["link", "rank", "len", "spd"])
    return d, d[d.spd != d["rank"].map(RANK_DEFAULT)]


def space_mean(fp):
    d, meas = measured(fp)
    return {"all": sm(meas), "express": sm(meas[meas["rank"].isin(EXPRESS)]),
            "general": sm(meas[~meas["rank"].isin(EXPRESS)]),
            "meas_km": meas.len.sum() / 1000, "meas_len_share": meas.len.sum() / d.len.sum()}


def monthly_job(args):
    y, m, h = args
    d, meas = measured(MONTHLY_FP.format(y=y, m=m, h=h))
    s = {"all": sm(meas), "express": sm(meas[meas["rank"].isin(EXPRESS)]),
         "general": sm(meas[~meas["rank"].isin(EXPRESS)]),
         "meas_km": meas.len.sum() / 1000, "meas_len_share": meas.len.sum() / d.len.sum()}
    links = meas.drop_duplicates("link").set_index("link")[["rank", "len", "spd"]] if h == "12" else None
    return y, m, h, s, links


def main():
    rep = {y: report_tables(y) for y in YEARS}
    with ProcessPoolExecutor(16) as ex:
        annual = dict(zip(YEARS, ex.map(space_mean, [ANNUAL_FP.format(y=y) for y in YEARS])))
        mon = list(ex.map(monthly_job, [(y, m, h) for y in YEARS for m in range(1, 13) for h in HOURS]))

    # 월별
    md = pd.DataFrame([{"year": y, "month": m, "hour": h, **s} for y, m, h, s, _ in mon])
    # 공통 링크: 4년 48개월 12시 그래프에서 모두 실측된 링크만 → 실측 범위 변화 제거
    links = {(y, m): l for y, m, h, _, l in mon if h == "12"}
    common = sorted(set.intersection(*(set(l.index) for l in links.values())))
    ref = links[(2022, 1)].loc[common]
    common_sm = {k: sm(pd.DataFrame({"len": ref.len, "spd": l.loc[common, "spd"]})) for k, l in links.items()}
    print(f">> 공통 실측 링크 {len(common)}개, {ref.len.sum() / 1000:.0f} km "
          f"(도시고속 {ref[ref['rank'].isin(EXPRESS)].len.sum() / 1000:.0f} km)", flush=True)
    m12 = md[md.hour == "12"].set_index(["year", "month"])
    m1112 = md.groupby(["year", "month"])[["all", "express", "general"]].mean()
    mo = pd.DataFrame({
        "report_noon": [rep[y]["monthly"][m - 1] for y, m in m12.index],
        "ours_12h_all": m12["all"], "ours_11_12h_all": m1112["all"],
        "ours_12h_express": m12["express"], "ours_12h_general": m12["general"],
        "ours_12h_meas_km": m12["meas_km"], "ours_12h_meas_len_share": m12["meas_len_share"],
        "ours_12h_common": [common_sm[k] for k in m12.index],
    }, index=m12.index).reset_index()
    for c in ["report_noon", "ours_12h_all", "ours_11_12h_all", "ours_12h_common"]:
        mo[f"{c}_rel"] = mo[c] / mo.groupby("year")[c].transform("mean")  # 연평균 대비
    mo.round(4).to_csv(MONTHLY_OUT, index=False, encoding="utf-8-sig")

    # 연간
    an = pd.DataFrame([{
        "year": y,
        "report_weekday_noon": rep[y]["weekday_noon"],
        "report_noon_express": rep[y]["band"].get("도시고속도로"),
        "report_noon_main_arterial": rep[y]["band"].get("주간선도로"),
        "report_noon_downtown": rep[y]["band"].get("도심평균"),
        "ours_od_all": annual[y]["all"], "ours_od_express": annual[y]["express"],
        "ours_od_general": annual[y]["general"], "ours_od_meas_km": annual[y]["meas_km"],
        "ours_12h_monthly_mean": mo[mo.year == y].ours_12h_all.mean(),
        "ours_12h_common_mean": mo[mo.year == y].ours_12h_common.mean(),
        "ours_12h_common_excl_9_11_12": mo[(mo.year == y) & ~mo.month.isin([9, 11, 12])].ours_12h_common.mean(),
    } for y in YEARS])
    for c in ["report_weekday_noon", "report_noon_express", "ours_od_all", "ours_od_express", "ours_od_general",
              "ours_12h_monthly_mean", "ours_12h_common_mean", "ours_12h_common_excl_9_11_12"]:
        an[f"{c}_idx22"] = an[c] / an.loc[an.year == 2022, c].iloc[0]
    an.round(4).to_csv(ANNUAL_OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print("=== 연간 (보고서 평일 낮 12–14시 vs 우리 OD 연평균 그래프, 실측 링크 공간평균) ===")
    print(an.round(3).to_string(index=False))
    print("\n=== 월별 (연평균 대비 비율) ===")
    piv = mo.pivot(index="month", columns="year", values=["report_noon_rel", "ours_12h_all_rel", "ours_12h_common_rel"]).round(3)
    print(piv.to_string())
    print("\n=== 2023 월별 절대값 ===")
    print(mo[mo.year == 2023][["month", "report_noon", "ours_12h_all", "ours_12h_common", "ours_11_12h_all", "ours_12h_express",
                                "ours_12h_general", "ours_12h_meas_km"]].round(2).to_string(index=False))
    print(f"\n>> 저장: {ANNUAL_OUT}\n         {MONTHLY_OUT}")


if __name__ == "__main__":
    main()
