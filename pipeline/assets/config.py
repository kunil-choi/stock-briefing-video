# pipeline/assets/config.py
import os

W, H = 1920, 1080

C = {
    "bg":             (10,  12,  35),
    "gold":           (255, 195,   0),
    "white":          (240, 240, 250),
    "green":          (  0, 230, 118),
    "red":            (255,  61,  87),
    "blue":           ( 41, 182, 246),
    "card":           ( 20,  24,  60),
    "border":         ( 50,  60, 120),
    "tag_bg":         ( 30,  40,  90),
    "hidden_accent":  ( 80,  30, 120),
    "chart_bg":       ( 13,  17,  43),
    "chart_up":       (  0, 230, 118),
    "chart_down":     (255,  61,  87),
    "chart_grid":     ( 30,  40,  80),
    "chart_text":     (160, 160, 200),
}

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT_PATHS = {
    "bold": [
        # 1순위: 프로젝트 내 폰트
        os.path.join(_BASE, "assets", "fonts", "NotoSansKR-Bold.ttf"),
        # 2순위: Ubuntu opentype/noto (fonts-noto-cjk 실제 설치 경로) ← 추가
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf",
        # 3순위: Ubuntu truetype/noto
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        # 4순위: macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NanumGothicBold.ttf",
    ],
    "regular": [
        os.path.join(_BASE, "assets", "fonts", "NotoSansKR-Regular.ttf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",       # ← 추가
        "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NanumGothic.ttf",
    ],
}

STOCK_CODES = {
    "삼성전자":          "005930",
    "SK하이닉스":        "000660",
    "현대차":            "005380",
    "현대로템":          "064350",
    "현대위아":          "011210",
    "신세계":            "004170",
    "두산에너빌리티":    "034020",
    "크래프톤":          "259960",
    "하이브":            "352820",
    "에이피알":          "278470",
    "기아":              "000270",
    "LG에너지솔루션":    "373220",
    "POSCO홀딩스":       "005490",
    "삼성바이오로직스":  "207940",
    "카카오":            "035720",
    "네이버":            "035420",
    "셀트리온":          "068270",
    "한화에어로스페이스":"012450",
}

NEWS_IMAGE_FALLBACKS = {
    "삼성전자":       "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Samsung_Logo.svg/800px-Samsung_Logo.svg.png",
    "SK하이닉스":     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/SK_Hynix_Logo.svg/800px-SK_Hynix_Logo.svg.png",
    "현대차":         "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Hyundai_Motor_Company_logo.svg/800px-Hyundai_Motor_Company_logo.svg.png",
    "현대로템":       "https://www.hyundai-rotem.co.kr/images/common/logo.png",
    "두산에너빌리티": "https://www.doosan.com/images/common/logo_doosan.png",
}
