# pipeline/assets/builders.py
import os
from PIL import Image, ImageDraw
from .config import W, H, C
from .drawing import (
    fnt, new_frame, draw_topbar, draw_bottombar,
    gold_underline, paste_image, draw_wrapped_text,
    draw_divider, draw_badge,
)
from .chart import build_chart_image
from .image_fetch import fetch_news_image

Y_MAX        = H - 80
MARGIN_X     = 80
CX           = W // 2
# 자막은 generate_video.py의 ASS burn-in으로 처리 — PNG에는 자막 바 없음
CHART_BOTTOM = H - 80


def _save(img, path):
    img.save(path)
    print(f"  ✅ {os.path.basename(path)}")
    return path


def _find_section(sections, id_prefix):
    for s in sections:
        if s.get("id", "").startswith(id_prefix):
            return s
    return {}


def _color_change(val):
    raw = str(val)
    if "▼" in raw or raw.startswith("-"):
        return C["blue"]
    return C["red"]


def _paste_fill(img: Image.Image, path: str, box: tuple):
    if not path or not os.path.isfile(path):
        return
    try:
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        src = Image.open(path).convert("RGB")
        scale = max(bw / src.width, bh / src.height)
        new_w = int(src.width  * scale)
        new_h = int(src.height * scale)
        src   = src.resize((new_w, new_h), Image.LANCZOS)
        left  = (new_w - bw) // 2
        top   = (new_h - bh) // 2
        src   = src.crop((left, top, left + bw, top + bh))
        img.paste(src, (box[0], box[1]))
    except Exception as e:
        print(f"[builders] 이미지 붙이기 실패 ({path}): {e}")


# ── 오프닝 ─────────────────────────────────────────────────────────────────
# 변경 3: 브랜드명 "머니올라 AI 주식 브리핑", 키워드 중앙정렬 + 2배 크기
def build_opening(data, out_dir):
    sec      = _find_section(data.get("sections", []), "opening")
    img      = new_frame()
    draw     = ImageDraw.Draw(img)
    keywords = sec.get("keywords", [])
    date_str = data.get("date", "")

    # 배경 그라디언트
    for i in range(H):
        alpha = int(15 * (1 - i / H))
        draw.line([0, i, W, i], fill=(30 + alpha, 32 + alpha, 80 + alpha))

    # ── 변경: 큰 제목을 "머니올라 AI 주식 브리핑" 으로 2줄 분리
    #    "머니올라"는 골드, "AI 주식 브리핑"은 화이트
    cy = H // 2 - 200

    # 줄 1: "머니올라"
    draw.text((CX, cy), "머니올라",
              font=fnt(90, bold=True), fill=C["gold"], anchor="mm")
    cy += 108

    # 줄 2: "AI 주식 브리핑"
    draw.text((CX, cy), "AI 주식 브리핑",
              font=fnt(80, bold=True), fill=C["white"], anchor="mm")
    cy += 96

    # 날짜
    if date_str:
        draw.text((CX, cy), date_str,
                  font=fnt(42, bold=False), fill=C["gold"], anchor="mm")
        cy += 60

    # 골드 구분선
    draw.line([CX - 300, cy, CX + 300, cy], fill=C["gold"], width=3)
    cy += 52

    # ── 변경: 키워드를 중앙 정렬 + 폰트 크기 2배(52px), 배지 대신 텍스트로 표시
    if keywords:
        kw_list = keywords[:4]
        # 각 키워드 너비 계산 후 전체 너비 측정
        font_kw  = fnt(52, bold=False)
        sep      = "    "   # 구분 공백
        sep_w    = int(draw.textlength(sep, font=font_kw))

        kw_widths = []
        for kw in kw_list:
            try:
                kw_widths.append(int(draw.textlength(kw, font=font_kw)))
            except Exception:
                kw_widths.append(len(kw) * 28)

        total_w = sum(kw_widths) + sep_w * (len(kw_list) - 1)
        kx = (W - total_w) // 2

        for i, kw in enumerate(kw_list):
            draw.text((kx, cy), kw,
                      font=font_kw, fill=C["gold"])
            kx += kw_widths[i]
            if i < len(kw_list) - 1:
                draw.text((kx, cy), sep,
                          font=font_kw, fill=(120, 120, 160))
                kx += sep_w

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "00_opening.png"))


