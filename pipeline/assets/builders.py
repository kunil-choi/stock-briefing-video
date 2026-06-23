# pipeline/assets/builders.py
"""
KBS 머니올라 — 고품질 방송 비주얼 빌더
Google NotebookLM 이상의 비주얼 퀄리티를 목표로 합니다.
"""
import os
import re
import math
from PIL import Image, ImageDraw, ImageFilter
from .config import W, H, C
from .drawing import (
    fnt, new_frame, draw_topbar, draw_bottombar,
    draw_wrapped_text, draw_divider, draw_badge,
    draw_accent_card, draw_glass_card, draw_rounded_card,
    draw_glow_text, draw_gradient_bar, draw_progress_bar,
    paste_image, _lerp_color,
)
from .chart import build_chart_image
from .image_fetch import fetch_news_image

Y_MAX    = H - 80
MARGIN_X = 72
CX       = W // 2
CHART_BOTTOM = H - 80


def _save(img, path):
    img.save(path, quality=95)
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
    if not path or not os.path.isfile(path): return
    try:
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        src = Image.open(path).convert("RGB")
        scale = max(bw / src.width, bh / src.height)
        new_w = int(src.width * scale)
        new_h = int(src.height * scale)
        src = src.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - bw) // 2
        top  = (new_h - bh) // 2
        src  = src.crop((left, top, left + bw, top + bh))
        img.paste(src, (box[0], box[1]))
    except Exception as e:
        print(f"[builders] 이미지 붙이기 실패 ({path}): {e}")


def _draw_stat_box(draw, img, x, y, width, height, label, value, change="",
                   positive=True, color=None):
    """데이터 통계 박스 컴포넌트."""
    color = color or C["gold"]
    # 배경
    draw.rounded_rectangle([x, y, x + width, y + height],
                            radius=14, fill=(18, 22, 62))
    draw.rounded_rectangle([x, y, x + width, y + 4],
                            radius=0, fill=color)
    # 레이블
    draw.text((x + 16, y + 16), label,
              font=fnt(26, bold=False), fill=(160, 170, 210))
    # 값
    draw.text((x + 16, y + 48), value,
              font=fnt(48, bold=True), fill=C["white"])
    # 등락
    if change:
        change_color = C["red"] if positive else C["blue"]
        arrow = "▲" if positive else "▼"
        draw.text((x + 16, y + height - 36), f"{arrow} {change}",
                  font=fnt(28, bold=True), fill=change_color)


def _draw_market_indicator_row(draw, img, x, y, label, value, change, positive):
    """시장 지표 한 줄 표시."""
    indicator_h = 70
    draw.rounded_rectangle([x, y, W - MARGIN_X, y + indicator_h],
                            radius=10, fill=(15, 20, 52))
    draw.line([x, y, x + 5, y + indicator_h], fill=C["gold"], width=5)

    draw.text((x + 22, y + 14), label,
              font=fnt(30, bold=True), fill=C["white"])
    val_color = C["red"] if positive else C["blue"]
    draw.text((W - MARGIN_X - 20, y + 14), value,
              font=fnt(30, bold=True), fill=val_color, anchor="ra")
    arrow = "▲" if positive else "▼"
    draw.text((W - MARGIN_X - 20, y + 44), f"{arrow} {change}",
              font=fnt(22, bold=False), fill=val_color, anchor="ra")


# ── 오프닝 ─────────────────────────────────────────────────────────────────

