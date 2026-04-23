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
    """한국식: 상승=빨강, 하락=파랑"""
    raw = str(val)
    if "▼" in raw or raw.startswith("-"):
        return C["blue"]       # ← 하락: 파랑
    return C["red"]            # ← 상승: 빨강


def _paste_fill(img: Image.Image, path: str, box: tuple):
    """차트/이미지를 box 영역에 꽉 채워서 붙입니다 (비율 유지, 중앙 크롭)."""
    if not path or not os.path.isfile(path):
        return
    try:
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        src = Image.open(path).convert("RGB")
        scale = max(bw / src.width, bh / src.height)
        new_w = int(src.width  * scale)
        new_h = int(src.height * scale)
        src = src.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - bw) // 2
        top  = (new_h - bh) // 2
        src  = src.crop((left, top, left + bw, top + bh))
        img.paste(src, (box[0], box[1]))
    except Exception as e:
        print(f"[builders] 이미지 채우기 실패 ({path}): {e}")


# ── 오프닝 ──────────────────────────────────────────────────────────────────

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
    draw.text((CX, cy), "AI 주식 브리핑",
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

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "00_opening.png"))


# ── 시장 요약 ───────────────────────────────────────────────────────────────

def build_market_summary(data, out_dir):
    sec      = _find_section(data.get("sections", []), "market_summary")
    img      = new_frame()
    draw     = ImageDraw.Draw(img)
    draw_topbar(draw, "시장 개요")

    kospi    = sec.get("kospi_value", "")
    change   = sec.get("kospi_change", "")
    positive = sec.get("kospi_change_positive", True)
    points   = sec.get("points", [])

    cy = 110
    if kospi:
        draw.text((CX, cy), "KOSPI", font=fnt(36, bold=False),
                  fill=C["gold"], anchor="mm")
        cy += 52
        draw.text((CX, cy), kospi, font=fnt(96, bold=True),
                  fill=C["white"], anchor="mm")
        if change:
            # 한국식: 상승=빨강, 하락=파랑
            change_color = C["red"] if positive else C["blue"]
            cy += 72
            draw.text((CX, cy), change, font=fnt(52, bold=True),
                      fill=change_color, anchor="mm")
        cy += 56
    else:
        cy += 80

    draw_divider(draw, cy)
    cy += 32

    for point in points[:5]:
        if cy >= Y_MAX:
            break
        text = f"• {point}"
        cy = draw_wrapped_text(draw, text, MARGIN_X, cy,
                               W - MARGIN_X * 2, size=32,
                               bold=False, color=C["white"], line_gap=12)
        cy += 4

    draw_bottombar(draw)
    path = os.path.join(out_dir, "01_market_00.png")
    return [_save(img, path)]


# ── 섹터 ────────────────────────────────────────────────────────────────────

def build_sector(data, out_dir):
    sec  = _find_section(data.get("sections", []), "sectors")
    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "주목 섹터", color=C["blue"])

    sector_list = sec.get("sector_list", sec.get("sectors", sec.get("list", [])))

    cy = 100
    draw.text((CX, cy), "핵심 투자 섹터",
              font=fnt(52, bold=True), fill=C["white"], anchor="mm")
    cy += 20
    draw.line([CX - 200, cy + 20, CX + 200, cy + 20], fill=C["gold"], width=3)
    cy += 52

    palette = [C["gold"], C["red"], C["blue"],
               (220, 100, 220), (0, 230, 118), (100, 220, 220)]
    card_w  = (W - MARGIN_X * 2 - 40) // 2
    card_h  = 150

    for idx, sector in enumerate(sector_list[:6]):
        color = palette[idx % len(palette)]
        if isinstance(sector, dict):
            name = sector.get("name", "")
            desc = sector.get("desc", sector.get("description", ""))
        else:
            name = str(sector)
            desc = ""

        col    = idx % 2
        row    = idx // 2
        card_x = MARGIN_X + col * (card_w + 40)
        card_y = cy + row * (card_h + 20)
        if card_y + card_h > Y_MAX:
            break

        draw.rounded_rectangle(
            [card_x, card_y, card_x + card_w, card_y + card_h],
            radius=16, fill=C["card"]
        )
        draw.rounded_rectangle(
            [card_x, card_y, card_x + 8, card_y + card_h],
            radius=4, fill=color
        )
        draw.text((card_x + 28, card_y + 18),
                  name, font=fnt(36, bold=True), fill=C["white"])
        if desc:
            draw_wrapped_text(draw, desc, card_x + 28, card_y + 70,
                              card_w - 50, size=27,
                              color=(180, 180, 200), line_gap=8)

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "02_sector.png"))


# ── 종목 요약 화면 ───────────────────────────────────────────────────────────

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
    bar_label = "히든종목" if is_hidden else "종목 분석"
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
            # 한국식: 상승=빨강, 하락=파랑
            change_color = C["red"] if positive else C["blue"]
            draw.text((px, cy + 10), change,
                      font=fnt(40, bold=True), fill=change_color)
        cy += 76

    draw_divider(draw, cy)
    cy += 28

    half_w = (W - MARGIN_X * 2 - 60) // 2

    if catalysts:
        # 투자 포인트 라벨: 한국식 상승색(빨강)
        draw.text((MARGIN_X, cy), "투자 포인트",
                  font=fnt(34, bold=True), fill=C["red"])
        ty = cy + 48
        for c in catalysts[:4]:
            if ty >= Y_MAX:
                break
            ty = draw_wrapped_text(draw, f"• {c}", MARGIN_X, ty,
                                   half_w, size=28, line_gap=8)

    if risks:
        rx = MARGIN_X + half_w + 60
        # 리스크 라벨: 한국식 하락색(파랑)
        draw.text((rx, cy), "리스크",
                  font=fnt(34, bold=True), fill=C["blue"])
        ty = cy + 48
        for r in risks[:3]:
            if ty >= Y_MAX:
                break
            ty = draw_wrapped_text(draw, f"• {r}", rx, ty,
                                   half_w, size=28, line_gap=8)

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 종목 차트 화면 ───────────────────────────────────────────────────────────

