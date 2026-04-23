# pipeline/assets/config.py
import os

W, H = 1920, 1080

C = {
    "bg":             (10,  12,  35),
    "gold":           (255, 195,  0),
    "white":          (240, 240, 250),
    "green":          (  0, 230, 118),
    "red":            (255,  61,  87),
    "blue":           ( 41, 182, 246),
    "card":           ( 20,  24,  60),
    "border":         ( 50,  60, 120),
    "tag_bg":         ( 30,  40,  90),
    "hidden_accent":  ( 80,  30, 120),
    "chart_bg":       ( 13,  17,  43),
    "chart_up":       (255,  61,  87),   # ← 상승: 빨강 (한국식)
    "chart_down":     ( 41, 130, 220),   # ← 하락: 파랑 (한국식)
    "chart_grid":     ( 30,  40,  80),
    "chart_text":     (160, 160, 200),
}

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT_PATHS = {
    "bold": [
        os.path.join(_BASE, "assets", "fonts", "NotoSansKR-Bold.ttf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NanumGothicBold.ttf",
    ],
    "regular": [
        os.path.join(_BASE, "assets", "fonts", "NotoSansKR-Regular.ttf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NanumGothic.ttf",
    ],
}

# 종목명 → 종목코드 매핑
STOCK_CODES = {
    "삼성전자":        "005930",
    "SK하이닉스":      "000660",
    "현대차":          "005380",
    "현대로템":        "064350",
    "현대위아":        "011210",
    "신세계":          "004170",
    "두산에너빌리티":  "034020",
    "크래프톤":        "259960",
    "하이브":          "352820",
    "에이피알":        "278470",
    "기아":            "000270",
    "LG에너지솔루션":  "373220",
    "POSCO홀딩스":     "005490",
    "삼성바이오로직스":"207940",
    "카카오":          "035720",
    "네이버":          "035420",
    "셀트리온":        "068270",
    "한화에어로스페이스": "012450",
    "HD현대중공업":    "329180",
    "한국항공우주":    "047810",
    "LIG넥스원":       "079550",
    "에코프로비엠":    "247540",
    "포스코퓨처엠":    "003670",
    "삼성SDI":         "006400",
    "현대모비스":      "012330",
    "KB금융":          "105560",
    "신한지주":        "055550",
    "하나금융지주":    "086790",
    "카카오뱅크":      "323410",
    "엔씨소프트":      "036570",
}

# GPT가 다르게 표기할 수 있는 종목명 별칭 → 정규 종목명 매핑
STOCK_NAME_ALIASES = {
    "SK 하이닉스":         "SK하이닉스",
    "SK하이닉스스":        "SK하이닉스",
    "현대 차":             "현대차",
    "현대자동차":          "현대차",
    "두산 에너빌리티":     "두산에너빌리티",
    "두산에너":            "두산에너빌리티",
    "한화 에어로스페이스": "한화에어로스페이스",
    "POSCO 홀딩스":        "POSCO홀딩스",
    "포스코홀딩스":        "POSCO홀딩스",
    "LG 에너지솔루션":     "LG에너지솔루션",
    "LG에너지 솔루션":     "LG에너지솔루션",
    "삼성 전자":           "삼성전자",
    "삼성바이오":          "삼성바이오로직스",
    "카카오 뱅크":         "카카오뱅크",
    "HD 현대중공업":       "HD현대중공업",
    "한국 항공우주":       "한국항공우주",
    "현대 로템":           "현대로템",
    "현대 위아":           "현대위아",
    "에코프로 비엠":       "에코프로비엠",
    "포스코 퓨처엠":       "포스코퓨처엠",
    "현대 모비스":         "현대모비스",
    "신한 지주":           "신한지주",
    "하나 금융지주":       "하나금융지주",
    "하나금융":            "하나금융지주",
    "KB 금융":             "KB금융",
    "엔씨":                "엔씨소프트",
}


def normalize_stock_name(name: str) -> str:
    """GPT 생성 종목명을 STOCK_CODES 키와 일치하도록 정규화"""
    name = name.strip()
    if name in STOCK_NAME_ALIASES:
        return STOCK_NAME_ALIASES[name]
    no_space = name.replace(" ", "")
    if no_space in STOCK_CODES:
        return no_space
    for alias, canonical in STOCK_NAME_ALIASES.items():
        if alias.replace(" ", "") == no_space:
            return canonical
    return name


NEWS_IMAGE_FALLBACKS = {
    "삼성전자":    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Samsung_Logo.svg/800px-Samsung_Logo.svg.png",
    "SK하이닉스":  "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/SK_Hynix_Logo.svg/800px-SK_Hynix_Logo.svg.png",
    "현대차":      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Hyundai_Motor_Company_logo.svg/800px-Hyundai_Motor_Company_logo.svg.png",
    "현대로템":    "https://www.hyundai-rotem.co.kr/images/common/logo.png",
    "두산에너빌리티": "https://www.doosan.com/images/common/logo_doosan.png",
}
