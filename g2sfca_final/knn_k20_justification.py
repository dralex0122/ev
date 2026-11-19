"""
2026-11-18 개별미팅: Gi* KNN k=20 근거 자료.

1. 집계구 중심점 간 거리 — k번째 이웃까지 거리(k=1·8·15·20·30) 분포, 도심/비도심 비교
2. k=20 이웃이 들어가는 반경을 2SFCA 임계 통행시간(15분)·Gaussian 감쇠와 같은 축(m)으로 비교할 수 있게 요약
3. (참고) 전역 Moran's I를 k=4~60에서 계산 — z값이 최대가 되는 k(증분 공간자기상관, Incremental Spatial Autocorrelation)

출력: output/recheck_2026-10-13/gistar95/knn_justification/
"""
import os
import sys

import pyproj
os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())

import numpy as np
import pandas as pd
import geopandas as gpd
import libpysal
import esda
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import recheck_uselimitation_week_day as R
from recompute_exclude_nonpublic import NONPUBLIC_DIR

OUT = f"{R.OUT_DIR}/gistar95/knn_justification"
os.makedirs(OUT, exist_ok=True)
pr = lambda *a: print(*a, flush=True)

for f in ["AppleGothic", "NanumGothic", "Malgun Gothic"]:
    if any(f in x.name for x in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams["axes.unicode_minus"] = False

gdf = gpd.read_file(R.BOUNDARY_FP).set_crs(epsg=5179, allow_override=True)
gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].reset_index(drop=True)
gu = gdf["TOT_REG_CD"].str[:5].map(R.GU_MAP)
downtown = gu.isin(["종로구", "중구"]).values
pts = np.array([[p.x, p.y] for p in gdf.geometry.centroid])
area_km2 = gdf.geometry.area.values / 1e6
pr(f"집계구 {len(gdf):,}개, 도심(종로·중구) {downtown.sum():,}개")
pr(f"집계구 면적(km²) 중앙값 {np.median(area_km2):.4f}, 평균 {area_km2.mean():.4f}")

# ---------- 1. k번째 이웃 거리 ----------
KS = [1, 8, 15, 20, 30]
tree = cKDTree(pts)
d, _ = tree.query(pts, k=max(KS) + 1)  # 0번째 = 자기 자신
dist = pd.DataFrame({f"d{k}": d[:, k] for k in KS})
dist["oa_code"] = gdf["TOT_REG_CD"].values
dist["gu"] = gu.values
dist["downtown"] = downtown
dist.to_csv(f"{OUT}/knn_distance_per_oa.csv", index=False, encoding="utf-8-sig")


def summ(x):
    return pd.Series({"평균": x.mean(), "p10": np.percentile(x, 10), "p25": np.percentile(x, 25),
                      "중앙값": np.median(x), "p75": np.percentile(x, 75), "p90": np.percentile(x, 90),
                      "최대": x.max()})


rows = []
for k in KS:
    for lab, m in [("서울 전체", np.ones(len(dist), bool)), ("도심(종로·중구)", downtown), ("그 외", ~downtown)]:
        s = summ(dist.loc[m, f"d{k}"]).round(0)
        rows.append({"k": k, "지역": lab, **s.to_dict()})
tab = pd.DataFrame(rows)
tab.to_csv(f"{OUT}/knn_distance_summary.csv", index=False, encoding="utf-8-sig")
pr("\n=== k번째 이웃까지 거리(m) ===\n", tab.to_string(index=False))

# 구별 k=20 반경 중앙값
gu_tab = dist.groupby("gu")["d20"].median().sort_values().round(0)
gu_tab.to_csv(f"{OUT}/knn20_radius_by_gu.csv", encoding="utf-8-sig")
pr("\n=== 구별 k=20 반경 중앙값(m) ===\n", gu_tab.to_string())

# 고정거리 비교: 모든 집계구가 이웃을 1개 이상 갖는 최소 거리, 평균 이웃수 20이 되는 거리
thr_min = d[:, 1].max()
for r in [500, 750, 1000, 1500]:
    n = np.array([len(x) - 1 for x in tree.query_ball_point(pts, r)])
    pr(f"고정거리 {r}m: 이웃수 평균 {n.mean():.1f}, 중앙값 {np.median(n):.0f}, 최소 {n.min()}, 최대 {n.max()}")
pr(f"모든 집계구가 이웃 1개 이상 갖는 최소 거리: {thr_min:.0f} m")

# 그림: 박스플롯
fig, ax = plt.subplots(figsize=(7, 4.2), dpi=200)
data = [dist[f"d{k}"].values for k in KS]
ax.boxplot(data, tick_labels=[f"k={k}" for k in KS], showfliers=False, widths=0.5,
           medianprops=dict(color="#c0392b", lw=1.6), boxprops=dict(color="#333"),
           whiskerprops=dict(color="#333"), capprops=dict(color="#333"))
for i, k in enumerate(KS, 1):
    med = np.median(dist[f"d{k}"])
    ax.text(i + 0.3, med, f"{med:,.0f} m", va="center", fontsize=8, color="#c0392b")
ax.set_ylabel("k번째 이웃 집계구까지 거리 (m)")
ax.set_title("집계구 중심점 간 k번째 이웃 거리 분포 (서울 19,153개 집계구)", fontsize=10)
ax.grid(axis="y", color="#ddd", lw=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{OUT}/knn_distance_boxplot.png")
plt.close(fig)

# ---------- 3. 증분 공간자기상관 ----------
mi_rows = []
KGRID = [4, 6, 8, 10, 12, 15, 18, 20, 22, 25, 30, 35, 40, 50, 60]
for y in R.YEARS:
    s = pd.read_csv(f"{NONPUBLIC_DIR}/g2sfca_score_{y}_week_낮_normal.csv", dtype={"oa_code": str}) \
        .set_index("oa_code").accessibility_score.reindex(gdf["TOT_REG_CD"]).fillna(0).values
    for k in KGRID:
        w = libpysal.weights.KNN.from_array(pts, k=k)
        w.transform = "R"
        mi = esda.moran.Moran(s, w, permutations=0)
        mi_rows.append({"year": y, "k": k, "I": mi.I, "z": mi.z_norm,
                        "median_radius_m": np.median(d[:, k]) if k <= max(KS) else np.nan})
    pr(f"{y} Moran's I 완료")
mi = pd.DataFrame(mi_rows)
mi.to_csv(f"{OUT}/incremental_moran_by_k.csv", index=False, encoding="utf-8-sig")
piv_z = mi.pivot(index="k", columns="year", values="z").round(1)
piv_i = mi.pivot(index="k", columns="year", values="I").round(3)
pr("\n=== Moran's I (k별) ===\n", piv_i.to_string())
pr("\n=== Moran's I z값 (k별) ===\n", piv_z.to_string())

fig, ax = plt.subplots(figsize=(7, 4), dpi=200)
for y, c in zip(R.YEARS, ["#9ecae1", "#6baed6", "#3182bd", "#08519c"]):
    sub = mi[mi.year == y]
    ax.plot(sub.k, sub.z, marker="o", ms=3, lw=1.5, color=c, label=str(y))
ax.axvline(20, color="#c0392b", lw=1, ls="--")
ax.set_xlabel("이웃 수 k")
ax.set_ylabel("전역 Moran's I z값")
ax.set_title("k별 전역 Moran's I z값 (증분 공간자기상관)", fontsize=10)
ax.legend(frameon=False, fontsize=8)
ax.grid(color="#eee", lw=0.6)
fig.tight_layout()
fig.savefig(f"{OUT}/incremental_moran_z.png")
plt.close(fig)
pr("\n저장:", OUT)
