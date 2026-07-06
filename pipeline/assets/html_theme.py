# pipeline/assets/html_theme.py
"""
'PPT 슬라이드'를 만든다는 관점의 HTML/CSS 디자인 시스템.
NotebookLM 스타일 참고: 밝은 배경 + 점그리드, 민트/틸 액센트 + 노란 하이라이트,
큰 볼드 타이포, 말풍선형 인용 카드, 심플한 표. 한국 증권가 관행(상승=빨강/하락=파랑)은 유지.
"""
import os
import re
import html as _he
from datetime import date

W, H = 1920, 1080

PALETTE = {
    "bg":           "#faf9f6",
    "dot":          "#e6e4dc",
    "ink":          "#16181d",
    "muted":        "#6b7280",
    "accent":       "#0e9f8e",
    "accent_soft":  "#e3f7f3",
    "highlight":    "#ffe066",
    "up":           "#e0393e",
    "down":         "#2f6fed",
    "card":         "#ffffff",
    "border":       "#e8e6df",
    "shadow":       "rgba(20,20,20,.08)",
}

_ACCENT_CYCLE = [PALETTE["accent"], "#f2a341", PALETTE["down"], "#a05bd6", PALETTE["up"]]


def esc(s) -> str:
    return _he.escape(str(s or ""))


def strip_emoji(s: str) -> str:
    return re.sub(
        r'[\U00010000-\U0010ffff\U0001F300-\U0001F9FF☀-⛿✀-➿]',
        '', s or ''
    ).strip()


def file_uri(path: str) -> str:
    return "file://" + os.path.abspath(path)


BASE_CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;}}
body{{
  font-family:'Noto Sans KR','NanumGothic','Malgun Gothic',sans-serif;
  color:{PALETTE['ink']};
  background:
    radial-gradient(circle, {PALETTE['dot']} 1.6px, transparent 1.6px) 0 0/30px 30px,
    {PALETTE['bg']};
  position:relative;
}}
.stage{{position:absolute; left:0; top:0; width:{W}px; height:{H}px;}}
.topbar{{
  position:absolute; left:0; top:0; width:{W}px; height:96px;
  display:flex; align-items:center; padding:0 56px;
  background:{PALETTE['card']}; border-bottom:1px solid {PALETTE['border']};
}}
.topbar .brand{{
  font-weight:800; font-size:26px; color:{PALETTE['accent']};
  letter-spacing:.01em; margin-right:28px;
}}
.topbar .brand-sub{{font-weight:600; font-size:18px; color:{PALETTE['muted']}; margin-right:28px;}}
.topbar .divider{{width:2px; height:40px; background:{PALETTE['border']}; margin-right:28px;}}
.topbar .label{{font-weight:800; font-size:36px; color:{PALETTE['ink']}; flex:1;}}
.topbar .date{{font-weight:600; font-size:24px; color:{PALETTE['muted']};}}
.bottombar{{
  position:absolute; left:0; bottom:0; width:{W}px; height:60px;
  display:flex; align-items:center; justify-content:space-between;
  padding:0 40px; background:{PALETTE['card']}; border-top:1px solid {PALETTE['border']};
}}
.bottombar .disclaimer{{font-size:17px; color:{PALETTE['muted']};}}
.bottombar .tag{{font-size:19px; font-weight:700; color:{PALETTE['accent']};}}
.content{{position:absolute; left:56px; right:56px; top:120px; bottom:84px;}}
.card{{
  background:{PALETTE['card']}; border:1px solid {PALETTE['border']};
  border-radius:20px; box-shadow:0 10px 28px {PALETTE['shadow']};
}}
.pill{{
  display:inline-flex; align-items:center; gap:8px;
  border-radius:999px; padding:8px 20px; font-weight:700; font-size:22px;
}}
.corner-summary{{
  display:flex; align-items:center; gap:14px;
  background:{PALETTE['accent_soft']}; border-left:6px solid {PALETTE['accent']};
  border-radius:12px; padding:18px 24px; font-size:26px; font-weight:600;
  color:{PALETTE['ink']}; margin-bottom:28px;
}}
.badge-num{{
  display:flex; align-items:center; justify-content:center;
  width:52px; height:52px; border-radius:50%; font-weight:800; font-size:24px;
  flex-shrink:0;
}}
"""


def shell(topbar_label: str, content_html: str, stock_tag: str = "",
          date_str: str = "") -> str:
    date_str = date_str or date.today().strftime("%Y.%m.%d")
    tag_html = f'<div class="tag">#{esc(stock_tag)}</div>' if stock_tag else '<div></div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}</style></head>
<body><div class="stage">
  <div class="topbar">
    <div class="brand">KBS</div>
    <div class="brand-sub">머니올라</div>
    <div class="divider"></div>
    <div class="label">{esc(strip_emoji(topbar_label))}</div>
    <div class="date">{esc(date_str)}</div>
  </div>
  <div class="content">{content_html}</div>
  <div class="bottombar">
    <div class="disclaimer">본 브리핑은 AI 분석 참고자료이며 투자 권유가 아닙니다. 주식 투자에는 원금 손실 위험이 있으며, 최종 투자 결정과 책임은 본인에게 있습니다.</div>
    {tag_html}
  </div>
</div></body></html>"""