def build_opening(data, out_dir):
    sec      = _find_section(data.get("sections", []), "opening")
    img      = new_frame(theme="default")
    draw     = ImageDraw.Draw(img)
    keywords = sec.get("keywords", [])
    date_str = data.get("date", "")

    # ── 중앙 원형 글로우 배경 ─────────────────────────────────────────
    glow_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw    = ImageDraw.Draw(glow_img)
    for r in range(320, 0, -4):
        t   = r / 320
        col = _lerp_color((255, 195, 0), (10, 12, 35), t)
        alpha = int(25 * (1 - t))
        gdraw.ellipse([CX - r * 2, H // 2 - 200 - r,
                       CX + r * 2, H // 2 - 200 + r],
                      fill=(*col, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), glow_img).convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── KBS 머니올라 로고 배지 ────────────────────────────────────────
    badge_y = H // 2 - 310
    badge_w, badge_h = 380, 64
    draw.rounded_rectangle([CX - badge_w // 2, badge_y,
                             CX + badge_w // 2, badge_y + badge_h],
                            radius=32, fill=C["gold"])
    draw.text((CX, badge_y + badge_h // 2), "KBS 머니올라",
              font=fnt(36, bold=True), fill=(10, 12, 35), anchor="mm")

    cy = H // 2 - 210

    # ── 메인 타이틀 ──────────────────────────────────────────────────
    draw_glow_text(draw, (CX, cy), "주식시장 브리핑",
                   font=fnt(92, bold=True), fill=C["white"],
                   glow_color=C["gold"], glow_radius=4, anchor="mm")
    cy += 110

    # ── 서브 타이틀 ──────────────────────────────────────────────────
    draw.text((CX, cy), "오늘의 핵심만 골라 드립니다",
              font=fnt(42, bold=False), fill=(180, 190, 230), anchor="mm")
    cy += 60

    # ── 날짜 ─────────────────────────────────────────────────────────
    if date_str:
        # 날짜 배지
        dw = 320
        draw.rounded_rectangle([CX - dw // 2, cy, CX + dw // 2, cy + 52],
                                radius=26, fill=(20, 28, 75))
        draw.rounded_rectangle([CX - dw // 2, cy, CX + dw // 2, cy + 52],
                                radius=26, outline=C["gold"], width=1)
        draw.text((CX, cy + 26), date_str,
                  font=fnt(32, bold=False), fill=C["gold"], anchor="mm")
        cy += 76

    # ── 구분선 ───────────────────────────────────────────────────────
    for i in range(3):
        alpha = [200, 120, 60][i]
        offset = [0, 6, 12][i]
        draw.line([CX - 260 + offset, cy, CX + 260 - offset, cy],
                  fill=(*C["gold"], alpha), width=2 - i if i < 2 else 1)
    cy += 30

    # ── 키워드 태그 ──────────────────────────────────────────────────
    if keywords:
        kw_colors = [C["gold"], C["green"], C["blue"], (220, 100, 220)]
        kw_list   = keywords[:4]
        font_kw   = fnt(30, bold=False)
        tag_pad   = 22
        tag_hs    = []
        for kw in kw_list:
            try: tw = int(draw.textlength(kw, font=font_kw))
            except Exception: tw = len(kw) * 16
            tag_hs.append(tw + tag_pad * 2)
        total_w = sum(tag_hs) + 20 * (len(kw_list) - 1)
        kx = (W - total_w) // 2

        for i, kw in enumerate(kw_list):
            col = kw_colors[i % len(kw_colors)]
            tw  = tag_hs[i] - tag_pad * 2
            tag_w = tag_hs[i]
            draw.rounded_rectangle([kx, cy, kx + tag_w, cy + 50],
                                    radius=25, fill=(*col, 30))
            draw.rounded_rectangle([kx, cy, kx + tag_w, cy + 50],
                                    radius=25, outline=col, width=2)
            draw.text((kx + tag_w // 2, cy + 25), kw,
                      font=font_kw, fill=col, anchor="mm")
            kx += tag_w + 20

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "00_opening.png"))


# ── 시장 요약 ───────────────────────────────────────────────────────────────

def build_market_summary(data, out_dir):
    sec      = _find_section(data.get("sections", []), "market_summary")
    img      = new_frame(theme="blue")
    draw     = ImageDraw.Draw(img)
    draw_topbar(draw, "시장 요약")

    kospi    = sec.get("kospi_value", "")
    change   = sec.get("kospi_change", "")
    positive = sec.get("kospi_change_positive", True)
    kosdaq   = sec.get("kosdaq_value", "")
    kosdaq_ch = sec.get("kosdaq_change", "")
    kosdaq_pos = sec.get("kosdaq_change_positive", True)
    points   = sec.get("points", [])
    corner_summary = sec.get("corner_summary", "")

    cy = 96

    # ── 코너 요약 배지 ────────────────────────────────────────────────
    if corner_summary:
        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + 50],
                                radius=25, fill=(25, 35, 80))
        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + 50],
                                radius=25, outline=C["gold"], width=1)
        draw_wrapped_text(draw, f"  {corner_summary}",
                          MARGIN_X + 20, cy + 10, W - MARGIN_X * 2 - 40,
                          size=26, bold=False, color=C["gold"], line_gap=6)
        cy += 66

    # ── 지수 카드 (가로 2분할) ─────────────────────────────────────────
    card_w = (W - MARGIN_X * 2 - 40) // 2

    # KOSPI 카드
    if kospi:
        kx = MARGIN_X
        draw.rounded_rectangle([kx, cy, kx + card_w, cy + 140],
                                radius=16, fill=(18, 25, 65))
        draw.rounded_rectangle([kx, cy, kx + 6, cy + 140],
                                radius=4, fill=C["gold"])
        draw.text((kx + 22, cy + 12), "KOSPI",
                  font=fnt(30, bold=True), fill=C["gold"])
        draw.text((kx + 22, cy + 52), kospi,
                  font=fnt(56, bold=True), fill=C["white"])
        if change:
            ch_color = C["red"] if positive else C["blue"]
            arrow = "▲" if positive else "▼"
            draw.text((kx + 22, cy + 112), f"{arrow} {change}",
                      font=fnt(28, bold=True), fill=ch_color)

    # KOSDAQ 카드
    if kosdaq:
        dx = MARGIN_X + card_w + 40
        draw.rounded_rectangle([dx, cy, dx + card_w, cy + 140],
                                radius=16, fill=(18, 25, 65))
        draw.rounded_rectangle([dx, cy, dx + 6, cy + 140],
                                radius=4, fill=C["blue"])
        draw.text((dx + 22, cy + 12), "KOSDAQ",
                  font=fnt(30, bold=True), fill=C["blue"])
        draw.text((dx + 22, cy + 52), kosdaq,
                  font=fnt(56, bold=True), fill=C["white"])
        if kosdaq_ch:
            ch_color = C["red"] if kosdaq_pos else C["blue"]
            arrow = "▲" if kosdaq_pos else "▼"
            draw.text((dx + 22, cy + 112), f"{arrow} {kosdaq_ch}",
                      font=fnt(28, bold=True), fill=ch_color)

    if kospi or kosdaq:
        cy += 162

    # ── 구분선 ───────────────────────────────────────────────────────
    draw_divider(draw, cy, style="gradient")
    cy += 28

    # ── 오늘의 핵심 포인트 ────────────────────────────────────────────
    if points:
        draw.text((MARGIN_X, cy), "오늘의 핵심 포인트",
                  font=fnt(30, bold=True), fill=C["gold"])
        cy += 46

        for i, point in enumerate(points[:5]):
            if cy >= Y_MAX - 20: break
            icon_colors = [C["gold"], C["green"], C["blue"], (220, 100, 220), C["red"]]
            col = icon_colors[i % len(icon_colors)]
            # 포인트 카드
            ph = 72
            draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + ph],
                                    radius=10, fill=(15, 20, 52))
            draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 5, cy + ph],
                                    radius=0, fill=col)
            # 번호 원
            draw.ellipse([MARGIN_X + 14, cy + ph // 2 - 18,
                          MARGIN_X + 50, cy + ph // 2 + 18],
                         fill=col)
            draw.text((MARGIN_X + 32, cy + ph // 2), str(i + 1),
                      font=fnt(24, bold=True), fill=(10, 12, 35), anchor="mm")
            draw_wrapped_text(draw, point,
                              MARGIN_X + 64, cy + 12,
                              W - MARGIN_X * 2 - 80,
                              size=26, bold=False, color=C["white"], line_gap=8)
            cy += ph + 10

    draw_bottombar(draw)
    path = os.path.join(out_dir, "01_market_00.png")
    return [_save(img, path)]


# ── 업종 분석 ───────────────────────────────────────────────────────────────

def build_sector(data, out_dir):
    sec  = _find_section(data.get("sections", []), "sectors")
    img  = new_frame(theme="purple")
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "핵심 업종 분석", color=(25, 12, 55))

    sector_list = sec.get("sector_list", sec.get("sectors", sec.get("list", [])))
    corner_summary = sec.get("corner_summary", "")

    cy = 96

    # 코너 요약
    if corner_summary:
        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + 50],
                                radius=25, fill=(30, 18, 65))
        draw_wrapped_text(draw, f"  {corner_summary}",
                          MARGIN_X + 20, cy + 10, W - MARGIN_X * 2 - 40,
                          size=26, bold=False, color=C["gold"], line_gap=6)
        cy += 66

    # 섹터 카드 그리드
    palette = [
        C["gold"], C["green"], C["blue"],
        (220, 100, 220), C["red"], (100, 220, 220),
        (255, 140, 60), (80, 200, 120)
    ]
    card_w = (W - MARGIN_X * 2 - 40) // 2
    card_h = 142

    for idx, sector in enumerate(sector_list[:6]):
        color = palette[idx % len(palette)]
        if isinstance(sector, dict):
            name     = sector.get("name", "")
            desc     = sector.get("desc", sector.get("description", ""))
            momentum = sector.get("momentum", "")
        else:
            name = str(sector); desc = ""; momentum = ""

        col    = idx % 2
        row    = idx // 2
        card_x = MARGIN_X + col * (card_w + 40)
        card_y = cy + row * (card_h + 16)
        if card_y + card_h > Y_MAX: break

        # 카드 배경
        draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h],
                                radius=16, fill=(18, 15, 52))
        # 상단 컬러 바
        draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + 6],
                                radius=4, fill=color)
        # 왼쪽 강조선
        draw.rounded_rectangle([card_x, card_y, card_x + 5, card_y + card_h],
                                radius=4, fill=(*color, 150))

        # 아이콘 원 배경
        draw.ellipse([card_x + 18, card_y + 20, card_x + 56, card_y + 58],
                     fill=(*color, 40))
        # 번호
        draw.text((card_x + 37, card_y + 39), str(idx + 1),
                  font=fnt(24, bold=True), fill=color, anchor="mm")

        # 종목명
        draw.text((card_x + 70, card_y + 18), name,
                  font=fnt(34, bold=True), fill=C["white"])

        # 모멘텀 배지
        if momentum:
            mom_colors = {"상승": C["red"], "하락": C["blue"], "보합": C["gold"]}
            mom_col = mom_colors.get(momentum, C["gold"])
            draw.rounded_rectangle([card_x + card_w - 80, card_y + 14,
                                     card_x + card_w - 12, card_y + 46],
                                    radius=16, fill=(*mom_col, 40))
            draw.text((card_x + card_w - 46, card_y + 30), momentum,
                      font=fnt(20, bold=True), fill=mom_col, anchor="mm")

        # 설명
        if desc:
            draw_wrapped_text(draw, desc,
                              card_x + 22, card_y + 68,
                              card_w - 40, size=24,
                              color=(170, 175, 215), line_gap=8)

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "02_sector.png"))


