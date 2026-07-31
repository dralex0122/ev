"""
서버용: 서울 2024년 7~12월 이어서 생성 (1~6월은 로컬에서 이미 완료해서 NAS 업로드됨).
build_seoul_network_years.py와 동일 로직, 대상만 2024년 7~12월로 한정.
"""
import glob
import os
import time

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd

BASE = os.path.expanduser("~/ev-charger-accessibility/graph_years")
OUT_ROOT = os.path.expanduser("~/ev-charger-accessibility/graph_years/output")

YEAR = "2024"
MONTHS = range(7, 13)
HOUR_LABELS = {"7": "07시", "8": "08시", "11": "11시", "12": "12시", "17": "17시", "18": "18시"}
SCENARIOS = {"congested": "15% 주행속도 (km/h)", "normal": "30% 주행속도 (km/h)", "freeflow": "85% 주행속도 (km/h)"}
DAYTYPES = ["week", "weekend"]
RANK_DEFAULT = {"101": 100, "102": 80, "103": 50, "104": 50, "105": 50, "106": 50, "107": 50, "108": 40}

t0 = time.time()


def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)


def find_shp(year_dir, keyword):
    matches = glob.glob(os.path.join(year_dir, f"*{keyword}*.shp"))
    if not matches:
        raise FileNotFoundError(f"{year_dir}에서 {keyword} shp를 못 찾음")
    return matches[0]


year_net_dir = os.path.join(BASE, "network_raw", YEAR)
node_fp = find_shp(year_net_dir, "node")
link_fp = find_shp(year_net_dir, "link")

log("도로망 shp 로드")
nodes_viewt = gpd.read_file(node_fp, encoding="cp949")
edges_viewt = gpd.read_file(link_fp, encoding="cp949")
log(f"   노드 {len(nodes_viewt):,}개, 엣지 {len(edges_viewt):,}개")

nodes_gdf = nodes_viewt.copy()
nodes_gdf["node_id"] = nodes_gdf["node_id"].astype(int).astype(str)
nodes_gdf["node_type"] = nodes_gdf["node_type"].astype(int).astype(str)
nodes_gdf["y"] = nodes_gdf["geometry"].y
nodes_gdf["x"] = nodes_gdf["geometry"].x
nodes_gdf = nodes_gdf[["node_id", "node_type", "geometry", "x", "y"]].set_index("node_id")

two_way = edges_viewt["oneway"] == 0
one_way = ~two_way
cols = ["max_speed", "road_name", "road_rank", "link_type"]
fwd_two = edges_viewt.loc[two_way, ["up_v_link", "up_f_node", "up_t_node"] + cols + ["geometry"]].rename(
    columns={"up_v_link": "link_id", "up_f_node": "f_node", "up_t_node": "t_node"})
bwd_two = edges_viewt.loc[two_way, ["dw_v_link", "dw_f_node", "dw_t_node"] + cols + ["geometry"]].rename(
    columns={"dw_v_link": "link_id", "dw_f_node": "f_node", "dw_t_node": "t_node"})
bwd_two["geometry"] = bwd_two["geometry"].apply(lambda g: g.reverse())
fwd_one = edges_viewt.loc[one_way, ["up_v_link", "up_f_node", "up_t_node"] + cols + ["geometry"]].rename(
    columns={"up_v_link": "link_id", "up_f_node": "f_node", "up_t_node": "t_node"})

edges_base = pd.concat([fwd_two, bwd_two, fwd_one], ignore_index=True)
edges_base = gpd.GeoDataFrame(edges_base, geometry="geometry", crs=edges_viewt.crs)
edges_base["length"] = edges_base.geometry.length
edges_base["link_id"] = edges_base["link_id"].astype(int).astype(str)
edges_base["f_node"] = edges_base["f_node"].astype(int).astype(str)
edges_base["t_node"] = edges_base["t_node"].astype(int).astype(str)
edges_base["road_rank"] = edges_base["road_rank"].astype(int).astype(str)
edges_base["link_type"] = edges_base["link_type"].astype(int).astype(str)
edges_base["max_speed"] = edges_base["max_speed"].astype(int)
log(f"   엣지(양방향 처리 후) {len(edges_base):,}개")

out_dir = os.path.join(OUT_ROOT, YEAR)
os.makedirs(out_dir, exist_ok=True)
speed_dir = os.path.join(BASE, "speed_raw", YEAR)

total_done = 0
total_target = len(list(MONTHS)) * 2 * 6 * 3

for month in MONTHS:
    mm = f"{month:02d}"
    for daytype in DAYTYPES:
        csv_fp = os.path.join(speed_dir, f"{YEAR[2:]}{mm}_seoul_{daytype}_PercentileSpeed.csv")
        if not os.path.isfile(csv_fp):
            log(f"[{YEAR}-{mm} {daytype}] CSV 없음, 스킵")
            continue
        speed_df = pd.read_csv(csv_fp, encoding="utf-8-sig")
        speed_df.columns = [c.strip().lstrip("﻿") for c in speed_df.columns]
        speed_df["주요시간대"] = speed_df["주요시간대"].astype(str)
        speed_df["level6 LINK ID"] = speed_df["level6 LINK ID"].astype(str)

        for hour_code, hour_label in HOUR_LABELS.items():
            for scenario_name, speed_col in SCENARIOS.items():
                edges_gdf = edges_base.copy()
                hour_speed = speed_df[speed_df["주요시간대"] == hour_code][["level6 LINK ID", speed_col]]
                hour_speed = hour_speed.rename(columns={"level6 LINK ID": "link_id", speed_col: "speed"})
                hour_speed = hour_speed.groupby("link_id", as_index=False)["speed"].mean()

                edges_gdf = edges_gdf.merge(hour_speed, on="link_id", how="left")
                missing = edges_gdf["speed"].isna() | (edges_gdf["speed"] == 0)
                edges_gdf.loc[missing, "speed"] = edges_gdf.loc[missing, "road_rank"].map(RANK_DEFAULT)
                edges_gdf["speed"] = edges_gdf["speed"].fillna(50)

                edges_gdf["travel_time"] = edges_gdf["length"] / (edges_gdf["speed"] * 1000 / 3600)
                edges_gdf = edges_gdf.rename(columns={"f_node": "u", "t_node": "v"})
                edges_gdf["key"] = 0
                edges_gdf = edges_gdf.set_index(["u", "v", "key"])
                edges_gdf = edges_gdf.loc[
                    edges_gdf.index.get_level_values("u").isin(nodes_gdf.index)
                    & edges_gdf.index.get_level_values("v").isin(nodes_gdf.index)
                ]

                G = ox.graph_from_gdfs(nodes_gdf, edges_gdf)
                largest = max(nx.strongly_connected_components(G), key=len)
                G = G.subgraph(largest).copy()

                out_fp = os.path.join(out_dir, f"seoul_{YEAR}{mm}_{daytype}_{hour_label}_{scenario_name}.graphml")
                ox.save_graphml(G, out_fp)
                total_done += 1
        log(f"[{YEAR}-{mm} {daytype}] 완료 (누적 {total_done}/{total_target})")

log(f"=== 2024년 7~12월 완료: {total_done}/{total_target} ===")
