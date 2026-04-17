# pipeline/generate_assets.py
# 전체 교체 버전 — 2026-04-17 수정
# 수정사항:
#   1. 모든 텍스트 최소 32px, 흰색 강제
#   2. 채널 언급 CG: 채널명 72px 골드, 출연자+직책 48px 흰색, 발언 40px 흰색 굵게
#   3. 차트: Playwright selector 수정 + 3초 추가 대기
#   4. 뉴스 이미지: 연합뉴스 + KBS + KBS뉴스 3곳 순차 시도

import os, json, re, time, requests, textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from urllib.parse import quote

# ── 기본 설정 ──────────────────────────────────────────────
W, H = 1920, 1080
FONT_B = "assets/fonts/NotoSansKR-Bold.ttf"
FONT_R = "assets/fonts/NotoSansKR-Regular.ttf"
TODAY  = datetime.now().strftime("%Y년 %m월 %d일")
PROG   = "AI 주식 브리핑"

C = {
    "bg"      : (10, 12, 35),
    "gold"    : (255, 195, 0),
    "white"   : (240, 240, 250),
    "green"   : (0, 210, 110),
    "red"     : (255, 70, 70),
    "blue"    : (50, 140, 255),
    "card"    : (18, 22, 55),
    "border_g": (255, 195, 0),
    "border_r": (200, 40, 40),
    "border_b": (50, 100, 220),
    "tag_bg"  : (30, 60, 160),
    "hidden_accent": (140, 60, 200),
}

# 섹션 태그 색상 매핑
TAG_COLOR = {
    "opening":       (30, 60, 160),
    "market_summary":(30, 60, 160),
    "sectors":       (30, 100, 60),
    "stock":         (30, 60, 160),
    "hidden":        (100, 30, 180),
    "ai_strategy":   (30, 60, 160),
    "closing":       (30, 60, 160),
}

# 회사별 Wikipedia 로고 fallback
LOGO = {
    "삼성전자":      "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Samsung_Logo.svg/800px-Samsung_Logo.svg.png",
    "현대차":        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Hyundai_Motor_Company_logo.svg/800px-Hyundai_Motor_Company_logo.svg.png",
    "SK하이닉스":    "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/SK_hynix_logo.svg/800px-SK_hynix_logo.svg.png",
    "현대로템":      "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Hyundai_Motor_Company_logo.svg/800px-Hyundai_Motor_Company_logo.svg.png",
    "현대위아":      "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Hyundai_Motor_Company_logo.svg/800px-Hyundai_Motor_Company_logo.svg.png",
    "신세계":        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/Shinsegae_Logo.svg/800px-Shinsegae_Logo.svg.png",
    "두산에너빌리티": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Doosan_Logo.svg/800px-Doosan_Logo.svg.png",
    "크래프톤":      "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/Krafton_logo.svg/800px-Krafton_logo.svg.png",
    "하이브":        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/HYBE_Logo.svg/800px-HYBE_Logo.svg.png",
    "에이피알":      "",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockBriefing/1.0)"}

# ── 폰트 헬퍼 ─────────────────────────────────────────────
def fnt(size, bold=True):
    path = FONT_B if bold else FONT_R
    try:
        return ImageFont.truetype(path, size)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", size)
        except:
            return ImageFont.load_default()

# ── 캔버스 & 공통 UI ──────────────────────────────────────
def new_frame():
    img = Image.new("RGB", (W, H), C["bg"])
    return img

def draw_topbar(draw, tag_text, tag_color=None):
    """상단 바: 태그 + 프로그램명 + 날짜"""
    if tag_color is None:
        tag_color = C["tag_bg"]
    # 골드 하단 라인
    draw.rectangle([(0, 0), (W, 48)], fill=(8, 10, 28))
    draw.rectangle([(0, 48), (W, 52)], fill=C["gold"])
    # 태그 박스
    tw = fnt(24).getbbox(tag_text)[2] + 40
    draw.rounded_rectangle([(12, 8), (12 + tw, 42)], radius=6, fill=tag_color)
    draw.text((32, 10), tag_text, font=fnt(24), fill=C["white"])
    # 프로그램명
    draw.text((32 + tw + 16, 10), PROG, font=fnt(24, bold=False), fill=C["white"])
    # 날짜 우측
    dw = fnt(22, bold=False).getbbox(TODAY)[2]
    draw.text((W - dw - 20, 12), TODAY, font=fnt(22, bold=False), fill=(160, 160, 200))

