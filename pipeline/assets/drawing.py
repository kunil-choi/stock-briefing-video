# pipeline/assets/drawing.py
import os
from PIL import Image, ImageDraw, ImageFont
from .config import W, H, C, FONT_PATHS


# ── 폰트 로더 ──────────────────────────────────────────────────────────────────
def fnt(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    key = "bold" if bold else "regular"
    for path in FONT_PATHS[key]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── 새 프레임 생성 ─────────────────────────────────────────────────────────────
def new_frame() -> Image.Image:
    img = Image.new("RGB", (W, H), C["bg"])
    return img


# ── 상단 바 ────────────────────────────────────────────────────────────────────
def draw_topbar(d: ImageDraw.Draw, label: str, color: tuple = None):
    color = color or C["tag_bg"]
    d.rectangle([0, 0, W, 70], fill=color)
    d.text((30, 14), label, font=fnt(36), fill=C["gold"])

    # 우측 날짜
    from datetime import datetime
    date_str = datetime.now().strftime("%Y.%m.%d")
    tw = fnt(28, bold=False).getbbox(date_str)[2]
    d.text((W - tw - 30, 20), date_str, font=fnt(28, bold=False), fill=C["white"])


# ── 하단 바 ────────────────────────────────────────────────────────────────────
def draw_bottombar(d: ImageDraw.Draw, stock_name: str, date_str: str, color: tuple = None):
    color = color or C["tag_bg"]
    d.rectangle([0, H - 60, W, H], fill=color)
    label = f"⚠ 본 브리핑은 AI 자동 생성 참고자료이며 투자 권유가 아닙니다  |  {stock_name}  {date_str}"
    d.text((30, H - 46), label, font=fnt(24, bold=False), fill=C["white"])


# ── 골드 언더라인 제목 ─────────────────────────────────────────────────────────
def gold_underline(d: ImageDraw.Draw, x: int, y: int, text: str, font_size: int = 52):
    f = fnt(font_size)
    d.text((x, y), text, font=f, fill=C["white"])
    tw = f.getbbox(text)[2]
    d.rectangle([x, y + font_size + 6, x + tw, y + font_size + 10], fill=C["gold"])


# ── 이미지 붙이기 (비율 유지 + 크롭) ──────────────────────────────────────────
def paste_image(base: Image.Image, path: str, box: tuple):
    """box = (x1, y1, x2, y2)"""
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    try:
        img = Image.open(path).convert("RGB")
        iw, ih = img.size
        scale = max(bw / iw, bh / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        ox = (nw - bw) // 2
        oy = (nh - bh) // 2
        img = img.crop((ox, oy, ox + bw, oy + bh))
        base.paste(img, (x1, y1))
    except Exception as e:
        print(f"  [paste_image] 실패: {e}")


# ── 텍스트 자동 줄바꿈 ─────────────────────────────────────────────────────────
def draw_wrapped_text(d: ImageDraw.Draw, text: str, x: int, y: int,
                      max_width: int, font_size: int = 36,
                      color: tuple = None, line_gap: int = 10) -> int:
    """텍스트를 max_width 안에서 자동 줄바꿈 후 마지막 y 반환"""
    color = color or C["white"]
    f = fnt(font_size, bold=False)
    words = text.replace("\n", " ").split(" ")
    line = ""
    cy = y
    for word in words:
        test = (line + " " + word).strip()
        if f.getbbox(test)[2] > max_width and line:
            d.text((x, cy), line, font=f, fill=color)
            cy += font_size + line_gap
            line = word
        else:
            line = test
    if line:
        d.text((x, cy), line, font=f, fill=color)
        cy += font_size + line_gap
    return cy


# ── 구분선 ─────────────────────────────────────────────────────────────────────
def draw_divider(d: ImageDraw.Draw, y: int, color: tuple = None):
    color = color or C["border"]
    d.rectangle([40, y, W - 40, y + 2], fill=color)


# ── 배지 (태그) ────────────────────────────────────────────────────────────────
def draw_badge(d: ImageDraw.Draw, x: int, y: int, text: str,
               bg: tuple = None, fg: tuple = None) -> int:
    """배지를 그리고 오른쪽 끝 x 반환"""
    bg = bg or C["tag_bg"]
    fg = fg or C["gold"]
    f = fnt(26)
    tw = f.getbbox(text)[2]
    pad = 16
    d.rounded_rectangle([(x, y), (x + tw + pad * 2, y + 44)], radius=8, fill=bg)
    d.text((x + pad, y + 6), text, font=f, fill=fg)
    return x + tw + pad * 2 + 12
