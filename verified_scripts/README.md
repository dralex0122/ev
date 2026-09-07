# verified_scripts/

`g2sfca_final/`에 있는 스크립트 중, **사용자가 직접 `_mw`(또는 `_my`) ipynb로
변환·검증한 것만** 원본 `.py`와 짝으로 모아둔 폴더. "진짜 필요한 것"의
기준은 이 페어링 자체 — ipynb가 있다는 건 사용자가 결과를 직접 열어보고
확인했다는 뜻.

- **원본(실행용)**: `g2sfca_final/*.py` — 실제 파이프라인은 여기서 계속 돌림
- **여기(`verified_scripts/`)**: 위 파일들의 복사본 + 사용자 개인 ipynb를 나란히 둔
  참조용 폴더. `.py`를 여기서 고쳐도 실제 파이프라인엔 반영 안 됨 — 수정은
  `g2sfca_final/`에서 하고, 여기는 다시 복사해서 갱신.

## 목록 (18쌍, `.py` ↔ `.ipynb`)

| py | ipynb | 비고 |
|---|---|---|
| poster_study_area_map.py | poster_study_area_map_mw.ipynb | 포스터 그림1 |
| poster_timeseries_week_day.py | poster_timeseries_week_day_mw.ipynb | 포스터 그림2 |
| poster_2sfca_weekday_grid.py | poster_2sfca_weekday_grid_mw.ipynb | 포스터 그림3 |
| plot_hotspot_transition.py | plot_hotspot_transition_mw.ipynb | 포스터 그림4 (hotspot_transition_2SFCA.png) |
| poster_spike_cause_summary.py | poster_spike_cause_summary_mw.ipynb | 포스터 그림5 |
| poster_spike_dong_minimap.py | poster_spike_dong_minimap_mw.ipynb | 포스터 그림5 부속 |
| plot_two_model_hotspot.py | plot_two_model_hotspot_mw.ipynb | 2모형 핫스팟 지도(모형비교용) |
| plot_two_model_by_year.py | plot_two_model_by_year_mw.ipynb | 2모형 연도별 지도(모형비교용) |
| plot_two_model_fig4.py | plot_two_model_fig4_mw.ipynb | Park et al. Fig4 재현(모형비교용) |
| two_model_hotspot.py | two_model_hotspot_my.ipynb | Gi* 계산(계산 전용, 이미지 없음) |
| hotspot_transition.py | hotspot_transition_mw.ipynb | 전이 판정 계산(계산 전용, 이미지 없음) |
| hotspot_gi_star.py | hotspot_gi_star_mw.ipynb | Gi* 계산(계산 전용, 이미지 없음) |
| g2sfca_final_supply.py | g2sfca_final_supply_mw.ipynb | 2SFCA 접근성 계산(계산 전용) |
| gravity_model_supply.py | gravity_model_supply.ipynb | Gravity 접근성 계산(계산 전용) |
| gini_palma.py | gini_palma_mw.ipynb | 형평성 지표 계산(계산 전용) |
| freeflow_sensitivity_check.py | freeflow_sensitivity_check_mw.ipynb | 민감도 검증(계산 전용) |
| plot_ev_charger_overlay.py | plot_ev_charger_overlay_mw.ipynb | EV vs EVCS 급등 오버레이(포스터 범위 밖) |
| spike_2021_2022_by_dong.py | spike_2021_2022_by_dong_mw.ipynb | 급증 동단위 중간분석(포스터 범위 밖) |

이미지가 나오는 스크립트(9개)의 결과물은 `../verified_figures/`에 정리.
