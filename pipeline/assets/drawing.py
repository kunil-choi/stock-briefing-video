# pipeline/assets/drawing.py
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
from .config import W, H, C, FONT_PATHS

# ── 폰트 경로를 모듈 로드 시점에 한 번만 결정 ──────────────────────────────

def _find_font(bold: bool) -> str | None:
    """시스템에서 한글 CJK 폰트 경로를 탐색하여 반환합니다."""
    # 1) config.py 에 정의된 경로 우선 시도
    candidates = FONT_PATHS.get("bold" if bold else "regular", [])
    for p in candidates:
        if os.path.isfile(p):
            return p

    # 2) fc-list 로 시스템 폰트 탐색 (Linux/macOS)
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
                if os.path.isfile(p):
                    return p
            elif not bold and not any(k in lower for k in ["bold", "heavy", "black"]):
                if os.path.isfile(p):
                    return p
        # bold/regular 구분 없이 첫 번째 한글 폰트라도 사용
        for line in result.stdout.splitlines():
            p = line.strip()
            if p and os.path.isfile(p):
                return p
    except Exception:
        pass

    # 3) 하드코딩된 공통 경로 fallback
    fallback_bold = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Bold.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo-Bold.otf",
        "/Library/Fonts/NanumGothicBold.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
    ]
    fallback_regular = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo-Regular.otf",
        "/Library/Fonts/NanumGothic.ttf",
        "C:/Windows/Fonts/malgun.ttf",
    ]
    fallbacks = fallback_bold if bold else fallback_regular
    for p in fallbacks:
        if os.path.isfile(p):
            return p

    return None


# 모듈 로드 시 한 번만 경로 탐색
_FONT_PATH_BOLD    = _find_font(bold=True)
_FONT_PATH_REGULAR = _find_font(bold=False)

if _FONT_PATH_BOLD:
    print(f"[drawing] Bold 폰트: {_FONT_PATH_BOLD}")
else:
    print("[drawing] ⚠️ Bold 한글 폰트를 찾지 못했습니다. 기본 폰트를 사용합니다.")

if _FONT_PATH_REGULAR:
    print(f"[drawing] Regular 폰트: {_FONT_PATH_REGULAR}")
else:
    print("[drawing] ⚠️ Regular 한글 폰트를 찾지 못했습니다. 기본 폰트를 사용합니다.")


# ── 폰트 캐시 (dict 기반, lru_cache 미사용) ────────────────────────────────

_font_cache: dict = {}

def fnt(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """지정된 크기와 스타일의 폰트를 반환합니다 (캐시 적용)."""
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
            print(f"[drawing] 폰트 로드 실패 ({path}, size={size}): {e}")

    # fallback: Pillow 기본 폰트
    default = ImageFont.load_default()
    _font_cache[key] = default
    return default


# ── 프레임 생성 ────────────────────────────────────────────────────────────

def new_frame() -> Image.Image:
    """배경색으로 채운 새 캔버스를 반환합니다."""
    return Image.new("RGB", (W, H), C["bg"])


# ── 상단 바 ────────────────────────────────────────────────────────────────

def draw_topbar(draw: ImageDraw.ImageDraw, label: str, color=None):
    """상단 바를 그립니다."""
    from datetime import date
    bar_color = color or C.get("bar", (20, 22, 60))
    draw.rectangle([0, 0, W, 74], fill=bar_color)
    draw.line([0, 74, W, 74], fill=C["gold"], width=2)
    draw.text((30, 18), label, font=fnt(36, bold=True), fill=C["white"])
    date_str = date.today().strftime("%Y.%m.%d")
    draw.text((W - 30, 20), date_str, font=fnt(28, bold=False),
              fill=C["gold"], anchor="ra")


# ── 하단 바 ────────────────────────────────────────────────────────────────

def draw_bottombar(draw: ImageDraw.ImageDraw, stock_name: str = ""):
    """하단 바를 그립니다."""
    bar_color = C.get("bar", (20, 22, 60))
    draw.rectangle([0, H - 52, W, H], fill=bar_color)
    draw.line([0, H - 52, W, H - 52], fill=C["gold"], width=2)
    disclaimer = "본 영상은 AI가 생성한 참고용 정보이며, 투자 권유가 아닙니다."
    draw.text((30, H - 36), disclaimer,
              font=fnt(22, bold=False), fill=(150, 150, 170))
    if stock_name:
        draw.text((W - 30, H - 36), f"#{stock_name}",
                  font=fnt(22, bold=False), fill=C["gold"], anchor="ra")


# ── 골드 언더라인 텍스트 ────────────────────────────────────────────────────

def gold_underline(draw: ImageDraw.ImageDraw, x: int, y: int,
                   text: str, size: int = 48):
    """텍스트 아래 금색 밑줄을 그립니다."""
    draw.text((x, y), text, font=fnt(size, bold=True), fill=C["white"])
    try:
        tw = int(draw.textlength(text, font=fnt(size, bold=True)))
    except Exception:
        tw = len(text) * (size // 2)
    draw.line([x, y + size + 6, x + tw, y + size + 6],
              fill=C["gold"], width=3)


# ── 이미지 붙이기 ──────────────────────────────────────────────────────────

def paste_image(img: Image.Image, path: str, box: tuple):
    """이미지를 불러와 box 크기에 맞게 리사이즈 후 붙여넣습니다."""
    if not path or not os.path.isfile(path):
        return
    try:
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        src = Image.open(path).convert("RGBA")
        src.thumbnail((bw, bh), Image.LANCZOS)
        # 중앙 정렬
        ox = box[0] + (bw - src.width) // 2
        oy = box[1] + (bh - src.height) // 2
        if src.mode == "RGBA":
            img.paste(src, (ox, oy), src)
        else:
            img.paste(src, (ox, oy))
    except Exception as e:
        print(f"[drawing] 이미지 붙이기 실패 ({path}): {e}")


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
    """최대 너비에 맞게 텍스트를 줄바꿈하며 그립니다. 최종 y 좌표를 반환합니다."""
    if not text:
        return y
    font  = fnt(size, bold=bold)
    color = color or C["white"]
    words = list(text)          # 한글은 글자 단위로 분리
    line  = ""

    for ch in words:
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
                 color=None, margin: int = 60):
    """수평 구분선을 그립니다."""
    draw.line([margin, y, W - margin, y],
              fill=color or C.get("border", (60, 60, 90)), width=1)


# ── 배지 ──────────────────────────────────────────────────────────────────

def draw_badge(draw: ImageDraw.ImageDraw, x: int, y: int,
               text: str, bg=None, fg=None, size: int = 26) -> int:
    """둥근 직사각형 배지를 그리고, 다음 배지의 x 좌표를 반환합니다."""
    bg  = bg  or C.get("tag_bg", (40, 40, 80))
    fg  = fg  or C["gold"]
    font = fnt(size, bold=False)
    try:
        tw = int(draw.textlength(text, font=font))
    except Exception:
        tw = len(text) * (size // 2)
    pad = 16
    rx2 = x + tw + pad * 2
    ry2 = y + size + pad
    draw.rounded_rectangle([x, y, rx2, ry2], radius=10, fill=bg)
    draw.text((x + pad, y + pad // 2), text, font=font, fill=fg)
    return rx2 + 12     # 다음 배지 시작 x
