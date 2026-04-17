import os
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap

# ── 기본 설정 ──────────────────────────────────────────
W, H = 1920, 1080
FONT_PATH = "assets/fonts/NotoSansKR-Bold.ttf"
FONT_PATH_REGULAR = "assets/fonts/NotoSansKR-Regular.ttf"

# 컬러 팔레트
C = {
    "bg":        (10, 12, 25),       # 배경 다크 네이비
    "bg2":       (18, 22, 45),       # 보조 배경
    "gold":      (255, 195, 0),      # 골드 강조
    "white":     (235, 235, 245),    # 본문 흰색
    "subtext":   (160, 165, 185),    # 보조 텍스트
    "green":     (0, 210, 120),      # 상승
    "red":       (255, 75, 75),      # 하락
    "blue":      (50, 140, 255),     # 포인트 블루
    "strip_bg":  (20, 24, 50),       # 자막 띠 배경
    "name_bg":   (255, 255, 255),    # 이름 자막 흰색 배경
    "name_text": (20, 20, 30),       # 이름 자막 텍스트
    "tag_news":  (180, 0, 0),        # 뉴스 태그 빨강
    "tag_stock": (0, 80, 200),       # 종목 태그 블루
    "overlay":   (0, 0, 0, 160),     # 반투명 오버레이
}

TODAY = datetime.now().strftime("%Y년 %m월 %d일")
PROGRAM = "AI 주식 브리핑"
WATERMARK = "AI STOCK BRIEFING"


def font(size, bold=True):
    path = FONT_PATH if bold else FONT_PATH_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


def new_frame():
    """기본 다크 배경 프레임 생성"""
    img = Image.new("RGB", (W, H), C["bg"])
    draw = ImageDraw.Draw(img)
    # 미세 그라디언트 효과 (상단 약간 밝게)
    for y in range(300):
        alpha = int(8 * (1 - y / 300))
        draw.line([(0, y), (W, y)], fill=(
            min(255, C["bg"][0] + alpha),
            min(255, C["bg"][1] + alpha),
            min(255, C["bg"][2] + alpha + 5)
        ))
    return img


def draw_top_bar(img, program=PROGRAM, date=TODAY, tag_text="", tag_color=None):
    """상단 채널/프로그램 띠 (MBC 스타일)"""
    draw = ImageDraw.Draw(img)
    bar_h = 72
    draw.rectangle([(0, 0), (W, bar_h)], fill=C["bg2"])
    draw.line([(0, bar_h), (W, bar_h)], fill=C["gold"], width=2)

    # 태그 박스 (프로그램 앞)
    tag_color = tag_color or C["tag_stock"]
    tag_text = tag_text or "LIVE"
    tw = font(22).getlength(tag_text) + 28
    draw.rounded_rectangle([(20, 18), (20 + tw, 54)], radius=5, fill=tag_color)
    draw.text((20 + 14, 36), tag_text, font=font(22), fill=C["white"], anchor="lm")

    # 프로그램명
    draw.text((20 + tw + 18, 36), program, font=font(28), fill=C["white"], anchor="lm")

    # 날짜 (우측)
    draw.text((W - 30, 36), date, font=font(22, bold=False), fill=C["subtext"], anchor="rm")
    return img


