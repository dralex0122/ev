"""
G2SFCA 전체 실행: 2024년 평일 오전 normal 시나리오

1. 충전소(공급) -> 250m 인구격자(수요) 이동시간 행렬 계산 (15분 컷오프)
2. G2SFCA 2단계 접근성 점수 계산 (임계값 컷오프 방식, t0=15분)
   - 공급: 충전소 total_count
   - 수요: 250m 격자 night_avg (생활인구, 평일 새벽 평균) -- 잠정 기준
"""
import csv
import json
import os
import time
import unicodedata

import networkx as nx
from pyproj import Transformer
from scipy.spatial import cKDTree

BASE = os.path.expanduser("~/ev-charger-accessibility")
NAS = "/mnt/cowork/EV"

GRAPH_FP = os.path.join(
    NAS, "도로망_그래프/서울_연도별_시간대통합/2024/seoul_2024_week_오전_normal_연평균.graphml"
)
CHARGER_FP = os.path.join(NAS, "yearly_snapshots/metro7_ev_chargers_2024.geojson")

TILE_LETTERS = "가나다라마바사아"
WGS84_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
CUTOFF_SEC = 900  # 15분

OUT_DIR = os.path.join(NAS, "g2sfca")


def tile_origin(prefix):
    col = TILE_LETTERS.index(prefix[0]) + 1
    row = TILE_LETTERS.index(prefix[1]) + 1
    return 700000 + (col - 1) * 100000, 1300000 + (row - 1) * 100000


def cell250_center_xy(cell250_id):
    prefix = cell250_id[:2]
    digits = cell250_id[2:]
    x0, y0 = tile_origin(prefix)
    x = x0 + int(digits[:4]) * 10 + 125
    y = y0 + int(digits[4:]) * 10 + 125
    return x, y


def load_pop250():
    import glob
    fp = glob.glob(os.path.join(BASE, "grid_stats", "seoul_250m_생활인구_평일평균프로파일*.csv"))[0]
    demand = {}
    with open(fp, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            demand[row["grid_id"]] = {
                "night_avg": float(row["night_avg_00_05"]),
                "day_avg": float(row["day_avg_12_16"]),
            }
    return demand


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    print(f"그래프 로드: {GRAPH_FP}", flush=True)
    G = nx.read_graphml(GRAPH_FP)
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
    charger_fp = unicodedata.normalize("NFD", CHARGER_FP)
    with open(charger_fp, encoding="utf-8") as f:
        data = json.load(f)
    chargers = [f for f in data["features"] if f["properties"].get("city") == "서울특별시"]
    print(f"충전소: {len(chargers):,}개", flush=True)

    charger_info = {}  # station_id -> {node, total_count, lat, lon}
    for c in chargers:
        lon, lat = c["geometry"]["coordinates"]
        x, y = WGS84_TO_5179.transform(lon, lat)
        node = nearest_node(x, y)
        sid = c["properties"]["station_id"]
        charger_info[sid] = {
            "node": node,
            "total_count": c["properties"].get("total_count", 0),
            "lat": lat, "lon": lon,
        }

    # 인구격자 로드 + 수요값
    demand = load_pop250()
    grid_node_map = {}
    for gid in demand:
        x, y = cell250_center_xy(gid)
        node = nearest_node(x, y)
        grid_node_map.setdefault(node, []).append(gid)
    print(f"인구격자: {len(demand):,}개 -> 고유노드 {len(grid_node_map):,}개", flush=True)

    # ---- 1) 이동시간 행렬 계산 (전체 충전소) ----
    t1 = time.time()
    od_fp = os.path.join(OUT_DIR, "od_2024_week_오전_normal.csv")
    total_pairs = 0
    catchment_by_station = {}  # station_id -> [(grid_id, travel_time), ...]
    with open(od_fp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["station_id", "grid_id", "travel_time_sec"])
        for i, (sid, info) in enumerate(charger_info.items(), 1):
            reach = nx.single_source_dijkstra_path_length(G, info["node"], cutoff=CUTOFF_SEC, weight="travel_time")
            pairs = []
            for reached_node, tt in reach.items():
                if reached_node in grid_node_map:
                    for gid in grid_node_map[reached_node]:
                        pairs.append((gid, tt))
                        w.writerow([sid, gid, f"{tt:.1f}"])
            catchment_by_station[sid] = pairs
            total_pairs += len(pairs)
            if i % 1000 == 0:
                print(f"  [{i}/{len(charger_info)}] 진행 중... ({time.time()-t1:.1f}s)", flush=True)
    od_time = time.time() - t1
    print(f"이동시간 행렬 계산 완료: {total_pairs:,}쌍, {od_time:.1f}초 -> {od_fp}", flush=True)
    print(f"  파일 크기: {os.path.getsize(od_fp)/1024/1024:.1f} MB", flush=True)

    # ---- 2) G2SFCA step 1: 공급 대비 비율 R_j ----
    # R_j = S_j / sum_{k in catchment(j)} D_k   (임계값 컷오프, 감쇠함수 없음)
    R = {}
    for sid, pairs in catchment_by_station.items():
        S_j = charger_info[sid]["total_count"]
        D_sum = sum(demand[gid]["night_avg"] for gid, tt in pairs)
        R[sid] = S_j / D_sum if D_sum > 0 else 0.0

    # ---- 3) G2SFCA step 2: 격자별 접근성 A_i ----
    # 격자 -> 그 격자를 15분 내에 포함하는 충전소 목록이 필요 -> catchment_by_station을 뒤집음
    grid_catchment = {}  # grid_id -> [station_id, ...]
    for sid, pairs in catchment_by_station.items():
        for gid, tt in pairs:
            grid_catchment.setdefault(gid, []).append(sid)

    A = {}
    for gid in demand:
        stations = grid_catchment.get(gid, [])
        A[gid] = sum(R[sid] for sid in stations)

    # ---- 저장 ----
    score_fp = os.path.join(OUT_DIR, "g2sfca_score_2024_week_오전_normal.csv")
    with open(score_fp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["grid_id", "accessibility_score", "n_stations_in_catchment", "demand_night_avg"])
        for gid in demand:
            w.writerow([gid, f"{A[gid]:.6f}", len(grid_catchment.get(gid, [])), demand[gid]["night_avg"]])
    print(f"G2SFCA 점수 저장: {score_fp}", flush=True)

    # ---- 요약 통계 ----
    import statistics
    scores = list(A.values())
    zero_access = sum(1 for s in scores if s == 0)
    print("\n=== 접근성 점수(A_i) 분포 ===")
    print(f"평균: {statistics.mean(scores):.6f}")
    print(f"중앙값: {statistics.median(scores):.6f}")
    print(f"최댓값: {max(scores):.6f}")
    print(f"0(접근 불가) 격자: {zero_access:,} / {len(scores):,} ({zero_access/len(scores)*100:.1f}%)")

    n_reach_list = [len(pairs) for pairs in catchment_by_station.values()]
    print("\n=== 충전소별 도달 격자 수 분포 ===")
    print(f"평균: {statistics.mean(n_reach_list):.1f}")
    print(f"중앙값: {statistics.median(n_reach_list):.1f}")
    print(f"최소/최대: {min(n_reach_list)} / {max(n_reach_list)}")

    print(f"\n전체 경과 시간: {time.time()-t0:.1f}초")


if __name__ == "__main__":
    main()
