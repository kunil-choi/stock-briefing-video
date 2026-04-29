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

Y_MAX    = H - 80
MARGIN_X = 80
CX       = W // 2

# ── 자막 위치 상수 (전체 슬라이드 공통) ─────────────────────────────────────
# 하단 바(52px) 바로 위에 자막 바를 고정합니다.
# 모든 슬라이드(summary / chart / mention / market / sector 등)에서 동일 위치 사용.
SUBTITLE_H = 40          # 자막 배경 높이 (17px 폰트 기준 2줄까지 여유)
SUBTITLE_Y = H - 52 - SUBTITLE_H   # = 하단 바 상단 바로 위
CHART_BOTTOM = SUBTITLE_Y          # 차트 이미지는 자막 바 위까지만


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
    """box 영역에 이미지를 꽉 채워 붙임 (중앙 크롭)."""
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


def _draw_subtitle_bar(draw: ImageDraw.ImageDraw, text: str):
    """
    전체 슬라이드 공통 자막 바.

    위치: SUBTITLE_Y (하단 바 바로 위, 전 슬라이드 동일)
    폰트: 17px (34px의 50%)
    배경: 반투명 검정 (alpha 180)
    텍스트: subtitle 필드 원문 그대로 (자막용 표기 — 숫자·영문 원형 유지)
    줄바꿈: 한 줄이 max_w 초과 시 두 번째 줄로 이동
    """
    if not text:
        return

    # 반투명 배경
    overlay   = Image.new("RGBA", (W, SUBTITLE_H), (0, 0, 0, 180))
    base      = draw._image
    base_rgba = base.convert("RGBA")
    base_rgba.paste(overlay, (0, SUBTITLE_Y), overlay)
    merged    = Image.alpha_composite(base_rgba, Image.new("RGBA", base.size, (0, 0, 0, 0)))
    base.paste(merged.convert("RGB"))

    font  = fnt(17, bold=False)
    max_w = W - MARGIN_X * 2
    line1 = ""
    line2 = ""

    for ch in text:
        test = line1 + ch
        try:
            tw = int(draw.textlength(test, font=font))
        except Exception:
            tw = len(test) * 9
        if tw > max_w and line1:
            if not line2:
                line2 = ch
            else:
                line2 += ch
        else:
            line1 = test

    line_h = 19
    if line2:
        total_h = line_h * 2 + 2
        start_y = SUBTITLE_Y + (SUBTITLE_H - total_h) // 2
        draw.text((CX, start_y),               line1, font=font, fill=C["white"], anchor="mt")
        draw.text((CX, start_y + line_h + 2),  line2, font=font, fill=C["white"], anchor="mt")
    else:
        center_y = SUBTITLE_Y + (SUBTITLE_H - line_h) // 2
        draw.text((CX, center_y), line1, font=font, fill=C["white"], anchor="mt")


# ── 오프닝 ─────────────────────────────────────────────────────────────────
def build_opening(data, out_dir):
    sec      = _find_section(data.get("sections", []), "opening")
    img      = new_frame()
    draw     = ImageDraw.Draw(img)
    keywords = sec.get("keywords", [])
    date_str = data.get("date", "")

    for i in range(H):
        alpha = int(15 * (1 - i / H))
        draw.line([0, i, W, i], fill=(30 + alpha, 32 + alpha, 80 + alpha))

    cy = H // 2 - 160
    draw.text((CX, cy), "AI 증권 브리핑",
              font=fnt(80, bold=True), fill=C["white"], anchor="mm")
    cy += 100
    if date_str:
        draw.text((CX, cy), date_str,
                  font=fnt(42, bold=False), fill=C["gold"], anchor="mm")
        cy += 60
    draw.line([CX - 240, cy, CX + 240, cy], fill=C["gold"], width=3)
    cy += 40
    if keywords:
        total_w = sum(len(k) * 22 + 60 for k in keywords[:4]) + 20
        kx = (W - total_w) // 2
        for kw in keywords[:4]:
            kx = draw_badge(draw, kx, cy, kw, bg=C["tag_bg"], size=26)

    # 오프닝은 자막 없음 (로고 화면)
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
    # subtitle 필드: 자막용(숫자·영문 원형)
    subtitle_text = sec.get("subtitle", sec.get("narration", ""))

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
        if cy >= SUBTITLE_Y - 20:
            break
        cy = draw_wrapped_text(
            draw, f"• {point}",
            MARGIN_X, cy, W - MARGIN_X * 2,
            size=36, bold=False, color=C["white"], line_gap=16
        )
        cy += 10

    _draw_subtitle_bar(draw, subtitle_text)
    draw_bottombar(draw)
    path = os.path.join(out_dir, "01_market_00.png")
    return [_save(img, path)]


# ── 업종 분석 ───────────────────────────────────────────────────────────────
def build_sector(data, out_dir):
    sec  = _find_section(data.get("sections", []), "sectors")
    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "업종 분석", color=C["blue"])

    sector_list   = sec.get("sector_list", sec.get("sectors", sec.get("list", [])))
    subtitle_text = sec.get("subtitle", sec.get("narration", ""))

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
        if card_y + card_h > SUBTITLE_Y:
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

    _draw_subtitle_bar(draw, subtitle_text)
    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "02_sector.png"))


