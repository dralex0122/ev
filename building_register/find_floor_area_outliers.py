import glob
import pandas as pd

BASE = "/home/jmw/ev-charger-accessibility/building_register/building_register_seoul"

rows = []
for f in glob.glob(BASE + "/*.csv"):
    df = pd.read_csv(
        f, encoding="utf-8-sig",
        usecols=["대지위치", "건물명", "연면적(㎡)", "대지면적(㎡)", "건축면적(㎡)", "주용도코드명", "세대수(세대)"],
    )
    df["__file"] = f.split("/")[-1]
    rows.append(df)

full = pd.concat(rows, ignore_index=True)
for c in ["연면적(㎡)", "대지면적(㎡)", "건축면적(㎡)", "세대수(세대)"]:
    full[c] = pd.to_numeric(full[c], errors="coerce")

full["gu"] = full["__file"].str.split(" ").str[0]

has_site = full["대지면적(㎡)"] > 0
ratio_site = full["연면적(㎡)"] / full["대지면적(㎡)"]
flag_site = has_site & (ratio_site > 20)

has_hh = full["세대수(세대)"] > 0
ratio_hh = full["연면적(㎡)"] / full["세대수(세대)"]
flag_hh = has_hh & (ratio_hh > 1000)

flagged = full[flag_site | flag_hh].copy()
flagged["연면적_보정"] = flagged["연면적(㎡)"] / 1000

print(f"총 {len(flagged)}건 이상치 발견")
cols = ["gu", "대지위치", "건물명", "주용도코드명", "세대수(세대)", "대지면적(㎡)", "연면적(㎡)", "연면적_보정"]
print(flagged[cols].to_string())

flagged[["gu", "주용도코드명", "세대수(세대)", "연면적(㎡)", "연면적_보정"]].to_csv(
    "/home/jmw/ev-charger-accessibility/building_register/floor_area_outliers.csv",
    index=False, encoding="utf-8-sig",
)
print("저장: floor_area_outliers.csv")