# ── 종목 요약 슬라이드 ──────────────────────────────────────────────────────

def _build_stock_summary(sec, out_path, img_dir):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    price      = sec.get("price", "")
    change     = sec.get("change", "")
    positive   = sec.get("change_positive", True)
    summary    = sec.get("summary", "")
    catalysts  = sec.get("catalysts", [])
    risks      = sec.get("risks", [])
    corner_summary = sec.get("corner_summary", "")

    is_hidden  = sec.get("id", "").startswith("hidden_")
    theme      = "purple" if is_hidden else "default"

    img  = new_frame(theme=theme)
    draw = ImageDraw.Draw(img)

    bar_label = "숨은 종목 분석" if is_hidden else "종목 분석"
    bar_color = (35, 12, 65) if is_hidden else None
    draw_topbar(draw, f"{bar_label}: {stock_name}", color=bar_color)

    # ── 뉴스 이미지 (우측 상단 원형 프레임) ─────────────────────────
    img_path = fetch_news_image(stock_name, img_dir, [])
    if img_path:
        try:
            logo_size = 200
            logo_x = W - MARGIN_X - logo_size
            logo_y = 90
            mask = Image.new("L", (logo_size, logo_size), 0)
            mdraw = ImageDraw.Draw(mask)
            mdraw.ellipse([0, 0, logo_size, logo_size], fill=255)
            logo_img = Image.open(img_path).convert("RGBA")
            logo_img = logo_img.resize((logo_size, logo_size), Image.LANCZOS)
            border_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            bdraw = ImageDraw.Draw(border_img)
            bdraw.ellipse([logo_x - 4, logo_y - 4,
                           logo_x + logo_size + 4, logo_y + logo_size + 4],
                          fill=C["gold"])
            img = Image.alpha_composite(img.convert("RGBA"), border_img).convert("RGB")
            temp = Image.new("RGB", (W, H), (0, 0, 0))
            full_mask = Image.new("L", (W, H), 0)
            full_mask.paste(mask, (logo_x, logo_y))
            temp.paste(logo_img.convert("RGB"), (logo_x, logo_y))
            img.paste(temp, (0, 0), full_mask)
            draw = ImageDraw.Draw(img)
        except Exception as e:
            print(f"[builders] 로고 적용 실패: {e}")
            draw = ImageDraw.Draw(img)
    else:
        draw = ImageDraw.Draw(img)

    # ── 종목명 + 요약 ────────────────────────────────────────────────
    NAME_Y = 90

    # 숨은 종목 배지
    if is_hidden:
        draw.rounded_rectangle([MARGIN_X, NAME_Y - 4, MARGIN_X + 140, NAME_Y + 38],
                                radius=19, fill=C.get("hidden_accent", (80, 30, 120)))
        draw.text((MARGIN_X + 70, NAME_Y + 17), "숨은 종목",
                  font=fnt(24, bold=True), fill=C["white"], anchor="mm")
        NAME_Y += 50

    draw_glow_text(draw, (MARGIN_X, NAME_Y), stock_name,
                   font=fnt(74, bold=True), fill=C["white"],
                   glow_color=C["gold"], glow_radius=3)

    # 코너 요약
    SUMMARY_Y = NAME_Y + 88
    if corner_summary:
        draw.rounded_rectangle([MARGIN_X, SUMMARY_Y, W - 300, SUMMARY_Y + 44],
                                radius=22, fill=(20, 28, 72))
        draw_wrapped_text(draw, f"  ★ {corner_summary}",
                          MARGIN_X + 16, SUMMARY_Y + 8,
                          W - 360, size=26, bold=False, color=C["gold"], line_gap=8)
        SUMMARY_Y += 58

    elif summary:
        draw_wrapped_text(draw, summary,
                          MARGIN_X, SUMMARY_Y, W - 360,
                          size=30, bold=False, color=(180, 185, 220), line_gap=12)
        SUMMARY_Y += 48

    # ── 주가 + 등락률 ────────────────────────────────────────────────
    PRICE_Y = SUMMARY_Y + 16
    if price:
        draw.text((MARGIN_X, PRICE_Y), f"₩ {price}",
                  font=fnt(60, bold=True), fill=C["gold"])
        if change:
            try:
                px = MARGIN_X + int(draw.textlength(f"₩ {price}", font=fnt(60, bold=True))) + 24
            except Exception:
                px = MARGIN_X + len(f"₩ {price}") * 32 + 24
            ch_color = C["red"] if positive else C["blue"]
            arrow = "▲" if positive else "▼"
            # 등락 배지
            ch_text = f" {arrow} {change} "
            try: chw = int(draw.textlength(ch_text, font=fnt(36, bold=True))) + 20
            except Exception: chw = 120
            draw.rounded_rectangle([px - 10, PRICE_Y + 12,
                                     px + chw, PRICE_Y + 56],
                                    radius=12, fill=(*ch_color, 30))
            draw.text((px, PRICE_Y + 18), f"{arrow} {change}",
                      font=fnt(36, bold=True), fill=ch_color)

    # ── 구분선 ───────────────────────────────────────────────────────
    DIVIDER_Y = H // 2 - 10
    draw_divider(draw, DIVIDER_Y, style="gradient")

    # ── 투자 포인트 & 리스크 (하단 2분할) ─────────────────────────────
    CARD_Y = DIVIDER_Y + 30
    half_w = (W - MARGIN_X * 2 - 60) // 2

    # 투자 포인트
    if catalysts:
        draw.rounded_rectangle([MARGIN_X, CARD_Y,
                                  MARGIN_X + half_w, CARD_Y + 30],
                                radius=6, fill=C["red"])
        draw.text((MARGIN_X + 12, CARD_Y + 4), "▶ 투자 포인트",
                  font=fnt(28, bold=True), fill=C["white"])
        ty = CARD_Y + 46
        for cat in catalysts[:4]:
            if ty >= Y_MAX - 10: break
            draw.ellipse([MARGIN_X + 8, ty + 8, MARGIN_X + 22, ty + 22],
                         fill=C["red"])
            ty = draw_wrapped_text(draw, f"   {cat}",
                                   MARGIN_X, ty, half_w,
                                   size=26, line_gap=12, color=C["white"])
            ty += 4

    # 리스크
    if risks:
        rx = MARGIN_X + half_w + 60
        draw.rounded_rectangle([rx, CARD_Y,
                                  rx + half_w, CARD_Y + 30],
                                radius=6, fill=C["blue"])
        draw.text((rx + 12, CARD_Y + 4), "▶ 리스크",
                  font=fnt(28, bold=True), fill=C["white"])
        ty = CARD_Y + 46
        for risk in risks[:4]:
            if ty >= Y_MAX - 10: break
            draw.ellipse([rx + 8, ty + 8, rx + 22, ty + 22],
                         fill=C["blue"])
            ty = draw_wrapped_text(draw, f"   {risk}",
                                   rx, ty, half_w,
                                   size=26, line_gap=12, color=C["white"])
            ty += 4

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 종목 차트 슬라이드 ──────────────────────────────────────────────────────

