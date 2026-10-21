"""
2026-10-20: 2023 OD 속도 이상 월(9·11·12월) 제외 민감도 분석.

배경: 2023 week_낮_normal OD가 2022 대비 약 8% 느림. 월별 그래프를 보면 2023년 9·11·12월만
평균 속도가 약 30% 급락(조화평균 약 15 → 10.5 km/h)하고, 기본값으로 채우던 링크 약 7,300개에
시속 4 km 안팎의 실측값이 새로 들어옴 → 자료 이상으로 보고 해당 월을 빼서 재계산.

1. 2023 연평균 그래프 재구성: 원 파이프라인(average_monthly_graphs → average_timeperiods)과 같이
   월별 속도 산술평균 → 11·12시 평균. 대상 월만 1~8·10월로 제한. 12개월 전체로도 만들어 원본과 대조.
2. 같은 충전소·집계구 최근접 노드 매핑(g2sfca_run.py)으로 15분 컷오프 OD 재계산
3. 최종 공급(nonpublic)으로 2SFCA → Gi* k=20, 지니·Palma(낮인구 가중)를 원본 2023과 비교
"""
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import networkx as nx
import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.expanduser("~/ev-charger-accessibility"))
from g2sfca_run import load_chargers, load_oa_demand, WGS84_TO_5179, CUTOFF_SEC  # noqa: E402

from g2sfca_final_supply import APT_FP, D1_FP, GAUSSIAN_OD_DIR
from recheck_uselimitation_week_day import load_stations, g2sfca, gi_classes, BOUNDARY_FP, OUT_DIR, K, GU_MAP
from recompute_exclude_nonpublic import CAND_FP, NONPUBLIC_DIR
from inequality_gini_palma import weighted_gini, weighted_share

NAS = "/mnt/cowork/EV"
MONTHLY_DIR = f"{NAS}/input/processed/도로망_그래프/서울_연도별/2023"
GRAPH_FP = f"{NAS}/input/processed/도로망_그래프/서울_연도별_시간대통합/2023/seoul_2023_week_낮_normal_연평균.graphml"
YEAR, TAG = 2023, "2023_week_낮_normal"
KEEP_MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 10]
HOURS = ["11", "12"]
OD_OUT = f"{OUT_DIR}/od_{TAG}_excl_m09_11_12.csv"
SCORE_OUT = f"{OUT_DIR}/g2sfca_score_{TAG}_excl_m09_11_12.csv"
SUMMARY_OUT = f"{OUT_DIR}/od2023_anomaly_month_sensitivity.csv"

G = None
OA_NODE_MAP = None


def read_speeds(args):
    m, h = args
    g = nx.read_graphml(f"{MONTHLY_DIR}/seoul_2023{m:02d}_week_{h}시_normal.graphml")
    return m, h, {(u, v): float(d["speed"]) for u, v, d in g.edges(data=True)}


def rebuild_graph(base, speeds, months):
    """월별 산술평균 → 시간대 평균. 원 파이프라인과 같은 순서."""
    out = base.copy()
    for u, v, d in out.edges(data=True):
        per_hour = [np.mean([speeds[(m, h)][(u, v)] for m in months]) for h in HOURS]
        s = sum(per_hour) / len(per_hour)
        d["speed"] = s
        d["travel_time"] = float(d["length"]) / (s * 1000 / 3600)
    return out


def reach(item):
    sid, node = item
    r = nx.single_source_dijkstra_path_length(G, node, cutoff=CUTOFF_SEC, weight="travel_time")
    return [(sid, oa, tt) for n, tt in r.items() for oa in OA_NODE_MAP.get(n, [])]


def build_od(graph):
    global G, OA_NODE_MAP
    G = graph
    ids = list(G.nodes())
    tree = cKDTree([(float(G.nodes[n]["x"]), float(G.nodes[n]["y"])) for n in ids])

    def nearest(lon, lat):
        return ids[tree.query(WGS84_TO_5179.transform(lon, lat))[1]]

    stations = [(c["properties"]["station_id"], nearest(*c["geometry"]["coordinates"])) for c in load_chargers(YEAR, "sfast")]
    OA_NODE_MAP = {}
    for oa, info in load_oa_demand(YEAR, "낮").items():
        OA_NODE_MAP.setdefault(nearest(info["lon"], info["lat"]), []).append(oa)
    with ProcessPoolExecutor(20) as ex:
        rows = [r for chunk in ex.map(reach, stations, chunksize=50) for r in chunk]
    od = pd.DataFrame(rows, columns=["station_id", "oa_code", "travel_time_sec"])
    od["travel_time_sec"] = od.travel_time_sec.round(1)
    return od


