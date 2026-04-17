import os
import json
import time
import textwrap
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

# ── 기본 설정 ──────────────────────────────────────────
W, H = 1920, 1080
FONT_PATH = "assets/fonts/NotoSansKR-Bold.ttf"
FONT_PATH_REG = "assets/fonts/NotoSansKR-Regular.ttf"

C = {
    "bg":       (10, 12, 25),
    "bg2":      (18, 22, 45),
    "gold":     (255, 195, 0),
    "white":    (235, 235, 245),
    "subtext":  (160, 165, 185),
    "green":    (0, 210, 120),
    "red":      (255, 75, 75),
    "blue":     (50, 140, 255),
    "purple":   (160, 50, 200),
    "name_bg":  (255, 255, 255),
    "name_txt": (20, 20, 30),
    "tag_red":  (180, 0, 0),
    "tag_blue": (0, 80, 200),
}

TODAY = datetime.now().strftime("%Y년 %m월 %d일")
PROGRAM = "AI 주식 브리핑"
WATERMARK = "AI STOCK BRIEFING"

STOCK_CODE_MAP = {
    "삼성전자": "005930", "SK하이닉스": "000660", "현대차": "005380",
    "현대로템": "064350", "현대위아": "011210", "신세계": "004170",
    "두산에너빌리티": "034020", "크래프톤": "259960", "하이브": "352820",
    "에이피알": "278470",
}

YONHAP_KEYWORDS = {
    "삼성전자": "삼성전자 반도체",
    "SK하이닉스": "SK하이닉스 HBM",
    "현대차": "현대차 로보틱스",
    "현대로템": "현대로템 방산",
    "현대위아": "현대위아 로보틱스",
    "신세계": "신세계 면세점 관광",
    "두산에너빌리티": "두산에너빌리티 원전",
    "크래프톤": "크래프톤 PUBG",
    "하이브": "하이브 BTS",
    "에이피알": "에이피알 K뷰티",
    "시장요약": "코스피 증시 반등",
    "AI반도체": "AI 반도체 엔비디아",
    "피지컬AI": "로봇 피지컬AI 휴머노이드",
    "원자력": "원자력 SMR 원전",
}


# ── 폰트 ──────────────────────────────────────────────
def font(size, bold=True):
    path = FONT_PATH if bold else FONT_PATH_REG
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


# ── 기본 프레임 ───────────────────────────────────────
def new_frame():
    img = Image.new("RGB", (W, H), C["bg"])
    draw = ImageDraw.Draw(img)
    for y in range(300):
        alpha = int(8 * (1 - y / 300))
        r = min(255, C["bg"][0] + alpha)
        g = min(255, C["bg"][1] + alpha)
        b = min(255, C["bg"][2] + alpha + 5)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def draw_top_bar(img, tag_text="TODAY", tag_color=None, program=PROGRAM, date=TODAY):
    draw = ImageDraw.Draw(img)
    tag_color = tag_color or C["tag_blue"]
    draw.rectangle([(0, 0), (W, 72)], fill=C["bg2"])
    draw.line([(0, 72), (W, 72)], fill=C["gold"], width=2)
    f22 = font(22)
    tw = int(f22.getlength(tag_text)) + 28
    draw.rounded_rectangle([(20, 18), (20 + tw, 54)], radius=5, fill=tag_color)
    draw.text((20 + 14, 36), tag_text, font=f22, fill=C["white"], anchor="lm")
    draw.text((20 + tw + 18, 36), program, font=font(28), fill=C["white"], anchor="lm")
    draw.text((W - 30, 36), date, font=font(22, bold=False), fill=C["subtext"], anchor="rm")
    return img


