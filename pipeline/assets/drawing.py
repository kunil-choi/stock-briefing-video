# pipeline/assets/drawing.py
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
from .config import W, H, C, FONT_PATHS


def _find_font(bold: bool) -> str | None:
    """사용 가능한 폰트 경로를 탐색하여 반환"""
    candidates = list(FONT_PATHS["bold"] if bold else FONT_PATHS["regular"])

    # fc-list로 시스템 CJK 폰트 탐색
    try:
        result = subprocess.run(
            ["fc-list", ":lang=ko", "--format=%{file}\n"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            path = line.strip()
            if path and os.path.isfile(path):
                if bold and any(k in path for k in ["Bold", "bold", "Heavy", "Black"]):
                    candidates.insert(0, path)
                elif not bold and not any(k in path for k in ["Bold", "bold", "Heavy", "Black"]):
                    candidates.insert(0, path)
                else:
                    candidates.append(path)
    except Exception:
        pass

    # 알려진 경로 하드코딩
    known = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJKkr-Bold.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/AppleGothic.ttf",
        "/Library/Fonts/NanumGothicBold.ttf",
        "/Library/Fonts/NanumGothic.ttf",
    ]
    if bold:
        candidates += [p for p in known if "Bold" in p or "bold" in p]
        candidates += [p for p in known if "Bold" not in p and "bold" not in p]
    else:
        candidates += [p for p in known if "Bold" not in p and "bold" not in p]
        candidates += [p for p in known if "Bold" in p or "bold" in p]

    for path in candidates:
        if path and os.path.isfile(path):
            return path

    return None


# 폰트 경로를 프로세스 시작 시 한 번만 탐색해서 고정
_FONT_PATH_BOLD    = _find_font(bold=True)
_FONT_PATH_REGULAR = _find_font(bold=False)

if _FONT_PATH_BOLD:
    print(f"  [font] Bold 폰트: {_FONT_PATH_BOLD}")
else:
    print("  ⚠️  Bold 폰트를 찾지 못했습니다. 기본 폰트로 대체합니다.")

if _FONT_PATH_REGULAR:
    print(f"  [font] Regular 폰트: {_FONT_PATH_REGULAR}")
else:
    print("  ⚠️  Regular 폰트를 찾지 못했습니다. 기본 폰트로 대체합니다.")

# 폰트 캐시 — 고정된 경로 기반이므로 lru_cache 없이 dict로 안전하게 관리
_font_cache: dict = {}


def fnt(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    path = _FONT_PATH_BOLD if bold else _FONT_PATH_REGULAR
    if path:
        try:
            font = ImageFont.truetype(path, size)
            _font_cache[key] = font
            return font
        except Exception as e:
            print(f"  ⚠️  폰트 로드 실패 ({path}, size={size}): {e}")

    print(f"  ⚠️  폰트를 찾지 못했습니다 (size={size}, bold={bold}). 기본 폰트로 대체합니다.")
    fallback = ImageFont.load_default()
    _font_cache[key] = fallback
    return fallback


def new_frame() -> Image.Image:
    return Image.new("RGB", (W, H), C["bg"])


def draw_topbar(draw: ImageDraw.ImageDraw, label: str, color: tuple = None):
    from datetime import date
    bar_color = color or C["gold"]
    draw.rectangle([0, 0, W, 72], fill=bar_color)
    draw.text((40, 14), label, font=fnt(32, bold=True), fill=C["bg"])
    date_str = date.today().strftime("%Y.%m.%d")
    draw.text((W - 220, 18), date_str, font=fnt(28, bold=False), fill=C["bg"])


def draw_bottombar(draw: ImageDraw.ImageDraw, stock_name: str = ""):
    draw.rectangle([0, H - 60, W, H], fill=(20, 22, 50))
    disclaimer = "본 영상은 AI가 생성한 참고용 정보이며, 투자 권유가 아닙니다."
    draw.text((40, H - 42), disclaimer, font=fnt(22, bold=False), fill=(160, 160, 180))
    if stock_name:
        draw.text((W - 320, H - 42), stock_name, font=fnt(22, bold=True), fill=C["gold"])


def gold_underline(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, size: int = 48):
    draw.text((x, y), text, font=fnt(size, bold=True), fill=C["white"])
    try:
        bbox = draw.textbbox((x, y), text, font=fnt(size, bold=True))
        text_w = bbox[2] - bbox[0]
    except Exception:
        text_w = len(text) * size * 0.6
    draw.rectangle([x, y + size + 4, x + int(text_w), y + size + 10], fill=C["gold"])
    return y + size + 18


def paste_image(img: Image.Image, path: str, box: tuple):
    try:
        src = Image.open(path).convert("RGBA")
        bw, bh = box[2] - box[0], box[3] - box[1]
        src_ratio = src.width / src.height
        box_ratio = bw / bh
        if src_ratio > box_ratio:
            new_h = bh
            new_w = int(bh * src_ratio)
        else:
            new_w = bw
            new_h = int(bw / src_ratio)
        src = src.resize((new_w, new_h), Image.LANCZOS)
        crop_x = (new_w - bw) // 2
        crop_y = (new_h - bh) // 2
        src = src.crop((crop_x, crop_y, crop_x + bw, crop_y + bh))
        bg = Image.new("RGB", (bw, bh), C["card"])
        bg.paste(src, (0, 0), src.split()[3] if src.mode == "RGBA" else None)
        img.paste(bg, (box[0], box[1]))
    except Exception as e:
        print(f"  [이미지] 붙이기 실패: {e}")


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    size: int = 30,
    bold: bool = False,
    color: tuple = None,
    line_gap: int = 10,
) -> int:
    color = color or C["white"]
    font = fnt(size, bold=bold)
    line = ""
    for ch in list(text):
        test = line + ch
        try:
            w = draw.textlength(test, font=font)
        except Exception:
            w = len(test) * size * 0.6
        if w > max_width and line:
            draw.text((x, y), line, font=font, fill=color)
            y += size + line_gap
            line = ch
        else:
            line = test
    if line:
        draw.text((x, y), line, font=font, fill=color)
        y += size + line_gap
    return y


def draw_divider(draw: ImageDraw.ImageDraw, y: int, color: tuple = None, margin: int = 60):
    color = color or C["border"]
    draw.line([margin, y, W - margin, y], fill=color, width=2)


def draw_badge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    bg: tuple = None,
    fg: tuple = None,
    size: int = 26,
) -> int:
    bg = bg or C["tag_bg"]
    fg = fg or C["white"]
    font = fnt(size, bold=True)
    try:
        tw = draw.textlength(text, font=font)
    except Exception:
        tw = len(text) * size * 0.6
    pad = 16
    rx1, ry1 = x, y
    rx2, ry2 = int(x + tw + pad * 2), int(y + size + pad)
    draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=8, fill=bg)
    draw.text((rx1 + pad, ry1 + pad // 2), text, font=font, fill=fg)
    return rx2 + 12