def main():
    t0 = time.time()
    base = nx.read_graphml(GRAPH_FP)
    with ProcessPoolExecutor(12) as ex:
        speeds = {(m, h): s for m, h, s in ex.map(read_speeds, [(m, h) for m in range(1, 13) for h in HOURS])}
    print(f">> 월별 그래프 24개 로드 ({time.time() - t0:.0f}s)", flush=True)

    full = rebuild_graph(base, speeds, range(1, 13))
    diff = max(abs(full[u][v]["speed"] - float(d["speed"])) for u, v, d in base.edges(data=True))
    print(f">> 12개월 재구성 vs 원본 그래프 속도 최대 차이 {diff:.6f} km/h", flush=True)

    excl = rebuild_graph(base, speeds, KEEP_MONTHS)
    od = build_od(excl)
    od.to_csv(OD_OUT, index=False, encoding="utf-8-sig")
    print(f">> OD 재계산 {len(od):,}쌍 ({time.time() - t0:.0f}s) → {OD_OUT}", flush=True)

    od_orig = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_{TAG}.csv", dtype={"station_id": str, "oa_code": str})
    od22 = pd.read_csv(f"{GAUSSIAN_OD_DIR}/od_2022_week_낮_normal.csv", dtype={"station_id": str, "oa_code": str})
    k = ["station_id", "oa_code"]
    j = od22.merge(od_orig, on=k, suffixes=("_22", "_23")).merge(od.rename(columns={"travel_time_sec": "tt_ex"}), on=k)
    j = j[j.travel_time_sec_22 > 60]
    print(f">> 공통쌍 {len(j):,}: 2022 대비 통행시간 중앙비 원본 {np.median(j.travel_time_sec_23 / j.travel_time_sec_22):.3f}"
          f" / 이상월 제외 {np.median(j.tt_ex / j.travel_time_sec_22):.3f}", flush=True)

    # 최종 공급(nonpublic): 아파트·영업시간 외·UseLimitation=Y·운수사 키워드 제외
    apt = pd.read_csv(APT_FP, dtype={"station_id": str})
    apt_set = set(apt[apt.is_apt_v3]["station_id"])
    cand = pd.read_csv(CAND_FP, dtype={"station_id": str})
    kw_excl = set(cand[cand.final_label == "제외"].station_id)
    st = load_stations(YEAR)
    kept = st[~st.station_id.isin(apt_set) & st.is_open & (st.UseLimitation != "Y") & ~st.station_id.isin(kw_excl)]
    supply = dict(zip(kept.station_id, kept.fast_count))

    d1 = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    demand_all = {y: d1[d1.year == y].set_index("집계구코드") for y in [2021, 2022, 2023, 2024]}
    demand = demand_all[YEAR]["낮_avg"].astype(float).to_dict()
    score_ex = g2sfca(supply, demand, od)
    pd.DataFrame({"oa_code": score_ex.index, "accessibility_score": score_ex.values}).to_csv(
        SCORE_OUT, index=False, encoding="utf-8-sig")

    gdf = gpd.read_file(BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)
    w = libpysal.weights.KNN.from_array(np.array([[p.x, p.y] for p in gdf.geometry.centroid]), k=K)
    gu = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)

    versions = {f"{y}": (y, pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{y}_week_낮_normal.csv", dtype={"oa_code": str})
                         .set_index("oa_code").accessibility_score) for y in [2021, 2022, 2023, 2024]}
    versions["2023_이상월제외"] = (YEAR, score_ex)
    rows, cls = [], {}
    for name, (y, s) in versions.items():
        dw = demand_all[y]["낮_avg"].astype(float).reindex(s.index).fillna(0).values
        x = s.values
        c = gi_classes(gdf, w, s)
        cls[name] = c
        hot = pd.Series(c == "Hot Spot").groupby(gu.values).sum()
        rows.append({"version": name, "mean_score_x1000": round(float(s.mean()) * 1000, 4),
                     "gini": round(weighted_gini(x, dw), 4),
                     "palma": round(weighted_share(x, dw, 0.9, 1.0) / weighted_share(x, dw, 0.0, 0.4), 3),
                     "hot": int((c == "Hot Spot").sum()), "cold": int((c == "Cold Spot").sum()),
                     "hot_종로중구": int(hot.get("종로구", 0) + hot.get("중구", 0))})
    out = pd.DataFrame(rows)
    out.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print(f"\n{out.to_string(index=False)}")
    chg = (cls["2023"] != cls["2023_이상월제외"]).mean() * 100
    print(f"\n>> 2023 원본 vs 이상월 제외: Gi* 분류 바뀐 집계구 {chg:.1f}%")
    print(f">> 저장: {SUMMARY_OUT} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
