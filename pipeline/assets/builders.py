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
        return C["red"]
    return C["green"]


# ── 오프닝 ──────────────────────────────────────────────────────────────────

def build_opening(data, out_dir):
    sec = _find_section(data.get("sections", []), "opening")
    img = new_frame()
    draw = ImageDraw.Draw(img)

    for i in range(H):
        alpha = int(15 * (1 - i / H))
        draw.line([0, i, W, i], fill=(30 + alpha, 32 + alpha, 80 + alpha))

    title = sec.get("narration", data.get("title", "AI 주식 브리핑")).split(".")[0]
    date_str = data.get("date", "")
    keywords = sec.get("keywords", [])

    cy = H // 2 - 130
    draw.text((W // 2, cy), "📊", font=fnt(80), fill=C["gold"], anchor="mm")
    cy += 110
    draw.text((W // 2, cy), data.get("title", "AI 주식 브리핑"),
              font=fnt(64, bold=True), fill=C["white"], anchor="mm")
    cy += 84
    if date_str:
        draw.text((W // 2, cy), date_str,
                  font=fnt(36, bold=False), fill=C["gold"], anchor="mm")
    cy += 56
    draw.line([W // 2 - 200, cy, W // 2 + 200, cy], fill=C["gold"], width=3)
    cy += 32

    # 키워드 뱃지
    if keywords:
        total_w = sum(len(k) * 22 + 60 for k in keywords[:4]) + 20
        kx = (W - total_w) // 2
        for kw in keywords[:4]:
            kx = draw_badge(draw, kx, cy, kw, bg=C["tag_bg"], size=24)

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "00_opening.png"))


# ── 시장 요약 ───────────────────────────────────────────────────────────────

def build_market_summary(data, out_dir):
    sec = _find_section(data.get("sections", []), "market_summary")
    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "📈 시장 개요")

    y = 110
    # ── KOSPI: 실제 키는 kospi_value / kospi_change ──────────────────────
    kospi = sec.get("kospi_value", "")
    change = sec.get("kospi_change", "")
    positive = sec.get("kospi_change_positive", True)

    if kospi:
        draw.text((60, y), "KOSPI", font=fnt(36, bold=False), fill=C["gold"])
        y += 50
        draw.text((60, y), kospi, font=fnt(72, bold=True), fill=C["white"])
        if change:
            try:
                cx = 60 + int(draw.textlength(kospi, font=fnt(72, bold=True))) + 20
            except Exception:
                cx = 60 + len(kospi) * 40 + 20
            change_color = C["green"] if positive else C["red"]
            draw.text((cx, y + 20), change, font=fnt(40, bold=True), fill=change_color)
        y += 100

    draw_divider(draw, y)
    y += 24

    # ── 내레이션 요약 (첫 문장만) ────────────────────────────────────────
    narration = sec.get("narration", "")
    if narration:
        first_sentence = narration.split(".")[0] + "."
        y = draw_wrapped_text(draw, first_sentence, 60, y, W - 120, size=32, line_gap=14)
        y += 8

    # ── 포인트: 실제 키는 points ─────────────────────────────────────────
    points = sec.get("points", [])
    for point in points[:5]:
        draw.ellipse([60, y + 12, 76, y + 28], fill=C["gold"])
        y = draw_wrapped_text(draw, str(point), 96, y, W - 160, size=30, line_gap=10)

    draw_bottombar(draw)
    path = os.path.join(out_dir, "01_market_00.png")
    return [_save(img, path)]


# ── 섹터 ────────────────────────────────────────────────────────────────────

def build_sector(data, out_dir):
    sec = _find_section(data.get("sections", []), "sectors")
    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "🔍 주목 섹터", color=C["blue"])

    y = 130
    gold_underline(draw, 60, y, "핵심 투자 섹터", size=48)
    y += 90

    # ── 실제 키는 sector_list ────────────────────────────────────────────
    sector_list = sec.get("sector_list", sec.get("sectors", sec.get("list", [])))

    palette = [C["gold"], C["green"], C["blue"], (220, 100, 220), C["red"], (100, 220, 220)]
    for idx, sector in enumerate(sector_list[:6]):
        color = palette[idx % len(palette)]
        if isinstance(sector, dict):
            name = sector.get("name", "")
            desc = sector.get("desc", sector.get("description", ""))
            icon = sector.get("icon", "")
        else:
            name = str(sector)
            desc = ""
            icon = ""

        card_x = 60 + (idx % 2) * (W // 2)
        card_y = y + (idx // 2) * 168
        draw.rounded_rectangle(
            [card_x, card_y, card_x + W // 2 - 80, card_y + 138],
            radius=16, fill=C["card"]
        )
        draw.rounded_rectangle(
            [card_x, card_y, card_x + 8, card_y + 138],
            radius=4, fill=color
        )
        label = f"{icon} {name}" if icon else name
        draw.text((card_x + 28, card_y + 18), label,
                  font=fnt(34, bold=True), fill=C["white"])
        if desc:
            draw_wrapped_text(draw, desc, card_x + 28, card_y + 68,
                              W // 2 - 120, size=26, color=(180, 180, 200))

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "02_sector.png"))


# ── 종목 카드 ────────────────────────────────────────────────────────────────

def _build_stock_summary(sec, out_path, img_dir):
    # ── GPT 생성 JSON: data 서브키 없음, 최상위 레벨에 바로 있음 ──────────
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    price   = sec.get("price", "")
    change  = sec.get("change", "")
    positive = sec.get("change_positive", True)
    summary  = sec.get("summary", "")
    catalysts = sec.get("catalysts", [])
    risks     = sec.get("risks", [])

    img = new_frame()
    draw = ImageDraw.Draw(img)
    is_hidden = sec.get("id", "").startswith("hidden_")
    bar_color = C.get("hidden_accent", (80, 30, 120)) if is_hidden else None
    draw_topbar(draw, f"{'🔒 히든종목' if is_hidden else '📌 종목 분석'}: {stock_name}",
                color=bar_color)

    # 뉴스 이미지 (우측)
    img_path = fetch_news_image(stock_name, img_dir, [])
    if img_path:
        paste_image(img, img_path, (W - 520, 84, W - 44, 460))

    y = 110
    draw.text((60, y), stock_name, font=fnt(56, bold=True), fill=C["white"])
    y += 68

    if summary:
        y = draw_wrapped_text(draw, summary, 60, y, W - 580, size=28,
                              bold=False, color=(180, 180, 210), line_gap=8)
        y += 4

    if price:
        draw.text((60, y), f"₩ {price}", font=fnt(48, bold=True), fill=C["gold"])
        if change:
            try:
                cx = 60 + int(draw.textlength(f"₩ {price}", font=fnt(48, bold=True))) + 20
            except Exception:
                cx = 60 + len(f"₩ {price}") * 26 + 20
            change_color = C["green"] if positive else C["red"]
            draw.text((cx, y + 6), change, font=fnt(36, bold=True), fill=change_color)
        y += 68

    draw_divider(draw, y)
    y += 24

    # 촉매
    if catalysts:
        draw.text((60, y), "📈 투자 포인트", font=fnt(32, bold=True), fill=C["green"])
        y += 46
        for c in catalysts[:4]:
            y = draw_wrapped_text(draw, f"• {c}", 80, y, W - 600, size=27, line_gap=8)

    y += 12
    # 리스크
    if risks:
        draw.text((60, y), "⚠️ 리스크", font=fnt(32, bold=True), fill=C["red"])
        y += 46
        for r in risks[:3]:
            y = draw_wrapped_text(draw, f"• {r}", 80, y, W - 600, size=27, line_gap=8)

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


def _build_stock_chart(sec, out_path, img_dir):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"📊 최근 2주 차트: {stock_name}", color=(20, 55, 30))

    chart_path = build_chart_image(stock_name, img_dir)
    if chart_path:
        paste_image(img, chart_path, (60, 90, W - 60, H - 80))
    else:
        draw.text((W // 2, H // 2), f"{stock_name} 차트 데이터 없음",
                  font=fnt(36), fill=(120, 120, 140), anchor="mm")

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


def _build_mention_page(sec, out_path, page_idx):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    mentions = sec.get("mentions", [])

    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"💬 전문가 멘션: {stock_name}", color=(40, 20, 60))

    if not mentions:
        narration = sec.get("narration", "")
        mentions = [{"source": "브리핑 요약", "reporter": "", "quote": narration}] if narration else []

    y = 110
    page_mentions = mentions[page_idx * 3: page_idx * 3 + 3]

    for m in page_mentions:
        if isinstance(m, str):
            m = {"source": "", "reporter": "", "quote": m}

        source   = m.get("source", m.get("channel", ""))
        reporter = m.get("reporter", m.get("analyst", m.get("speaker", "")))
        # ── 실제 키는 quote ──────────────────────────────────────────────
        content  = m.get("quote", m.get("report", m.get("content", m.get("comment", ""))))

        card_h = 210
        draw.rounded_rectangle([60, y, W - 60, y + card_h], radius=14, fill=C["card"])
        draw.rounded_rectangle([60, y, 68, y + card_h], radius=4, fill=C["gold"])

        header = f"📺 {source}" + (f"  |  {reporter}" if reporter else "")
        draw.text((90, y + 16), header, font=fnt(28, bold=True), fill=C["gold"])
        if content:
            draw_wrapped_text(draw, content, 90, y + 60, W - 160, size=28,
                              color=C["white"], line_gap=10)
        y += card_h + 20

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


def build_stock_cards(sec, out_dir, img_dir, prefix):
    paths = [
        _build_stock_summary(sec, os.path.join(out_dir, f"{prefix}_1_summary.png"), img_dir),
        _build_stock_chart(sec, os.path.join(out_dir, f"{prefix}_2_chart.png"), img_dir),
    ]
    mentions = sec.get("mentions", [])
    pages = max(1, (len(mentions) + 2) // 3)
    for p in range(pages):
        paths.append(
            _build_mention_page(sec, os.path.join(out_dir, f"{prefix}_3_mention_{p:02d}.png"), p)
        )
    return paths


# ── AI 전략 ─────────────────────────────────────────────────────────────────

def build_ai_strategy(data, out_dir):
    sec = _find_section(data.get("sections", []), "ai_strategy")
    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "🤖 AI 투자 전략", color=(40, 20, 70))

    y = 110
    gold_underline(draw, 60, y, "AI 분석 종합 전략", size=48)
    y += 90

    # ── 실제 키는 bullet_points ──────────────────────────────────────────
    bullet_points = sec.get("bullet_points", sec.get("strategies", sec.get("items", [])))

    for bp in bullet_points[:6]:
        text = bp if isinstance(bp, str) else bp.get("strategy", bp.get("content", str(bp)))
        draw.rounded_rectangle([60, y, W - 60, y + 100], radius=12, fill=C["card"])

        # "종목명 — 전략" 형식 파싱
        if " — " in text:
            stock_part, strat_part = text.split(" — ", 1)
            draw.text((90, y + 14), stock_part.strip(),
                      font=fnt(28, bold=True), fill=C["gold"])
            draw_wrapped_text(draw, strat_part.strip(), 90, y + 50,
                              W - 160, size=26, color=C["white"])
        else:
            draw_wrapped_text(draw, text, 90, y + 22, W - 160, size=27, color=C["white"])
        y += 114

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "98_ai_strategy.png"))


# ── 클로징 ──────────────────────────────────────────────────────────────────

def build_closing(data, out_dir):
    sec = _find_section(data.get("sections", []), "closing")
    img = new_frame()
    draw = ImageDraw.Draw(img)

    for i in range(H):
        alpha = int(10 * (1 - i / H))
        draw.line([0, i, W, i], fill=(20 + alpha, 22 + alpha, 60 + alpha))

    cy = H // 2 - 110
    draw.text((W // 2, cy), "감사합니다",
              font=fnt(72, bold=True), fill=C["white"], anchor="mm")
    cy += 90
    draw.text((W // 2, cy), "구독과 좋아요는 큰 힘이 됩니다 🙏",
              font=fnt(36, bold=False), fill=C["gold"], anchor="mm")
    cy += 64
    disclaimer = sec.get("disclaimer",
                          "본 영상은 AI가 생성한 참고용 정보이며, 투자 권유가 아닙니다.")
    # disclaimer 줄바꿈 처리
    for line in disclaimer.split("\\n"):
        draw.text((W // 2, cy), line.strip(),
                  font=fnt(26, bold=False), fill=(150, 150, 170), anchor="mm")
        cy += 36

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "99_closing.png"))