# ── 시장 요약 ───────────────────────────────────────────────────────────────
def build_market_summary(data, out_dir):
    sec      = _find_section(data.get("sections", []), "market_summary")
    img      = new_frame()
    draw     = ImageDraw.Draw(img)
    draw_topbar(draw, "시장 요약")

    kospi    = sec.get("kospi_value", "")
    change   = sec.get("kospi_change", "")
    positive = sec.get("kospi_change_positive", True)
    points   = sec.get("points", [])

    cy = 100
    if kospi:
        draw.text((CX, cy), "KOSPI",
                  font=fnt(38, bold=False), fill=C["gold"], anchor="mm")
        cy += 56
        draw.text((CX, cy), kospi,
                  font=fnt(100, bold=True), fill=C["white"], anchor="mm")
        cy += 80
        if change:
            change_color = C["red"] if positive else C["blue"]
            draw.text((CX, cy), change,
                      font=fnt(56, bold=True), fill=change_color, anchor="mm")
            cy += 66
    else:
        cy += 80

    draw_divider(draw, cy)
    cy += 40

    for point in points[:5]:
        if cy >= Y_MAX - 20:
            break
        cy = draw_wrapped_text(
            draw, f"• {point}",
            MARGIN_X, cy, W - MARGIN_X * 2,
            size=36, bold=False, color=C["white"], line_gap=16
        )
        cy += 10

    draw_bottombar(draw)
    path = os.path.join(out_dir, "01_market_00.png")
    return [_save(img, path)]


# ── 업종 분석 ───────────────────────────────────────────────────────────────
def build_sector(data, out_dir):
    sec  = _find_section(data.get("sections", []), "sectors")
    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "업종 분석", color=C["blue"])

    sector_list = sec.get("sector_list", sec.get("sectors", sec.get("list", [])))

    cy = 100
    draw.text((CX, cy), "오늘의 주목 업종",
              font=fnt(52, bold=True), fill=C["white"], anchor="mm")
    cy += 20
    draw.line([CX - 200, cy + 20, CX + 200, cy + 20], fill=C["gold"], width=3)
    cy += 52

    palette = [C["gold"], C["green"], C["blue"], (220,100,220), C["red"], (100,220,220)]
    card_w  = (W - MARGIN_X * 2 - 40) // 2
    card_h  = 150

    for idx, sector in enumerate(sector_list[:6]):
        color = palette[idx % len(palette)]
        if isinstance(sector, dict):
            name = sector.get("name", "")
            desc = sector.get("desc", sector.get("description", ""))
        else:
            name = str(sector); desc = ""

        col    = idx % 2
        row    = idx // 2
        card_x = MARGIN_X + col * (card_w + 40)
        card_y = cy + row * (card_h + 20)
        if card_y + card_h > Y_MAX:
            break

        draw.rounded_rectangle(
            [card_x, card_y, card_x + card_w, card_y + card_h],
            radius=16, fill=C["card"])
        draw.rounded_rectangle(
            [card_x, card_y, card_x + 8, card_y + card_h],
            radius=4, fill=color)
        draw.text((card_x + 28, card_y + 18), name,
                  font=fnt(36, bold=True), fill=C["white"])
        if desc:
            draw_wrapped_text(draw, desc, card_x + 28, card_y + 70,
                              card_w - 50, size=27,
                              color=(180, 180, 200), line_gap=8)

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "02_sector.png"))


