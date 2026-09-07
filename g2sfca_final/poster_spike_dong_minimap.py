"""
포스터 그림5(급증 원인) 보조 인셋맵 — 2021→2022 급증 상위 10개 동이
실제로 어디에 몰려있는지 보여주는 미니맵.

spike_cause_decomposition.py가 만든 spike_cause_decomposition_2021_2022.csv
(자치구+동 단위 판정 결과)를 그대로 쓰고, 좌표는 집계구 shp를 동 단위로
dissolve해서 얻음(별도 동 경계 파일 없음).
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

NAS = "/mnt/cowork/EV"
BOUNDARY_FP = f"{NAS}/input/raw/집계구_2016/집계구.shp"
SPIKE_FP = f"{NAS}/output/spike_cause_decomposition_2021_2022.csv"
OUT_PNG = f"{NAS}/output/maps/poster_spike_dong_minimap.png"

GU_MAP = {
    "11010": "종로구", "11020": "중구", "11030": "용산구", "11040": "성동구", "11050": "광진구",
    "11060": "동대문구", "11070": "중랑구", "11080": "성북구", "11090": "강북구", "11100": "도봉구",
    "11110": "노원구", "11120": "은평구", "11130": "서대문구", "11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구", "11180": "금천구", "11190": "영등포구", "11200": "동작구",
    "11210": "관악구", "11220": "서초구", "11230": "강남구", "11240": "송파구", "11250": "강동구",
}

# poster_study_area_map.py와 동일 톤(연구지역 지도와 짝을 이루는 그림이라 팔레트 통일)
GU_FILL = "#f2ede1"
GU_BORDER = "#a89f8a"
INK = "#2b2b2b"
MUTED = "#7a7568"
COLOR_SUPPLY = "#c0392b"   # 신규 공급형
COLOR_MIXED = "#33586b"    # 공급+도로망 복합


def load_gu_and_dong():
    gdf = gpd.read_file(BOUNDARY_FP)
    gdf = gdf.set_crs(epsg=5179, allow_override=True)
    gdf["TOT_REG_CD"] = gdf["TOT_REG_CD"].astype(str)
    gdf = gdf[gdf["TOT_REG_CD"].str.startswith("11")].copy()
    gdf["gu"] = gdf["TOT_REG_CD"].str[:5].map(GU_MAP)

    gu = gdf.dissolve(by="gu").reset_index()
    gu["geometry"] = gu.geometry.buffer(15).buffer(-15).simplify(20)

    dong = gdf.dissolve(by=["gu", "ADM_NM"]).reset_index()
    dong["geometry"] = dong.geometry.buffer(5).buffer(-5)
    return gu, dong


def main():
    gu, dong = load_gu_and_dong()
    spike = pd.read_csv(SPIKE_FP)
    spike["rank"] = spike["delta_score"].rank(ascending=False).astype(int)

    hi = dong.merge(spike, left_on=["gu", "ADM_NM"], right_on=["gu", "dong"], how="inner")
    print(f"매칭된 동: {len(hi)}/10개")
    missing = set(zip(spike["gu"], spike["dong"])) - set(zip(hi["gu"], hi["dong"]))
    if missing:
        print(f"매칭 실패(동 이름 확인 필요): {missing}")

    fig, ax = plt.subplots(figsize=(9, 9.5))
    gu.plot(ax=ax, color=GU_FILL, edgecolor=GU_BORDER, linewidth=0.9)

    for verdict, color in [("신규 공급형", COLOR_SUPPLY), ("공급+도로망 복합", COLOR_MIXED)]:
        sub = hi[hi["verdict"] == verdict]
        if len(sub):
            sub.plot(ax=ax, color=color, edgecolor="white", linewidth=0.6, alpha=0.92)

    # 클러스터로 몰려있는 동은 폴리곤 안에 라벨을 못 넣으므로(마포구 3동,
    # 강서/양천 3동, 서초 4동) 리더라인으로 밖에 빼서 배치. 값은 렌더링
    # 결과 보고 수동으로 잡은 오프셋(포인트 단위)이라 동이 바뀌면 재조정 필요.
    LEADER_OFFSET = {
        "성산2동": (52, -16, "left"),
        "수색동": (0, 30, "center"),
        "발산1동": (-58, 8, "right"),
        "화곡1동": (52, -6, "left"),
        "신정3동": (0, -32, "center"),
        "양재1동": (-52, 8, "right"),
        "양재2동": (0, -32, "center"),
        "내곡동": (50, 6, "left"),
        "세곡동": (48, 22, "left"),
    }

    for _, row in hi.sort_values("rank").iterrows():
        c = row.geometry.representative_point()
        name = row["ADM_NM"]
        label = f"{row['rank']}. {name}"
        color = COLOR_SUPPLY if row["verdict"] == "신규 공급형" else COLOR_MIXED

        if name not in LEADER_OFFSET:
            # 폴리곤이 라벨을 담을 만큼 커서(상암동) 안에 그대로 표기
            ax.annotate(label, xy=(c.x, c.y), xytext=(0, 0), textcoords="offset points",
                        fontsize=7.3, color="white", ha="center", va="center", fontweight="bold")
            continue

        dx, dy, ha = LEADER_OFFSET[name]
        ax.plot(c.x, c.y, "o", color=color, markersize=5, markeredgecolor="white", markeredgewidth=0.8, zorder=5)
        ax.annotate(
            label, xy=(c.x, c.y), xytext=(dx, dy), textcoords="offset points",
            fontsize=7.5, color=INK, ha=ha, va="center", fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7, shrinkA=0, shrinkB=4),
            zorder=6,
        )

    for _, row in gu.iterrows():
        c = row.geometry.representative_point()
        ax.text(c.x, c.y, row["gu"], fontsize=6, color=MUTED, ha="center", va="center", alpha=0.75)

    ax.set_axis_off()
    ax.set_title("2021→2022 접근성 급증 상위 10개 동", fontsize=15, color=INK, fontweight="bold", pad=12)

    handles = [
        mpatches.Patch(facecolor=COLOR_SUPPLY, label="신규 공급형 (8개 동)"),
        mpatches.Patch(facecolor=COLOR_MIXED, label="공급+도로망 복합 (2개 동)"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=9)
    fig.text(0.5, 0.03, "Δ2SFCA score(week_낮_normal) 상위 10개 동 · 순번은 급증 순위",
              ha="center", fontsize=9, color=MUTED)

    fig.tight_layout(rect=[0, 0.02, 1, 1])
    fig.savefig(OUT_PNG, dpi=150, facecolor="white", bbox_inches="tight")
    print(f"saved {OUT_PNG}")


if __name__ == "__main__":
    main()
