# pipeline/assets/drawing.py
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
from .config import W, H, C, FONT_PATHS


# ── 폰트 로더 ──────────────────────────────────────────────────────────────────
def _find_system_font(bold: bool) -> str | None:
    """fc-list로 시스템에 설치된 CJK 폰트 경로를 동적으로 탐색"""
    try:
        keywords = ["NotoSansCJK", "NotoSans CJK", "AppleSDGothic",
                    "Malgun", "UnDotum", "NanumGothic"]
        result = subprocess.run(
            ["fc-list", ":lang=ko"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.splitlines()
        for kw in keywords:
            for line in lines:
                if kw.lower() in line.lower():
                    path = line.split(":")[0].strip()
                    if os.path.exists(path):
                        return path
    except Exception:
        pass
    return None


_font_cache: dict = {}

def fnt(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    cache_key = (size, bold)
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    key = "bold" if bold else "regular"

    # 1순위: config에 정의된 경로
    for path in FONT_PATHS[key]:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size)
                _font_cache[cache_key] = f
                return f
            except Exception:
                continue

    # 2순위: fc-list로 시스템 폰트 탐색
    sys_path = _find_system_font(bold)
    if sys_path:
        try:
            f = ImageFont.truetype(sys_path, size)
            _font_cache[cache_key] = f
            return f
        except Exception:
            pass

    # 3순위: 알려진 경로 추가 탐색
    fallback_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Bold.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in fallback_paths:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size)
                _font_cache[cache_key] = f
                print(f"  [font] fallback 사용: {path} (size={size})")
                return f
            except Exception:
                continue

    # 최후 수단: load_default는 한글 불가 → 크기 경고
    print(f"  ⚠️ [font] 폰트 없음! 기본폰트 사용 (size={size}) — 한글 깨짐 발생")
    f = ImageFont.load_default()
    _font_cache[cache_key] = f
    return f


# ── 새 프레임 생성 ─────────────────────────────────────────────────────────────
def new_frame() -> Image.Image:
    return Image.new("RGB", (W, H), C["bg"])


# ── 상단 바 ────────────────────────────────────────────────────────────────────
def draw_topbar(d: ImageDraw.Draw, label: str, color: tuple = None):
    color = color or C["tag_bg"]
    d.rectangle([0, 0, W, 70], fill=color)
    d.text((30, 14), label, font=fnt(36), fill=C["gold"])
    from datetime import datetime
    date_str = datetime.now().strftime("%Y.%m.%d")
    tw = fnt(28, bold=False).getbbox(date_str)[2]
    d.text((W - tw - 30, 20), date_str,
           font=fnt(28, bold=False), fill=C["white"])


# ── 하단 바 ────────────────────────────────────────────────────────────────────
def draw_bottombar(d: ImageDraw.Draw, stock_name: str,
                   date_str: str, color: tuple = None):
    color = color or C["tag_bg"]
    d.rectangle([0, H - 60, W, H], fill=color)
    label = (f"⚠ 본 브리핑은 AI 자동 생성 참고자료이며 투자 권유가 아닙니다"
             f"  |  {stock_name}  {date_str}").strip(" |")
    d.text((30, H - 46), label,
           font=fnt(24, bold=False), fill=C["white"])


# ── 골드 언더라인 제목 ─────────────────────────────────────────────────────────
def gold_underline(d: ImageDraw.Draw, x: int, y: int,
                   text: str, font_size: int = 52):
    f = fnt(font_size)
    d.text((x, y), text, font=f, fill=C["white"])
    tw = f.getbbox(text)[2]
    d.rectangle([x, y + font_size + 6,
                 x + tw, y + font_size + 10], fill=C["gold"])


# ── 이미지 붙이기 (비율 유지 + 크롭) ──────────────────────────────────────────
def paste_image(base: Image.Image, path: str, box: tuple):
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
def draw_wrapped_text(d: ImageDraw.Draw, text: str,
                      x: int, y: int, max_width: int,
                      font_size: int = 36,
                      color: tuple = None,
                      line_gap: int = 10) -> int:
    color = color or C["white"]
    f = fnt(font_size, bold=False)
    words = text.replace("\n", " ").split(" ")
    line, cy = "", y
    for word in words:
        test = (line + " " + word).strip()
        try:
            w = f.getbbox(test)[2]
        except Exception:
            w = len(test) * font_size * 0.6
        if w > max_width and line:
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
    bg = bg or C["tag_bg"]
    fg = fg or C["gold"]
    f = fnt(26)
    try:
        tw = f.getbbox(text)[2]
    except Exception:
        tw = len(text) * 16
    pad = 16
    d.rounded_rectangle([(x, y), (x + tw + pad * 2, y + 44)],
                         radius=8, fill=bg)
    d.text((x + pad, y + 6), text, font=f, fill=fg)
    return x + tw + pad * 2 + 12