def _build_stock_chart(sec, out_path, img_dir):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")

    img  = new_frame(theme="green")
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"2주간 주가 차트: {stock_name}", color=(8, 30, 18))

    briefing_chart = os.path.join(img_dir, f"briefing_chart_{stock_name}.png")
    if os.path.exists(briefing_chart):
        chart_path = briefing_chart
        print(f"  [chart] 브리핑 앱 차트 사용: {stock_name}")
    else:
        chart_path = build_chart_image(stock_name, img_dir)

    if chart_path:
        _paste_fill(img, chart_path, (0, 82, W, CHART_BOTTOM))
    else:
        # 차트 데이터 없을 때 안내 메시지
        draw.rounded_rectangle([MARGIN_X, H // 2 - 60, W - MARGIN_X, H // 2 + 60],
                                radius=16, fill=(18, 30, 22))
        draw.text((CX, H // 2), f"{stock_name} 차트 데이터 준비 중",
                  font=fnt(36), fill=(120, 160, 140), anchor="mm")

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 언급(mention) 슬라이드 ─────────────────────────────────────────────────

def _build_mention_page(sec, out_path, page_idx):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    mentions   = sec.get("mentions", [])

    if mentions:
        page_mentions = mentions[page_idx * 3: page_idx * 3 + 3]
    else:
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
            paragraphs = [" ".join(sentences[i:i + chunk])
                          for i in range(0, len(sentences), chunk)][:3]

        page_mentions = [
            {"speaker": "", "channel": stock_name,
             "quote_subtitle": p, "quote_narration": p}
            for p in paragraphs[:3]
        ]

    img  = new_frame(theme="dark")
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, f"전문가·방송 언급: {stock_name}", color=(18, 8, 40))

    # 페이지 인디케이터
    total_pages = max(1, (len(mentions) + 2) // 3) if mentions else 1
    if total_pages > 1:
        for pi in range(total_pages):
            dot_x = CX - (total_pages * 20) // 2 + pi * 20
            dot_color = C["gold"] if pi == page_idx else (60, 65, 100)
            draw.ellipse([dot_x - 6, H - 74, dot_x + 6, H - 62], fill=dot_color)

    cy = 96
    n  = max(len(page_mentions), 1)
    avail_h = Y_MAX - cy - 20
    card_h  = min(240, (avail_h - 20 * n) // n)

    mention_colors = [C["gold"], C["green"], C["blue"]]

    for mi, m in enumerate(page_mentions):
        if cy >= Y_MAX: break
        if isinstance(m, str):
            m = {"speaker": "", "channel": "", "quote_subtitle": m}

        speaker = m.get("speaker", "").strip()
        channel = m.get("channel", m.get("source", "")).strip()
        header  = f"{channel}  |  {speaker}" if speaker else channel
        content = m.get("quote_subtitle", m.get("quote", m.get("content", "")))

        accent_col = mention_colors[mi % len(mention_colors)]
        actual_h   = min(card_h, Y_MAX - cy)

        # 카드 배경 (그라디언트 느낌)
        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + actual_h],
                                radius=18, fill=(16, 18, 50))
        # 왼쪽 강조 바
        draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 7, cy + actual_h],
                                radius=4, fill=accent_col)
        # 상단 하이라이트
        draw.line([MARGIN_X + 18, cy + 1, W - MARGIN_X - 18, cy + 1],
                  fill=(*accent_col, 40), width=1)

        # 채널 헤더 (배지 스타일)
        draw.rounded_rectangle([MARGIN_X + 22, cy + 14,
                                  MARGIN_X + 22 + min(len(header) * 16 + 24, 500),
                                  cy + 50],
                                radius=18, fill=(*accent_col, 35))
        draw.text((MARGIN_X + 34, cy + 32), header,
                  font=fnt(26, bold=True), fill=accent_col, anchor="lm")

        # 인용부호 장식
        draw.text((W - MARGIN_X - 70, cy + 14), "❝",
                  font=fnt(48, bold=False), fill=(*accent_col, 60))

        # 내용
        if content:
            draw_wrapped_text(draw, content,
                              MARGIN_X + 28, cy + 62,
                              W - MARGIN_X * 2 - 56,
                              size=28, color=C["white"], line_gap=14)

        cy += actual_h + 20

    draw_bottombar(draw, stock_name)
    return _save(img, out_path)


