"""심야 시간대 도로망 그래프 근사 생성.
View-T 원본 데이터에 심야 시간대 자체가 없어(오전/낮/밤 6개 시간대만 제공),
심야는 교통정체가 거의 없다고 가정하고 기존 오전/낮/밤 각각의 freeflow(85% 주행속도)
시나리오 그래프를 평균내어 근사치로 사용.
"""
import os
import networkx as nx

BASE = '/mnt/cowork/EV/input/processed/도로망_그래프/서울_연도별_시간대통합'
YEARS = [2021, 2022, 2023, 2024]
DAYTYPES = ['week', 'weekend']
PERIODS = ['오전', '낮', '밤']

for year in YEARS:
    for daytype in DAYTYPES:
        graphs = []
        for period in PERIODS:
            fp = os.path.join(BASE, str(year), f'seoul_{year}_{daytype}_{period}_freeflow_연평균.graphml')
            graphs.append(nx.read_graphml(fp))

        ref = graphs[0]
        avg_g = nx.DiGraph()
        avg_g.graph.update(ref.graph)
        for n, d in ref.nodes(data=True):
            avg_g.add_node(n, **d)

        for u, v in ref.edges():
            d0 = ref[u][v]
            speeds = [float(g[u][v]['speed']) for g in graphs]
            avg_speed = sum(speeds) / len(speeds)
            new_d = dict(d0)
            new_d['speed'] = avg_speed
            length = float(d0['length'])
            new_d['travel_time'] = length / (avg_speed * 1000 / 3600)
            avg_g.add_edge(u, v, **new_d)

        out_path = os.path.join(BASE, str(year), f'seoul_{year}_{daytype}_심야_freeflow_연평균.graphml')
        nx.write_graphml(avg_g, out_path)
        print(f'{year} {daytype} 심야: 완료 (노드 {avg_g.number_of_nodes()}, 엣지 {avg_g.number_of_edges()}) -> {out_path}')
