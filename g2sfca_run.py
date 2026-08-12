"""
G2SFCA 실행 (집계구 기반, 파라미터화 버전)

1. 충전소(공급) -> 집계구(수요) 이동시간 행렬 계산 (15분/900초 컷오프)
2. G2SFCA 2단계 접근성 점수 계산 (임계값 컷오프 방식, t0=15분)
   - 공급: S1(단순 total_count) 또는 S2(급속:완속 가중, --supply로 선택)
   - 수요: 집계구 시간대별 평균 생활인구 (D1, 2021~2024 확보, 오전/낮/밤/심야)

S2 가중치(SUPPLY_S2_FAST_RATIO=2.4)는 서울 10분 가용률 루프 실측(2026-08-05,
2026-08-10 재검증) 기반. 문헌값(12:1, Li et al. 2022 인용)은 원출처(Schroeder &
Traber 2012, 독일)를 추적한 결과 원문 수치가 75:4였고 근거 불명으로 48:4로
재조정된 값이라 provenance가 약함 - 2026-08-10 논의 후 실측값 채택.

250m 인구격자 대신 집계구(2016년 경계, d1_final_2021_2024.csv)를 수요점으로 사용 -
2026-08-05 확인 결과 250m 격자는 2021~2022년 데이터가 없어 종단분석에 부적합했음.

S1/S2 결과는 서로 다른 폴더에 저장되어 기존 S1 결과와 섞이지 않음:
  S1 -> /mnt/cowork/EV/g2sfca/
  S2 -> /mnt/cowork/EV/g2sfca_s2/
"""
import argparse
import csv
import json
import os
import time
import unicodedata

import networkx as nx
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

BASE = os.path.expanduser("~/ev-charger-accessibility")
NAS = "/mnt/cowork/EV"

GRAPH_DIR = os.path.join(NAS, "도로망_그래프/서울_연도별_시간대통합")
CHARGER_DIR = os.path.join(NAS, "yearly_snapshots")
D1_FP = os.path.join(NAS, "서울시 생활인구/집계구_생활인구_원본(OA-14979)/d1_final_2021_2024.csv")

WGS84_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
CUTOFF_SEC = 900  # 15분 (t0)

OUT_DIRS = {
    "s1": os.path.join(NAS, "g2sfca"),
    "s2": os.path.join(NAS, "g2sfca_s2"),
    "s2park": os.path.join(NAS, "g2sfca_s2_park10"),
}

SUPPLY_FAST_RATIOS = {
    "s2": 2.4,       # 서울 10분 루프 실측 기반(2026-08-10 재검증, 20일치)
    "s2park": 10.0,  # Park et al.(2022) 문헌값 - 급속충전 속도가 10배 빠르다는 스펙 기반, 강건성 비교용
}

PERIOD_COL = {
    "오전": "오전_avg",
    "낮": "낮_avg",
    "밤": "밤_avg",
    "심야": "심야_avg",
}


def load_oa_demand(year, period):
    """집계구 수요 데이터 로드: 집계구코드 -> {value, lon, lat}"""
    df = pd.read_csv(D1_FP, dtype={"집계구코드": str})
    df = df[df["year"] == year]
    col = PERIOD_COL[period]
    demand = {}
    for _, row in df.iterrows():
        demand[row["집계구코드"]] = {
            "value": float(row[col]),
            "lon": float(row["lon"]),
            "lat": float(row["lat"]),
        }
    return demand


def load_chargers(year):
    """충전소 로드: 연도별 스냅샷(설치연도 누적 필터링), 서울(zcode=11)만"""
    fp = unicodedata.normalize("NFD", os.path.join(CHARGER_DIR, f"metro7_ev_chargers_{year}.geojson"))
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    return [f for f in data["features"] if f["properties"].get("city") == "서울특별시"]


def supply_value(props, supply_mode):
    if supply_mode == "s1":
        return props.get("total_count", 0)
    fast = props.get("fast_count", 0) or 0
    slow = props.get("slow_count", 0) or 0
    return fast * SUPPLY_FAST_RATIOS[supply_mode] + slow * 1