def centered_shell(content_html: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}
.center-wrap{{
  position:absolute; left:0; top:0; width:{W}px; height:{H-60}px;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  text-align:center; gap:22px;
}}
</style></head>
<body><div class="stage">
  <div class="center-wrap">{content_html}</div>
  <div class="bottombar">
    <div class="disclaimer">본 브리핑은 AI 분석 참고자료이며 투자 권유가 아닙니다. 주식 투자에는 원금 손실 위험이 있으며, 최종 투자 결정과 책임은 본인에게 있습니다.</div>
    <div></div>
  </div>
</div></body></html>"""


def kbs_badge() -> str:
    return (f'<div class="pill" style="background:{PALETTE["accent"]};color:#fff;'
            f'font-size:26px;padding:12px 30px;">KBS 머니올라</div>')


def stat_table(rows: list) -> str:
    """rows: [(label, value, change_str, positive_bool), ...]"""
    header = (
        f'<tr style="background:{PALETTE["accent_soft"]};">'
        f'<th style="text-align:left;padding:18px 28px;border-radius:20px 0 0 0;">지수</th>'
        f'<th style="text-align:right;padding:18px 28px;">현재가</th>'
        f'<th style="text-align:right;padding:18px 28px;border-radius:0 20px 0 0;">등락률</th>'
        f'</tr>'
    )
    body = "".join(
        f'<tr style="border-top:1px solid {PALETTE["border"]};">'
        f'<td style="padding:16px 28px;font-weight:700;color:{PALETTE["muted"]};">{esc(l)}</td>'
        f'<td style="padding:16px 28px;text-align:right;font-weight:800;font-size:30px;">{esc(v)}</td>'
        f'<td style="padding:16px 28px;text-align:right;font-weight:700;font-size:24px;'
        f'color:{PALETTE["up"] if p else PALETTE["down"]};">{"▲" if p else "▼"} {esc(c)}</td>'
        f'</tr>'
        for l, v, c, p in rows if v
    )
    return (
        f'<table class="card" style="width:100%;border-collapse:collapse;'
        f'font-size:26px;">{header}{body}</table>'
    )


def point_card(num: int, text: str, color: str) -> str:
    return (
        f'<div class="card" style="display:flex;align-items:flex-start;gap:16px;'
        f'padding:22px 24px;">'
        f'<div class="badge-num" style="background:{color}22;color:{color};'
        f'border:2px solid {color};">{num}</div>'
        f'<div style="font-size:25px;line-height:1.5;font-weight:600;padding-top:4px;">'
        f'{esc(text)}</div>'
        f'</div>'
    )


def sector_card(idx: int, name: str, desc: str, momentum: str, color: str) -> str:
    mom_colors = {"상승": PALETTE["up"], "하락": PALETTE["down"], "보합": "#f2a341"}
    mcolor = mom_colors.get(momentum, PALETTE["muted"])
    mom_html = (
        f'<span class="pill" style="background:{mcolor}1a;color:{mcolor};'
        f'font-size:20px;padding:6px 16px;margin-left:auto;">{esc(momentum)}</span>'
        if momentum else ""
    )
    return f"""
<div class="card" style="padding:24px 26px;">
  <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;">
    <div class="badge-num" style="background:{color}22;color:{color};border:2px solid {color};">{idx}</div>
    <div style="font-size:32px;font-weight:800;">{esc(name)}</div>
    {mom_html}
  </div>
  <div style="font-size:23px;color:{PALETTE['muted']};line-height:1.55;">{esc(desc)}</div>
</div>"""


def bullet_column(title: str, items: list, color: str) -> str:
    lis = "".join(
        f'<li style="margin-bottom:14px;line-height:1.5;">{esc(it)}</li>'
        for it in items
    )
    return f"""
<div class="card" style="padding:26px 30px;flex:1;">
  <div class="pill" style="background:{color};color:#fff;font-size:24px;margin-bottom:18px;">{esc(title)}</div>
  <ul style="list-style:none;font-size:25px;color:{PALETTE['ink']};">{lis}</ul>
</div>"""


def quote_bubble(channel: str, speaker: str, text: str, color: str) -> str:
    header_parts = [p for p in (channel, speaker) if p]
    header = "  ·  ".join(header_parts)
    header_html = (
        f'<div class="pill" style="background:{color}1a;color:{color};'
        f'font-size:22px;padding:6px 18px;margin-bottom:14px;">{esc(header)}</div>'
        if header else ""
    )
    return f"""
<div class="card" style="border-left:8px solid {color};padding:26px 30px;position:relative;">
  <div style="position:absolute;top:14px;right:26px;font-size:52px;color:{color}33;font-weight:800;">&rdquo;</div>
  {header_html}
  <div style="font-size:27px;line-height:1.55;font-weight:600;">{esc(text)}</div>
</div>"""


def page_dots(total: int, current: int) -> str:
    if total <= 1:
        return ""
    dots = "".join(
        f'<div style="width:12px;height:12px;border-radius:50%;'
        f'background:{PALETTE["accent"] if i == current else PALETTE["border"]};"></div>'
        for i in range(total)
    )
    return (f'<div style="display:flex;gap:10px;justify-content:center;'
            f'margin-top:18px;">{dots}</div>')


def numbered_bullets_from_text(text: str, max_items: int = 6) -> list:
    """긴 문단 텍스트를 문장 단위로 쪼개 불릿 리스트처럼 보여주기 위한 헬퍼."""
    if not text:
        return []
    sentences = re.split(r'(?<=[.다요]\.)\s+|(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        return [text.strip()]
    if len(sentences) <= max_items:
        return sentences
    chunk = max(1, -(-len(sentences) // max_items))
    return [" ".join(sentences[i:i + chunk]) for i in range(0, len(sentences), chunk)][:max_items]
