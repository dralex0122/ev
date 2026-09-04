import os
import time
import networkx as nx

SRC_BASE = "/mnt/cowork/EV/input/processed/도로망_그래프/서울_연도별_월평균"
OUT_BASE = "/mnt/cowork/EV/input/processed/도로망_그래프/서울_연도별_시간대통합"

YEARS = [2021, 2022, 2023, 2024]
DAYTYPES = ["week", "weekend"]
SCENARIOS = ["congested", "normal", "freeflow"]
PERIODS = {
    "오전": ["07", "08"],
    "낮": ["11", "12"],
    "밤": ["17", "18"],
}


def average_combo(year, daytype, period, hours, scenario):
    src_dir = os.path.join(SRC_BASE, str(year))
    graphs = []
    for hour in hours:
        fname = f"seoul_{year}_{daytype}_{hour}시_{scenario}_연평균.graphml"
        path = os.path.join(src_dir, fname)
        graphs.append(nx.read_graphml(path))

    ref = graphs[0]
    avg_g = nx.DiGraph()
    avg_g.graph.update(ref.graph)
    for n, d in ref.nodes(data=True):
        avg_g.add_node(n, **d)

    for u, v in ref.edges():
        d0 = ref[u][v]
        speeds = [float(g[u][v]["speed"]) for g in graphs]
        avg_speed = sum(speeds) / len(speeds)
        new_d = dict(d0)
        new_d["speed"] = avg_speed
        length = float(d0["length"])
        new_d["travel_time"] = length / (avg_speed * 1000 / 3600)
        avg_g.add_edge(u, v, **new_d)

    out_dir = os.path.join(OUT_BASE, str(year))
    os.makedirs(out_dir, exist_ok=True)
    out_name = f"seoul_{year}_{daytype}_{period}_{scenario}_연평균.graphml"
    out_path = os.path.join(out_dir, out_name)
    nx.write_graphml(avg_g, out_path)
    return out_path, avg_g.number_of_nodes(), avg_g.number_of_edges()


def main():
    combos = [
        (y, d, p, s)
        for y in YEARS
        for d in DAYTYPES
        for p in PERIODS
        for s in SCENARIOS
    ]
    total = len(combos)
    print(f"총 {total}개 조합 처리 시작", flush=True)
    t_start = time.time()
    for i, (y, d, p, s) in enumerate(combos, 1):
        t0 = time.time()
        out_path, n_nodes, n_edges = average_combo(y, d, p, PERIODS[p], s)
        dt = time.time() - t0
        elapsed = time.time() - t_start
        print(
            f"[{i}/{total}] {y} {d} {p} {s} -> {out_path} "
            f"(nodes={n_nodes}, edges={n_edges}, {dt:.1f}s, 누적 {elapsed/60:.1f}분)",
            flush=True,
        )
    print("전체 완료", flush=True)


if __name__ == "__main__":
    main()
