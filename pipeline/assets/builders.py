# pipeline/assets/builders.py
"""
script.json의 sections 배열 구조에 맞춰 각 프레임을 생성합니다.
sections[i] 구조:
  {
    "id": "opening" | "market_overview" | "sector_analysis"
         | "stock_삼성전자" | "hidden_크래프톤"
         | "ai_strategy" | "closing",
    "label": "...",
    "narration": "...",
    "data": { ... }   ← 섹션별 데이터
  }
"""
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


# ── 내부 헬퍼 ──────────────────────────────────────────────────────────────

def _save(img: Image.Image, path: str) -> str:
    img.save(path)
    print(f"  ✅ {os.path.basename(path)}")
    return path


def _section_by_id(sections: list, id_prefix: str) -> dict | None:
    for s in sections:
        if s.get("id", "").startswith(id_prefix):
            return s
    return None


def _sections_by_prefix(sections: list, prefix: str) -> list:
    return [s for s in sections if s.get("id", "").startswith(prefix)]


def _color_change(val) -> tuple:
    """변동값에 따라 색상 반환"""
    try:
        v = float(str(val).replace(",", "").replace("%", "").replace("▲","").replace("▼","").replace("+","").replace("-",""))
        raw = str(val)
        if "▼" in raw or (raw.startswith("-") and v != 0):
            return C["red"]
    except Exception:
        pass
    return C["green"]


# ── 오프닝 ──────────────────────────────────────────────────────────────────