# ── 종목 요약 슬라이드 ──────────────────────────────────────────────────────
def _build_stock_summary(sec, out_path, img_dir):
    stock_name    = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    price         = sec.get("price", "")
    change        = sec.get("change", "")
    positive      = sec.get("change_positive", True)
    summary       = sec.get("summary", "")
    catalysts     = sec.get("catalysts", [])
    risks         = sec.get("risks", [])
    # 자막: subtitle_summary (자막용 표기)
    subtitle_text = sec.get("subtitle_summary", sec.get("subtitle", ""))

    img  = new_frame()
    draw = ImageDraw.Draw(img)

    is_hidden = sec.get("id", "").startswith("hidden_")
    bar_color = C.get("hidden_accent", (80, 30, 120)) if is_hidden else None
    bar_label = "숨은 종목" if is_hidden else "종목 분석"
    draw_topbar(draw, f"{bar_label}: {stock_name}", color=bar_color)

    img_path = fetch_news_image(stock_name, img_dir, [])
    if img_path:
        paste_image(img, img_path, (W - 480, 84, W - 44, 400))

    cy = 100
    draw.text((MARGIN_X, cy), stock_name,
              font=fnt(72, bold=True), fill=C["white"])
    cy += 86

    if summary:
        cy = draw_wrapped_text(draw, summary, MARGIN_X, cy,
                               W - 540, size=30,
                               color=(180, 180, 210), line_gap=10)
        cy += 8

    if price:
        draw.text((MARGIN_X, cy), f"₩ {price}",
                  font=fnt(56, bold=True), fill=C["gold"])
        if change:
            try:
                px = MARGIN_X + int(draw.textlength(
                    f"₩ {price}", font=fnt(56, bold=True))) + 24
            except Exception:
                px = MARGIN_X + len(f"₩ {price}") * 30 + 24
            change_color = C["red"] if positive else C["blue"]
            draw.text((px, cy + 10), change,
                      font=fnt(40, bold=True), fill=change_color)
        cy += 76

    draw_divider(draw, cy)
    cy += 28

    half_w = (W - MARGIN_X * 2 - 60) // 2
    if catalysts:
        draw.text((MARGIN_X, cy), "투자 포인트",
                  font=fnt(34, bold=True), fill=C["red"])
        ty = cy + 48
        for c in catalysts[:4]:
            if ty >= SUBTITLE_Y: break
            ty = draw_wrapped_text(draw, f"• {c}", MARGIN_X, ty,
                                   half_w, size=28, line_gap=8)
    if risks:
        rx = MARGIN_X + half_w + 60
        draw.text((rx, cy), "리스크",
                  font=fnt(34, bold=True), fill=C["blue"])
        ty = cy + 48
        for r in risks[:3]:
            if ty >= SUBTITLE_Y: break
            ty = draw_wrapped_text(draw, f"• {r}", rx, ty,
                                   half_w, size=28, line_gap=8)

    _draw_subtitle_bar(draw, subtitle_text)
    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 종목 차트 슬라이드 ──────────────────────────────────────────────────────
