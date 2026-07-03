# pipeline/assets/builders.py
"""
KBS 머니올라 — 고품질 방송 비주얼 빌더
프레젠테이션 퀄리티: 정보를 그래픽 요소로 시각화
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


# ── 공통: 대형 지수 카드 ───────────────────────────────────────────────────

def _draw_index_card(draw, img, x, y, w, h, label, value, change, positive,
                     accent_color, label_color=None):
    """대형 지수 카드 — 깔끔한 정보 계층 구조"""
    bg = (14, 20, 58)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=20, fill=bg)

    # 상단 강조 바
    draw.rounded_rectangle([x, y, x + w, y + 6], radius=4, fill=accent_color)
    # 왼쪽 강조 바
    draw.rounded_rectangle([x, y, x + 6, y + h], radius=4, fill=(*accent_color, 180))

    # 레이블
    lc = label_color or accent_color
    draw.text((x + 28, y + 22), label, font=fnt(32, bold=True), fill=lc)

    # 값 (대형)
    draw.text((x + 28, y + 62), value, font=fnt(68, bold=True), fill=C["white"])

    # 등락 배지
    if change:
        ch_color = C["red"] if positive else C["blue"]
        arrow = "▲" if positive else "▼"
        badge_text = f" {arrow} {change} "
        try:
            bw2 = int(draw.textlength(badge_text, font=fnt(30, bold=True))) + 16
        except Exception:
            bw2 = 160
        bx = x + 28
        by = y + h - 56
        draw.rounded_rectangle([bx, by, bx + bw2, by + 44],
                                radius=10, fill=(*ch_color, 35))
        draw.rounded_rectangle([bx, by, bx + bw2, by + 44],
                                radius=10, outline=ch_color, width=1)
        draw.text((bx + 8, by + 7), f"{arrow} {change}",
                  font=fnt(30, bold=True), fill=ch_color)


def _draw_mini_index_row(draw, x, y, w, label, value, change, positive, accent_color):
    """소형 지수 행 — 여러 지수를 세로로 나열할 때"""
    h = 78
    draw.rounded_rectangle([x, y, x + w, y + h], radius=12, fill=(12, 18, 50))
    draw.rounded_rectangle([x, y, x + 5, y + h], radius=4, fill=accent_color)

    draw.text((x + 22, y + 10), label, font=fnt(26, bold=True),
              fill=(180, 185, 225))
    ch_color = C["red"] if positive else C["blue"]
    arrow = "▲" if positive else "▼"
    draw.text((x + w - 20, y + 10), value,
              font=fnt(30, bold=True), fill=C["white"], anchor="ra")
    draw.text((x + w - 20, y + 46), f"{arrow} {change}",
              font=fnt(22, bold=False), fill=ch_color, anchor="ra")
    return y + h + 10


# ── 오프닝 ─────────────────────────────────────────────────────────────────

def build_opening(data, out_dir):
    sec      = _find_section(data.get("sections", []), "opening")
    img      = new_frame(theme="default")
    draw     = ImageDraw.Draw(img)
    keywords = sec.get("keywords", [])
    date_str = data.get("date", "")

    # 중앙 원형 글로우 배경
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

    # KBS 머니올라 로고 배지
    badge_y = H // 2 - 310
    badge_w, badge_h = 380, 64
    draw.rounded_rectangle([CX - badge_w // 2, badge_y,
                             CX + badge_w // 2, badge_y + badge_h],
                            radius=32, fill=C["gold"])
    draw.text((CX, badge_y + badge_h // 2), "KBS 머니올라",
              font=fnt(36, bold=True), fill=(10, 12, 35), anchor="mm")

    cy = H // 2 - 210

    draw_glow_text(draw, (CX, cy), "주식시장 브리핑",
                   font=fnt(92, bold=True), fill=C["white"],
                   glow_color=C["gold"], glow_radius=4, anchor="mm")
    cy += 110

    draw.text((CX, cy), "오늘의 핵심만 골라 드립니다",
              font=fnt(42, bold=False), fill=(180, 190, 230), anchor="mm")
    cy += 60

    if date_str:
        dw = 320
        draw.rounded_rectangle([CX - dw // 2, cy, CX + dw // 2, cy + 52],
                                radius=26, fill=(20, 28, 75))
        draw.rounded_rectangle([CX - dw // 2, cy, CX + dw // 2, cy + 52],
                                radius=26, outline=C["gold"], width=1)
        draw.text((CX, cy + 26), date_str,
                  font=fnt(32, bold=False), fill=C["gold"], anchor="mm")
        cy += 76

    for i in range(3):
        alpha = [200, 120, 60][i]
        offset = [0, 6, 12][i]
        draw.line([CX - 260 + offset, cy, CX + 260 - offset, cy],
                  fill=(*C["gold"], alpha), width=2 - i if i < 2 else 1)
    cy += 30

    if keywords:
        kw_colors = [C["gold"], C["green"], C["blue"], (220, 100, 220)]
        kw_list   = keywords[:4]
        font_kw   = fnt(30, bold=False)
        tag_hs    = []
        for kw in kw_list:
            try: tw = int(draw.textlength(kw, font=font_kw))
            except Exception: tw = len(kw) * 16
            tag_hs.append(tw + 44)
        total_w = sum(tag_hs) + 20 * (len(kw_list) - 1)
        kx = (W - total_w) // 2

        for i, kw in enumerate(kw_list):
            col = kw_colors[i % len(kw_colors)]
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
    sec = _find_section(data.get("sections", []), "market_summary")
    img  = new_frame(theme="blue")
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "오늘의 시장 요약")

    kospi        = sec.get("kospi_value", "")
    kospi_ch     = sec.get("kospi_change", "")
    kospi_pos    = sec.get("kospi_change_positive", True)
    kosdaq       = sec.get("kosdaq_value", "")
    kosdaq_ch    = sec.get("kosdaq_change", "")
    kosdaq_pos   = sec.get("kosdaq_change_positive", True)
    points       = sec.get("points", [])
    corner_summary = sec.get("corner_summary", "")

    # ── 레이아웃: 상단 2/3 = 지수 카드, 하단 1/3 = 핵심 포인트 ──

    # 코너 요약 한줄 배너
    cy = 96
    if corner_summary:
        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + 52],
                                radius=10, fill=(8, 25, 72))
        draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 5, cy + 52],
                                radius=0, fill=C["gold"])
        draw.text((MARGIN_X + 22, cy + 14), corner_summary,
                  font=fnt(28, bold=False), fill=C["gold"])
        cy += 68

    # ── 상단: 국내 지수 대형 카드 (좌) + 해외/환율 소형 스택 (우) ──
    LEFT_W  = int((W - MARGIN_X * 2) * 0.52)
    RIGHT_W = W - MARGIN_X * 2 - LEFT_W - 32
    CARD_H  = 200
    RX      = MARGIN_X + LEFT_W + 32

    # KOSPI 대형 카드
    if kospi:
        _draw_index_card(draw, img,
                         MARGIN_X, cy, LEFT_W, CARD_H,
                         "KOSPI", kospi, kospi_ch, kospi_pos,
                         C["gold"])

    # KOSDAQ 소형 (우측 상단)
    ry = cy
    if kosdaq:
        ry = _draw_mini_index_row(draw, RX, ry, RIGHT_W,
                                  "KOSDAQ", kosdaq, kosdaq_ch, kosdaq_pos,
                                  C["blue"])

    # 해외 지수 — script에서 제공되지 않으면 레이블만 표시
    overseas = [
        ("NASDAQ", sec.get("nasdaq_value", ""), sec.get("nasdaq_change", ""), sec.get("nasdaq_positive", False)),
        ("S&P500",  sec.get("sp500_value", ""),  sec.get("sp500_change", ""),  sec.get("sp500_positive",  False)),
        ("USD/KRW", sec.get("usdkrw_value", ""), sec.get("usdkrw_change", ""), sec.get("usdkrw_positive", False)),
    ]
    for label, val, ch, pos in overseas:
        if val and ry + 88 < cy + CARD_H + 10:
            ry = _draw_mini_index_row(draw, RX, ry, RIGHT_W,
                                      label, val, ch or "", pos,
                                      (100, 220, 220))

    cy += CARD_H + 28

    # ── 구분선 ──
    draw_divider(draw, cy, style="gradient")
    cy += 24

    # ── 핵심 포인트: 번호+텍스트 카드 ──
    if points:
        # 타이틀
        draw.text((MARGIN_X, cy), "오늘의 핵심 포인트",
                  font=fnt(30, bold=True), fill=C["gold"])
        cy += 46

        icon_colors = [C["gold"], C["green"], C["blue"], (220, 100, 220), C["red"]]
        col_count = 2
        col_w = (W - MARGIN_X * 2 - 20) // col_count
        pt_h  = 80

        for i, point in enumerate(points[:6]):
            if cy + pt_h > Y_MAX: break
            col_idx = i % col_count
            row_idx = i // col_count
            px = MARGIN_X + col_idx * (col_w + 20)
            py = cy + row_idx * (pt_h + 10)
            if py + pt_h > Y_MAX: break

            color = icon_colors[i % len(icon_colors)]
            # 카드 배경
            draw.rounded_rectangle([px, py, px + col_w, py + pt_h],
                                    radius=12, fill=(12, 18, 52))
            # 컬러 왼쪽 바
            draw.rounded_rectangle([px, py, px + 5, py + pt_h],
                                    radius=4, fill=color)
            # 번호 원
            draw.ellipse([px + 14, py + pt_h // 2 - 18,
                          px + 50, py + pt_h // 2 + 18],
                         fill=(*color, 40))
            draw.ellipse([px + 14, py + pt_h // 2 - 18,
                          px + 50, py + pt_h // 2 + 18],
                         outline=color, width=2)
            draw.text((px + 32, py + pt_h // 2), str(i + 1),
                      font=fnt(24, bold=True), fill=color, anchor="mm")
            # 텍스트
            draw_wrapped_text(draw, point,
                              px + 60, py + 12, col_w - 72,
                              size=24, bold=False, color=C["white"], line_gap=8)

    draw_bottombar(draw)
    return [_save(img, os.path.join(out_dir, "01_market_00.png"))]


# ── 업종 분석 ───────────────────────────────────────────────────────────────

def build_sector(data, out_dir):
    sec  = _find_section(data.get("sections", []), "sectors")
    img  = new_frame(theme="purple")
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "핵심 업종 분석", color=(25, 12, 55))

    sector_list    = sec.get("sector_list", sec.get("sectors", sec.get("list", [])))
    corner_summary = sec.get("corner_summary", "")

    cy = 96

    if corner_summary:
        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + 52],
                                radius=10, fill=(30, 18, 65))
        draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 5, cy + 52],
                                radius=0, fill=C["gold"])
        draw.text((MARGIN_X + 22, cy + 14), corner_summary,
                  font=fnt(28, bold=False), fill=C["gold"])
        cy += 68

    palette = [
        C["gold"], C["green"], C["blue"],
        (220, 100, 220), C["red"], (100, 220, 220),
    ]
    momentum_colors = {"상승": C["red"], "하락": C["blue"], "보합": C["gold"]}

    # ── 섹터 카드: 2열 그리드, 카드 내부 정보 계층 강화 ──
    col_count = 2
    col_w = (W - MARGIN_X * 2 - 24) // col_count
    card_h = 148

    for idx, sector in enumerate(sector_list[:6]):
        color = palette[idx % len(palette)]
        if isinstance(sector, dict):
            name     = sector.get("name", "")
            desc     = sector.get("desc", sector.get("description", ""))
            momentum = sector.get("momentum", "")
        else:
            name = str(sector); desc = ""; momentum = ""

        col_i  = idx % col_count
        row_i  = idx // col_count
        card_x = MARGIN_X + col_i * (col_w + 24)
        card_y = cy + row_i * (card_h + 14)
        if card_y + card_h > Y_MAX: break

        # 카드 배경
        draw.rounded_rectangle([card_x, card_y, card_x + col_w, card_y + card_h],
                                radius=18, fill=(15, 12, 48))
        # 상단 컬러 바
        draw.rounded_rectangle([card_x, card_y, card_x + col_w, card_y + 5],
                                radius=4, fill=color)

        # 번호 원 (좌측)
        cx_icon = card_x + 40
        cy_icon = card_y + 44
        draw.ellipse([cx_icon - 26, cy_icon - 26, cx_icon + 26, cy_icon + 26],
                     fill=(*color, 45))
        draw.ellipse([cx_icon - 26, cy_icon - 26, cx_icon + 26, cy_icon + 26],
                     outline=color, width=2)
        draw.text((cx_icon, cy_icon), str(idx + 1),
                  font=fnt(26, bold=True), fill=color, anchor="mm")

        # 섹터명
        draw.text((card_x + 80, card_y + 18), name,
                  font=fnt(36, bold=True), fill=C["white"])

        # 모멘텀 배지 (우측 상단)
        if momentum:
            mom_col = momentum_colors.get(momentum, C["gold"])
            try:
                mw = int(draw.textlength(momentum, font=fnt(22, bold=True))) + 24
            except Exception:
                mw = 80
            mx = card_x + col_w - mw - 12
            my = card_y + 16
            draw.rounded_rectangle([mx, my, mx + mw, my + 36],
                                    radius=18, fill=(*mom_col, 40))
            draw.rounded_rectangle([mx, my, mx + mw, my + 36],
                                    radius=18, outline=mom_col, width=1)
            draw.text((mx + mw // 2, my + 18), momentum,
                      font=fnt(22, bold=True), fill=mom_col, anchor="mm")

        # 설명 텍스트
        if desc:
            draw_wrapped_text(draw, desc,
                              card_x + 80, card_y + 66,
                              col_w - 96, size=24,
                              color=(170, 175, 215), line_gap=8)

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "02_sector.png"))


# ── 종목 요약 슬라이드 ──────────────────────────────────────────────────────

def _build_stock_summary(sec, out_path, img_dir):
    stock_name   = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    price        = sec.get("price", "")
    change       = sec.get("change", "")
    positive     = sec.get("change_positive", True)
    summary      = sec.get("summary", "")
    catalysts    = sec.get("catalysts", [])
    risks        = sec.get("risks", [])
    corner_summary = sec.get("corner_summary", "")
    is_hidden    = sec.get("id", "").startswith("hidden_")
    theme        = "purple" if is_hidden else "default"

    img  = new_frame(theme=theme)
    draw = ImageDraw.Draw(img)
    bar_label = "숨은 종목 분석" if is_hidden else "종목 분석"
    bar_color = (35, 12, 65) if is_hidden else None
    draw_topbar(draw, f"{bar_label}: {stock_name}", color=bar_color)

    # ── 뉴스 이미지 (우측 상단, 원형 마스크) ──────────────────────────
    img_path = fetch_news_image(stock_name, img_dir, [])
    if img_path:
        try:
            logo_size = 180
            logo_x    = W - MARGIN_X - logo_size
            logo_y    = 96
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

    # ── 상단 히어로 영역: 종목명 + 가격 + 신호 ──────────────────────
    HERO_Y = 96

    # 숨은 종목 배지
    if is_hidden:
        draw.rounded_rectangle([MARGIN_X, HERO_Y, MARGIN_X + 140, HERO_Y + 38],
                                radius=19, fill=C.get("hidden_accent", (80, 30, 120)))
        draw.text((MARGIN_X + 70, HERO_Y + 19), "숨은 종목",
                  font=fnt(24, bold=True), fill=C["white"], anchor="mm")
        HERO_Y += 46

    # 종목명 (대형 글로우)
    draw_glow_text(draw, (MARGIN_X, HERO_Y), stock_name,
                   font=fnt(78, bold=True), fill=C["white"],
                   glow_color=C["gold"], glow_radius=3)

    # 가격 + 등락
    PRICE_Y = HERO_Y + 90
    if price:
        draw.text((MARGIN_X, PRICE_Y), f"₩ {price}",
                  font=fnt(56, bold=True), fill=C["gold"])
        if change:
            try:
                px = MARGIN_X + int(draw.textlength(f"₩ {price}", font=fnt(56, bold=True))) + 20
            except Exception:
                px = MARGIN_X + len(f"₩ {price}") * 30 + 20
            ch_color = C["red"] if positive else C["blue"]
            arrow = "▲" if positive else "▼"
            try:
                chw = int(draw.textlength(f"{arrow} {change}", font=fnt(32, bold=True))) + 24
            except Exception:
                chw = 120
            draw.rounded_rectangle([px, PRICE_Y + 8, px + chw, PRICE_Y + 52],
                                    radius=10, fill=(*ch_color, 35))
            draw.rounded_rectangle([px, PRICE_Y + 8, px + chw, PRICE_Y + 52],
                                    radius=10, outline=ch_color, width=1)
            draw.text((px + 12, PRICE_Y + 14), f"{arrow} {change}",
                      font=fnt(32, bold=True), fill=ch_color)

    # 한줄 요약 (코너 요약 또는 summary)
    SUMMARY_Y = PRICE_Y + 66
    summary_text = corner_summary or summary
    if summary_text:
        # 배경 배너
        draw.rounded_rectangle([MARGIN_X, SUMMARY_Y, W - 260, SUMMARY_Y + 48],
                                radius=10, fill=(14, 22, 60))
        draw.rounded_rectangle([MARGIN_X, SUMMARY_Y, MARGIN_X + 5, SUMMARY_Y + 48],
                                radius=0, fill=C["gold"])
        draw_wrapped_text(draw, f"  {summary_text}",
                          MARGIN_X + 16, SUMMARY_Y + 9,
                          W - 280, size=26, bold=False,
                          color=(210, 215, 240), line_gap=8)

    # ── 구분선 ──
    DIV_Y = H // 2 + 10
    draw_divider(draw, DIV_Y, style="gradient")

    # ── 하단 2분할: 투자 포인트(좌) / 리스크(우) ──────────────────────
    LOWER_Y = DIV_Y + 24
    half_w  = (W - MARGIN_X * 2 - 32) // 2

    # 투자 포인트 섹션
    if catalysts:
        # 섹션 타이틀 바
        draw.rounded_rectangle([MARGIN_X, LOWER_Y, MARGIN_X + half_w, LOWER_Y + 36],
                                radius=8, fill=(*C["red"], 200))
        draw.text((MARGIN_X + 14, LOWER_Y + 5), "▶  투자 포인트",
                  font=fnt(26, bold=True), fill=C["white"])
        ty = LOWER_Y + 48
        for cat in catalysts[:4]:
            if ty >= Y_MAX - 8: break
            # 불릿
            draw.ellipse([MARGIN_X + 10, ty + 8, MARGIN_X + 22, ty + 20],
                         fill=C["red"])
            ty = draw_wrapped_text(draw, f"   {cat}",
                                   MARGIN_X, ty, half_w,
                                   size=25, line_gap=10, color=(230, 235, 255))
            ty += 4

    # 리스크 섹션
    if risks:
        rx = MARGIN_X + half_w + 32
        draw.rounded_rectangle([rx, LOWER_Y, rx + half_w, LOWER_Y + 36],
                                radius=8, fill=(*C["blue"], 200))
        draw.text((rx + 14, LOWER_Y + 5), "▶  리스크",
                  font=fnt(26, bold=True), fill=C["white"])
        ty = LOWER_Y + 48
        for risk in risks[:4]:
            if ty >= Y_MAX - 8: break
            draw.ellipse([rx + 10, ty + 8, rx + 22, ty + 20],
                         fill=C["blue"])
            ty = draw_wrapped_text(draw, f"   {risk}",
                                   rx, ty, half_w,
                                   size=25, line_gap=10, color=(230, 235, 255))
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
        draw.rounded_rectangle([MARGIN_X, H // 2 - 60, W - MARGIN_X, H // 2 + 60],
                                radius=16, fill=(18, 30, 22))
        draw.text((CX, H // 2), f"{stock_name} 차트 데이터 준비 중",
                  font=fnt(36), fill=(200, 200, 220), anchor="mm")

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
    card_h  = min(250, (avail_h - 20 * n) // n)

    mention_colors = [C["gold"], C["green"], C["blue"]]

    for mi, m in enumerate(page_mentions):
        if cy >= Y_MAX: break
        if isinstance(m, str):
            m = {"speaker": "", "channel": "", "quote_subtitle": m}

        speaker  = (m.get("speaker") or "").strip()
        channel  = (m.get("channel") or m.get("source") or "").strip()
        content  = m.get("quote_subtitle", m.get("quote", m.get("content", "")))
        accent_col = mention_colors[mi % len(mention_colors)]
        actual_h   = min(card_h, Y_MAX - cy)

        # 카드 배경
        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + actual_h],
                                radius=18, fill=(14, 16, 46))
        # 왼쪽 강조 바
        draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 7, cy + actual_h],
                                radius=4, fill=accent_col)
        # 상단 하이라이트
        draw.line([MARGIN_X + 18, cy + 1, W - MARGIN_X - 18, cy + 1],
                  fill=(*accent_col, 35), width=1)

        # 채널/발화자 배지
        header_parts = []
        if channel:
            header_parts.append(channel)
        if speaker:
            header_parts.append(speaker)
        header = "  |  ".join(header_parts)

        if header:
            try:
                hw = int(draw.textlength(header, font=fnt(26, bold=True))) + 32
            except Exception:
                hw = min(len(header) * 14 + 32, 600)
            draw.rounded_rectangle([MARGIN_X + 18, cy + 12,
                                     MARGIN_X + 18 + hw, cy + 48],
                                    radius=18, fill=(30, 30, 60))
            draw.text((MARGIN_X + 34, cy + 30), header,
                      font=fnt(26, bold=True), fill=(240, 240, 250), anchor="lm")

        # 인용부호 장식 (우측)
        draw.text((W - MARGIN_X - 56, cy + 10), "\u275d",
                  font=fnt(44, bold=False), fill=(*accent_col, 55))

        # 내용 텍스트
        if content:
            draw_wrapped_text(draw, content,
                              MARGIN_X + 28, cy + 60,
                              W - MARGIN_X * 2 - 56,
                              size=28, color=C["white"], line_gap=14)

        cy += actual_h + 18

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


# ── 집계형 종목 섹션 (추가 관심 종목 / 오늘의 픽 / 증권사 리포트) ────────────
# summary+chart+mention 개별 카드가 아니라 단일 나레이션 슬라이드 한 장으로 구성.

def _build_aggregate_stock_slide(sec, out_dir, filename, title, theme="default", bar_color=None):
    img  = new_frame(theme=theme)
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, title, color=bar_color)

    corner_summary = sec.get("corner_summary", "")
    body_text = sec.get("subtitle", sec.get("narration", ""))

    cy = 96
    if corner_summary:
        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + 52],
                                radius=10, fill=(14, 22, 60))
        draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 5, cy + 52],
                                radius=0, fill=C["gold"])
        draw.text((MARGIN_X + 22, cy + 14), corner_summary,
                  font=fnt(28, bold=False), fill=C["gold"])
        cy += 68

    if body_text:
        draw_wrapped_text(draw, body_text,
                          MARGIN_X, cy, W - MARGIN_X * 2,
                          size=30, bold=False, color=C["white"], line_gap=14)

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, filename))


def build_extra_watchlist(data, out_dir):
    sec = _find_section(data.get("sections", []), "stock_추가관심종목")
    if not sec:
        return None
    return _build_aggregate_stock_slide(sec, out_dir, "90_extra_watchlist.png",
                                        "추가 관심 종목", theme="blue")


def build_today_pick(data, out_dir):
    sec = _find_section(data.get("sections", []), "stock_오늘의픽")
    if not sec:
        return None
    return _build_aggregate_stock_slide(sec, out_dir, "91_today_pick.png",
                                        "오늘의 픽", theme="purple", bar_color=(35, 12, 65))


def build_brokerage_report(data, out_dir):
    sec = _find_section(data.get("sections", []), "stock_증권사리포트")
    if not sec:
        return None
    return _build_aggregate_stock_slide(sec, out_dir, "92_brokerage_report.png",
                                        "증권사 리포트", theme="green", bar_color=(8, 30, 18))


# ── AI 투자 전략 ────────────────────────────────────────────────────────────

def build_ai_strategy(data, out_dir):
    sec  = _find_section(data.get("sections", []), "ai_strategy")
    img  = new_frame(theme="purple")
    draw = ImageDraw.Draw(img)
    draw_topbar(draw, "AI 투자 전략", color=(22, 10, 55))

    corner_summary = sec.get("corner_summary", "")
    bullet_points  = sec.get("bullet_points", sec.get("strategies", sec.get("items", [])))

    cy = 96

    # 헤더 카드
    draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + 82],
                            radius=14, fill=(18, 12, 52))
    draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 6, cy + 82],
                            radius=4, fill=C["gold"])

    # AI 배지
    draw.rounded_rectangle([MARGIN_X + 20, cy + 16,
                             MARGIN_X + 84, cy + 66],
                            radius=10, fill=(*C["gold"], 30))
    draw.rounded_rectangle([MARGIN_X + 20, cy + 16,
                             MARGIN_X + 84, cy + 66],
                            radius=10, outline=C["gold"], width=1)
    draw.text((MARGIN_X + 52, cy + 41), "AI",
              font=fnt(36, bold=True), fill=C["gold"], anchor="mm")

    draw.text((MARGIN_X + 100, cy + 18), "오늘의 투자 전략 제안",
              font=fnt(34, bold=True), fill=C["white"])
    if corner_summary:
        draw.text((MARGIN_X + 100, cy + 54), corner_summary,
                  font=fnt(24, bold=False), fill=(160, 168, 210))

    cy += 102

    # 전략 카드 목록
    card_h = 104
    strategy_colors = [C["gold"], C["green"], C["blue"],
                       (220, 100, 220), C["red"], (100, 200, 220)]

    for i, bp in enumerate(bullet_points[:6]):
        if cy + card_h > Y_MAX: break
        text  = bp if isinstance(bp, str) else bp.get("strategy", bp.get("content", str(bp)))
        color = strategy_colors[i % len(strategy_colors)]

        draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + card_h],
                                radius=14, fill=(15, 12, 44))
        # 왼쪽 강조 바
        draw.rounded_rectangle([MARGIN_X, cy, MARGIN_X + 6, cy + card_h],
                                radius=4, fill=color)

        # 번호 배지
        draw.ellipse([MARGIN_X + 18, cy + card_h // 2 - 24,
                      MARGIN_X + 66, cy + card_h // 2 + 24],
                     fill=(*color, 45))
        draw.ellipse([MARGIN_X + 18, cy + card_h // 2 - 24,
                      MARGIN_X + 66, cy + card_h // 2 + 24],
                     outline=color, width=2)
        draw.text((MARGIN_X + 42, cy + card_h // 2), str(i + 1),
                  font=fnt(28, bold=True), fill=color, anchor="mm")

        # 내용
        if " — " in text:
            stock_part, strat_part = text.split(" — ", 1)
            draw.text((MARGIN_X + 82, cy + 16), stock_part.strip(),
                      font=fnt(30, bold=True), fill=color)
            draw_wrapped_text(draw, strat_part.strip(),
                              MARGIN_X + 82, cy + 54,
                              W - MARGIN_X * 2 - 100,
                              size=26, color=C["white"], line_gap=8)
        else:
            draw_wrapped_text(draw, text,
                              MARGIN_X + 82, cy + 24,
                              W - MARGIN_X * 2 - 100,
                              size=28, color=C["white"], line_gap=10)

        cy += card_h + 12

    draw_bottombar(draw)
    return _save(img, os.path.join(out_dir, "98_ai_strategy.png"))


# ── 클로징 ─────────────────────────────────────────────────────────────────

def build_closing(data, out_dir):
    sec        = _find_section(data.get("sections", []), "closing")
    img        = new_frame(theme="default")
    draw       = ImageDraw.Draw(img)

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

    draw.line([CX - 280, cy, CX + 280, cy], fill=C["gold"], width=2)
    cy += 24

    warn_h = 170
    draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + warn_h],
                            radius=14, fill=(40, 10, 10))
    draw.rounded_rectangle([MARGIN_X, cy, W - MARGIN_X, cy + warn_h],
                            radius=14, outline=(180, 40, 40), width=2)
    draw.text((MARGIN_X + 24, cy + 14), "투자 유의사항",
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