# ── 종목 요약 슬라이드 ──────────────────────────────────────────────────────
# 변경 6: 레이아웃 전면 개편
#   - 종목명: 좌상단 고정 (MARGIN_X, 90)
#   - 줄간격 대폭 확대 (시원시원한 편집)
#   - 투자 포인트 & 리스크: 화면 중간(cy ≈ H//2 - 60) 부터 시작
def _build_stock_summary(sec, out_path, img_dir):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    price      = sec.get("price", "")
    change     = sec.get("change", "")
    positive   = sec.get("change_positive", True)
    summary    = sec.get("summary", "")
    catalysts  = sec.get("catalysts", [])
    risks      = sec.get("risks", [])

    img  = new_frame()
    draw = ImageDraw.Draw(img)

    is_hidden = sec.get("id", "").startswith("hidden_")
    bar_color = C.get("hidden_accent", (80, 30, 120)) if is_hidden else None
    bar_label = "숨은 종목" if is_hidden else "종목 분석"
    draw_topbar(draw, f"{bar_label}: {stock_name}", color=bar_color)

    # 뉴스 이미지 — 우측 상단 (더 작게)
    img_path = fetch_news_image(stock_name, img_dir, [])
    if img_path:
        paste_image(img, img_path, (W - 360, 84, W - 60, 320))

    # ── 좌상단: 종목명 ────────────────────────────────────────────────────
    NAME_Y = 90
    draw.text((MARGIN_X, NAME_Y), stock_name,
              font=fnt(80, bold=True), fill=C["white"])

    # ── 종목명 아래 한줄 요약 ─────────────────────────────────────────────
    SUMMARY_Y = NAME_Y + 100
    if summary:
        draw_wrapped_text(draw, summary,
                          MARGIN_X, SUMMARY_Y,
                          W - 460,          # 이미지 영역 피하기
                          size=32, bold=False,
                          color=(180, 180, 210), line_gap=14)

    # ── 주가 + 등락률 ─────────────────────────────────────────────────────
    PRICE_Y = SUMMARY_Y + 90
    if price:
        draw.text((MARGIN_X, PRICE_Y), f"₩ {price}",
                  font=fnt(62, bold=True), fill=C["gold"])
        if change:
            try:
                px = MARGIN_X + int(draw.textlength(
                    f"₩ {price}", font=fnt(62, bold=True))) + 28
            except Exception:
                px = MARGIN_X + len(f"₩ {price}") * 34 + 28
            change_color = C["red"] if positive else C["blue"]
            draw.text((px, PRICE_Y + 12), change,
                      font=fnt(44, bold=True), fill=change_color)

    # ── 구분선 ───────────────────────────────────────────────────────────
    DIVIDER_Y = H // 2 - 30
    draw_divider(draw, DIVIDER_Y)

    # ── 투자 포인트 & 리스크: 화면 중간부터 시작 ─────────────────────────
    CARD_START_Y = DIVIDER_Y + 36
    half_w = (W - MARGIN_X * 2 - 80) // 2

    if catalysts:
        draw.text((MARGIN_X, CARD_START_Y), "투자 포인트",
                  font=fnt(36, bold=True), fill=C["red"])
        ty = CARD_START_Y + 56
        for c in catalysts[:4]:
            if ty >= Y_MAX - 10:
                break
            ty = draw_wrapped_text(draw, f"• {c}",
                                   MARGIN_X, ty,
                                   half_w, size=30, line_gap=18)

    if risks:
        rx = MARGIN_X + half_w + 80
        draw.text((rx, CARD_START_Y), "리스크",
                  font=fnt(36, bold=True), fill=C["blue"])
        ty = CARD_START_Y + 56
        for r in risks[:4]:
            if ty >= Y_MAX - 10:
                break
            ty = draw_wrapped_text(draw, f"• {r}",
                                   rx, ty,
                                   half_w, size=30, line_gap=18)

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 종목 차트 슬라이드 ──────────────────────────────────────────────────────
def _build_stock_chart(sec, out_path, img_dir):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")

    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"최근 2주 차트: {stock_name}", color=(20, 55, 30))

    briefing_chart = os.path.join(img_dir, f"briefing_chart_{stock_name}.png")
    if os.path.exists(briefing_chart):
        chart_path = briefing_chart
        print(f"  [chart] 브리핑 앱 차트 사용: {stock_name}")
    else:
        chart_path = build_chart_image(stock_name, img_dir)

    if chart_path:
        _paste_fill(img, chart_path, (0, 74, W, CHART_BOTTOM))
    else:
        draw.text((CX, H // 2), f"{stock_name} 차트 데이터 없음",
                  font=fnt(40), fill=(120, 120, 140), anchor="mm")

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 언급 슬라이드 ───────────────────────────────────────────────────────────
# 변경 1: quote_subtitle (문어체 요약) 사용 — 구어체 narration 미사용
def _build_mention_page(sec, out_path, page_idx):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    mentions   = sec.get("mentions", [])

    if mentions:
        page_mentions = mentions[page_idx * 3: page_idx * 3 + 3]
    else:
        # mentions 배열 없을 때 — subtitle_mention 계열 필드 사용 (문어체)
        if page_idx == 0:
            raw = sec.get("subtitle_mention_0", sec.get("subtitle_mention", ""))
        elif page_idx == 1:
            raw = sec.get("subtitle_mention_1", "")
        elif page_idx == 2:
            raw = sec.get("subtitle_mention_2", "")
        else:
            raw = sec.get("subtitle_mention", "")

        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [raw] if raw else []
        if len(paragraphs) == 1 and len(paragraphs[0]) > 100:
            sentences = re.split(r'(?<=[.。])\s*', paragraphs[0])
            sentences = [s.strip() for s in sentences if s.strip()]
            chunk = max(1, len(sentences) // 3)
            paragraphs = [" ".join(sentences[i:i+chunk])
                          for i in range(0, len(sentences), chunk)][:3]

        page_mentions = [
            {"speaker": "", "channel": stock_name,
             "quote_subtitle": p, "quote_narration": p}
            for p in paragraphs[:3]
        ]

    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"전문가 언급: {stock_name}", color=(40, 20, 60))

    cy     = 96
    n      = max(len(page_mentions), 1)
    card_h = min(260, (Y_MAX - cy - 20 * n) // n)

    for m in page_mentions:
        if cy >= Y_MAX:
            break
        if isinstance(m, str):
            m = {"speaker": "", "channel": "", "quote_subtitle": m}

        speaker = m.get("speaker", "").strip()
        channel = m.get("channel", m.get("source", "")).strip()
        # 헤더: "채널명 | 발화자" 또는 "채널명" 만
        header  = f"{channel} | {speaker}" if speaker else channel

        # ★ 화면 그래픽에는 quote_subtitle (문어체 요약) 사용
        content = m.get("quote_subtitle",
                   m.get("quote", m.get("content", "")))

        actual_h = min(card_h, Y_MAX - cy)
        draw.rounded_rectangle(
            [MARGIN_X, cy, W - MARGIN_X, cy + actual_h],
            radius=16, fill=C["card"])
        draw.rounded_rectangle(
            [MARGIN_X, cy, MARGIN_X + 8, cy + actual_h],
            radius=4, fill=C["gold"])

        draw.text((MARGIN_X + 28, cy + 18), header,
                  font=fnt(30, bold=True), fill=C["gold"])
        if content:
            draw_wrapped_text(draw, content,
                              MARGIN_X + 28, cy + 66,
                              W - MARGIN_X * 2 - 56,
                              size=30, color=C["white"], line_gap=14)
        cy += actual_h + 20

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


def build_stock_cards(sec, out_dir, img_dir, prefix):
    paths = [
        _build_stock_summary(
            sec, os.path.join(out_dir, f"{prefix}_1_summary.png"), img_dir),
        _build_stock_chart(
            sec, os.path.join(out_dir, f"{prefix}_2_chart.png"), img_dir),
    ]

    mentions = sec.get("mentions", [])
    if mentions:
        pages = max(1, (len(mentions) + 2) // 3)
    else:
        has_0 = bool(sec.get("narration_mention_0") or sec.get("subtitle_mention_0"))
        has_1 = bool(sec.get("narration_mention_1") or sec.get("subtitle_mention_1"))
        has_2 = bool(sec.get("narration_mention_2") or sec.get("subtitle_mention_2"))
        pages = 3 if has_2 else (2 if has_1 else 1)

    for p in range(pages):
        paths.append(
            _build_mention_page(
                sec,
                os.path.join(out_dir, f"{prefix}_3_mention_{p:02d}.png"),
                p)
        )
    return paths


# ── AI 전략 ─────────────────────────────────────────────────────────────────
def build_ai_strategy(data, out_dir):
    sec  = _find_section(data.get("sections", []), "ai_strategy")
    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "AI 투자 전략", color=(40, 20, 70))

    cy = 100
    draw.text((CX, cy), "AI 투자 전략 제안",
              font=fnt(56, bold=True), fill=C["white"], anchor="mm")
    cy += 16
    draw.line([CX - 220, cy + 20, CX + 220, cy + 20], fill=C["gold"], width=3)
    cy += 56

    bullet_points = sec.get("bullet_points",
                        sec.get("strategies", sec.get("items", [])))
    card_h = 110
    for bp in bullet_points[:6]:
        if cy + card_h > Y_MAX:
            break
        text = bp if isinstance(bp, str) else \
               bp.get("strategy", bp.get("content", str(bp)))
        draw.rounded_rectangle(
            [MARGIN_X, cy, W - MARGIN_X, cy + card_h],
            radius=14, fill=C["card"])
        if " — " in text:
            stock_part, strat_part = text.split(" — ", 1)
            draw.text((MARGIN_X + 30, cy + 16), stock_part.strip(),
                      font=fnt(32, bold=True), fill=C["gold"])
            draw_wrapped_text(draw, strat_part.strip(),
                              MARGIN_X + 30, cy + 58,
                              W - MARGIN_X * 2 - 60,
                              size=28, color=C["white"], line_gap=8)
        else:
            draw_wrapped_text(draw, text,
                              MARGIN_X + 30, cy + 26,
                              W - MARGIN_X * 2 - 60,
                              size=30, color=C["white"], line_gap=10)
        cy += card_h + 16

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "98_ai_strategy.png"))


