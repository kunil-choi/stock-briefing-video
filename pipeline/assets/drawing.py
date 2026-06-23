# pipeline/assets/drawing.py
"""
고품질 방송용 비주얼 드로잉 모듈
- 멀티레이어 그라디언트 배경
- 유리 효과 카드 (glassmorphism)
- 골드/그린/레드 강조 색상 시스템
- 반투명 오버레이, 글로우 효과
"""
import os
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .config import W, H, C, FONT_PATHS

# ── 폰트 경로 탐색 ────────────────────────────────────────────────────────

def _find_font(bold: bool) -> str | None:
    candidates = FONT_PATHS.get("bold" if bold else "regular", [])
    for p in candidates:
        if os.path.isfile(p):
            return p
    try:
        result = subprocess.run(
            ["fc-list", ":lang=ko", "--format=%{file}\n"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            p = line.strip()
            if not p:
                continue
            lower = p.lower()
            if bold and any(k in lower for k in ["bold", "heavy", "black"]):
                if os.path.isfile(p): return p
            elif not bold and not any(k in lower for k in ["bold", "heavy", "black"]):
                if os.path.isfile(p): return p
        for line in result.stdout.splitlines():
            p = line.strip()
            if p and os.path.isfile(p): return p
    except Exception:
        pass
    fallback_bold = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Bold.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    ]
    fallback_regular = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for p in (fallback_bold if bold else fallback_regular):
        if os.path.isfile(p): return p
    return None


_FONT_PATH_BOLD    = _find_font(bold=True)
_FONT_PATH_REGULAR = _find_font(bold=False)

if _FONT_PATH_BOLD:    print(f"[drawing] Bold 폰트: {_FONT_PATH_BOLD}")
else:                  print("[drawing] ⚠️ Bold 한글 폰트를 찾지 못했습니다.")
if _FONT_PATH_REGULAR: print(f"[drawing] Regular 폰트: {_FONT_PATH_REGULAR}")
else:                  print("[drawing] ⚠️ Regular 한글 폰트를 찾지 못했습니다.")

_font_cache: dict = {}

def fnt(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _font_cache: return _font_cache[key]
    path = _FONT_PATH_BOLD if bold else _FONT_PATH_REGULAR
    if path:
        try:
            font = ImageFont.truetype(path, size)
            _font_cache[key] = font
            return font
        except Exception as e:
            print(f"[drawing] 폰트 로드 실패 ({path}, size={size}): {e}")
    default = ImageFont.load_default()
    _font_cache[key] = default
    return default


# ── 색상 유틸 ─────────────────────────────────────────────────────────────

def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def _with_alpha(rgb, a):
    return (rgb[0], rgb[1], rgb[2], a)


# ── 고품질 배경 생성 ──────────────────────────────────────────────────────

def new_frame(theme: str = "default") -> Image.Image:
    """멀티레이어 그라디언트 배경 캔버스를 반환합니다."""
    img = Image.new("RGB", (W, H), (8, 10, 30))
    draw = ImageDraw.Draw(img)

    themes = {
        "default": [(8, 10, 30), (16, 24, 72), (10, 18, 55)],
        "gold":    [(20, 14, 5), (40, 30, 8), (25, 20, 5)],
        "blue":    [(5, 15, 40), (8, 30, 70), (5, 20, 50)],
        "green":   [(5, 25, 15), (8, 45, 25), (5, 35, 18)],
        "purple":  [(20, 8, 40), (35, 15, 70), (25, 10, 50)],
        "dark":    [(5, 5, 20), (12, 12, 40), (8, 8, 30)],
    }
    colors = themes.get(theme, themes["default"])

    # 수직 그라디언트 (3색 정지점)
    for y in range(H):
        t = y / H
        if t < 0.5:
            col = _lerp_color(colors[0], colors[1], t * 2)
        else:
            col = _lerp_color(colors[1], colors[2], (t - 0.5) * 2)
        draw.line([0, y, W, y], fill=col)

    # 미묘한 격자 패턴 (프로 방송 느낌)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for x in range(0, W, 80):
        odraw.line([x, 0, x, H], fill=(255, 255, 255, 4))
    for y in range(0, H, 80):
        odraw.line([0, y, W, y], fill=(255, 255, 255, 4))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # 코너 비네팅 효과
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for r in range(200, 0, -2):
        alpha = int((1 - r / 200) * 60)
        vdraw.ellipse([
            W // 2 - r * 5, H // 2 - r * 3,
            W // 2 + r * 5, H // 2 + r * 3
        ], fill=(0, 0, 0, 0), outline=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB")

    return img


# ── 유리 효과 카드 ────────────────────────────────────────────────────────

def draw_glass_card(img: Image.Image, draw: ImageDraw.ImageDraw,
                    box: tuple, color: tuple = None,
                    opacity: int = 55, radius: int = 18,
                    border_color: tuple = None, border_width: int = 1):
    """반투명 유리 효과 카드를 그립니다."""
    x1, y1, x2, y2 = box
    card_color = color or (30, 40, 90)
    alpha_color = (*card_color, opacity)

    # 배경 블러 영역
    region = img.crop(box)
    try:
        blurred = region.filter(ImageFilter.GaussianBlur(radius=3))
        overlay = Image.new("RGBA", region.size, alpha_color)
        blended = Image.alpha_composite(blurred.convert("RGBA"), overlay)
        img.paste(blended.convert("RGB"), (x1, y1))
    except Exception:
        pass

    # 테두리
    border = border_color or (80, 100, 180, 60)
    if len(border) == 3:
        border = (*border, 80)
    border_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(border_img)
    bdraw.rounded_rectangle([x1, y1, x2, y2], radius=radius,
                             outline=border, width=border_width, fill=(0, 0, 0, 0))
    img.paste(Image.alpha_composite(img.convert("RGBA"), border_img).convert("RGB"),
              (0, 0))

    # 상단 하이라이트 라인 (유리 효과)
    draw.line([x1 + radius, y1, x2 - radius, y1],
              fill=(255, 255, 255, 30), width=1)


def draw_rounded_card(draw: ImageDraw.ImageDraw, box: tuple,
                      fill: tuple, radius: int = 16,
                      border: tuple = None, border_width: int = 1):
    """그라디언트 없는 단순 라운드 카드."""
    draw.rounded_rectangle(box, radius=radius, fill=fill)
    if border:
        draw.rounded_rectangle(box, radius=radius, outline=border, width=border_width)


def draw_accent_card(draw: ImageDraw.ImageDraw, box: tuple,
                     accent_color: tuple, fill: tuple = None,
                     radius: int = 16, accent_width: int = 6):
    """왼쪽 강조 컬러 바가 있는 카드."""
    x1, y1, x2, y2 = box
    bg = fill or C["card"]
    draw.rounded_rectangle(box, radius=radius, fill=bg)
    draw.rounded_rectangle([x1, y1, x1 + accent_width, y2],
                            radius=radius // 2, fill=accent_color)


# ── 글로우 텍스트 ─────────────────────────────────────────────────────────

def draw_glow_text(draw: ImageDraw.ImageDraw, pos: tuple, text: str,
                   font, fill: tuple, glow_color: tuple = None,
                   glow_radius: int = 3, anchor: str = None):
    """글로우 효과가 있는 텍스트를 그립니다."""
    glow = glow_color or tuple(min(255, int(c * 1.5)) for c in fill[:3])
    for dx in range(-glow_radius, glow_radius + 1):
        for dy in range(-glow_radius, glow_radius + 1):
            if dx == 0 and dy == 0:
                continue
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > glow_radius:
                continue
            alpha = int(40 * (1 - dist / glow_radius))
            glow_col = (*glow, alpha)
            glow_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow_img)
            gx = pos[0] + dx
            gy = pos[1] + dy
            if anchor:
                gdraw.text((gx, gy), text, font=font, fill=glow_col, anchor=anchor)
            else:
                gdraw.text((gx, gy), text, font=font, fill=glow_col)

    if anchor:
        draw.text(pos, text, font=font, fill=fill, anchor=anchor)
    else:
        draw.text(pos, text, font=font, fill=fill)


# ── 프레임 생성 ────────────────────────────────────────────────────────────

def new_frame_simple() -> Image.Image:
    """기본 단색 배경 (하위 호환)."""
    return Image.new("RGB", (W, H), C["bg"])


# ── 상단 바 ────────────────────────────────────────────────────────────────

def draw_topbar(draw: ImageDraw.ImageDraw, label: str, color=None):
    """현대적인 상단 바 (그라디언트 + 브랜드)."""
    import re
    from datetime import date

    bar_color = color or (15, 18, 55)

    # 상단 바 배경
    draw.rectangle([0, 0, W, 78], fill=bar_color)

    # KBS 머니올라 로고 영역 (왼쪽)
    logo_bg = (20, 25, 70)
    draw.rectangle([0, 0, 220, 78], fill=logo_bg)
    draw.text((14, 12), "KBS", font=fnt(30, bold=True), fill=C["gold"])
    draw.text((14, 44), "머니올라", font=fnt(22, bold=True), fill=(200, 200, 220))

    # 구분선 (수직)
    draw.line([220, 8, 220, 70], fill=C["gold"], width=2)

    # 섹션 레이블 (이모지 제거)
    clean_label = re.sub(
        r'[\U00010000-\U0010ffff\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]',
        '', label
    ).strip()
    draw.text((242, 22), clean_label, font=fnt(34, bold=True), fill=C["white"])

    # 날짜 (오른쪽)
    date_str = date.today().strftime("%Y.%m.%d")
    draw.text((W - 30, 24), date_str, font=fnt(28, bold=False),
              fill=C["gold"], anchor="ra")

    # 골드 하단 경계선 (그라디언트 느낌)
    for i, x in enumerate(range(0, W, 3)):
        alpha = int(255 * (0.5 + 0.5 * math.sin(x / W * math.pi)))
        gold_w = tuple(int(c * alpha / 255) for c in C["gold"])
        draw.line([x, 78, x + 3, 78], fill=gold_w, width=2)


# ── 하단 바 (투자 경고 포함) ───────────────────────────────────────────────

def draw_bottombar(draw: ImageDraw.ImageDraw, stock_name: str = ""):
    """투자 경고가 표시되는 하단 바."""
    draw.rectangle([0, H - 56, W, H], fill=(10, 12, 40))
    draw.line([0, H - 56, W, H - 56], fill=C["gold"], width=2)

    disclaimer = "⚠️ 본 브리핑은 AI 분석 참고자료이며, 투자 권유가 아닙니다. 주식 투자에는 원금 손실 위험이 있습니다. 최종 투자 결정과 책임은 본인에게 있습니다."
    # 이모지 제거 후 렌더링
    import re
    clean = re.sub(
        r'[\U00010000-\U0010ffff\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]',
        '', disclaimer
    ).strip()
    draw.text((30, H - 38), clean,
              font=fnt(20, bold=False), fill=(140, 140, 170))
    if stock_name:
        draw.text((W - 30, H - 38), f"#{stock_name}",
                  font=fnt(22, bold=False), fill=C["gold"], anchor="ra")


# ── 텍스트 줄바꿈 ──────────────────────────────────────────────────────────

def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int, y: int,
    max_width: int,
    size: int = 30,
    bold: bool = False,
    color=None,
    line_gap: int = 10,
) -> int:
    """최대 너비에 맞게 텍스트를 줄바꿈하며 그립니다."""
    if not text: return y
    font  = fnt(size, bold=bold)
    color = color or C["white"]
    line  = ""

    for ch in list(text):
        test = line + ch
        try:
            tw = int(draw.textlength(test, font=font))
        except Exception:
            tw = len(test) * (size // 2)
        if tw > max_width and line:
            draw.text((x, y), line, font=font, fill=color)
            y   += size + line_gap
            line = ch
        else:
            line = test

    if line:
        draw.text((x, y), line, font=font, fill=color)
        y += size + line_gap

    return y


# ── 구분선 ─────────────────────────────────────────────────────────────────

def draw_divider(draw: ImageDraw.ImageDraw, y: int,
                 color=None, margin: int = 60, style: str = "solid"):
    """수평 구분선."""
    col = color or (60, 70, 130)
    if style == "gradient":
        for i in range(margin, W - margin):
            t = (i - margin) / (W - 2 * margin)
            a = int(255 * math.sin(t * math.pi))
            gc = tuple(int(c * a / 255) for c in col)
            draw.line([i, y, i, y], fill=gc, width=1)
    else:
        draw.line([margin, y, W - margin, y], fill=col, width=1)


# ── 배지 ──────────────────────────────────────────────────────────────────

def draw_badge(draw: ImageDraw.ImageDraw, x: int, y: int,
               text: str, bg=None, fg=None, size: int = 26) -> int:
    bg  = bg  or C.get("tag_bg", (40, 40, 80))
    fg  = fg  or C["gold"]
    font = fnt(size, bold=False)
    try: tw = int(draw.textlength(text, font=font))
    except Exception: tw = len(text) * (size // 2)
    pad = 14
    rx2 = x + tw + pad * 2
    ry2 = y + size + pad
    draw.rounded_rectangle([x, y, rx2, ry2], radius=10, fill=bg)
    draw.text((x + pad, y + pad // 2), text, font=font, fill=fg)
    return rx2 + 12


# ── 진행 바 (차트 시각화 보조) ────────────────────────────────────────────

def draw_progress_bar(draw: ImageDraw.ImageDraw, x: int, y: int,
                      width: int, height: int, value: float,
                      max_value: float = 100,
                      fg_color: tuple = None, bg_color: tuple = None):
    """가로 진행 바를 그립니다."""
    bg = bg_color or (30, 35, 70)
    fg = fg_color or C["gold"]
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height // 2, fill=bg)
    fill_w = int(width * min(1.0, max(0.0, value / max_value)))
    if fill_w > 0:
        draw.rounded_rectangle([x, y, x + fill_w, y + height],
                                radius=height // 2, fill=fg)


# ── 수직 그라디언트 바 ────────────────────────────────────────────────────

def draw_gradient_bar(draw: ImageDraw.ImageDraw, x: int, y_top: int,
                      y_bottom: int, width: int,
                      top_color: tuple, bottom_color: tuple):
    """수직 그라디언트 바."""
    h = y_bottom - y_top
    for i in range(h):
        t = i / max(h - 1, 1)
        col = _lerp_color(top_color, bottom_color, t)
        draw.rectangle([x, y_top + i, x + width, y_top + i + 1], fill=col)


# ── 이미지 붙이기 ──────────────────────────────────────────────────────────

def paste_image(img: Image.Image, path: str, box: tuple):
    if not path or not os.path.isfile(path): return
    try:
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        src = Image.open(path).convert("RGBA")
        src.thumbnail((bw, bh), Image.LANCZOS)
        ox = box[0] + (bw - src.width) // 2
        oy = box[1] + (bh - src.height) // 2
        if src.mode == "RGBA":
            img.paste(src, (ox, oy), src)
        else:
            img.paste(src, (ox, oy))
    except Exception as e:
        print(f"[drawing] 이미지 붙이기 실패 ({path}): {e}")


# ── 레거시 호환 ───────────────────────────────────────────────────────────
gold_underline = None  # 미사용, 호환 유지용
