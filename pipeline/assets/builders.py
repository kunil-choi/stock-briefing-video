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


# ════════════════════════════════════════════════════════════════════════════════
# 1. 오프닝
# ════════════════════════════════════════════════════════════════════════════════
def build_opening(data: dict, out_dir: str) -> str:
    from datetime import datetime
    img = new_frame()
    d = ImageDraw.Draw(img)

    # 배경 그라디언트 효과 (상단 accent bar)
    d.rectangle([0, 0, W, 8], fill=C["gold"])

    title = data.get("title", "AI 주식 브리핑")
    date  = datetime.now().strftime("%Y년 %m월 %d일")

    d.text((W // 2, 300), "AI 주식 브리핑",
           font=fnt(96), fill=C["gold"],
           anchor="mm")
    d.text((W // 2, 420), title,
           font=fnt(52, bold=False), fill=C["white"],
           anchor="mm")
    d.text((W // 2, 520), date,
           font=fnt(38, bold=False), fill=C["chart_text"],
           anchor="mm")

    # 하단 면책 문구
    d.text((W // 2, H - 80),
           "⚠ 본 브리핑은 AI 자동 생성 참고자료이며 투자 권유가 아닙니다",
           font=fnt(28, bold=False), fill=C["chart_text"],
           anchor="mm")

    path = os.path.join(out_dir, "00_opening.png")
    img.save(path, quality=95)
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 2. 시장 요약
# ════════════════════════════════════════════════════════════════════════════════
def build_market_summary(data: dict, out_dir: str) -> list[str]:
    summaries = data.get("market_summary", [])
    paths = []
    for idx, item in enumerate(summaries):
        img = new_frame()
        d = ImageDraw.Draw(img)
        draw_topbar(d, "🌍 시장 요약")

        gold_underline(d, 50, 90, item.get("title", ""), font_size=54)

        body = item.get("body", "")
        draw_wrapped_text(d, body, 50, 175,
                          max_width=W - 100,
                          font_size=38, line_gap=12)

        draw_bottombar(d, "시장 요약", item.get("date", ""))
        path = os.path.join(out_dir, f"01_market_{idx:02d}.png")
        img.save(path, quality=95)
        paths.append(path)
    return paths


# ════════════════════════════════════════════════════════════════════════════════
# 3. 섹터
# ════════════════════════════════════════════════════════════════════════════════
def build_sector(data: dict, out_dir: str) -> str:
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, "🔥 주목 섹터")
    gold_underline(d, 50, 90, "오늘의 주목 섹터", font_size=54)

    sectors = data.get("sectors", [])
    x, y = 50, 200
    for sec in sectors:
        x = draw_badge(d, x, y, sec, bg=C["tag_bg"], fg=C["gold"])
        if x > W - 300:
            x = 50
            y += 70

    path = os.path.join(out_dir, "02_sector.png")
    img.save(path, quality=95)
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 4. 종목 카드 묶음 (요약 + 차트 + 채널 언급)
# ════════════════════════════════════════════════════════════════════════════════
def build_stock_cards(sec: dict, out_dir: str, img_dir: str,
                      prefix: str) -> list[str]:
    paths = []
    stock_name = sec.get("name", "")
    date_str   = sec.get("date", "")

    # ── 4-1. 종목 요약 ──────────────────────────────────────────────────────
    p = _build_stock_summary(sec, stock_name, date_str, out_dir, img_dir, prefix)
    paths.append(p)

    # ── 4-2. 일봉 차트 ──────────────────────────────────────────────────────
    p = _build_stock_chart(sec, stock_name, date_str, out_dir, img_dir, prefix)
    paths.append(p)

    # ── 4-3. 채널 언급 ──────────────────────────────────────────────────────
    for i, mention in enumerate(sec.get("mentions", [])):
        p = _build_mention_page(mention, stock_name, date_str,
                                out_dir, prefix, i)
        paths.append(p)

    return paths


def _build_stock_summary(sec, stock_name, date_str,
                          out_dir, img_dir, prefix) -> str:
    img = new_frame()
    d = ImageDraw.Draw(img)
    tag_color = C["hidden_accent"] if sec.get("is_hidden") else C["tag_bg"]
    draw_topbar(d, f"🎯 {stock_name}", tag_color)

    # 좌측 텍스트 영역
    gold_underline(d, 40, 90, stock_name, font_size=62)

    # 주가
    price     = sec.get("price", "")
    change    = sec.get("change", "")
    change_pct= sec.get("change_pct", "")
    is_up     = not str(change).startswith("-")
    price_col = C["green"] if is_up else C["red"]
    arrow     = "▲" if is_up else "▼"

    d.text((40, 180),
           f"{price}원  {arrow} {change} ({change_pct}%)",
           font=fnt(44), fill=price_col)

    # 요약 텍스트
    summary = sec.get("summary", "")
    draw_wrapped_text(d, summary, 40, 260, max_width=920,
                      font_size=36, line_gap=10)

    # 촉매 / 리스크
    cy = 520
    for label, key, col in [
        ("🚀 상승 촉매", "catalyst", C["green"]),
        ("⚠️ 리스크",  "risk",     C["red"]),
    ]:
        d.text((40, cy), label, font=fnt(34), fill=col)
        cy += 44
        text = sec.get(key, "")
        cy = draw_wrapped_text(d, text, 40, cy,
                               max_width=920, font_size=32, line_gap=8)
        cy += 12

    # 우측 이미지
    img_path = fetch_news_image(stock_name, img_dir)
    if img_path:
        paste_image(img, img_path, (980, 90, W - 40, H - 80))
    else:
        d.rounded_rectangle([(980, 90), (W - 40, H - 80)],
                             radius=12, fill=C["card"])
        d.text((1200, 580), stock_name,
               font=fnt(48), fill=C["border"], anchor="mm")

    draw_bottombar(d, stock_name, date_str, tag_color)
    path = os.path.join(out_dir, f"{prefix}_1_summary.png")
    img.save(path, quality=95)
    return path


def _build_stock_chart(sec, stock_name, date_str,
                        out_dir, img_dir, prefix) -> str:
    tag_color = C["hidden_accent"] if sec.get("is_hidden") else C["tag_bg"]
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, f"📈 {stock_name} 주가 흐름 (최근 2주)", tag_color)
    gold_underline(d, 50, 90, f"{stock_name}  최근 2주 일봉 차트", font_size=52)

    chart_path = build_chart_image(stock_name, img_dir)

    if chart_path:
        paste_image(img, chart_path, (30, 150, W - 30, H - 80))
    else:
        _draw_chart_placeholder(d, 30, 150, W - 30, H - 80)

    draw_bottombar(d, stock_name, date_str, tag_color)
    path = os.path.join(out_dir, f"{prefix}_2_chart.png")
    img.save(path, quality=95)
    return path


def _draw_chart_placeholder(d, x1, y1, x2, y2):
    d.rounded_rectangle([(x1, y1), (x2, y2)],
                         radius=8, fill=(16, 20, 50))
    d.rounded_rectangle([(x1, y1), (x2, y2)],
                         radius=8, outline=(60, 70, 120), width=2)
    msg = "차트 데이터 준비 중"
    mw  = fnt(48, bold=False).getbbox(msg)[2]
    mx  = x1 + (x2 - x1 - mw) // 2
    my  = y1 + (y2 - y1) // 2 - 30
    d.text((mx, my), msg, font=fnt(48, bold=False),
           fill=(120, 120, 180))


def _build_mention_page(mention: dict, stock_name: str, date_str: str,
                         out_dir: str, prefix: str, idx: int) -> str:
    img = new_frame()
    d = ImageDraw.Draw(img)

    channel  = mention.get("channel", "")
    speaker  = mention.get("speaker", "")
    content  = mention.get("content", "")
    src_type = mention.get("source_type", "유튜브")

    tag_color = C["blue"]
    draw_topbar(d, f"📢 채널 언급  |  {stock_name}", tag_color)

    # 채널·출연자 하단 자막 스타일
    bar_y = H - 200
    d.rectangle([0, bar_y, W, bar_y + 130], fill=(0, 0, 0, 180))
    d.text((50, bar_y + 10), channel,
           font=fnt(52), fill=C["gold"])
    d.text((50, bar_y + 74), f"출연: {speaker}  |  {src_type}",
           font=fnt(34, bold=False), fill=C["white"])

    # 중앙 인용 텍스트
    d.text((80, 100), "\u201c", font=fnt(120), fill=C["gold"])
    draw_wrapped_text(d, content, 80, 210,
                      max_width=W - 160,
                      font_size=44, line_gap=14,
                      color=C["white"])

    draw_bottombar(d, stock_name, date_str, tag_color)
    path = os.path.join(out_dir, f"{prefix}_3_mention_{idx:02d}.png")
    img.save(path, quality=95)
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 5. AI 전략
# ════════════════════════════════════════════════════════════════════════════════
def build_ai_strategy(data: dict, out_dir: str) -> str:
    img = new_frame()
    d = ImageDraw.Draw(img)
    draw_topbar(d, "🤖 AI 종합 전략")
    gold_underline(d, 50, 90, "오늘의 AI 투자 전략", font_size=54)

    strategy = data.get("ai_strategy", "")
    draw_wrapped_text(d, strategy, 50, 180,
                      max_width=W - 100,
                      font_size=36, line_gap=12)

    draw_bottombar(d, "AI 전략", data.get("date", ""))
    path = os.path.join(out_dir, "98_ai_strategy.png")
    img.save(path, quality=95)
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 6. 클로징
# ════════════════════════════════════════════════════════════════════════════════
def build_closing(data: dict, out_dir: str) -> str:
    img = new_frame()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=C["gold"])

    d.text((W // 2, 360), "오늘 브리핑을 마칩니다",
           font=fnt(72), fill=C["white"], anchor="mm")
    d.text((W // 2, 480), "구독과 좋아요는 큰 힘이 됩니다 🙏",
           font=fnt(44, bold=False), fill=C["chart_text"], anchor="mm")
    d.text((W // 2, H - 80),
           "⚠ 본 브리핑은 AI 자동 생성 참고자료이며 투자 권유가 아닙니다",
           font=fnt(28, bold=False), fill=C["chart_text"], anchor="mm")

    path = os.path.join(out_dir, "99_closing.png")
    img.save(path, quality=95)
    return path
