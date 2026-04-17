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


# ── 공통 헬퍼: sections 섹션에서 종목명 추출 ──────────────────────────────────
def _stock_name_from_section(sec: dict) -> str:
    """
    label:  "관심종목 - 삼성전자"  →  "삼성전자"
            "히든종목 - 두산에너빌리티" → "두산에너빌리티"
    id:     "stock_삼성전자"        →  "삼성전자"  (fallback)
    """
    label = sec.get("label", "")
    for prefix in ("관심종목 - ", "히든종목 - "):
        if prefix in label:
            return label.split(prefix, 1)[1].strip()
    sid = sec.get("id", "")
    for prefix in ("stock_", "hidden_"):
        if sid.startswith(prefix):
            return sid[len(prefix):]
    return label.strip() or "종목"


# ════════════════════════════════════════════════════════════════════════════════
# 1. 오프닝
# ════════════════════════════════════════════════════════════════════════════════
def build_opening(sec: dict, data: dict, out_dir: str) -> str:
    from datetime import datetime
    img = new_frame()
    d   = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 8], fill=C["gold"])

    title = data.get("title", "AI 주식 브리핑")
    date  = data.get("date", datetime.now().strftime("%Y년 %m월 %d일"))

    d.text((W // 2, 280), "AI 주식 브리핑",
           font=fnt(96), fill=C["gold"], anchor="mm")
    d.text((W // 2, 400), title,
           font=fnt(52, bold=False), fill=C["white"], anchor="mm")
    d.text((W // 2, 490), date,
           font=fnt(38, bold=False), fill=C["chart_text"], anchor="mm")

    # 오프닝 내레이션 미리보기 (첫 2줄)
    narration = sec.get("narration", "")
    if narration:
        preview = narration[:60] + ("…" if len(narration) > 60 else "")
        d.text((W // 2, 590), preview,
               font=fnt(32, bold=False), fill=C["chart_text"], anchor="mm")

    d.text((W // 2, H - 60),
           "⚠ 본 브리핑은 AI 자동 생성 참고자료이며 투자 권유가 아닙니다",
           font=fnt(26, bold=False), fill=C["chart_text"], anchor="mm")

    path = os.path.join(out_dir, "00_opening.png")
    img.save(path, quality=95)
    print(f"  ✅ 오프닝")
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 2. 시장 요약
# ════════════════════════════════════════════════════════════════════════════════
def build_market_summary(market_secs: list, out_dir: str) -> list:
    """
    market_secs: id == "market_summary" 인 섹션 리스트
    script.json 구조:
      {
        "id": "market_summary",
        "label": "시장 요약",
        "narration": "...",
        "kospi_value": "6,226",
        "kospi_change": "+2.21%",
        "kospi_change_positive": true,
        "points": ["포인트1", "포인트2", ...]
      }
    """
    paths = []
    if not market_secs:
        return paths

    sec = market_secs[0]
    img = new_frame()
    d   = ImageDraw.Draw(img)
    draw_topbar(d, "🌍 시장 요약")

    # 코스피 수치
    kospi_val = sec.get("kospi_value", "")
    kospi_chg = sec.get("kospi_change", "")
    is_up     = sec.get("kospi_change_positive", True)
    price_col = C["green"] if is_up else C["red"]
    arrow     = "▲" if is_up else "▼"

    gold_underline(d, 50, 85, "코스피 지수", font_size=48)

    if kospi_val:
        d.text((50, 155),
               f"KOSPI  {kospi_val}  {arrow} {kospi_chg}",
               font=fnt(58), fill=price_col)

    # 포인트 불릿
    points = sec.get("points", [])
    cy = 250
    for pt in points[:6]:
        d.text((60, cy), "•", font=fnt(40), fill=C["gold"])
        draw_wrapped_text(d, pt, 100, cy, max_width=W - 140,
                          font_size=38, line_gap=8)
        cy += 54

    # 내레이션 하단 요약
    narration = sec.get("narration", "")
    if narration and cy < H - 180:
        draw_divider(d, cy + 10)
        draw_wrapped_text(d, narration[:200], 50, cy + 24,
                          max_width=W - 100, font_size=32,
                          color=C["chart_text"], line_gap=8)

    draw_bottombar(d, "시장 요약", "")
    path = os.path.join(out_dir, "01_market_summary.png")
    img.save(path, quality=95)
    paths.append(path)
    print(f"  ✅ 시장 요약")
    return paths


# ════════════════════════════════════════════════════════════════════════════════
# 3. 섹터
# ════════════════════════════════════════════════════════════════════════════════
def build_sector(sec: dict, out_dir: str) -> str:
    """
    script.json 구조:
      {
        "id": "sectors",
        "sector_list": [
          {"name": "AI 반도체 & HBM", "desc": "...", "icon": "🤖"},
          ...
        ]
      }
    """
    img = new_frame()
    d   = ImageDraw.Draw(img)
    draw_topbar(d, "🔥 주목 섹터")
    gold_underline(d, 50, 85, "오늘의 주목 섹터", font_size=54)

    sector_list = sec.get("sector_list", [])
    card_w = (W - 100) // max(len(sector_list), 1)
    card_w = min(card_w, 560)

    for i, item in enumerate(sector_list[:4]):
        cx = 50 + i * (card_w + 20)
        cy = 200
        # 카드 배경
        d.rounded_rectangle([(cx, cy), (cx + card_w, cy + 300)],
                             radius=16, fill=C["card"])
        d.rounded_rectangle([(cx, cy), (cx + card_w, cy + 300)],
                             radius=16, outline=C["border"], width=2)
        # 아이콘
        icon = item.get("icon", "📊")
        d.text((cx + card_w // 2, cy + 60), icon,
               font=fnt(64), fill=C["white"], anchor="mm")
        # 섹터명
        name = item.get("name", "")
        d.text((cx + card_w // 2, cy + 140), name,
               font=fnt(34), fill=C["gold"], anchor="mm")
        # 설명
        desc = item.get("desc", "")
        draw_wrapped_text(d, desc,
                          cx + 16, cy + 190,
                          max_width=card_w - 32,
                          font_size=28, color=C["chart_text"], line_gap=6)

    draw_bottombar(d, "주목 섹터", "")
    path = os.path.join(out_dir, "02_sector.png")
    img.save(path, quality=95)
    print(f"  ✅ 섹터")
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 4. 종목 카드 묶음
# ════════════════════════════════════════════════════════════════════════════════
def build_stock_cards(sec: dict, is_hidden: bool,
                      out_dir: str, img_dir: str,
                      prefix: str) -> list:
    """
    script.json 종목 섹션 구조:
      {
        "id": "stock_삼성전자",
        "label": "관심종목 - 삼성전자",
        "narration": "...",
        "summary": "기업 한 줄 소개",
        "price": "217,500",
        "change": "+3.08%",
        "change_positive": true,
        "catalysts": ["촉매1", "촉매2", ...],
        "risks": ["리스크1", "리스크2", ...],
        "mentions": [
          {"source": "채널명", "reporter": "이름", "quote": "인용문"},
          {"source": "증권사", "analyst": "이름", "report": "보고서 내용"}
        ]
      }
    """
    paths      = []
    stock_name = _stock_name_from_section(sec)
    date_str   = ""

    p = _build_stock_summary(sec, stock_name, is_hidden, date_str,
                              out_dir, img_dir, prefix)
    paths.append(p)

    p = _build_stock_chart(sec, stock_name, is_hidden, date_str,
                            out_dir, img_dir, prefix)
    paths.append(p)

    for i, mention in enumerate(sec.get("mentions", [])):
        p = _build_mention_page(mention, stock_name, date_str,
                                out_dir, prefix, i)
        paths.append(p)

    return paths


def _build_stock_summary(sec, stock_name, is_hidden,
                          date_str, out_dir, img_dir, prefix) -> str:
    img = new_frame()
    d   = ImageDraw.Draw(img)
    tag_color = C["hidden_accent"] if is_hidden else C["tag_bg"]
    draw_topbar(d, f"🎯 {'히든 ' if is_hidden else ''}종목  |  {stock_name}", tag_color)

    gold_underline(d, 40, 85, stock_name, font_size=62)

    # 주가
    price     = sec.get("price", "")
    change    = sec.get("change", "")
    is_up     = sec.get("change_positive", True)
    price_col = C["green"] if is_up else C["red"]
    arrow     = "▲" if is_up else "▼"

    if price:
        d.text((40, 175),
               f"{price}원   {arrow} {change}",
               font=fnt(48), fill=price_col)

    # 요약
    summary = sec.get("summary", "")
    cy = draw_wrapped_text(d, summary, 40, 255,
                           max_width=920, font_size=36, line_gap=10)
    cy += 10

    # 촉매 (리스트)
    catalysts = sec.get("catalysts", [])
    if catalysts:
        d.text((40, cy), "🚀 상승 촉매", font=fnt(34), fill=C["green"])
        cy += 46
        for cat in catalysts[:4]:
            d.text((56, cy), "·", font=fnt(34), fill=C["green"])
            cy = draw_wrapped_text(d, cat, 80, cy,
                                   max_width=880, font_size=32, line_gap=6)
        cy += 8

    # 리스크 (리스트)
    risks = sec.get("risks", [])
    if risks and cy < H - 200:
        d.text((40, cy), "⚠️ 리스크", font=fnt(34), fill=C["red"])
        cy += 46
        for risk in risks[:3]:
            d.text((56, cy), "·", font=fnt(34), fill=C["red"])
            cy = draw_wrapped_text(d, risk, 80, cy,
                                   max_width=880, font_size=32, line_gap=6)

    # 우측 이미지
    img_path = fetch_news_image(stock_name, img_dir)
    if img_path:
        paste_image(img, img_path, (960, 85, W - 30, H - 70))
    else:
        d.rounded_rectangle([(960, 85), (W - 30, H - 70)],
                             radius=12, fill=C["card"])
        d.rounded_rectangle([(960, 85), (W - 30, H - 70)],
                             radius=12, outline=C["border"], width=2)
        d.text(((960 + W - 30) // 2, (85 + H - 70) // 2),
               stock_name, font=fnt(44), fill=C["border"], anchor="mm")

    draw_bottombar(d, stock_name, date_str, tag_color)
    path = os.path.join(out_dir, f"{prefix}_1_summary.png")
    img.save(path, quality=95)
    print(f"  ✅ 종목 요약: {stock_name}")
    return path


def _build_stock_chart(sec, stock_name, is_hidden,
                        date_str, out_dir, img_dir, prefix) -> str:
    tag_color = C["hidden_accent"] if is_hidden else C["tag_bg"]
    img = new_frame()
    d   = ImageDraw.Draw(img)
    draw_topbar(d, f"📈 {stock_name}  주가 흐름 (최근 2주)", tag_color)
    gold_underline(d, 50, 85, f"{stock_name}  최근 2주 일봉 차트", font_size=52)

    chart_path = build_chart_image(stock_name, img_dir)

    if chart_path:
        paste_image(img, chart_path, (30, 155, W - 30, H - 70))
    else:
        _draw_chart_placeholder(d, 30, 155, W - 30, H - 70)

    draw_bottombar(d, stock_name, date_str, tag_color)
    path = os.path.join(out_dir, f"{prefix}_2_chart.png")
    img.save(path, quality=95)
    print(f"  ✅ 종목 차트: {stock_name}")
    return path


def _draw_chart_placeholder(d, x1, y1, x2, y2):
    d.rounded_rectangle([(x1, y1), (x2, y2)],
                         radius=8, fill=(16, 20, 50))
    d.rounded_rectangle([(x1, y1), (x2, y2)],
                         radius=8, outline=(60, 70, 120), width=2)
    msg = "차트 데이터 준비 중"
    f   = fnt(48, bold=False)
    mw  = f.getbbox(msg)[2]
    mx  = x1 + (x2 - x1 - mw) // 2
    my  = y1 + (y2 - y1) // 2 - 30
    d.text((mx, my), msg, font=f, fill=(120, 120, 180))


def _build_mention_page(mention: dict, stock_name: str,
                         date_str: str, out_dir: str,
                         prefix: str, idx: int) -> str:
    """
    mention 구조:
      {"source": "채널명/증권사", "reporter": "기자명", "quote": "인용문"}
      {"source": "증권사명",      "analyst":  "애널리스트", "report": "보고서 내용"}
    """
    img = new_frame()
    d   = ImageDraw.Draw(img)

    source  = mention.get("source", "")
    # 발언자: reporter 또는 analyst
    speaker = mention.get("reporter") or mention.get("analyst") or ""
    # 인용문: quote 또는 report
    content = mention.get("quote") or mention.get("report") or ""

    tag_color = C["blue"]
    draw_topbar(d, f"📢 채널 언급  |  {stock_name}", tag_color)

    # 큰 따옴표
    d.text((60, 90), "\u201c", font=fnt(130), fill=C["gold"])

    # 인용 본문
    draw_wrapped_text(d, content, 70, 200,
                      max_width=W - 140,
                      font_size=48, line_gap=16,
                      color=C["white"])

    # 하단 출처 바
    bar_y = H - 190
    d.rectangle([0, bar_y, W, bar_y + 120], fill=(8, 10, 30))
    d.rectangle([0, bar_y, 8, bar_y + 120], fill=C["gold"])   # 좌측 포인트 바

    d.text((40, bar_y + 12), source,
           font=fnt(52), fill=C["gold"])
    if speaker:
        d.text((40, bar_y + 72),
               f"출연 / 작성:  {speaker}",
               font=fnt(34, bold=False), fill=C["white"])

    draw_bottombar(d, stock_name, date_str, tag_color)
    path = os.path.join(out_dir, f"{prefix}_3_mention_{idx:02d}.png")
    img.save(path, quality=95)
    print(f"  ✅ 채널 언급: {stock_name} [{source}]")
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 5. AI 전략
# ════════════════════════════════════════════════════════════════════════════════
def build_ai_strategy(sec: dict, out_dir: str) -> str:
    """
    script.json 구조:
      {
        "id": "ai_strategy",
        "narration": "...",
        "bullet_points": ["종목 — 전략", ...]
      }
    """
    img = new_frame()
    d   = ImageDraw.Draw(img)
    draw_topbar(d, "🤖 AI 종합 전략")
    gold_underline(d, 50, 85, "오늘의 AI 투자 전략", font_size=54)

    bullet_points = sec.get("bullet_points", [])
    narration     = sec.get("narration", "")

    if bullet_points:
        cy = 180
        for bp in bullet_points[:7]:
            # 종목명 — 전략 으로 분리해서 종목명은 골드로
            if "—" in bp:
                name_part, strat_part = bp.split("—", 1)
                d.text((50, cy), name_part.strip(),
                       font=fnt(36), fill=C["gold"])
                nw = fnt(36).getbbox(name_part.strip())[2]
                d.text((50 + nw + 10, cy), "—",
                       font=fnt(36, bold=False), fill=C["border"])
                cy = draw_wrapped_text(d, strat_part.strip(),
                                       50 + nw + 36, cy,
                                       max_width=W - 100 - nw - 36,
                                       font_size=34, line_gap=6)
            else:
                d.text((50, cy), "•", font=fnt(36), fill=C["gold"])
                cy = draw_wrapped_text(d, bp, 80, cy,
                                       max_width=W - 130,
                                       font_size=34, line_gap=6)
            cy += 10
            draw_divider(d, cy)
            cy += 14
    elif narration:
        draw_wrapped_text(d, narration, 50, 180,
                          max_width=W - 100,
                          font_size=36, line_gap=12)

    draw_bottombar(d, "AI 전략", "")
    path = os.path.join(out_dir, "98_ai_strategy.png")
    img.save(path, quality=95)
    print(f"  ✅ AI 전략")
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 6. 클로징
# ════════════════════════════════════════════════════════════════════════════════
def build_closing(sec: dict, out_dir: str) -> str:
    img = new_frame()
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=C["gold"])

    disclaimer = sec.get("disclaimer",
                          "본 브리핑은 AI가 생성한 참고 자료이며 투자 권유가 아닙니다.\n"
                          "투자의 최종 판단과 책임은 본인에게 있습니다.")

    d.text((W // 2, 340), "오늘 브리핑을 마칩니다",
           font=fnt(72), fill=C["white"], anchor="mm")
    d.text((W // 2, 450), "구독과 좋아요는 큰 힘이 됩니다 🙏",
           font=fnt(44, bold=False), fill=C["chart_text"], anchor="mm")

    # 면책 고지 (두 줄 처리)
    for i, line in enumerate(disclaimer.split("\n")):
        d.text((W // 2, 580 + i * 52), line,
               font=fnt(30, bold=False), fill=C["chart_text"], anchor="mm")

    d.rectangle([0, H - 8, W, H], fill=C["gold"])

    path = os.path.join(out_dir, "99_closing.png")
    img.save(path, quality=95)
    print(f"  ✅ 클로징")
    return path