def _build_stock_chart(sec, out_path, img_dir):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    # 자막: subtitle_chart (자막용 표기), 차트와 겹치지 않는 SUBTITLE_Y 위치
    subtitle_text = sec.get("subtitle_chart", sec.get("subtitle", ""))

    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"최근 2주 차트: {stock_name}", color=(20, 55, 30))

    chart_path = build_chart_image(stock_name, img_dir)
    if chart_path:
        # 차트는 topbar(74px) ~ CHART_BOTTOM(= SUBTITLE_Y) 사이에만 배치
        # → 자막 바와 절대 겹치지 않음
        _paste_fill(img, chart_path, (0, 74, W, CHART_BOTTOM))
    else:
        draw.text((CX, H // 2), f"{stock_name} 차트 데이터 없음",
                  font=fnt(40), fill=(120, 120, 140), anchor="mm")

    _draw_subtitle_bar(draw, subtitle_text)
    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 언급 슬라이드 ───────────────────────────────────────────────────────────
def _build_mention_page(sec, out_path, page_idx):
    """
    채널별 언급 슬라이드.

    - 1페이지에 최대 3개 언급 카드를 표시합니다.
    - 4번째 언급부터는 다음 페이지(page_idx+1)에 표시됩니다.
    - 발화자(speaker)가 확인된 경우에만 카드 헤더에 표시합니다.
      확인되지 않으면 채널명만 표시합니다.
    - 자막: subtitle_mention/_0/_1 (자막용 표기)
    """
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    mentions   = sec.get("mentions", [])

    # ── 자막 텍스트 선택 (subtitle 계열 사용) ───────────────────────────
    if page_idx == 0:
        subtitle_text = sec.get("subtitle_mention_0",
                           sec.get("subtitle_mention", ""))
    elif page_idx == 1:
        subtitle_text = sec.get("subtitle_mention_1",
                           sec.get("subtitle_mention", ""))
    elif page_idx == 2:
        subtitle_text = sec.get("subtitle_mention_2",
                           sec.get("subtitle_mention", ""))
    else:
        subtitle_text = sec.get("subtitle_mention", "")

    # ── 이번 페이지에 표시할 3개 언급 항목 ──────────────────────────────
    if mentions:
        page_mentions = mentions[page_idx * 3: page_idx * 3 + 3]
    else:
        # mentions 배열 없음 → narration_mention 텍스트를 문단 분할
        if page_idx == 0:
            raw = sec.get("narration_mention_0", sec.get("narration_mention", ""))
        elif page_idx == 1:
            raw = sec.get("narration_mention_1", "")
        elif page_idx == 2:
            raw = sec.get("narration_mention_2", "")
        else:
            raw = sec.get("narration_mention", "")

        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [raw] if raw else []
        if len(paragraphs) == 1 and len(paragraphs[0]) > 120:
            sentences = paragraphs[0].replace("。", ".").split(". ")
            sentences = [s.strip() + ("." if not s.endswith(".") else "")
                         for s in sentences if s.strip()]
            chunk = max(1, len(sentences) // 3)
            paragraphs = [" ".join(sentences[i:i+chunk])
                          for i in range(0, len(sentences), chunk)][:3]

        page_mentions = [
            {"speaker": "", "channel": stock_name,
             "quote_subtitle": p, "quote_narration": p}
            for p in paragraphs[:3]
        ]

    # ── 슬라이드 렌더링 ──────────────────────────────────────────────────
    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"전문가 언급: {stock_name}", color=(40, 20, 60))

    cy     = 96
    n      = len(page_mentions)
    card_h = min(260, (SUBTITLE_Y - cy - 20 * max(n, 1)) // max(n, 1))

    for m in page_mentions:
        if cy >= SUBTITLE_Y:
            break
        if isinstance(m, str):
            m = {"speaker": "", "channel": "", "quote_subtitle": m, "quote_narration": m}

        # ── 발화자/채널 헤더 ─────────────────────────────────────────────
        speaker = m.get("speaker", "").strip()
        channel = m.get("channel", m.get("source", "")).strip()
        # speaker가 확인된 경우만 표시, 없으면 채널명만
        if speaker:
            header = f"{channel} | {speaker}"
        else:
            header = channel

        # 자막용 quote 우선 사용 (없으면 일반 quote fallback)
        content = m.get("quote_subtitle",
                   m.get("quote", m.get("report",
                   m.get("content", m.get("comment", "")))))

        actual_h = min(card_h, SUBTITLE_Y - cy)
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
                              size=30, color=C["white"], line_gap=12)
        cy += actual_h + 20

    _draw_subtitle_bar(draw, subtitle_text)
    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


def build_stock_cards(sec, out_dir, img_dir, prefix):
    """
    종목 1개에 대한 전체 슬라이드 생성:
      {prefix}_1_summary.png
      {prefix}_2_chart.png
      {prefix}_3_mention_00.png  (언급 1~3개)
      {prefix}_3_mention_01.png  (언급 4~6개일 때 추가)
      {prefix}_3_mention_02.png  (언급 7~9개일 때 추가)
    """
    paths = [
        _build_stock_summary(
            sec, os.path.join(out_dir, f"{prefix}_1_summary.png"), img_dir),
        _build_stock_chart(
            sec, os.path.join(out_dir, f"{prefix}_2_chart.png"), img_dir),
    ]

    mentions = sec.get("mentions", [])
    if mentions:
        # mentions 배열 기준으로 페이지 수 결정: 3개당 1페이지
        pages = max(1, (len(mentions) + 2) // 3)
    else:
        # narration_mention 계열 필드 유무로 페이지 수 결정
        has_0 = bool(sec.get("narration_mention_0") or sec.get("subtitle_mention_0"))
        has_1 = bool(sec.get("narration_mention_1") or sec.get("subtitle_mention_1"))
        has_2 = bool(sec.get("narration_mention_2") or sec.get("subtitle_mention_2"))
        if has_2:
            pages = 3
        elif has_1:
            pages = 2
        else:
            pages = 1

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

    subtitle_text = sec.get("subtitle", sec.get("narration", ""))

    cy = 100
    draw.text((CX, cy), "AI 전략 투자 제안",
              font=fnt(56, bold=True), fill=C["white"], anchor="mm")
    cy += 16
    draw.line([CX - 220, cy + 20, CX + 220, cy + 20], fill=C["gold"], width=3)
    cy += 56

    bullet_points = sec.get("bullet_points",
                        sec.get("strategies", sec.get("items", [])))
    card_h = 110
    for bp in bullet_points[:6]:
        if cy + card_h > SUBTITLE_Y:
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

    _draw_subtitle_bar(draw, subtitle_text)
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

    # 클로징은 자막 없음 (엔딩 화면)
    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "99_closing.png"))
