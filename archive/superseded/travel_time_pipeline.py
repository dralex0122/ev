"""
G2SFCA 이동시간 행렬 계산 파이프라인 (테스트 실행: 2024년 평일 오전 normal 시나리오)

각 충전소(공급, source)에서 15분(900초) 이내 도달 가능한 250m 인구격자(수요)를
networkx의 single_source_dijkstra_path_length로 계산.
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
POP250_GLOB_DIR = os.path.join(BASE, "grid_stats")

TILE_LETTERS = "가나다라마바사아"
WGS84_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
CUTOFF_SEC = 900  # 15분


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


def load_pop250_grid_ids():
    import glob
    fp = glob.glob(os.path.join(POP250_GLOB_DIR, "seoul_250m_생활인구_평일평균프로파일*.csv"))[0]
    ids = []
    with open(fp, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            ids.append(row["grid_id"])
    return ids


def main():
    t0 = time.time()
    print(f"그래프 로드 중: {GRAPH_FP}", flush=True)
    G = nx.read_graphml(GRAPH_FP)
    print(f"  노드 {G.number_of_nodes():,}개, 엣지 {G.number_of_edges():,}개 ({time.time()-t0:.1f}s)", flush=True)

    # travel_time을 float으로, length도 float으로 캐스팅 (graphml은 전부 문자열로 읽힘)
    for u, v, d in G.edges(data=True):
        d["travel_time"] = float(d["travel_time"])
        d["length"] = float(d["length"])

    # 노드 좌표 배열 (KDTree용)
    node_ids = list(G.nodes())
    node_xy = [(float(G.nodes[n]["x"]), float(G.nodes[n]["y"])) for n in node_ids]
    tree = cKDTree(node_xy)

    def nearest_node(x, y):
        _, idx = tree.query([x, y])
        return node_ids[idx]

    # 충전소 로드 (서울, 2024)
    t1 = time.time()
    charger_fp = unicodedata.normalize("NFD", CHARGER_FP)
    with open(charger_fp, encoding="utf-8") as f:
        data = json.load(f)
    chargers = [f for f in data["features"] if f["properties"].get("city") == "서울특별시"]
    print(f"충전소(서울, 2024): {len(chargers):,}개", flush=True)

    charger_nodes = []
    for c in chargers:
        lon, lat = c["geometry"]["coordinates"]
        x, y = WGS84_TO_5179.transform(lon, lat)
        node = nearest_node(x, y)
        charger_nodes.append((c["properties"]["station_id"], node))
    print(f"  충전소 -> 최근접 노드 매핑 완료 ({time.time()-t1:.1f}s)", flush=True)

    # 250m 인구격자 로드 및 최근접 노드 매핑
    t2 = time.time()
    grid_ids = load_pop250_grid_ids()
    grid_node_map = {}  # node_id -> [grid_id, ...]
    for gid in grid_ids:
        x, y = cell250_center_xy(gid)
        node = nearest_node(x, y)
        grid_node_map.setdefault(node, []).append(gid)
    print(f"인구격자: {len(grid_ids):,}개 -> 고유 노드 {len(grid_node_map):,}개 ({time.time()-t2:.1f}s)", flush=True)

    # ---- 샘플 테스트: 50개 충전소로 시간 측정 ----
    SAMPLE = 50
    t3 = time.time()
    sample_results = []
    for station_id, node in charger_nodes[:SAMPLE]:
        reach = nx.single_source_dijkstra_path_length(G, node, cutoff=CUTOFF_SEC, weight="travel_time")
        matched_grids = 0
        for reached_node, tt in reach.items():
            if reached_node in grid_node_map:
                matched_grids += len(grid_node_map[reached_node])
        sample_results.append((station_id, len(reach), matched_grids))
    sample_time = time.time() - t3
    per_station = sample_time / SAMPLE
    print(f"\n샘플 {SAMPLE}개 충전소 처리: {sample_time:.2f}초 (충전소당 평균 {per_station:.3f}초)", flush=True)
    print(f"전체 {len(charger_nodes):,}개 충전소 예상 소요시간: {per_station*len(charger_nodes)/60:.1f}분", flush=True)

    print("\n샘플 결과 (충전소ID, 도달노드수, 도달격자수):")
    for r in sample_results[:10]:
        print(" ", r)

    print(f"\n전체 경과: {time.time()-t0:.1f}초")


if __name__ == "__main__":
    main()