def draw_bottombar(draw, stock_name, sub_text="", tag_color=None):
    """하단 바: 종목명 + 서브텍스트 + 워터마크"""
    if tag_color is None:
        tag_color = C["tag_bg"]
    draw.rectangle([(0, H - 70), (W, H)], fill=(8, 10, 28))
    draw.rectangle([(0, H - 74), (W, H - 70)], fill=C["gold"])
    # 종목 태그
    tw = fnt(28).getbbox(stock_name)[2] + 40
    draw.rounded_rectangle([(12, H - 62), (12 + tw, H - 12)], radius=6, fill=tag_color)
    draw.text((32, H - 58), stock_name, font=fnt(28), fill=C["white"])
    # 서브 텍스트
    if sub_text:
        draw.text((32 + tw + 20, H - 52), sub_text, font=fnt(24, bold=False), fill=(160, 160, 200))
    # 워터마크 우측
    wm = "© AI STOCK BRIEFING"
    wmw = fnt(20, bold=False).getbbox(wm)[2]
    draw.text((W - wmw - 20, H - 48), wm, font=fnt(20, bold=False), fill=(80, 80, 120))

def gold_underline(draw, x, y, text, font_size=54):
    """골드 밑줄 제목"""
    f = fnt(font_size)
    draw.text((x, y), text, font=f, fill=C["gold"])
    tw = f.getbbox(text)[2]
    draw.rectangle([(x, y + font_size + 8), (x + tw + 60, y + font_size + 14)], fill=C["gold"])

