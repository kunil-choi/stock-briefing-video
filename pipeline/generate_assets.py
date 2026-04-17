import os
import json
import time
import requests
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

VIDEO_WIDTH  = 1920
VIDEO_HEIGHT = 1080
FONT_PATH    = "assets/fonts/NotoSansKR-Bold.ttf"
BG_COLOR     = (10, 15, 30)       # 다크 배경
GOLD_COLOR   = (255, 200, 0)      # 골드 (타이틀)
WHITE_COLOR  = (220, 220, 240)    # 흰색 (본문)
GREEN_COLOR  = (0, 255, 150)      # 초록 (상승)
RED_COLOR    = (255, 100, 100)    # 빨강 (하락/리스크)
BLUE_COLOR   = (100, 180, 255)    # 파랑 (정보)

STOCK_CODE_MAP = {
    "삼성전자":     "005930",
    "SK하이닉스":   "000660",
    "현대차":       "005380",
    "현대로템":     "064350",
    "현대위아":     "011210",
    "신세계":       "004170",
    "두산에너빌리티": "034020",
    "크래프톤":     "259960",
    "하이브":       "352820",
    "에이피알":     "278470",
    "한화":         "000880",
    "카카오":       "035720",
    "OCI홀딩스":    "010060",
    "대우건설":     "047040",
    "한국전력":     "015760",
    "KB금융":       "105560",
}

# ─────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────

def get_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()

def make_base_frame() -> Image.Image:
    """기본 배경 프레임 생성 (1920x1080 다크 테마)"""
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    # 하단 그라데이션 효과 (간단히 직사각형으로)
    draw.rectangle(
        [(0, VIDEO_HEIGHT - 120), (VIDEO_WIDTH, VIDEO_HEIGHT)],
        fill=(5, 8, 20)
    )
    return img

def draw_title_bar(img: Image.Image,
                   title: str,
                   subtitle: str = "") -> Image.Image:
    """상단 타이틀 바"""
    draw = ImageDraw.Draw(img)
    # 타이틀 바 배경
    draw.rectangle([(0, 0), (VIDEO_WIDTH, 110)], fill=(20, 25, 50))
    # 좌측 골드 강조선
    draw.rectangle([(0, 0), (8, 110)], fill=GOLD_COLOR)
    # 타이틀 텍스트
    draw.text((40, 18), title,    font=get_font(44), fill=GOLD_COLOR)
    draw.text((40, 72), subtitle, font=get_font(26), fill=(180, 180, 200))
    # 하단 구분선
    draw.line([(0, 110), (VIDEO_WIDTH, 110)], fill=GOLD_COLOR, width=2)
    return img