def main(year, daytype, period, scenario, supply="s1"):
    out_dir = OUT_DIRS[supply]
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()

    graph_fp = os.path.join(GRAPH_DIR, str(year), f"seoul_{year}_{daytype}_{period}_{scenario}_연평균.graphml")
    print(f"그래프 로드: {graph_fp}", flush=True)
    G = nx.read_graphml(graph_fp)
    for u, v, d in G.edges(data=True):
        d["travel_time"] = float(d["travel_time"])
    print(f"  노드 {G.number_of_nodes():,} 엣지 {G.number_of_edges():,} ({time.time()-t0:.1f}s)", flush=True)

    node_ids = list(G.nodes())
    node_xy = [(float(G.nodes[n]["x"]), float(G.nodes[n]["y"])) for n in node_ids]
    tree = cKDTree(node_xy)

    def nearest_node(x, y):
        _, idx = tree.query([x, y])
        return node_ids[idx]

    # 충전소 로드
    chargers = load_chargers(year)
    ratio_note = f"(급속가중 {SUPPLY_FAST_RATIOS[supply]}배)" if supply in SUPPLY_FAST_RATIOS else ""
    print(f"충전소({year}, 서울): {len(chargers):,}개, 공급 정의: {supply}" + ratio_note, flush=True)

    charger_info = {}
    for c in chargers:
        lon, lat = c["geometry"]["coordinates"]
        x, y = WGS84_TO_5179.transform(lon, lat)
        node = nearest_node(x, y)
        sid = c["properties"]["station_id"]
        charger_info[sid] = {
            "node": node,
            "supply": supply_value(c["properties"], supply),
            "lat": lat, "lon": lon,
        }

    # 집계구 수요 로드 + 최근접 노드 매핑
    demand = load_oa_demand(year, period)
    oa_node_map = {}
    for oa_code, info in demand.items():
        x, y = WGS84_TO_5179.transform(info["lon"], info["lat"])
        node = nearest_node(x, y)
        oa_node_map.setdefault(node, []).append(oa_code)
    print(f"집계구: {len(demand):,}개 -> 고유노드 {len(oa_node_map):,}개", flush=True)

    # ---- 1) 이동시간 행렬 계산 ----
    t1 = time.time()
    tag = f"{year}_{daytype}_{period}_{scenario}"
    od_fp = os.path.join(out_dir, f"od_{tag}.csv")
    total_pairs = 0
    catchment_by_station = {}
    with open(od_fp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["station_id", "oa_code", "travel_time_sec"])
        for i, (sid, info) in enumerate(charger_info.items(), 1):
            reach = nx.single_source_dijkstra_path_length(G, info["node"], cutoff=CUTOFF_SEC, weight="travel_time")
            pairs = []
            for reached_node, tt in reach.items():
                if reached_node in oa_node_map:
                    for oa_code in oa_node_map[reached_node]:
                        pairs.append((oa_code, tt))
                        w.writerow([sid, oa_code, f"{tt:.1f}"])
            catchment_by_station[sid] = pairs
            total_pairs += len(pairs)
            if i % 1000 == 0:
                print(f"  [{i}/{len(charger_info)}] 진행 중... ({time.time()-t1:.1f}s)", flush=True)
    od_time = time.time() - t1
    print(f"이동시간 행렬 계산 완료: {total_pairs:,}쌍, {od_time:.1f}초 -> {od_fp}", flush=True)
    print(f"  파일 크기: {os.path.getsize(od_fp)/1024/1024:.1f} MB", flush=True)

    # ---- 2) G2SFCA step 1: 공급 대비 비율 R_j ----
    R = {}
    for sid, pairs in catchment_by_station.items():
        S_j = charger_info[sid]["supply"]
        D_sum = sum(demand[oa_code]["value"] for oa_code, tt in pairs)
        R[sid] = S_j / D_sum if D_sum > 0 else 0.0

    # ---- 3) G2SFCA step 2: 집계구별 접근성 A_i ----
    oa_catchment = {}
    for sid, pairs in catchment_by_station.items():
        for oa_code, tt in pairs:
            oa_catchment.setdefault(oa_code, []).append(sid)

    A = {}
    for oa_code in demand:
        stations = oa_catchment.get(oa_code, [])
        A[oa_code] = sum(R[sid] for sid in stations)

    # ---- 저장 ----
    score_fp = os.path.join(out_dir, f"g2sfca_score_{tag}.csv")
    with open(score_fp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["oa_code", "accessibility_score", "n_stations_in_catchment", "demand_value"])
        for oa_code in demand:
            w.writerow([oa_code, f"{A[oa_code]:.6f}", len(oa_catchment.get(oa_code, [])), demand[oa_code]["value"]])
    print(f"G2SFCA 점수 저장: {score_fp}", flush=True)

    # ---- 요약 통계 ----
    import statistics
    scores = list(A.values())
    zero_access = sum(1 for s in scores if s == 0)
    print("\n=== 접근성 점수(A_i) 분포 ===")
    print(f"평균: {statistics.mean(scores):.6f}")
    print(f"중앙값: {statistics.median(scores):.6f}")
    print(f"최댓값: {max(scores):.6f}")
    print(f"0(접근 불가) 집계구: {zero_access:,} / {len(scores):,} ({zero_access/len(scores)*100:.1f}%)")

    n_reach_list = [len(pairs) for pairs in catchment_by_station.values()]
    print("\n=== 충전소별 도달 집계구 수 분포 ===")
    print(f"평균: {statistics.mean(n_reach_list):.1f}")
    print(f"중앙값: {statistics.median(n_reach_list):.1f}")
    print(f"최소/최대: {min(n_reach_list)} / {max(n_reach_list)}")

    print(f"\n전체 경과 시간: {time.time()-t0:.1f}초")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--daytype", default="week", choices=["week", "weekend"])
    parser.add_argument("--period", default="오전", choices=["오전", "낮", "밤", "심야"])
    parser.add_argument("--scenario", default="normal", choices=["normal", "congested", "freeflow"])
    parser.add_argument("--supply", default="s1", choices=["s1", "s2", "s2park"])
    args = parser.parse_args()
    main(args.year, args.daytype, args.period, args.scenario, args.supply)
