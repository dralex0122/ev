"""
2026-11-11 개별미팅: 21→24 Hot 전이 지도 색 변경.
기존(downtown_hot_loss_supplement.py)은 신규 Hot이 파란색이라 Cold로 오해됨.
2024년 Hot(유지·신규)은 빨강 계열, 이탈은 옅은 파랑으로 바꿈. 집계·분류는 원 스크립트 그대로.
"""
import downtown_hot_loss_supplement as m

m.TRANS_COLOR = {
    "그 외": "#ecebe6",
    "Hot 이탈": "#9ecae1",
    "신규 Hot": "#fb8c3c",
    "Hot 유지": "#b2182b",
}
m.MAP_OUT = f"{m.NAS}/new_output/presentation_hot_transition_2021_2024_k20_recolor.png"

if __name__ == "__main__":
    m.main()