# ── 클로징 ──────────────────────────────────────────────────────────────────
def build_closing(data, out_dir):
    sec  = _find_section(data.get("sections", []), "closing")
    img  = new_frame()
    draw = ImageDraw.Draw(img)

    for i in range(H):
        alpha = int(10 * (1 - i / H))
        draw.line([0, i, W, i], fill=(20 + alpha, 22 + alpha, 60 + alpha))

    cy = H // 2 - 120
    draw.text((CX, cy), "감사합니다",
              font=fnt(80, bold=True), fill=C["white"], anchor="mm")
    cy += 100
    draw.text((CX, cy), "성공적인 투자 되시길 바랍니다",
              font=fnt(40, bold=False), fill=C["gold"], anchor="mm")
    cy += 70
    draw.line([CX - 200, cy, CX + 200, cy], fill=C["gold"], width=2)
    cy += 30

    disclaimer = sec.get("disclaimer",
                         "본 영상은 AI를 통해 제작되었으며, 투자 결정은 직접 판단하시기 바랍니다.")
    for line in disclaimer.split("\\n"):
        if cy >= Y_MAX: break
        draw.text((CX, cy), line.strip(),
                  font=fnt(28, bold=False), fill=(150, 150, 170), anchor="mm")
        cy += 40

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "99_closing.png"))