def build_opening(data: dict, out_dir: str) -> str:
    sections = data.get("sections", [])
    sec = _section_by_id(sections, "opening") or {}
    d = sec.get("data", {})

    img = new_frame()
    draw = ImageDraw.Draw(img)

    # 배경 그라데이션 효과 (수평 바)
    for i in range(H):
        alpha = int(15 * (1 - i / H))
        draw.line([0, i, W, i], fill=(30 + alpha, 32 + alpha, 80 + alpha))

    # 중앙 타이틀
    title = d.get("title", data.get("title", "AI 주식 브리핑"))
    date_str = d.get("date", data.get("date", ""))

    cy = H // 2 - 120
    draw.text((W // 2, cy), "📊", font=fnt(80, bold=True), fill=C["gold"], anchor="mm")
    cy += 110
    draw.text((W // 2, cy), title, font=fnt(64, bold=True), fill=C["white"], anchor="mm")
    cy += 80
    if date_str:
        draw.text((W // 2, cy), date_str, font=fnt(36, bold=False), fill=C["gold"], anchor="mm")
    cy += 60
    draw.line([W // 2 - 200, cy, W // 2 + 200, cy], fill=C["gold"], width=3)

    draw_bottombar(draw)
    path = os.path.join(out_dir, "00_opening.png")
    return _save(img, path)


# ── 시장 개요 ───────────────────────────────────────────────────────────────

def build_market_summary(data: dict, out_dir: str) -> list:
    sections = data.get("sections", [])
    market_secs = _sections_by_prefix(sections, "market")
    if not market_secs:
        # 단일 market_overview 섹션
        sec = _section_by_id(sections, "market") or {}
        market_secs = [sec] if sec else []

    paths = []
    for i, sec in enumerate(market_secs):
        d = sec.get("data", {})
        img = new_frame()
        draw = ImageDraw.Draw(img)
        draw_topbar(draw, "📈 시장 개요")

        y = 110
        # KOSPI 수치
        kospi = d.get("kospi", d.get("index", ""))
        change = d.get("change", d.get("change_pct", ""))
        if kospi:
            draw.text((60, y), "KOSPI", font=fnt(36, bold=False), fill=C["gold"])
            y += 50
            draw.text((60, y), str(kospi), font=fnt(72, bold=True), fill=C["white"])
            if change:
                cx = 60 + int(draw.textlength(str(kospi), font=fnt(72, bold=True))) + 20
                draw.text((cx, y + 20), str(change), font=fnt(40, bold=True), fill=_color_change(change))
            y += 100

        draw_divider(draw, y)
        y += 24

        # 요약 텍스트
        summary = d.get("summary", sec.get("narration", ""))
        if summary:
            y = draw_wrapped_text(draw, summary, 60, y, W - 120, size=34, line_gap=14)

        # 불릿 포인트
        bullets = d.get("bullets", d.get("highlights", []))
        for bullet in bullets[:5]:
            y += 10
            draw.ellipse([60, y + 12, 76, y + 28], fill=C["gold"])
            y = draw_wrapped_text(draw, str(bullet), 96, y, W - 160, size=30, line_gap=10)

        draw_bottombar(draw)
        fname = f"01_market_{i:02d}.png"
        paths.append(_save(img, os.path.join(out_dir, fname)))

    if not paths:
        # 빈 placeholder
        img = new_frame()
        draw = ImageDraw.Draw(img)
        draw_topbar(draw, "📈 시장 개요")
        draw.text((W // 2, H // 2), "시장 데이터 없음", font=fnt(40), fill=C["white"], anchor="mm")
        draw_bottombar(draw)
        path = os.path.join(out_dir, "01_market_00.png")
        paths.append(_save(img, path))

    return paths


# ── 섹터 ────────────────────────────────────────────────────────────────────

def build_sector(data: dict, out_dir: str) -> str:
    sections = data.get("sections", [])
    sec = _section_by_id(sections, "sector") or {}
    d = sec.get("data", {})

    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "🔍 주목 섹터", color=C["blue"])

    y = 130
    gold_underline(draw, 60, y, "핵심 투자 섹터", size=48)
    y += 90

    sectors = d.get("sectors", d.get("list", []))
    if not sectors and "narration" in sec:
        # narration에서 섹터 추출 시도
        lines = [l.strip() for l in sec["narration"].split("\n") if l.strip()]
        sectors = lines[:6]

    colors = [C["gold"], C["green"], C["blue"], (220, 100, 220), C["red"], (100, 220, 220)]
    for idx, sector in enumerate(sectors[:6]):
        color = colors[idx % len(colors)]
        if isinstance(sector, dict):
            name = sector.get("name", str(sector))
            desc = sector.get("description", sector.get("desc", ""))
        else:
            name = str(sector)
            desc = ""

        # 섹터 카드
        card_x, card_y = 60 + (idx % 2) * (W // 2), y + (idx // 2) * 160
        draw.rounded_rectangle(
            [card_x, card_y, card_x + W // 2 - 80, card_y + 130],
            radius=16, fill=C["card"]
        )
        draw.rounded_rectangle(
            [card_x, card_y, card_x + 8, card_y + 130],
            radius=4, fill=color
        )
        draw.text((card_x + 28, card_y + 18), name, font=fnt(34, bold=True), fill=C["white"])
        if desc:
            draw_wrapped_text(draw, desc, card_x + 28, card_y + 64, W // 2 - 120, size=26, color=(180, 180, 200))

    draw_bottombar(draw)
    path = os.path.join(out_dir, "02_sector.png")
    return _save(img, path)


# ── 종목 카드 ────────────────────────────────────────────────────────────────

def _build_stock_summary(sec: dict, out_path: str, img_dir: str) -> str:
    d = sec.get("data", {})
    stock_name = d.get("name", sec.get("id", "").replace("stock_", "").replace("hidden_", ""))

    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"📌 종목 분석: {stock_name}")

    # 뉴스 이미지 (우측)
    img_path = fetch_news_image(stock_name, img_dir, d.get("image_urls", []))
    if img_path:
        paste_image(img, img_path, (W - 520, 80, W - 40, 480))

    y = 110
    # 종목명 + 가격
    draw.text((60, y), stock_name, font=fnt(56, bold=True), fill=C["white"])
    y += 70
    price = d.get("price", d.get("current_price", ""))
    change = d.get("change", d.get("change_pct", ""))
    if price:
        draw.text((60, y), f"₩{price}", font=fnt(48, bold=True), fill=C["gold"])
        if change:
            cx = 60 + int(draw.textlength(f"₩{price}", font=fnt(48, bold=True))) + 20
            draw.text((cx, y + 4), str(change), font=fnt(36, bold=True), fill=_color_change(change))
    y += 70

    draw_divider(draw, y)
    y += 24

    # 촉매
    catalysts = d.get("catalysts", d.get("catalyst", []))
    if catalysts:
        draw.text((60, y), "📈 투자 포인트", font=fnt(34, bold=True), fill=C["green"])
        y += 48
        if isinstance(catalysts, str):
            catalysts = [catalysts]
        for c in catalysts[:3]:
            y = draw_wrapped_text(draw, f"• {c}", 80, y, W - 620, size=28, line_gap=8)

    y += 16
    # 리스크
    risks = d.get("risks", d.get("risk", []))
    if risks:
        draw.text((60, y), "⚠️ 리스크", font=fnt(34, bold=True), fill=C["red"])
        y += 48
        if isinstance(risks, str):
            risks = [risks]
        for r in risks[:3]:
            y = draw_wrapped_text(draw, f"• {r}", 80, y, W - 620, size=28, line_gap=8)

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


def _build_stock_chart(sec: dict, out_path: str, img_dir: str) -> str:
    d = sec.get("data", {})
    stock_name = d.get("name", sec.get("id", "").replace("stock_", "").replace("hidden_", ""))

    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"📊 최근 2주 차트: {stock_name}", color=(30, 60, 30))

    chart_path = build_chart_image(stock_name, img_dir)
    if chart_path:
        paste_image(img, chart_path, (60, 90, W - 60, H - 80))
    else:
        draw.text((W // 2, H // 2), f"{stock_name} 차트 데이터 없음",
                  font=fnt(36), fill=(120, 120, 140), anchor="mm")

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


def _build_mention_page(sec: dict, out_path: str, page_idx: int) -> str:
    d = sec.get("data", {})
    stock_name = d.get("name", sec.get("id", "").replace("stock_", "").replace("hidden_", ""))

    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"💬 전문가 멘션: {stock_name}", color=(40, 20, 60))

    mentions = d.get("mentions", d.get("channel_mentions", []))
    if not mentions:
        # narration을 멘션으로 사용
        narration = sec.get("narration", "")
        if narration:
            mentions = [{"channel": "브리핑", "speaker": "", "content": narration}]

    y = 110
    for m in mentions[page_idx * 3: page_idx * 3 + 3]:
        if isinstance(m, str):
            m = {"channel": "", "speaker": "", "content": m}
        channel = m.get("channel", m.get("source", ""))
        speaker = m.get("speaker", m.get("expert", ""))
        content = m.get("content", m.get("comment", str(m)))

        # 멘션 카드
        card_h = 200
        draw.rounded_rectangle([60, y, W - 60, y + card_h], radius=14, fill=C["card"])
        draw.rounded_rectangle([60, y, 68, y + card_h], radius=4, fill=C["gold"])
        header = f"📺 {channel}" + (f"  |  {speaker}" if speaker else "")
        draw.text((90, y + 16), header, font=fnt(28, bold=True), fill=C["gold"])
        draw_wrapped_text(draw, content, 90, y + 56, W - 160, size=28, color=C["white"])
        y += card_h + 20

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


def build_stock_cards(sec: dict, out_dir: str, img_dir: str, prefix: str) -> list:
    paths = []
    paths.append(_build_stock_summary(sec, os.path.join(out_dir, f"{prefix}_1_summary.png"), img_dir))
    paths.append(_build_stock_chart(sec, os.path.join(out_dir, f"{prefix}_2_chart.png"), img_dir))

    d = sec.get("data", {})
    mentions = d.get("mentions", d.get("channel_mentions", []))
    if not mentions:
        mentions = [sec.get("narration", "")]
    pages = max(1, (len(mentions) + 2) // 3)
    for p in range(pages):
        paths.append(
            _build_mention_page(sec, os.path.join(out_dir, f"{prefix}_3_mention_{p:02d}.png"), p)
        )
    return paths


# ── AI 전략 ─────────────────────────────────────────────────────────────────

def build_ai_strategy(data: dict, out_dir: str) -> str:
    sections = data.get("sections", [])
    sec = _section_by_id(sections, "ai_strategy") or _section_by_id(sections, "strategy") or {}
    d = sec.get("data", {})

    img = new_frame()
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "🤖 AI 투자 전략", color=(40, 20, 70))

    y = 110
    gold_underline(draw, 60, y, "AI 분석 종합 전략", size=48)
    y += 90

    strategies = d.get("strategies", d.get("items", []))
    if not strategies and "narration" in sec:
        strategies = [{"stock": "종합", "strategy": sec["narration"]}]

    for strat in strategies[:6]:
        if isinstance(strat, str):
            strat = {"stock": "", "strategy": strat}
        stock = strat.get("stock", strat.get("name", ""))
        strategy = strat.get("strategy", strat.get("content", strat.get("description", "")))

        draw.rounded_rectangle([60, y, W - 60, y + 110], radius=12, fill=C["card"])
        if stock:
            draw.text((90, y + 14), stock, font=fnt(30, bold=True), fill=C["gold"])
        draw_wrapped_text(draw, strategy, 90, y + 52, W - 160, size=27, color=C["white"])
        y += 124

    draw_bottombar(draw)
    path = os.path.join(out_dir, "98_ai_strategy.png")
    return _save(img, path)


# ── 클로징 ──────────────────────────────────────────────────────────────────

def build_closing(data: dict, out_dir: str) -> str:
    sections = data.get("sections", [])
    sec = _section_by_id(sections, "closing") or {}
    d = sec.get("data", {})

    img = new_frame()
    draw = ImageDraw.Draw(img)

    cy = H // 2 - 100
    draw.text((W // 2, cy), "감사합니다", font=fnt(72, bold=True), fill=C["white"], anchor="mm")
    cy += 90
    draw.text((W // 2, cy), "구독과 좋아요는 큰 힘이 됩니다 🙏",
              font=fnt(36, bold=False), fill=C["gold"], anchor="mm")
    cy += 60
    disclaimer = d.get("disclaimer", "본 영상은 AI가 생성한 참고용 정보이며, 투자 권유가 아닙니다.")
    draw.text((W // 2, cy), disclaimer, font=fnt(26, bold=False), fill=(150, 150, 170), anchor="mm")

    draw_bottombar(draw)
    path = os.path.join(out_dir, "99_closing.png")
    return _save(img, path)