# ── 종목 카드 묶음 ─────────────────────────────────────────────────────────

def build_stock_cards(sec, out_dir, img_dir, prefix):
    generated_paths = set()

    summary_path = os.path.join(out_dir, f"{prefix}_1_summary.png")
    chart_path   = os.path.join(out_dir, f"{prefix}_2_chart.png")

    paths = [
        _build_stock_summary(sec, summary_path, img_dir),
        _build_stock_chart(sec, chart_path, img_dir),
    ]
    generated_paths.update([summary_path, chart_path])

    mentions = sec.get("mentions", [])
    if mentions:
        pages = max(1, (len(mentions) + 2) // 3)
    else:
        has_0 = bool(sec.get("narration_mention_0") or sec.get("subtitle_mention_0"))
        has_1 = bool(sec.get("narration_mention_1") or sec.get("subtitle_mention_1"))
        has_2 = bool(sec.get("narration_mention_2") or sec.get("subtitle_mention_2"))
        pages = 3 if has_2 else (2 if has_1 else 1)

    for p in range(pages):
        mention_path = os.path.join(out_dir, f"{prefix}_3_mention_{p:02d}.png")
        if mention_path in generated_paths:
            print(f"  ⚠️ 중복 프레임 건너뜀: {os.path.basename(mention_path)}")
            continue
        generated_paths.add(mention_path)
        paths.append(_build_mention_page(sec, mention_path, p))

    return paths


# ── AI 전략 ─────────────────────────────────────────────────────────────────

def build_ai_strategy(data, out_dir):
    sec  = _find_section(data.get("sections", []), "ai_strategy")
    img  = new_frame(theme="purple")
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "AI 투자 전략", color=(22, 10, 55))

    corner_summary = sec.get("corner_summary", "")
    bullet_points  = sec.get("bullet_points", sec.get("strategies", sec.get("items", [])))

    cy = 96

    # 상단 타이틀 영역
    draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + 80],
                            radius=14, fill=(22, 15, 58))
    draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 6, cy + 80],
                            radius=4, fill=C["gold"])

    # AI 아이콘 느낌 텍스트
    draw.text((MARGIN_X + 28, cy + 14), "AI",
              font=fnt(52, bold=True), fill=C["gold"])
    draw.text((MARGIN_X + 100, cy + 14), "오늘의 투자 전략 제안",
              font=fnt(36, bold=True), fill=C["white"])

    if corner_summary:
        draw.text((MARGIN_X + 100, cy + 52), corner_summary,
                  font=fnt(24, bold=False), fill=(170, 175, 215))

    cy += 104

    # 전략 카드 목록
    card_h = 108
    strategy_colors = [C["gold"], C["green"], C["blue"],
                       (220, 100, 220), C["red"], (100, 200, 220)]

    for i, bp in enumerate(bullet_points[:6]):
        if cy + card_h > Y_MAX: break
        text   = bp if isinstance(bp, str) else bp.get("strategy", bp.get("content", str(bp)))
        color  = strategy_colors[i % len(strategy_colors)]

        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + card_h],
                                radius=14, fill=(18, 14, 48))
        draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 6, cy + card_h],
                                radius=4, fill=color)

        # 번호 배지
        draw.ellipse([MARGIN_X + 18, cy + card_h // 2 - 24,
                      MARGIN_X + 66, cy + card_h // 2 + 24],
                     fill=(*color, 50))
        draw.ellipse([MARGIN_X + 20, cy + card_h // 2 - 22,
                      MARGIN_X + 64, cy + card_h // 2 + 22],
                     outline=color, width=2)
        draw.text((MARGIN_X + 42, cy + card_h // 2), str(i + 1),
                  font=fnt(28, bold=True), fill=color, anchor="mm")

        # 내용
        if " — " in text:
            stock_part, strat_part = text.split(" — ", 1)
            draw.text((MARGIN_X + 82, cy + 18), stock_part.strip(),
                      font=fnt(30, bold=True), fill=color)
            draw_wrapped_text(draw, strat_part.strip(),
                              MARGIN_X + 82, cy + 58,
                              W - MARGIN_X * 2 - 100,
                              size=26, color=C["white"], line_gap=8)
        else:
            draw_wrapped_text(draw, text,
                              MARGIN_X + 82, cy + 26,
                              W - MARGIN_X * 2 - 100,
                              size=28, color=C["white"], line_gap=10)

        cy += card_h + 12

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "98_ai_strategy.png"))


# ── 클로징 (투자 경고 강화) ────────────────────────────────────────────────

def build_closing(data, out_dir):
    sec        = _find_section(data.get("sections", []), "closing")
    img        = new_frame(theme="default")
    draw       = ImageDraw.Draw(img)
    disclaimer = sec.get("disclaimer", "")

    # 중앙 글로우
    glow_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw    = ImageDraw.Draw(glow_img)
    for r in range(300, 0, -4):
        t     = r / 300
        col   = _lerp_color((255, 195, 0), (8, 10, 30), t)
        alpha = int(20 * (1 - t))
        gdraw.ellipse([CX - r * 2, H // 2 - r,
                       CX + r * 2, H // 2 + r],
                      fill=(*col, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), glow_img).convert("RGB")
    draw = ImageDraw.Draw(img)

    # KBS 머니올라 로고 배지
    badge_y = H // 2 - 260
    badge_w, badge_h = 380, 64
    draw.rounded_rectangle([CX - badge_w // 2, badge_y,
                             CX + badge_w // 2, badge_y + badge_h],
                            radius=32, fill=C["gold"])
    draw.text((CX, badge_y + badge_h // 2), "KBS 머니올라",
              font=fnt(36, bold=True), fill=(10, 12, 35), anchor="mm")

    cy = H // 2 - 160
    draw_glow_text(draw, (CX, cy), "감사합니다",
                   font=fnt(88, bold=True), fill=C["white"],
                   glow_color=C["gold"], glow_radius=4, anchor="mm")
    cy += 104

    draw.text((CX, cy), "성공적인 투자 되시길 바랍니다",
              font=fnt(42, bold=False), fill=C["gold"], anchor="mm")
    cy += 56

    # 구분선
    draw.line([CX - 280, cy, CX + 280, cy], fill=C["gold"], width=2)
    cy += 24

    # 투자 경고 박스
    warn_h = 170
    draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + warn_h],
                            radius=14, fill=(40, 10, 10))
    draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + warn_h],
                            radius=14, outline=(180, 40, 40), width=2)
    draw.text((MARGIN_X + 24, cy + 14), "⚠ 투자 유의사항",
              font=fnt(30, bold=True), fill=(220, 80, 80))

    warning_lines = [
        "본 브리핑은 AI가 공개 데이터를 분석한 참고용 정보입니다.",
        "특정 종목의 매수·매도 권유가 아니며, 수익을 보장하지 않습니다.",
        "주식 투자는 원금 손실 위험이 있으며, 최종 투자 결정과",
        "모든 책임은 전적으로 투자자 본인에게 있습니다.",
    ]
    ty = cy + 52
    for line in warning_lines:
        if ty >= cy + warn_h - 10: break
        draw.text((MARGIN_X + 24, ty), line,
                  font=fnt(24, bold=False), fill=(200, 170, 170))
        ty += 32

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "99_closing.png"))