def draw_bottom_strip(img, name, title="", org=""):
    draw = ImageDraw.Draw(img)
    strip_y = H - 130
    strip_h = 85
    base_crop = img.crop((0, strip_y, W, strip_y + strip_h)).convert("RGBA")
    overlay = Image.new("RGBA", (W, strip_h), (15, 18, 40, 220))
    merged = Image.alpha_composite(base_crop, overlay).convert("RGB")
    img.paste(merged, (0, strip_y))
    draw = ImageDraw.Draw(img)
    draw.line([(0, strip_y), (W, strip_y)], fill=C["gold"], width=2)
    f30 = font(30)
    name_w = int(f30.getlength(name)) + 36
    draw.rectangle([(40, strip_y + 16), (40 + name_w, strip_y + strip_h - 16)], fill=C["name_bg"])
    draw.text((40 + 18, strip_y + strip_h // 2), name, font=f30, fill=C["name_txt"], anchor="lm")
    if title or org:
        info = f"{title}  {org}".strip()
        draw.text((40 + name_w + 24, strip_y + strip_h // 2), info,
                  font=font(24, bold=False), fill=C["subtext"], anchor="lm")
    draw.text((W - 30, strip_y + strip_h // 2), WATERMARK,
              font=font(20, bold=False), fill=(80, 85, 110), anchor="rm")
    return img


def draw_divider(img, y, color=None, width=2):
    draw = ImageDraw.Draw(img)
    draw.line([(60, y), (W - 60, y)], fill=color or C["gold"], width=width)
    return img


# ── 연합뉴스 이미지 크롤링 ────────────────────────────
def fetch_yonhap_image(keyword, save_path):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            url = f"https://www.yna.co.kr/search/index?query={requests.utils.quote(keyword)}&ctype=A"
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)

            # 여러 셀렉터 시도
            selectors = [
                ".news-list li img",
                ".list-type038 li img",
                "article img",
                ".img-con img",
                ".thumb img",
                "figure img",
            ]
            src = None
            for sel in selectors:
                els = page.query_selector_all(sel)
                for el in els:
                    s = el.get_attribute("src") or el.get_attribute("data-src")
                    if s and ("yonhapnews" in s or "yna.co.kr" in s or s.startswith("http")):
                        if not s.endswith(".gif") and "logo" not in s.lower():
                            src = s
                            break
                if src:
                    break

            browser.close()

            if not src:
                print(f"⚠️ 연합뉴스 이미지 없음: {keyword}")
                return None

            if src.startswith("//"):
                src = "https:" + src

            r = requests.get(src, timeout=15,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(r.content)
                print(f"✅ 연합뉴스 이미지 저장: {keyword}")
                return save_path
    except Exception as e:
        print(f"⚠️ 이미지 크롤링 실패 ({keyword}): {e}")
    return None


# ── 네이버 금융 차트 캡처 ─────────────────────────────
def capture_naver_chart(stock_name, save_path):
    code = STOCK_CODE_MAP.get(stock_name)
    if not code:
        print(f"⚠️ 종목코드 없음: {stock_name}")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1200, "height": 700})
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            page.goto(url, wait_until="networkidle", timeout=20000)
            time.sleep(3)

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 차트 영역 시도
            chart_selectors = ["#chartArea", ".chart_area", "#stockChart", ".aside_chart"]
            captured = False
            for sel in chart_selectors:
                el = page.query_selector(sel)
                if el:
                    el.screenshot(path=save_path)
                    captured = True
                    break

            if not captured:
                page.screenshot(path=save_path,
                                clip={"x": 10, "y": 180, "width": 1180, "height": 420})

            browser.close()
            print(f"✅ 차트 캡처: {stock_name}")
            return save_path
    except Exception as e:
        print(f"⚠️ 차트 캡처 실패 ({stock_name}): {e}")
    return None


# ── 이미지를 프레임에 합성 ────────────────────────────
def paste_image_to_frame(img, image_path, x, y, w, h):
    """이미지를 지정 영역에 크롭/리사이즈해서 붙여넣기"""
    try:
        photo = Image.open(image_path).convert("RGB")
        # 비율 유지 리사이즈 (cover 방식)
        photo_ratio = photo.width / photo.height
        target_ratio = w / h
        if photo_ratio > target_ratio:
            new_h = h
            new_w = int(h * photo_ratio)
        else:
            new_w = w
            new_h = int(w / photo_ratio)
        photo = photo.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        photo = photo.crop((left, top, left + w, top + h))

        # 테두리 효과
        border_img = Image.new("RGB", (w + 4, h + 4), C["gold"])
        border_img.paste(photo, (2, 2))
        img.paste(border_img, (x - 2, y - 2))
        return True
    except Exception as e:
        print(f"⚠️ 이미지 합성 실패: {e}")
        return False


def draw_placeholder(img, x, y, w, h, label, sub=""):
    draw = ImageDraw.Draw(img)
    draw.rectangle([(x, y), (x + w, y + h)], fill=(25, 30, 60),
                   outline=(80, 90, 140), width=2)
    draw.line([(x, y), (x + w, y + h)], fill=(40, 45, 80), width=1)
    draw.line([(x + w, y), (x, y + h)], fill=(40, 45, 80), width=1)
    draw.text((x + w // 2, y + h // 2 - 18), label,
              font=font(26, bold=False), fill=(100, 110, 160), anchor="mm")
    if sub:
        draw.text((x + w // 2, y + h // 2 + 22), sub,
                  font=font(20, bold=False), fill=(70, 80, 120), anchor="mm")


# ══════════════════════════════════════════════════════
# 섹션별 프레임 빌더
# ══════════════════════════════════════════════════════

def build_opening(section, out_dir):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="TODAY", tag_color=C["tag_blue"])

    draw.text((W // 2, 240), PROGRAM, font=font(100), fill=C["gold"], anchor="mm")
    draw.text((W // 2, 355), TODAY, font=font(38, bold=False), fill=C["subtext"], anchor="mm")
    img = draw_divider(img, 415)

    keywords = section.get("keywords", ["코스피 회복", "주도 섹터", "관심 종목"])[:3]
    box_w, box_h = 480, 100
    gap = 60
    total_w = box_w * 3 + gap * 2
    sx = (W - total_w) // 2
    for i, kw in enumerate(keywords):
        bx = sx + i * (box_w + gap)
        by = 455
        draw.rounded_rectangle([(bx, by), (bx + box_w, by + box_h)],
                                radius=12, fill=C["bg2"], outline=C["gold"], width=2)
        draw.text((bx + box_w // 2, by + box_h // 2), kw,
                  font=font(32), fill=C["white"], anchor="mm")

    # 내레이션 첫 문장 표시
    narr = section.get("narration", "")
    first_sentence = narr.split("。")[0].split("!")[0][:60]
    draw.text((W // 2, 640), first_sentence,
              font=font(30, bold=False), fill=C["subtext"], anchor="mm")

    img = draw_bottom_strip(img, "최건일", "진행자", PROGRAM)
    path = os.path.join(out_dir, "01_opening.png")
    img.save(path)
    print(f"✅ 오프닝: {path}")
    return path


def build_market_summary(section, out_dir, img_dir):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="시장 요약", tag_color=C["tag_red"])

    draw.text((80, 100), "📊 오늘의 시장 요약", font=font(54), fill=C["gold"])
    img = draw_divider(img, 172)

    # 코스피 수치
    kospi = section.get("kospi_value", "6,226")
    change = section.get("kospi_change", "+2.21%")
    is_pos = section.get("kospi_change_positive", True)
    change_color = C["green"] if is_pos else C["red"]

    draw.text((80, 200), "KOSPI", font=font(32, bold=False), fill=C["subtext"])
    draw.text((80, 240), kospi, font=font(100), fill=C["white"])
    draw.text((80 + int(font(100).getlength(kospi)) + 20, 290),
              change, font=font(54), fill=change_color)

    img = draw_divider(img, 380, color=(40, 45, 80), width=1)

    # 포인트 리스트 (큰 글씨)
    points = section.get("points", [
        "33거래일 만에 6,200선 완전 회복",
        "외국인 순매수 전환",
        "AI 반도체·방산 섹터 주도",
        "전고점 6,347 돌파 여부 관건",
    ])
    for i, pt in enumerate(points[:4]):
        py = 400 + i * 85
        draw.rectangle([(80, py + 10), (92, py + 56)], fill=C["gold"])
        draw.text((112, py + 33), pt, font=font(34), fill=C["white"], anchor="lm")

    # 우측 연합뉴스 이미지
    img_path = os.path.join(img_dir, "news_시장요약.jpg")
    if not os.path.exists(img_path):
        fetch_yonhap_image(YONHAP_KEYWORDS.get("시장요약", "코스피"), img_path)

    if os.path.exists(img_path):
        paste_image_to_frame(img, img_path, 960, 185, 910, 710)
    else:
        draw_placeholder(img, 960, 185, 910, 710, "📰 뉴스 사진", "연합뉴스 이미지")

    img = draw_bottom_strip(img, "시장 요약", TODAY)
    path = os.path.join(out_dir, "02_market_summary.png")
    img.save(path)
    print(f"✅ 시장요약: {path}")
    return path


def build_sector(section, out_dir):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="주목 섹터", tag_color=(0, 120, 180))

    draw.text((W // 2, 148), "🔥 오늘의 주목 섹터",
              font=font(64), fill=C["gold"], anchor="mm")
    img = draw_divider(img, 210)

    sectors = section.get("sector_list", [
        {"name": "AI 반도체 & HBM", "desc": "TSMC 실적, 수요 폭발적 증가", "icon": "🤖"},
        {"name": "피지컬AI & 로보틱스", "desc": "현대차 보스턴다이내믹스 Atlas", "icon": "🦾"},
        {"name": "원자력 & 에너지", "desc": "SMR·대형 원전 수주 확대", "icon": "⚛️"},
    ])

    card_w, card_h = 520, 520
    gap = 60
    total_w = card_w * 3 + gap * 2
    sx = (W - total_w) // 2

    for i, s in enumerate(sectors[:3]):
        cx = sx + i * (card_w + gap)
        cy = 250
        draw.rounded_rectangle([(cx, cy), (cx + card_w, cy + card_h)],
                                radius=16, fill=C["bg2"], outline=C["gold"], width=2)
        draw.text((cx + card_w // 2, cy + 100), s.get("icon", "📊"),
                  font=font(80), fill=C["gold"], anchor="mm")
        draw.text((cx + card_w // 2, cy + 205), s["name"],
                  font=font(36), fill=C["white"], anchor="mm")
        draw.line([(cx + 40, cy + 245), (cx + card_w - 40, cy + 245)],
                  fill=C["gold"], width=1)
        desc_lines = textwrap.wrap(s.get("desc", ""), width=18)
        for j, dl in enumerate(desc_lines[:3]):
            draw.text((cx + card_w // 2, cy + 295 + j * 55),
                      dl, font=font(28, bold=False), fill=C["subtext"], anchor="mm")

    img = draw_bottom_strip(img, "주목 섹터", TODAY)
    path = os.path.join(out_dir, "03_sectors.png")
    img.save(path)
    print(f"✅ 섹터: {path}")
    return path


def build_stock_frame(section, stock_name, out_dir, img_dir,
                      is_hidden=False, frame_idx=10):
    paths = []
    prefix = "H" if is_hidden else "S"
    tag_label = "히든 종목" if is_hidden else "관심 종목"
    tag_color = C["purple"] if is_hidden else C["tag_blue"]

    # ── 프레임 1: 종목 요약 + 뉴스사진 ──────────────
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text=tag_label, tag_color=tag_color)

    # 종목명
    draw.text((80, 100), stock_name, font=font(80), fill=C["gold"])

    # 기업 요약 레이블
    summary = section.get("summary", section.get("label", ""))
    draw.text((80, 195), summary, font=font(30, bold=False), fill=C["subtext"])

    # 주가 + 등락
    price = section.get("price", "")
    change = section.get("change", "")
    is_pos = section.get("change_positive", "+" in change)
    change_color = C["green"] if is_pos else C["red"]

    draw.text((80, 250), price, font=font(88), fill=C["white"])
    if change:
        px_offset = int(font(88).getlength(price)) + 24
        draw.text((80 + px_offset, 298), change, font=font(52), fill=change_color)

    img = draw_divider(img, 378)

    # 내레이션 핵심 내용 CG 텍스트 (왼쪽 하단)
    narration = section.get("narration", "")
    cg_lines = textwrap.wrap(narration[:120], width=32)
    for i, line in enumerate(cg_lines[:4]):
        draw.text((80, 400 + i * 65), line,
                  font=font(34, bold=False), fill=C["white"])

    # 우측 연합뉴스 이미지
    img_path = os.path.join(img_dir, f"news_{stock_name}.jpg")
    if not os.path.exists(img_path):
        kw = YONHAP_KEYWORDS.get(stock_name, stock_name)
        fetch_yonhap_image(kw, img_path)

    if os.path.exists(img_path):
        paste_image_to_frame(img, img_path, 960, 100, 910, 710)
    else:
        draw_placeholder(img, 960, 100, 910, 710, "📰 뉴스 사진", f"{stock_name} 관련")

    img = draw_bottom_strip(img, stock_name, section.get("label", ""), TODAY)
    p1 = os.path.join(out_dir, f"{frame_idx:02d}_{prefix}_{stock_name}_1_summary.png")
    img.save(p1)
    paths.append(p1)
    print(f"✅ {stock_name} 요약: {p1}")

    # ── 프레임 2: 주가 차트 ──────────────────────────
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text=f"{stock_name} 주가 흐름", tag_color=tag_color)

    draw.text((80, 95), f"{stock_name}  최근 주가 흐름",
              font=font(54), fill=C["gold"])
    img = draw_divider(img, 165)

    chart_path = os.path.join(img_dir, f"chart_{stock_name}.png")
    if not os.path.exists(chart_path):
        capture_naver_chart(stock_name, chart_path)

    if os.path.exists(chart_path):
        paste_image_to_frame(img, chart_path, 60, 185, 1800, 660)
    else:
        draw_placeholder(img, 60, 185, 1800, 660, "📈 주가 차트", "네이버 금융 차트")

    img = draw_bottom_strip(img, stock_name, "주가 흐름", TODAY)
    p2 = os.path.join(out_dir, f"{frame_idx:02d}_{prefix}_{stock_name}_2_chart.png")
    img.save(p2)
    paths.append(p2)
    print(f"✅ {stock_name} 차트: {p2}")

    # ── 프레임 3: 촉매 / 리스크 / 채널 언급 ──────────
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text=f"{stock_name} 분석", tag_color=tag_color)

    draw.text((80, 95), f"{stock_name}  —  촉매 & 리스크",
              font=font(52), fill=C["gold"])
    img = draw_divider(img, 162)

    # 상승 촉매 박스
    draw.rounded_rectangle([(55, 180), (680, 860)],
                            radius=12, fill=C["bg2"], outline=C["green"], width=2)
    draw.text((368, 218), "📈 상승 촉매",
              font=font(36), fill=C["green"], anchor="mm")
    draw.line([(75, 248), (660, 248)], fill=C["green"], width=1)

    catalysts = section.get("catalysts", [])
    for i, cat in enumerate(catalysts[:5]):
        cy = 272 + i * 110
        draw.rectangle([(78, cy + 8), (92, cy + 56)], fill=C["green"])
        clines = textwrap.wrap(cat, width=20)
        for k, cl in enumerate(clines[:2]):
            draw.text((105, cy + 6 + k * 44),
                      cl, font=font(30, bold=(k == 0)), fill=C["white"])

    # 리스크 박스
    draw.rounded_rectangle([(700, 180), (1325, 860)],
                            radius=12, fill=C["bg2"], outline=C["red"], width=2)
    draw.text((1013, 218), "⚠️ 리스크",
              font=font(36), fill=C["red"], anchor="mm")
    draw.line([(720, 248), (1305, 248)], fill=C["red"], width=1)

    risks = section.get("risks", [])
    for i, risk in enumerate(risks[:5]):
        ry = 272 + i * 110
        draw.rectangle([(723, ry + 8), (737, ry + 56)], fill=C["red"])
        rlines = textwrap.wrap(risk, width=20)
        for k, rl in enumerate(rlines[:2]):
            draw.text((752, ry + 6 + k * 44),
                      rl, font=font(30, bold=(k == 0)), fill=C["white"])

    # 채널 언급 박스
    draw.rounded_rectangle([(1345, 180), (1870, 860)],
                            radius=12, fill=C["bg2"], outline=C["blue"], width=2)
    draw.text((1608, 218), "📺 채널 언급",
              font=font(36), fill=C["blue"], anchor="mm")
    draw.line([(1365, 248), (1850, 248)], fill=C["blue"], width=1)

    mentions = section.get("mentions", [])
    for i, m in enumerate(mentions[:4]):
        my = 272 + i * 140
        # 매체명
        source = m.get("source", "")
        draw.text((1365, my), source, font=font(32), fill=C["gold"])
        # 기자/애널리스트
        reporter = m.get("reporter", m.get("analyst", ""))
        if reporter:
            draw.text((1365, my + 42), reporter,
                      font=font(24, bold=False), fill=C["subtext"])
        # 인용 내용
        quote = m.get("quote", m.get("report", ""))
        qlines = textwrap.wrap(quote, width=22)
        for k, ql in enumerate(qlines[:2]):
            draw.text((1365, my + 75 + k * 38),
                      ql, font=font(26, bold=False), fill=C["white"])

    img = draw_bottom_strip(img, stock_name, "분석", TODAY)
    p3 = os.path.join(out_dir, f"{frame_idx:02d}_{prefix}_{stock_name}_3_analysis.png")
    img.save(p3)
    paths.append(p3)
    print(f"✅ {stock_name} 분석: {p3}")

    return paths


def build_ai_strategy(section, out_dir):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="AI 투자 전략", tag_color=C["purple"])

    draw.text((W // 2, 145), "🧠 AI 투자 전략",
              font=font(64), fill=C["gold"], anchor="mm")
    img = draw_divider(img, 208)

    # 좌측 진행자 캐릭터 영역
    draw_placeholder(img, 55, 228, 620, 690, "🎙️ 진행자", "캐릭터 영역")

    # 우측 전략 bullet 6개
    bullets = section.get("bullet_points", [])
    bx = 720
    for i, bp in enumerate(bullets[:6]):
        by = 240 + i * 105
        # 번호 원형 배경
        draw.ellipse([(bx, by + 4), (bx + 56, by + 60)], fill=C["gold"])
        draw.text((bx + 28, by + 32), str(i + 1),
                  font=font(30), fill=C["bg"], anchor="mm")
        # 종목명 (대시 앞 부분) 강조
        parts = bp.split("—", 1)
        if len(parts) == 2:
            stock_part = parts[0].strip()
            strategy_part = parts[1].strip()
            draw.text((bx + 74, by + 8), stock_part,
                      font=font(34), fill=C["gold"])
            slines = textwrap.wrap(strategy_part, width=42)
            for k, sl in enumerate(slines[:2]):
                draw.text((bx + 74, by + 50 + k * 36),
                          sl, font=font(28, bold=False), fill=C["white"])
        else:
            blines = textwrap.wrap(bp, width=48)
            for k, bl in enumerate(blines[:2]):
                draw.text((bx + 74, by + 8 + k * 42),
                          bl, font=font(30 if k == 0 else 26, bold=(k == 0)),
                          fill=C["white"] if k == 0 else C["subtext"])

    img = draw_bottom_strip(img, "최건일", "진행자", PROGRAM)
    path = os.path.join(out_dir, "90_ai_strategy.png")
    img.save(path)
    print(f"✅ AI전략: {path}")
    return path


def build_closing(section, out_dir):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="클로징", tag_color=C["tag_blue"])

    draw.text((W // 2, 290), PROGRAM, font=font(88), fill=C["gold"], anchor="mm")
    draw.text((W // 2, 395), TODAY,
              font=font(38, bold=False), fill=C["subtext"], anchor="mm")
    img = draw_divider(img, 460)

    disclaimer = section.get("disclaimer",
        "본 브리핑은 AI가 생성한 참고 자료이며 투자 권유가 아닙니다.\n투자의 최종 판단과 책임은 본인에게 있습니다.")
    for i, line in enumerate(disclaimer.split("\n")):
        draw.text((W // 2, 500 + i * 62), line,
                  font=font(28, bold=False), fill=C["subtext"], anchor="mm")

    draw.text((W // 2, 710), "다음 방송에서 만나요! 📈",
              font=font(52), fill=C["white"], anchor="mm")

    img = draw_bottom_strip(img, "최건일", "진행자", PROGRAM)
    path = os.path.join(out_dir, "99_closing.png")
    img.save(path)
    print(f"✅ 클로징: {path}")
    return path


# ══════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════

def run(lang="KO"):
    print(f"\n🎬 자료 화면 제작 시작 — {lang} ({TODAY})\n")

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

        if sid == "opening":
            asset_map[sid] = build_opening(sec, out_dir)

        elif sid == "market_summary":
            asset_map[sid] = build_market_summary(sec, out_dir, img_dir)

        elif sid == "sectors":
            asset_map[sid] = build_sector(sec, out_dir)

        elif sid.startswith("stock_"):
            sname = sid.replace("stock_", "")
            asset_map[sid] = build_stock_frame(
                sec, sname, out_dir, img_dir, is_hidden=False, frame_idx=stock_idx)
            stock_idx += 1

        elif sid.startswith("hidden_"):
            sname = sid.replace("hidden_", "")
            asset_map[sid] = build_stock_frame(
                sec, sname, out_dir, img_dir, is_hidden=True, frame_idx=stock_idx)
            stock_idx += 1

        elif sid == "ai_strategy":
            asset_map[sid] = build_ai_strategy(sec, out_dir)

        elif sid == "closing":
            asset_map[sid] = build_closing(sec, out_dir)

    map_path = os.path.join(out_dir, "asset_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    total = sum(len(v) if isinstance(v, list) else 1 for v in asset_map.values())
    print(f"\n🎉 완료! 총 {total}개 프레임 → {out_dir}")


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "KO")