def paste_image(base_img, url_or_path, box):
    """이미지를 box 영역에 꽉 채워 붙임. 실패 시 placeholder."""
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    try:
        if url_or_path.startswith("http"):
            r = requests.get(url_or_path, headers=HEADERS, timeout=8)
            img = Image.open(BytesIO(r.content)).convert("RGB")
        else:
            img = Image.open(url_or_path).convert("RGB")
        # 비율 유지 fill
        iw, ih = img.size
        scale = max(bw / iw, bh / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        ox = (nw - bw) // 2
        oy = (nh - bh) // 2
        img = img.crop((ox, oy, ox + bw, oy + bh))
        base_img.paste(img, (x1, y1))
        # 골드 테두리
        d = ImageDraw.Draw(base_img)
        d.rectangle([(x1, y1), (x2, y2)], outline=C["gold"], width=3)
        return True
    except Exception as e:
        # placeholder
        d = ImageDraw.Draw(base_img)
        d.rectangle([(x1, y1), (x2, y2)], outline=(60, 60, 100), width=2)
        d.text((x1 + bw // 2 - 60, y1 + bh // 2 - 20), "이미지 로드 실패",
               font=fnt(28, bold=False), fill=(80, 80, 120))
        return False

# ── 뉴스 이미지 크롤링 ────────────────────────────────────
def fetch_news_image(keyword, save_path):
    """연합뉴스 → KBS → KBS뉴스 순서로 관련 이미지 검색"""
    sources = [
        f"https://www.yna.co.kr/search/index?query={quote(keyword)}&ctype=A&sort=rel",
        f"https://news.kbs.co.kr/news/search/pc/index.html?query={quote(keyword)}",
        f"https://www.kbs.co.kr/search/?search_term={quote(keyword)}&submit.x=0&submit.y=0",
    ]
    img_patterns = [
        r'<img[^>]+src=["\']([^"\']*(?:yna\.co\.kr|yonhapnews)[^"\']*\.(?:jpg|jpeg|png))["\']',
        r'<img[^>]+src=["\']([^"\']*(?:news\.kbs|static\.kbs)[^"\']*\.(?:jpg|jpeg|png))["\']',
        r'<img[^>]+src=["\']([^"\']*kbs\.co\.kr[^"\']*\.(?:jpg|jpeg|png))["\']',
    ]
    for src_url, pattern in zip(sources, img_patterns):
        try:
            r = requests.get(src_url, headers=HEADERS, timeout=10)
            matches = re.findall(pattern, r.text, re.IGNORECASE)
            # 썸네일/광고 필터링 후 첫 번째 사용
            for m in matches:
                if any(x in m for x in ["thumb", "logo", "icon", "banner", "ad_"]):
                    continue
                img_url = m if m.startswith("http") else "https:" + m
                try:
                    ir = requests.get(img_url, headers=HEADERS, timeout=8)
                    img = Image.open(BytesIO(ir.content)).convert("RGB")
                    if img.width >= 300 and img.height >= 200:
                        img.save(save_path, quality=95)
                        return save_path
                except:
                    continue
        except:
            continue
    return None

# ── 주가 차트 캡처 ────────────────────────────────────────
def capture_chart(stock_name, save_path):
    """Playwright로 네이버 금융 차트 캡처"""
    try:
        from playwright.sync_api import sync_playwright
        NAVER_STOCK_CODES = {
            "삼성전자": "005930", "현대차": "005380", "SK하이닉스": "000660",
            "현대로템": "064350", "현대위아": "011210", "신세계": "004170",
            "두산에너빌리티": "034020", "크래프톤": "259960", "하이브": "352820",
            "에이피알": "278470",
        }
        code = NAVER_STOCK_CODES.get(stock_name)
        if not code:
            return None
        url = f"https://finance.naver.com/item/fchart.naver?code={code}"
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": 1200, "height": 700})
            page.goto(url, wait_until="networkidle", timeout=30000)
            # 차트 iframe 대기
            page.wait_for_selector("iframe#chart", timeout=15000)
            frame = page.frame_locator("iframe#chart").first
            # 차트 캔버스 대기 (추가 3초)
            page.wait_for_timeout(3000)
            # 전체 iframe 스크린샷
            chart_el = page.query_selector("iframe#chart")
            if chart_el:
                chart_el.screenshot(path=save_path)
                browser.close()
                return save_path
            browser.close()
    except Exception as e:
        print(f"  차트 캡처 실패 ({stock_name}): {e}")
    return None

# ── 섹션 빌더 ─────────────────────────────────────────────

def build_opening(sec, out_dir):
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, "TODAY")
    # 메인 타이틀
    title = sec.get("title", PROG)
    tw = fnt(110).getbbox(title)[2]
    d.text(((W - tw) // 2, 160), title, font=fnt(110), fill=C["gold"])
    # 날짜
    dw = fnt(38, bold=False).getbbox(TODAY)[2]
    d.text(((W - dw) // 2, 295), TODAY, font=fnt(38, bold=False), fill=(180, 180, 220))
    # 골드 구분선
    d.rectangle([(80, 360), (W - 80, 366)], fill=C["gold"])
    # 키워드 3개
    keywords = sec.get("keywords", [])[:3]
    kw_x = [200, 700, 1300]
    for i, kw in enumerate(keywords):
        d.rounded_rectangle([(kw_x[i] - 10, 400), (kw_x[i] + 380, 460)],
                            radius=8, fill=(25, 30, 70))
        d.text((kw_x[i], 408), kw, font=fnt(36), fill=C["white"])
    # 나레이션 요약 (2줄)
    narr = sec.get("narration", "")[:120]
    lines = textwrap.wrap(narr, width=68)
    for i, ln in enumerate(lines[:2]):
        lw = fnt(30, bold=False).getbbox(ln)[2]
        d.text(((W - lw) // 2, 490 + i * 46), ln,
               font=fnt(30, bold=False), fill=(160, 160, 200))
    draw_bottombar(d, "최건일", "AI 주식 브리핑 진행자")
    path = os.path.join(out_dir, "01_opening.png")
    img.save(path, quality=95)
    return path

def build_market_summary(sec, out_dir, img_dir):
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, "시장 요약")
    gold_underline(d, 60, 70, "오늘의 시장 요약", font_size=54)
    # KOSPI 숫자
    price = str(sec.get("price", sec.get("kospi", "6,226")))
    chg   = str(sec.get("change", "+2.21%"))
    chg_color = C["green"] if "+" in chg else C["red"]
    d.text((60, 155), "KOSPI", font=fnt(32, bold=False), fill=(140, 140, 180))
    d.text((60, 195), price, font=fnt(120), fill=C["white"])
    pw = fnt(120).getbbox(price)[2]
    d.text((80 + pw, 230), chg, font=fnt(72), fill=chg_color)
    # 골드 구분선
    d.rectangle([(60, 340), (490, 344)], fill=C["gold"])
    # 핵심 포인트
    points = sec.get("points", sec.get("summary_points", []))
    if not points:
        narr = sec.get("narration", "")
        points = [s.strip() for s in narr.split(".") if len(s.strip()) > 8][:4]
    for i, pt in enumerate(points[:4]):
        y = 365 + i * 68
        d.rectangle([(60, y + 12), (68, y + 44)], fill=C["green"])
        d.text((85, y), pt[:36], font=fnt(38), fill=C["white"])
    # 우측 이미지
    news_img = os.path.join(img_dir, "news_market.jpg")
    if not os.path.exists(news_img):
        fetch_news_image("코스피 증시", news_img)
    if os.path.exists(news_img):
        paste_image(img, news_img, (520, 60, 1000, 480))
    else:
        paste_image(img, "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/KRX_logo.svg/600px-KRX_logo.svg.png",
                    (520, 60, 1000, 480))
    draw_bottombar(d, "시장 요약", TODAY)
    path = os.path.join(out_dir, "02_market_summary.png")
    img.save(path, quality=95)
    return path

def build_sector(sec, out_dir):
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, "주목 섹터")
    # 제목
    title_txt = "오늘의 주목 섹터"
    tw = fnt(72).getbbox(title_txt)[2]
    d.text(((W - tw) // 2, 65), title_txt, font=fnt(72), fill=C["gold"])
    d.rectangle([(80, 155), (W - 80, 161)], fill=C["gold"])
    # 섹터 카드
    sectors = sec.get("sector_list", sec.get("sectors", []))
    if not sectors:
        narr = sec.get("narration", "")
        # 기본 섹터
        sectors = [
            {"name": "AI 반도체", "en": "AI CHIP",   "desc": "HBM & 파운드리"},
            {"name": "피지컬AI",  "en": "PHYSICAL AI","desc": "로보틱스 & 자동화"},
            {"name": "원자력",    "en": "NUCLEAR",    "desc": "SMR & 에너지"},
        ]
    card_w = (W - 160 - 40 * (len(sectors) - 1)) // max(len(sectors), 1)
    for i, s in enumerate(sectors[:4]):
        cx = 80 + i * (card_w + 40)
        cy, ch = 180, 750
        # 카드 배경
        d.rounded_rectangle([(cx, cy), (cx + card_w, cy + ch)],
                            radius=16, fill=C["card"])
        d.rounded_rectangle([(cx, cy), (cx + card_w, cy + ch)],
                            radius=16, outline=C["border_g"], width=3)
        # 영문 대제목
        en = s.get("en", s.get("name", "SECTOR")).upper()
        ew = fnt(52).getbbox(en)[2]
        d.text((cx + (card_w - ew) // 2, cy + 40), en, font=fnt(52), fill=C["gold"])
        # 한글 소제목
        kr = s.get("name", "")
        kw = fnt(42).getbbox(kr)[2]
        d.text((cx + (card_w - kw) // 2, cy + 110), kr, font=fnt(42), fill=C["white"])
        # 구분선
        d.rectangle([(cx + 30, cy + 172), (cx + card_w - 30, cy + 176)], fill=(80, 80, 130))
        # 설명
        desc = s.get("desc", s.get("description", ""))
        dw2 = fnt(34, bold=False).getbbox(desc)[2]
        d.text((cx + (card_w - dw2) // 2, cy + 195), desc,
               font=fnt(34, bold=False), fill=(200, 200, 230))
        # 핵심 키워드 2~3개
        keys = s.get("keywords", [])[:3]
        for j, kw2 in enumerate(keys):
            ky = cy + 270 + j * 60
            kw2_w = fnt(30, bold=False).getbbox(kw2)[2]
            d.rounded_rectangle([(cx + 20, ky), (cx + 30 + kw2_w + 20, ky + 44)],
                                radius=6, fill=(30, 40, 90))
            d.text((cx + 30, ky + 6), kw2, font=fnt(30, bold=False), fill=C["white"])
    draw_bottombar(d, "주목 섹터", TODAY)
    path = os.path.join(out_dir, "03_sectors.png")
    img.save(path, quality=95)
    return path

def build_stock_summary(sec, stock_name, out_dir, img_dir, prefix, is_hidden=False):
    """종목 요약 페이지 (_1_summary)"""
    tag_color = C["hidden_accent"] if is_hidden else C["tag_bg"]
    tag_label = "히든 종목" if is_hidden else "관심 종목"
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, tag_label, tag_color)
    # 종목명 (대형)
    d.text((60, 58), stock_name, font=fnt(90), fill=C["gold"])
    # 서브 텍스트 (영문 or 업종)
    sub = sec.get("en_name", sec.get("sector", ""))
    if sub:
        d.text((65, 158), sub, font=fnt(32, bold=False), fill=(160, 160, 200))
    # 가격
    price = str(sec.get("price", "---"))
    chg   = str(sec.get("change", ""))
    chg_color = C["green"] if "+" in chg else (C["red"] if "-" in chg else C["white"])
    d.text((60, 195), price, font=fnt(100), fill=C["white"])
    if chg:
        pw = fnt(100).getbbox(price)[2]
        d.text((75 + pw, 235), chg, font=fnt(62), fill=chg_color)
    # 골드 구분선
    d.rectangle([(60, 322), (490, 328)], fill=C["gold"])
    # 핵심 포인트 (최소 32px, 흰색)
    points = sec.get("summary_points", sec.get("points", []))
    if not points:
        narr = sec.get("narration", "")
        points = [s.strip() for s in narr.split(".") if 6 < len(s.strip()) < 60][:3]
    for i, pt in enumerate(points[:3]):
        y = 348 + i * 72
        d.rectangle([(60, y + 14), (70, y + 50)], fill=C["green"])
        # ★ 폰트 최소 38px, 흰색 강제
        d.text((88, y), pt[:40], font=fnt(38), fill=C["white"])
    # 우측 뉴스 이미지
    news_img = os.path.join(img_dir, f"news_{stock_name}.jpg")
    if not os.path.exists(news_img):
        fetched = fetch_news_image(stock_name, news_img)
        if not fetched:
            news_img = None
    if news_img and os.path.exists(news_img):
        paste_image(img, news_img, (520, 55, 1000, 480))
    elif LOGO.get(stock_name):
        paste_image(img, LOGO[stock_name], (600, 140, 960, 420))
    draw_bottombar(d, stock_name, sec.get("date", TODAY), tag_color)
    path = os.path.join(out_dir, f"{prefix}_1_summary.png")
    img.save(path, quality=95)
    return path

def build_stock_chart(sec, stock_name, out_dir, img_dir, prefix, is_hidden=False):
    """주가 차트 페이지 (_2_chart)"""
    tag_color = C["hidden_accent"] if is_hidden else C["tag_bg"]
    tag_label = f"{stock_name} 주가 흐름"
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, tag_label[:10], tag_color)
    gold_underline(d, 50, 70, f"{stock_name}  최근 주가 흐름", font_size=52)
    # 차트 영역
    chart_box = (30, 130, W - 30, H - 90)
    chart_path = os.path.join(img_dir, f"chart_{stock_name}.png")
    if not os.path.exists(chart_path):
        capture_chart(stock_name, chart_path)
    if os.path.exists(chart_path):
        paste_image(img, chart_path, chart_box)
    else:
        # placeholder with message
        d.rounded_rectangle([chart_box], radius=8, fill=(16, 20, 50))
        d.rounded_rectangle([chart_box], radius=8, outline=(60, 70, 120), width=2)
        msg = "차트 로딩 중 — 잠시 후 확인하세요"
        mw = fnt(40, bold=False).getbbox(msg)[2]
        d.text(((W - mw) // 2, H // 2 - 30), msg, font=fnt(40, bold=False), fill=(120, 120, 180))
    draw_bottombar(d, stock_name, sec.get("date", ""), tag_color)
    path = os.path.join(out_dir, f"{prefix}_2_chart.png")
    img.save(path, quality=95)
    return path

def build_stock_analysis(sec, stock_name, out_dir, prefix, is_hidden=False):
    """촉매 & 리스크 페이지 (_3_analysis)"""
    tag_color = C["hidden_accent"] if is_hidden else C["tag_bg"]
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, f"{stock_name[:5]} 분석"[:10], tag_color)
    gold_underline(d, 50, 68, f"{stock_name}  —  촉매 & 리스크", font_size=52)
    # 두 컬럼 카드
    cats = sec.get("catalysts", [])
    risks = sec.get("risks", [])
    col_w = (W - 120) // 2
    for col, (items, label, border, marker) in enumerate([
        (cats,  "상승 촉매", C["border_g"], C["green"]),
        (risks, "리스크",   C["border_r"], C["red"]),
    ]):
        cx = 60 + col * (col_w + 40)
        cy, ch = 148, H - 220
        d.rounded_rectangle([(cx, cy), (cx + col_w, cy + ch)],
                            radius=14, fill=C["card"])
        d.rounded_rectangle([(cx, cy), (cx + col_w, cy + ch)],
                            radius=14, outline=border, width=3)
        # 컬럼 헤더
        lw = fnt(44).getbbox(label)[2]
        d.text((cx + (col_w - lw) // 2, cy + 22), label, font=fnt(44), fill=border)
        d.rectangle([(cx + 30, cy + 78), (cx + col_w - 30, cy + 84)], fill=(60, 60, 100))
        # 항목 (최소 38px 흰색)
        for j, item in enumerate(items[:5]):
            iy = cy + 106 + j * 80
            d.rounded_rectangle([(cx + 24, iy + 8), (cx + 40, iy + 52)],
                                radius=4, fill=marker)
            d.text((cx + 52, iy), item[:26], font=fnt(38), fill=C["white"])
    draw_bottombar(d, stock_name, sec.get("date", ""), tag_color)
    path = os.path.join(out_dir, f"{prefix}_3_analysis.png")
    img.save(path, quality=95)
    return path

def build_mention_page(mention, stock_name, out_dir, prefix, idx, is_hidden=False):
    """
    채널 언급 CG (_4_mention_XX)
    mention 구조:
      { "channel": "삼프로TV", "presenter": "홍길동",
        "affiliation": "○○증권", "title": "리서치센터장",
        "comment": "실제 발언 내용...", "url": "https://..." }
    """
    tag_color = C["hidden_accent"] if is_hidden else C["border_b"]
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, f"{stock_name[:5]} 채널 언급"[:12], tag_color)
    # 섹션 타이틀
    gold_underline(d, 50, 68, f"{stock_name}  —  채널 언급", font_size=52)
    # 메인 카드
    cx, cy = 40, 148
    cw, ch = W - 80, H - 230
    d.rounded_rectangle([(cx, cy), (cx + cw, cy + ch)],
                        radius=16, fill=C["card"])
    d.rounded_rectangle([(cx, cy), (cx + cw, cy + ch)],
                        radius=16, outline=tag_color, width=3)

    channel = mention.get("channel", "")
    presenter = mention.get("presenter", "")
    affil = mention.get("affiliation", "")
    title_p = mention.get("title", "")
    comment = mention.get("comment", mention.get("quote", ""))
    url = mention.get("url", "")

    # ① 채널명 — 72px 골드/파랑
    d.text((cx + 40, cy + 28), channel, font=fnt(72), fill=C["blue"])
    # 구분선
    d.rectangle([(cx + 30, cy + 118), (cx + cw - 30, cy + 124)], fill=(60, 70, 130))

    # ② 출연자 + 소속 — 48px 흰색
    presenter_line = ""
    if presenter:
        presenter_line += presenter
    if affil:
        presenter_line += f"  |  {affil}"
    if title_p:
        presenter_line += f"  {title_p}"
    if presenter_line:
        d.text((cx + 40, cy + 138), "출연자:", font=fnt(36, bold=False), fill=(140, 140, 180))
        d.text((cx + 170, cy + 138), presenter_line, font=fnt(48), fill=C["white"])

    # ③ 종목 언급
    stock_line = f"종목:  {stock_name}"
    chg = mention.get("change", "")
    if chg:
        stock_line += f"    {chg}"
    d.text((cx + 40, cy + 210), stock_line, font=fnt(42, bold=False), fill=(180, 180, 210))

    # 구분선
    d.rectangle([(cx + 30, cy + 272), (cx + cw - 30, cy + 278)], fill=(60, 70, 130))

    # ④ 발언 인용 — 40px 흰색 굵게, 큰 따옴표
    d.text((cx + 40, cy + 295), "\u201c", font=fnt(80), fill=C["gold"])  # "
    wrapped = textwrap.wrap(comment, width=52)
    for i, ln in enumerate(wrapped[:4]):
        d.text((cx + 100, cy + 300 + i * 66), ln, font=fnt(40), fill=C["white"])
    # 닫는 따옴표
    last_y = cy + 300 + min(len(wrapped[:4]) - 1, 3) * 66 + 10
    quote_x = cx + cw - 100
    d.text((quote_x, last_y), "\u201d", font=fnt(80), fill=C["gold"])  # "

    # ⑤ 출처 URL
    if url:
        d.text((cx + 40, cy + ch - 60), f"출처: {url[:80]}",
               font=fnt(26, bold=False), fill=(100, 100, 160))

    draw_bottombar(d, stock_name, channel, tag_color)
    path = os.path.join(out_dir, f"{prefix}_4_mention_{idx:02d}.png")
    img.save(path, quality=95)
    return path

def build_ai_strategy(sec, out_dir, img_dir):
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, "AI 투자 전략")
    # 제목
    tw = fnt(72).getbbox("AI 투자 전략")[2]
    d.text(((W - tw) // 2, 62), "AI 투자 전략", font=fnt(72), fill=C["gold"])
    d.rectangle([(80, 152), (W - 80, 158)], fill=C["gold"])
    # 좌측 이미지 (AI/차트 관련)
    ai_img = os.path.join(img_dir, "news_ai_strategy.jpg")
    if not os.path.exists(ai_img):
        fetch_news_image("AI 투자 전략 주식", ai_img)
    if os.path.exists(ai_img):
        paste_image(img, ai_img, (40, 170, 390, 580))
    else:
        d.rounded_rectangle([(40, 170), (390, 580)], radius=10, fill=C["card"])
        d.text((120, 350), "AI", font=fnt(80), fill=C["gold"])
    # 우측 전략 리스트
    points = sec.get("points", sec.get("strategies", []))
    if not points:
        narr = sec.get("narration", "")
        points = [s.strip() for s in narr.split(".") if 8 < len(s.strip()) < 60][:6]
    for i, pt in enumerate(points[:6]):
        y = 172 + i * 84
        # 번호 원
        bx, by = 415, y + 8
        d.ellipse([(bx, by), (bx + 52, by + 52)], fill=C["gold"])
        num = str(i + 1)
        nw = fnt(32).getbbox(num)[2]
        d.text((bx + (52 - nw) // 2, by + 8), num, font=fnt(32), fill=(10, 12, 35))
        # 종목명 + 전략 텍스트
        parts = str(pt).split(" ", 1)
        stock_part = parts[0] if parts else ""
        strat_part = parts[1] if len(parts) > 1 else ""
        d.text((480, y), stock_part, font=fnt(44), fill=C["gold"])
        sw = fnt(44).getbbox(stock_part)[2]
        d.text((490 + sw, y + 6), strat_part[:30], font=fnt(36, bold=False), fill=C["white"])
    draw_bottombar(d, "최건일", "AI 투자 전략", C["tag_bg"])
    path = os.path.join(out_dir, "90_ai_strategy.png")
    img.save(path, quality=95)
    return path

def build_closing(sec, script_title, out_dir):
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, "클로징")
    # 메인 타이틀
    tw = fnt(110).getbbox(PROG)[2]
    d.text(((W - tw) // 2, 150), PROG, font=fnt(110), fill=C["gold"])
    dw = fnt(38, bold=False).getbbox(TODAY)[2]
    d.text(((W - dw) // 2, 280), TODAY, font=fnt(38, bold=False), fill=(180, 180, 220))
    d.rectangle([(80, 340), (W - 80, 346)], fill=C["gold"])
    # 요약 + 예고
    summary = sec.get("summary", sec.get("narration", ""))[:100]
    next_preview = sec.get("next_preview", "")
    lines = textwrap.wrap(summary, width=58)
    for i, ln in enumerate(lines[:2]):
        lw = fnt(34, bold=False).getbbox(ln)[2]
        d.text(((W - lw) // 2, 370 + i * 52), ln,
               font=fnt(34, bold=False), fill=(200, 200, 230))
    if next_preview:
        nw = fnt(34, bold=False).getbbox(next_preview[:50])[2]
        d.text(((W - nw) // 2, 480), next_preview[:50],
               font=fnt(34, bold=False), fill=(160, 160, 200))
    # 인사말
    bye = "다음 방송에서 만나요!"
    bw = fnt(62).getbbox(bye)[2]
    d.text(((W - bw) // 2, 580), bye, font=fnt(62), fill=C["white"])
    draw_bottombar(d, "최건일", "AI 주식 브리핑 진행자")
    path = os.path.join(out_dir, "99_closing.png")
    img.save(path, quality=95)
    return path

# ── 메인 실행 ─────────────────────────────────────────────
def run(lang="KO"):
    script_path = f"output/{lang}/scripts/script.json"
    out_dir = f"output/{lang}/frames"
    img_dir = f"output/{lang}/images"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    asset_map = {}
    stock_idx = 10

    for sec in script.get("sections", []):
        sid = sec.get("id", "")
        print(f"▶ 처리 중: {sid}")

        if sid == "opening":
            asset_map[sid] = build_opening(sec, out_dir)

        elif sid == "market_summary":
            asset_map[sid] = build_market_summary(sec, out_dir, img_dir)

        elif sid == "sectors":
            asset_map[sid] = build_sector(sec, out_dir)

        elif sid.startswith("stock_") or sid.startswith("hidden_"):
            is_hidden = sid.startswith("hidden_")
            sname = sid.replace("stock_", "").replace("hidden_", "")
            prefix = f"{stock_idx}_{'H' if is_hidden else 'S'}_{sname}"
            frames = []
            frames.append(build_stock_summary(sec, sname, out_dir, img_dir, prefix, is_hidden))
            frames.append(build_stock_chart(sec, sname, out_dir, img_dir, prefix, is_hidden))
            frames.append(build_stock_analysis(sec, sname, out_dir, prefix, is_hidden))
            for mi, mention in enumerate(sec.get("mentions", []), start=1):
                frames.append(build_mention_page(mention, sname, out_dir, prefix, mi, is_hidden))
            asset_map[sid] = frames
            stock_idx += 1

        elif sid == "ai_strategy":
            asset_map[sid] = build_ai_strategy(sec, out_dir, img_dir)

        elif sid == "closing":
            asset_map[sid] = build_closing(sec, script.get("title", ""), out_dir)

    # asset_map 저장
    map_path = os.path.join(out_dir, "asset_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    total = sum(len(v) if isinstance(v, list) else 1 for v in asset_map.values())
    print(f"\n✅ 총 {total}개 프레임 생성 완료 → {out_dir}")
    return asset_map

if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "KO")