def draw_bottom_bar(img: Image.Image, text: str) -> Image.Image:
    """하단 자막 바"""
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(0, VIDEO_HEIGHT - 80), (VIDEO_WIDTH, VIDEO_HEIGHT)],
        fill=(15, 20, 45)
    )
    draw.line(
        [(0, VIDEO_HEIGHT - 80), (VIDEO_WIDTH, VIDEO_HEIGHT - 80)],
        fill=GOLD_COLOR, width=2
    )
    draw.text(
        (VIDEO_WIDTH // 2, VIDEO_HEIGHT - 40),
        text, font=get_font(28),
        fill=WHITE_COLOR, anchor="mm"
    )
    return img

# ─────────────────────────────────────────────
# 연합뉴스 이미지 크롤링
# ─────────────────────────────────────────────

def fetch_yonhap_image(keyword: str, save_path: str) -> str | None:
    """연합뉴스에서 키워드 관련 뉴스 사진 크롤링"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            url = f"https://www.yna.co.kr/search/index?query={keyword}&ctype=A"
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(1)

            # 첫 번째 기사 이미지 추출
            img_el = page.query_selector(
                ".news-list img, .list-type038 img, article img, .img-con img"
            )
            if not img_el:
                browser.close()
                return None

            img_src = img_el.get_attribute("src")
            if not img_src:
                browser.close()
                return None
            if img_src.startswith("//"):
                img_src = "https:" + img_src

            # 이미지 다운로드
            r = requests.get(img_src, timeout=10)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(r.content)

            browser.close()
            print(f"    ✅ 연합뉴스 이미지 수집: {keyword}")
            return save_path

    except Exception as e:
        print(f"    ⚠️ 이미지 수집 실패 ({keyword}): {e}")
        return None

# ─────────────────────────────────────────────
# 네이버 주가 차트 캡처
# ─────────────────────────────────────────────

def capture_stock_chart(stock_name: str, save_path: str) -> str | None:
    """네이버 금융에서 주가 차트 캡처"""
    code = STOCK_CODE_MAP.get(stock_name)
    if not code:
        print(f"    ⚠️ 종목 코드 없음: {stock_name}")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1000, "height": 600}
            )
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(2)

            # 차트 영역 캡처
            chart_el = page.query_selector(
                "#chart_area, .chart_area, #stockChart"
            )
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            if chart_el:
                chart_el.screenshot(path=save_path)
            else:
                page.screenshot(
                    path=save_path,
                    clip={"x": 0, "y": 200, "width": 1000, "height": 400}
                )
            browser.close()
            print(f"    ✅ 주가 차트 캡처: {stock_name}")
            return save_path

    except Exception as e:
        print(f"    ⚠️ 차트 캡처 실패 ({stock_name}): {e}")
        return None

# ─────────────────────────────────────────────
# 섹션별 화면 생성
# ─────────────────────────────────────────────

def build_opening_frame(section: dict, out_dir: str) -> str:
    """오프닝 타이틀 화면"""
    out_path = f"{out_dir}/opening.png"
    img  = make_base_frame()
    draw = ImageDraw.Draw(img)

    # 중앙 타이틀
    draw.text(
        (VIDEO_WIDTH // 2, 380),
        "📊 AI 주식 브리핑",
        font=get_font(80), fill=GOLD_COLOR, anchor="mm"
    )
    draw.text(
        (VIDEO_WIDTH // 2, 500),
        section.get("narration", "")[:40],
        font=get_font(36), fill=WHITE_COLOR, anchor="mm"
    )
    # 하단 날짜
    draw_bottom_bar(img, section.get("date", ""))

    img.save(out_path)
    print(f"  ✅ 오프닝 화면 생성")
    return out_path

def build_market_summary_frame(section: dict,
                                out_dir: str) -> str:
    """시장 요약 화면 — 연합뉴스 사진 + 텍스트"""
    out_path  = f"{out_dir}/market_summary.png"
    news_path = f"{out_dir}/news_market.jpg"

    # 연합뉴스 이미지 수집
    fetch_yonhap_image("코스피 주식시장", news_path)

    img  = make_base_frame()
    draw = ImageDraw.Draw(img)
    draw_title_bar(img, "📊 시장 요약", "Market Summary")

    # 뉴스 이미지 (좌측)
    if os.path.exists(news_path):
        try:
            news_img = Image.open(news_path).resize((860, 540))
            img.paste(news_img, (40, 130))
        except:
            pass

    # 우측 텍스트
    narration = section.get("narration", "")
    lines = [narration[i:i+22] for i in range(0, min(len(narration), 440), 22)]
    y = 150
    for line in lines[:18]:
        draw.text((960, y), line, font=get_font(28), fill=WHITE_COLOR)
        y += 48

    draw_bottom_bar(img, "코스피 · 코스닥 · 글로벌 시장 동향")
    img.save(out_path)
    print(f"  ✅ 시장 요약 화면 생성")
    return out_path

def build_sector_frame(section: dict, out_dir: str) -> str:
    """주목 섹터 화면"""
    out_path = f"{out_dir}/sectors.png"
    img  = make_base_frame()
    draw = ImageDraw.Draw(img)
    draw_title_bar(img, "🔥 주목 섹터", "Hot Sectors")

    narration = section.get("narration", "")
    lines = [narration[i:i+40] for i in range(0, min(len(narration), 800), 40)]
    y = 160
    for line in lines[:16]:
        draw.text((80, y), line, font=get_font(34), fill=WHITE_COLOR)
        y += 56

    draw_bottom_bar(img, "AI반도체 · 피지컬AI · 로보틱스 · 원자력")
    img.save(out_path)
    print(f"  ✅ 섹터 화면 생성")
    return out_path

def build_stock_frame(section: dict,
                      stock_name: str,
                      out_dir: str,
                      is_hidden: bool = False) -> list:
    """
    종목 화면 생성 — 3개 프레임
    1) 종목 요약 + 뉴스 사진
    2) 주가 차트
    3) 채널 언급 텍스트
    """
    label  = "히든종목" if is_hidden else "관심종목"
    frames = []
    narration = section.get("narration", "")

    # ── 프레임 1: 종목 요약 + 뉴스 사진
    p1 = f"{out_dir}/{section['id']}_1_summary.png"
    news_path = f"{out_dir}/{section['id']}_news.jpg"
    fetch_yonhap_image(stock_name, news_path)

    img1  = make_base_frame()
    draw1 = ImageDraw.Draw(img1)
    draw_title_bar(img1, f"🎯 {stock_name}", f"{label} — 종목 요약")

    if os.path.exists(news_path):
        try:
            ni = Image.open(news_path).resize((820, 520))
            img1.paste(ni, (40, 130))
        except:
            pass

    lines = [narration[i:i+22] for i in range(0, min(len(narration), 440), 22)]
    y = 150
    for line in lines[:18]:
        draw1.text((920, y), line, font=get_font(27), fill=WHITE_COLOR)
        y += 47
    draw_bottom_bar(img1, f"{stock_name} — 종목 분석")
    img1.save(p1)
    frames.append(p1)

    # ── 프레임 2: 주가 차트
    p2 = f"{out_dir}/{section['id']}_2_chart.png"
    chart_path = f"{out_dir}/{section['id']}_chart_raw.png"
    capture_stock_chart(stock_name, chart_path)

    img2  = make_base_frame()
    draw2 = ImageDraw.Draw(img2)
    draw_title_bar(img2, f"📈 {stock_name}", "주가 흐름")

    if os.path.exists(chart_path):
        try:
            chart_img = Image.open(chart_path).resize((1400, 650))
            img2.paste(chart_img, (260, 130))
        except:
            pass

    draw_bottom_bar(img2, f"{stock_name} — 최근 주가 흐름")
    img2.save(p2)
    frames.append(p2)

    # ── 프레임 3: 채널 언급 텍스트
    p3 = f"{out_dir}/{section['id']}_3_mentions.png"
    img3  = make_base_frame()
    draw3 = ImageDraw.Draw(img3)
    draw_title_bar(img3, f"📢 {stock_name}", "채널별 언급 내용")

    lines = [narration[i:i+44] for i in range(0, len(narration), 44)]
    y = 160
    for line in lines[:16]:
        draw3.text((80, y), line, font=get_font(30), fill=WHITE_COLOR)
        y += 54
    draw_bottom_bar(img3, f"{stock_name} — 전문가 분석")
    img3.save(p3)
    frames.append(p3)

    print(f"  ✅ {label} 화면 생성: {stock_name} (3프레임)")
    return frames

def build_strategy_frames(section: dict, out_dir: str) -> list:
    """AI 투자 전략 — bullet_points별 프레임"""
    frames       = []
    bullet_points = section.get("bullet_points", [])
    narration    = section.get("narration", "")

    for i, point in enumerate(bullet_points[:6]):
        out_path = f"{out_dir}/ai_strategy_{i}.png"
        img  = make_base_frame()
        draw = ImageDraw.Draw(img)
        draw_title_bar(img, "💡 AI 투자 전략", "오늘의 핵심 전략")

        # 전략 목록 (현재 항목 강조)
        y = 160
        for j, bp in enumerate(bullet_points[:6]):
            if j == i:
                # 현재 항목 강조
                draw.rectangle(
                    [(60, y - 8), (VIDEO_WIDTH - 60, y + 52)],
                    fill=(30, 40, 80)
                )
                draw.text((80, y), f"▶  {bp}",
                          font=get_font(32), fill=GOLD_COLOR)
            else:
                draw.text((80, y), f"     {bp}",
                          font=get_font(28), fill=(150, 150, 170))
            y += 70

        # 하단 자막 (현재 항목)
        draw_bottom_bar(img, point[:50])
        img.save(out_path)
        frames.append(out_path)

    print(f"  ✅ AI 전략 화면 생성 ({len(frames)}프레임)")
    return frames

def build_closing_frame(section: dict,
                         title: str,
                         out_dir: str) -> str:
    """클로징 화면"""
    out_path = f"{out_dir}/closing.png"
    img  = make_base_frame()
    draw = ImageDraw.Draw(img)

    draw.text(
        (VIDEO_WIDTH // 2, 350),
        "📊 AI 주식 브리핑",
        font=get_font(72), fill=GOLD_COLOR, anchor="mm"
    )
    draw.text(
        (VIDEO_WIDTH // 2, 480),
        "감사합니다",
        font=get_font(52), fill=WHITE_COLOR, anchor="mm"
    )
    draw.text(
        (VIDEO_WIDTH // 2, 580),
        "⚠️  본 브리핑은 투자 권유가 아닙니다.",
        font=get_font(30), fill=(180, 180, 180), anchor="mm"
    )
    draw_bottom_bar(img, title)
    img.save(out_path)
    print(f"  ✅ 클로징 화면 생성")
    return out_path

# ─────────────────────────────────────────────
# 전체 실행
# ─────────────────────────────────────────────

def run(lang: str = "KO"):
    print(f"\n🖼️ 자료 화면 제작 시작 ({lang})...\n")

    script_path = f"output/{lang}/scripts/script.json"
    out_dir     = f"output/{lang}/frames"
    os.makedirs(out_dir, exist_ok=True)

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    title    = script.get("title", "")
    sections = script.get("sections", [])
    asset_map = {}

    for section in sections:
        sid = section["id"]
        print(f"\n  [{sid}] 화면 제작 중...")

        if sid == "opening":
            section["date"] = script.get("date", "")
            asset_map[sid] = build_opening_frame(section, out_dir)

        elif sid == "market_summary":
            asset_map[sid] = build_market_summary_frame(section, out_dir)

        elif sid == "sectors":
            asset_map[sid] = build_sector_frame(section, out_dir)

        elif sid.startswith("stock_"):
            stock_name = sid.replace("stock_", "")
            asset_map[sid] = build_stock_frame(
                section, stock_name, out_dir, is_hidden=False
            )

        elif sid.startswith("hidden_"):
            stock_name = sid.replace("hidden_", "")
            asset_map[sid] = build_stock_frame(
                section, stock_name, out_dir, is_hidden=True
            )

        elif sid == "ai_strategy":
            asset_map[sid] = build_strategy_frames(section, out_dir)

        elif sid == "closing":
            asset_map[sid] = build_closing_frame(section, title, out_dir)

    # asset_map 저장
    map_path = f"output/{lang}/frames/asset_map.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    total_frames = sum(
        len(v) if isinstance(v, list) else 1
        for v in asset_map.values()
    )
    print(f"\n{'='*40}")
    print(f"🎉 자료 화면 제작 완료!")
    print(f"   총 프레임 수: {total_frames}개")
    print(f"   저장 위치: {out_dir}")
    print(f"{'='*40}\n")

if __name__ == "__main__":
    import sys
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