def _build_stock_chart(sec, out_path, img_dir):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    img        = new_frame()
    draw       = ImageDraw.Draw(img)
    draw_topbar(draw, f"최근 2주 차트: {stock_name}", color=(20, 55, 30))

    chart_path = build_chart_image(stock_name, img_dir)
    if chart_path:
        _paste_fill(img, chart_path, (MARGIN_X, 84, W - MARGIN_X, H - 62))
    else:
        draw.text((CX, H // 2), f"{stock_name} 차트 데이터 없음",
                  font=fnt(40), fill=(120, 120, 140), anchor="mm")

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 전문가 멘션 화면 ─────────────────────────────────────────────────────────

def _build_mention_page(sec, out_path, page_idx):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    mentions   = sec.get("mentions", [])

    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"전문가 멘션: {stock_name}", color=(40, 20, 60))

    if not mentions:
        narration = sec.get("narration_mention", sec.get("narration", ""))
        mentions  = [{"source": "브리핑 요약", "reporter": "",
                      "quote": narration}] if narration else []

    cy            = 96
    page_mentions = mentions[page_idx * 3: page_idx * 3 + 3]
    n             = len(page_mentions)
    card_h        = min(260, (Y_MAX - cy - 20 * n) // max(n, 1))

    for m in page_mentions:
        if cy >= Y_MAX:
            break
        if isinstance(m, str):
            m = {"source": "", "reporter": "", "quote": m}

        source   = m.get("source",   m.get("channel",  ""))
        reporter = m.get("reporter", m.get("analyst",   m.get("speaker", "")))
        content  = m.get("quote",    m.get("report",    m.get("content",
                         m.get("comment", ""))))

        actual_h = min(card_h, Y_MAX - cy)
        draw.rounded_rectangle(
            [MARGIN_X, cy, W - MARGIN_X, cy + actual_h],
            radius=16, fill=C["card"]
        )
        draw.rounded_rectangle(
            [MARGIN_X, cy, MARGIN_X + 8, cy + actual_h],
            radius=4, fill=C["gold"]
        )

        header = source + (f"  |  {reporter}" if reporter else "")
        draw.text((MARGIN_X + 28, cy + 18), header,
                  font=fnt(30, bold=True), fill=C["gold"])
        if content:
            draw_wrapped_text(draw, content,
                              MARGIN_X + 28, cy + 66,
                              W - MARGIN_X * 2 - 56,
                              size=30, color=C["white"], line_gap=12)
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
    pages    = max(1, (len(mentions) + 2) // 3)
    for p in range(pages):
        paths.append(
            _build_mention_page(
                sec, os.path.join(out_dir, f"{prefix}_3_mention_{p:02d}.png"), p)
        )
    return paths


# ── AI 전략 ─────────────────────────────────────────────────────────────────

def build_ai_strategy(data, out_dir):
    sec  = _find_section(data.get("sections", []), "ai_strategy")
    img  = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "AI 투자 전략", color=(40, 20, 70))

    cy = 100
    draw.text((CX, cy), "AI 분석 종합 전략",
              font=fnt(56, bold=True), fill=C["white"], anchor="mm")
    cy += 16
    draw.line([CX - 220, cy + 20, CX + 220, cy + 20], fill=C["gold"], width=3)
    cy += 56

    bullet_points = sec.get("bullet_points",
                    sec.get("strategies",
                    sec.get("items", [])))
    card_h = 110

    for bp in bullet_points[:6]:
        if cy + card_h > Y_MAX:
            break
        text = bp if isinstance(bp, str) else \
               bp.get("strategy", bp.get("content", str(bp)))

        draw.rounded_rectangle(
            [MARGIN_X, cy, W - MARGIN_X, cy + card_h],
            radius=14, fill=C["card"]
        )
        if " — " in text:
            stock_part, strat_part = text.split(" — ", 1)
            draw.text((MARGIN_X + 30, cy + 16),
                      stock_part.strip(),
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
    draw.text((CX, cy), "구독과 좋아요는 큰 힘이 됩니다",
              font=fnt(40, bold=False), fill=C["gold"], anchor="mm")
    cy += 70
    draw.line([CX - 200, cy, CX + 200, cy], fill=C["gold"], width=2)
    cy += 30

    disclaimer = sec.get("disclaimer",
                          "본 영상은 AI가 생성한 참고용 정보이며, 투자 권유가 아닙니다.")
    for line in disclaimer.split("\\n"):
        if cy >= Y_MAX:
            break
        draw.text((CX, cy), line.strip(),
                  font=fnt(28, bold=False), fill=(150, 150, 170), anchor="mm")
        cy += 40

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "99_closing.png"))