def draw_bottom_name_strip(img, name, title="", org=""):
    """하단 발언자/종목 이름 자막 띠 (MBC 스타일: 흰 바탕 + 이름 굵게)"""
    draw = ImageDraw.Draw(img)
    strip_y = H - 130
    strip_h = 85

    # 반투명 배경 띠 (numpy 없이 Pillow RGBA 합성)
    overlay = Image.new("RGBA", (W, strip_h), (15, 18, 40, 220))
    base_crop = img.crop((0, strip_y, W, strip_y + strip_h)).convert("RGBA")
    merged = Image.alpha_composite(base_crop, overlay).convert("RGB")
    img.paste(merged, (0, strip_y))
    draw = ImageDraw.Draw(img)
    draw.line([(0, strip_y), (W, strip_y)], fill=C["gold"], width=2)

    # 이름 흰색 박스
    name_w = font(30).getlength(name) + 36
    draw.rectangle([(40, strip_y + 16), (40 + name_w, strip_y + strip_h - 16)],
                   fill=C["name_bg"])
    draw.text((40 + 18, strip_y + strip_h // 2), name,
              font=font(30), fill=C["name_text"], anchor="lm")

    # 직책 / 소속
    if title or org:
        info = f"{title}  {org}".strip()
        draw.text((40 + name_w + 24, strip_y + strip_h // 2),
                  info, font=font(24, bold=False), fill=C["subtext"], anchor="lm")

    # 워터마크 우측
    draw.text((W - 30, strip_y + strip_h // 2), WATERMARK,
              font=font(20, bold=False), fill=(80, 85, 110), anchor="rm")
    return img


def draw_quote_text(img, lines, x=120, y_start=200, max_width=1200,
                    font_size=52, color=None, line_gap=20, highlight_first=False):
    """본문 인용 텍스트 (줄바꿈 자동, 첫 줄 골드 강조 옵션)"""
    draw = ImageDraw.Draw(img)
    color = color or C["white"]
    f = font(font_size)
    y = y_start
    for i, line in enumerate(lines):
        if not line.strip():
            y += font_size // 2
            continue
        # 줄 자동 래핑
        wrapped = textwrap.wrap(line, width=int(max_width / (font_size * 0.55)))
        for j, wline in enumerate(wrapped):
            c = C["gold"] if (highlight_first and i == 0 and j == 0) else color
            draw.text((x, y), wline, font=f, fill=c)
            y += font_size + line_gap
    return img, y


def draw_placeholder_box(img, x, y, w, h, label="뉴스 사진 영역", sub=""):
    """뉴스사진 / 차트 플레이스홀더"""
    draw = ImageDraw.Draw(img)
    draw.rectangle([(x, y), (x + w, y + h)], fill=(25, 30, 60),
                   outline=(80, 90, 140), width=2)
    # 대각선
    draw.line([(x, y), (x + w, y + h)], fill=(50, 55, 90), width=1)
    draw.line([(x + w, y), (x, y + h)], fill=(50, 55, 90), width=1)
    # 레이블
    draw.text((x + w // 2, y + h // 2 - 20), label,
              font=font(28, bold=False), fill=(100, 110, 160), anchor="mm")
    if sub:
        draw.text((x + w // 2, y + h // 2 + 24), sub,
                  font=font(20, bold=False), fill=(70, 80, 120), anchor="mm")
    return img


def draw_divider(img, y, color=None, width=2):
    draw = ImageDraw.Draw(img)
    draw.line([(60, y), (W - 60, y)], fill=color or C["gold"], width=width)
    return img


# ═══════════════════════════════════════════════════════
# 섹션별 프레임 빌더
# ═══════════════════════════════════════════════════════

def build_opening(section, out_dir):
    """오프닝 – 대형 타이틀 + 키워드 3개"""
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="TODAY", tag_color=C["tag_stock"])

    # 메인 타이틀
    draw.text((W // 2, 260), PROGRAM,
              font=font(88), fill=C["gold"], anchor="mm")
    draw.text((W // 2, 360), TODAY,
              font=font(36, bold=False), fill=C["subtext"], anchor="mm")

    img = draw_divider(img, 420)

    # 키워드 박스 3개
    keywords = section.get("keywords", [])[:3]
    box_w, box_h = 480, 100
    gap = 60
    total_w = box_w * 3 + gap * 2
    start_x = (W - total_w) // 2
    for i, kw in enumerate(keywords):
        bx = start_x + i * (box_w + gap)
        by = 480
        draw.rounded_rectangle([(bx, by), (bx + box_w, by + box_h)],
                                radius=12, fill=C["bg2"], outline=C["gold"], width=2)
        draw.text((bx + box_w // 2, by + box_h // 2), kw,
                  font=font(30), fill=C["white"], anchor="mm")

    # 리드 멘트
    narration = section.get("narration", "")[:60]
    draw.text((W // 2, 660), narration,
              font=font(34, bold=False), fill=C["subtext"], anchor="mm")

    img = draw_bottom_name_strip(img, "최건일", "진행자", "AI 주식 브리핑")

    path = os.path.join(out_dir, "01_opening.png")
    img.save(path)
    print(f"✅ 오프닝: {path}")
    return path


def build_market_summary(section, out_dir):
    """시장 요약 – 좌: 텍스트, 우: 뉴스사진 플레이스홀더"""
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="시장 요약", tag_color=C["tag_news"])

    # 섹션 제목
    draw.text((80, 110), "📊 오늘의 시장 요약",
              font=font(52), fill=C["gold"])
    img = draw_divider(img, 180)

    # 좌측 텍스트 영역
    narration = section.get("narration", "")
    lines = [narration[i:i+28] for i in range(0, min(len(narration), 28*6), 28)]
    draw.text((80, 210), "코스피", font=font(36), fill=C["subtext"])

    # 수치 강조
    kospi = section.get("kospi_value", "6,226")
    change = section.get("kospi_change", "+2.21%")
    draw.text((80, 255), kospi, font=font(96), fill=C["white"])
    draw.text((310, 295), change, font=font(52), fill=C["green"])

    img = draw_divider(img, 380, color=(40, 45, 80), width=1)

    # 요약 포인트 리스트
    points = section.get("points", [
        "33거래일 만에 6,200선 완전 회복",
        "외국인 순매수 전환",
        "AI 반도체·방산 주도",
        "전고점 6,347 돌파 여부 관건",
    ])
    for i, pt in enumerate(points[:4]):
        py = 400 + i * 80
        draw.rectangle([(80, py + 8), (90, py + 52)], fill=C["gold"])
        draw.text((110, py + 30), pt, font=font(32, bold=False),
                  fill=C["white"], anchor="lm")

    # 우측 뉴스사진 플레이스홀더
    draw_placeholder_box(img, 960, 190, 900, 700,
                         label="📰 뉴스 사진 영역",
                         sub="(연합뉴스 이미지 삽입 예정)")

    img = draw_bottom_name_strip(img, "시장 요약", f"{TODAY}")

    path = os.path.join(out_dir, "02_market_summary.png")
    img.save(path)
    print(f"✅ 시장요약: {path}")
    return path


def build_sector(section, out_dir):
    """주목 섹터 – 섹터 3개 카드형"""
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="주목 섹터", tag_color=C["blue"])

    draw.text((W // 2, 160), "🔥 오늘의 주목 섹터",
              font=font(60), fill=C["gold"], anchor="mm")
    img = draw_divider(img, 220)

    sectors = section.get("sector_list", [
        {"name": "AI 반도체 & HBM",  "desc": "TSMC 실적 확인, 수요 폭발적 증가"},
        {"name": "피지컬AI & 로보틱스", "desc": "현대차 보스턴다이내믹스, Atlas 공개"},
        {"name": "원자력 & 에너지",   "desc": "SMR·대형 원전 수주 확대 기대"},
    ])

    card_w, card_h = 520, 500
    gap = 60
    total_w = card_w * 3 + gap * 2
    sx = (W - total_w) // 2

    icons = ["🤖", "🦾", "⚛️"]
    for i, sec_item in enumerate(sectors[:3]):
        cx = sx + i * (card_w + gap)
        cy = 260
        # 카드 배경
        draw.rounded_rectangle([(cx, cy), (cx + card_w, cy + card_h)],
                                radius=16, fill=C["bg2"], outline=C["gold"], width=2)
        # 아이콘
        draw.text((cx + card_w // 2, cy + 90),
                  icons[i], font=font(72), fill=C["gold"], anchor="mm")
        # 섹터명
        draw.text((cx + card_w // 2, cy + 200),
                  sec_item["name"], font=font(34), fill=C["white"], anchor="mm")
        # 구분선
        draw.line([(cx + 40, cy + 240), (cx + card_w - 40, cy + 240)],
                  fill=C["gold"], width=1)
        # 설명
        desc_lines = textwrap.wrap(sec_item["desc"], width=18)
        for j, dl in enumerate(desc_lines[:3]):
            draw.text((cx + card_w // 2, cy + 290 + j * 50),
                      dl, font=font(26, bold=False),
                      fill=C["subtext"], anchor="mm")

    img = draw_bottom_name_strip(img, "주목 섹터", TODAY)
    path = os.path.join(out_dir, "03_sectors.png")
    img.save(path)
    print(f"✅ 섹터: {path}")
    return path


def build_stock_frame(section, stock_name, out_dir, is_hidden=False, frame_idx=0):
    """종목 프레임 – 3장 생성: ①요약+뉴스, ②차트, ③촉매/리스크/채널"""
    paths = []
    prefix = "H" if is_hidden else "S"
    tag_label = "히든 종목" if is_hidden else "관심 종목"
    tag_color = (120, 0, 180) if is_hidden else C["tag_stock"]

    # ── 프레임 1: 종목 요약 + 뉴스사진 ──
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text=tag_label, tag_color=tag_color)

    # 종목명 대형 타이틀
    draw.text((80, 110), stock_name,
              font=font(72), fill=C["gold"])
    draw.text((80, 195), section.get("label", ""), font=font(30, bold=False),
              fill=C["subtext"])

    # 주가 정보
    price = section.get("price", "")
    change = section.get("change", "")
    change_color = C["green"] if "+" in change else C["red"]
    draw.text((80, 260), price, font=font(80), fill=C["white"])
    draw.text((80 + font(80).getlength(price) + 20, 300),
              change, font=font(48), fill=change_color)

    img = draw_divider(img, 380)

    # 요약 본문
    summary_lines = textwrap.wrap(section.get("summary", ""), width=38)
    for i, line in enumerate(summary_lines[:4]):
        draw.text((80, 400 + i * 60), line,
                  font=font(32, bold=False), fill=C["white"])

    # 우측 뉴스사진 플레이스홀더
    draw_placeholder_box(img, 960, 110, 900, 700,
                         label="📰 뉴스 사진",
                         sub=f"({stock_name} 관련 연합뉴스 이미지)")

    img = draw_bottom_name_strip(img, stock_name, section.get("label", ""), TODAY)
    p1 = os.path.join(out_dir, f"{frame_idx:02d}_{prefix}_{stock_name}_1_summary.png")
    img.save(p1); paths.append(p1)
    print(f"✅ {stock_name} 요약: {p1}")

    # ── 프레임 2: 주가 흐름 (차트 플레이스홀더) ──
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text=f"{stock_name} 주가 흐름", tag_color=tag_color)

    draw.text((80, 110), f"{stock_name} 최근 주가 흐름",
              font=font(52), fill=C["gold"])
    img = draw_divider(img, 180)

    draw_placeholder_box(img, 80, 200, 1760, 640,
                         label="📈 주가 차트 영역",
                         sub="(네이버 금융 차트 캡처 삽입 예정)")

    img = draw_bottom_name_strip(img, stock_name, "주가 흐름", TODAY)
    p2 = os.path.join(out_dir, f"{frame_idx:02d}_{prefix}_{stock_name}_2_chart.png")
    img.save(p2); paths.append(p2)
    print(f"✅ {stock_name} 차트: {p2}")

    # ── 프레임 3: 상승촉매 / 리스크 / 채널 언급 ──
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text=f"{stock_name} 분석", tag_color=tag_color)

    draw.text((80, 110), f"{stock_name} — 촉매 & 리스크",
              font=font(48), fill=C["gold"])
    img = draw_divider(img, 175)

    # 왼쪽: 상승 촉매
    draw.rounded_rectangle([(60, 195), (700, 700)],
                            radius=12, fill=C["bg2"], outline=C["green"], width=2)
    draw.text((380, 230), "📈 상승 촉매",
              font=font(32), fill=C["green"], anchor="mm")
    catalysts = section.get("catalysts", [])
    for i, cat in enumerate(catalysts[:4]):
        cy = 280 + i * 90
        draw.rectangle([(80, cy + 6), (90, cy + 46)], fill=C["green"])
        clines = textwrap.wrap(cat, width=22)
        for k, cl in enumerate(clines[:2]):
            draw.text((105, cy + 5 + k * 38),
                      cl, font=font(26, bold=False), fill=C["white"])

    # 가운데: 리스크
    draw.rounded_rectangle([(720, 195), (1360, 700)],
                            radius=12, fill=C["bg2"], outline=C["red"], width=2)
    draw.text((1040, 230), "⚠️ 리스크",
              font=font(32), fill=C["red"], anchor="mm")
    risks = section.get("risks", [])
    for i, risk in enumerate(risks[:4]):
        ry = 280 + i * 90
        draw.rectangle([(740, ry + 6), (750, ry + 46)], fill=C["red"])
        rlines = textwrap.wrap(risk, width=22)
        for k, rl in enumerate(rlines[:2]):
            draw.text((765, ry + 5 + k * 38),
                      rl, font=font(26, bold=False), fill=C["white"])

    # 오른쪽: 채널 언급
    draw.rounded_rectangle([(1380, 195), (1860, 700)],
                            radius=12, fill=C["bg2"], outline=C["blue"], width=2)
    draw.text((1620, 230), "📺 채널 언급",
              font=font(32), fill=C["blue"], anchor="mm")
    mentions = section.get("mentions", [])
    for i, m in enumerate(mentions[:4]):
        my = 280 + i * 110
        # 매체명
        draw.text((1400, my), m.get("source", ""),
                  font=font(24), fill=C["gold"])
        # 언급 내용
        mlines = textwrap.wrap(m.get("quote", ""), width=18)
        for k, ml in enumerate(mlines[:2]):
            draw.text((1400, my + 34 + k * 34),
                      ml, font=font(22, bold=False), fill=C["subtext"])

    img = draw_bottom_name_strip(img, stock_name, "분석", TODAY)
    p3 = os.path.join(out_dir, f"{frame_idx:02d}_{prefix}_{stock_name}_3_analysis.png")
    img.save(p3); paths.append(p3)
    print(f"✅ {stock_name} 분석: {p3}")

    return paths


def build_ai_strategy(section, out_dir):
    """AI 투자 전략 – 진행자 캐릭터 영역 + 자막 6개"""
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="AI 투자 전략", tag_color=(160, 50, 200))

    draw.text((W // 2, 155), "🧠 AI 투자 전략",
              font=font(60), fill=C["gold"], anchor="mm")
    img = draw_divider(img, 215)

    # 좌측: 진행자 캐릭터 플레이스홀더
    draw_placeholder_box(img, 60, 235, 640, 680,
                         label="🎙️ 진행자",
                         sub="(캐릭터 애니메이션 영역)")

    # 우측: 전략 bullet 6개
    bullets = section.get("bullet_points", [])
    bx = 740
    for i, bp in enumerate(bullets[:6]):
        by = 250 + i * 105
        # 번호 원형
        draw.ellipse([(bx, by + 5), (bx + 54, by + 59)], fill=C["gold"])
        draw.text((bx + 27, by + 32), str(i + 1),
                  font=font(28), fill=C["bg"], anchor="mm")
        # 텍스트
        blines = textwrap.wrap(bp, width=46)
        for k, bl in enumerate(blines[:2]):
            draw.text((bx + 70, by + 8 + k * 44),
                      bl, font=font(30 if k == 0 else 26, bold=(k == 0)),
                      fill=C["white"] if k == 0 else C["subtext"])

    img = draw_bottom_name_strip(img, "최건일", "진행자", "AI 주식 브리핑")
    path = os.path.join(out_dir, "90_ai_strategy.png")
    img.save(path)
    print(f"✅ AI 전략: {path}")
    return path


def build_closing(section, title, out_dir):
    """클로징 – 타이틀 + 면책 고지"""
    img = new_frame()
    draw = ImageDraw.Draw(img)
    img = draw_top_bar(img, tag_text="클로징", tag_color=C["tag_stock"])

    draw.text((W // 2, 300), PROGRAM,
              font=font(80), fill=C["gold"], anchor="mm")
    draw.text((W // 2, 405), TODAY,
              font=font(36, bold=False), fill=C["subtext"], anchor="mm")

    img = draw_divider(img, 470)

    # 면책 고지
    disclaimer = section.get("disclaimer",
        "본 브리핑은 AI가 생성한 참고 자료이며 투자 권유가 아닙니다.\n투자의 최종 판단과 책임은 본인에게 있습니다.")
    for i, line in enumerate(disclaimer.split("\n")):
        draw.text((W // 2, 510 + i * 60), line,
                  font=font(28, bold=False), fill=C["subtext"], anchor="mm")

    draw.text((W // 2, 700), "다음 방송에서 만나요! 📈",
              font=font(48), fill=C["white"], anchor="mm")

    img = draw_bottom_name_strip(img, "최건일", "진행자", "AI 주식 브리핑")
    path = os.path.join(out_dir, "99_closing.png")
    img.save(path)
    print(f"✅ 클로징: {path}")
    return path


# ═══════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════

def run(lang="KO"):
    print(f"\n🎬 자료 화면 제작 시작 — {lang} ({TODAY})\n")
    script_path = f"output/{lang}/scripts/script.json"
    out_dir = f"output/{lang}/frames"
    os.makedirs(out_dir, exist_ok=True)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    asset_map = {}
    stock_idx = 10

    for sec in script.get("sections", []):
        sid = sec.get("id", "")

        if sid == "opening":
            asset_map[sid] = build_opening(sec, out_dir)

        elif sid == "market_summary":
            asset_map[sid] = build_market_summary(sec, out_dir)

        elif sid == "sectors":
            asset_map[sid] = build_sector(sec, out_dir)

        elif sid.startswith("stock_"):
            sname = sid.replace("stock_", "")
            asset_map[sid] = build_stock_frame(sec, sname, out_dir,
                                               frame_idx=stock_idx)
            stock_idx += 1

        elif sid.startswith("hidden_"):
            sname = sid.replace("hidden_", "")
            asset_map[sid] = build_stock_frame(sec, sname, out_dir,
                                               is_hidden=True, frame_idx=stock_idx)
            stock_idx += 1

        elif sid == "ai_strategy":
            asset_map[sid] = build_ai_strategy(sec, out_dir)

        elif sid == "closing":
            asset_map[sid] = build_closing(sec, script.get("title", ""), out_dir)

    # asset_map 저장
    map_path = os.path.join(out_dir, "asset_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    total = sum(len(v) if isinstance(v, list) else 1
                for v in asset_map.values())
    print(f"\n🎉 완료! 총 {total}개 프레임 → {out_dir}")
    return asset_map


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "KO")
