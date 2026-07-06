# pipeline/assets/builders.py
"""
KBS 머니올라 — 방송 비주얼 빌더 (HTML/CSS 슬라이드 + Playwright 렌더링)
"동영상"이 아니라 "PPT 슬라이드를 만들어서 화면으로 쓴다"는 관점으로 설계.
generate_assets.py가 기대하는 함수 시그니처/반환값/출력 파일명은 기존과 동일하게 유지한다.
"""
import os

from .config import W, H
from .render import render_html_to_png
from .html_theme import (
    esc, file_uri, shell, centered_shell, kbs_badge, stat_table,
    point_card, sector_card, bullet_column, quote_bubble, page_dots,
    numbered_bullets_from_text, PALETTE, _ACCENT_CYCLE,
)
from .chart import build_chart_image
from .image_fetch import fetch_news_image


def _find_section(sections, id_prefix):
    for s in sections:
        if s.get("id", "").startswith(id_prefix):
            return s
    return {}


# ── 오프닝 ─────────────────────────────────────────────────────────────────

def build_opening(data, out_dir):
    sec      = _find_section(data.get("sections", []), "opening")
    keywords = sec.get("keywords", [])[:4]
    date_str = data.get("date", "")

    kw_html = "".join(
        f'<span class="pill" style="background:{c}1a;color:{c};border:2px solid {c};'
        f'font-size:26px;">{esc(k)}</span>'
        for k, c in zip(keywords, _ACCENT_CYCLE)
    )
    date_html = (
        f'<div class="pill" style="background:{PALETTE["accent_soft"]};'
        f'color:{PALETTE["accent"]};font-size:26px;">{esc(date_str)}</div>'
        if date_str else ""
    )

    content = f"""
<div style="position:absolute;width:900px;height:900px;border-radius:50%;
  background:radial-gradient(circle,{PALETTE['accent_soft']} 0%,transparent 70%);
  top:-260px;left:50%;transform:translateX(-50%);"></div>
{kbs_badge()}
<div style="font-size:104px;font-weight:800;line-height:1.15;">주식시장 브리핑</div>
<div style="font-size:40px;font-weight:600;color:{PALETTE['muted']};">오늘의 핵심만 골라 드립니다</div>
{date_html}
<div style="display:flex;gap:16px;margin-top:12px;">{kw_html}</div>
"""
    html = centered_shell(content)
    return render_html_to_png(html, os.path.join(out_dir, "00_opening.png"))


# ── 시장 요약 ───────────────────────────────────────────────────────────────

def build_market_summary(data, out_dir):
    sec = _find_section(data.get("sections", []), "market_summary")
    corner_summary = sec.get("corner_summary", "")
    points = sec.get("points", [])[:6]

    rows = [
        ("코스피",    sec.get("kospi_value", ""),  sec.get("kospi_change", ""),  sec.get("kospi_change_positive", True)),
        ("코스닥",    sec.get("kosdaq_value", ""), sec.get("kosdaq_change", ""), sec.get("kosdaq_change_positive", True)),
        ("나스닥",    sec.get("nasdaq_value", ""), sec.get("nasdaq_change", ""), sec.get("nasdaq_positive", False)),
        ("S&P500",    sec.get("sp500_value", ""),  sec.get("sp500_change", ""),  sec.get("sp500_positive", False)),
        ("원달러환율", sec.get("usdkrw_value", ""), sec.get("usdkrw_change", ""), sec.get("usdkrw_positive", False)),
    ]

    corner_html = (
        f'<div class="corner-summary">{esc(corner_summary)}</div>' if corner_summary else ""
    )
    points_html = ""
    if points:
        cards = "".join(point_card(i + 1, p, _ACCENT_CYCLE[i % len(_ACCENT_CYCLE)])
                         for i, p in enumerate(points))
        points_html = f"""
<div style="font-size:30px;font-weight:800;margin:28px 0 16px;color:{PALETTE['accent']};">오늘의 핵심 포인트</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">{cards}</div>"""

    content = f"""{corner_html}
<div style="display:flex;gap:32px;align-items:flex-start;">
  <div style="flex:1;">{stat_table(rows)}</div>
</div>
{points_html}"""

    html = shell("오늘의 시장 요약", content)
    return [render_html_to_png(html, os.path.join(out_dir, "01_market_00.png"))]


# ── 업종 분석 ───────────────────────────────────────────────────────────────

def build_sector(data, out_dir):
    sec = _find_section(data.get("sections", []), "sectors")
    corner_summary = sec.get("corner_summary", "")
    sector_list = sec.get("sector_list", sec.get("sectors", sec.get("list", [])))[:6]

    corner_html = (
        f'<div class="corner-summary">{esc(corner_summary)}</div>' if corner_summary else ""
    )

    cards = ""
    for idx, sector in enumerate(sector_list):
        color = _ACCENT_CYCLE[idx % len(_ACCENT_CYCLE)]
        if isinstance(sector, dict):
            name     = sector.get("name", "")
            desc     = sector.get("desc", sector.get("description", ""))
            momentum = sector.get("momentum", "")
        else:
            name, desc, momentum = str(sector), "", ""
        cards += sector_card(idx + 1, name, desc, momentum, color)

    content = f"""{corner_html}
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">{cards}</div>"""

    html = shell("핵심 업종 분석", content)
    return render_html_to_png(html, os.path.join(out_dir, "02_sector.png"))


# ── 종목 요약 슬라이드 ──────────────────────────────────────────────────────

def _build_stock_summary(sec, out_path, img_dir):
    stock_name     = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    price          = sec.get("price", "")
    change         = sec.get("change", "")
    positive       = sec.get("change_positive", True)
    summary        = sec.get("summary", "")
    catalysts      = sec.get("catalysts", [])[:4]
    risks          = sec.get("risks", [])[:4]
    corner_summary = sec.get("corner_summary", "")
    is_hidden      = sec.get("id", "").startswith("hidden_")

    logo_path = fetch_news_image(stock_name, img_dir, [])
    logo_html = (
        f'<img src="{file_uri(logo_path)}" style="width:150px;height:150px;'
        f'border-radius:50%;object-fit:cover;border:4px solid {PALETTE["accent"]};'
        f'position:absolute;top:0;right:0;">'
        if logo_path else ""
    )

    hidden_badge = (
        f'<span class="pill" style="background:{PALETTE["highlight"]};color:#5c4a00;'
        f'font-size:20px;padding:6px 18px;margin-bottom:10px;">숨은 종목</span><br>'
        if is_hidden else ""
    )

    price_html = ""
    if price:
        color = PALETTE["up"] if positive else PALETTE["down"]
        arrow = "▲" if positive else "▼"
        change_html = (
            f'<span class="pill" style="background:{color}1a;color:{color};'
            f'font-size:28px;margin-left:16px;">{arrow} {esc(change)}</span>'
            if change else ""
        )
        price_html = (
            f'<div style="margin-top:14px;">'
            f'<span style="font-size:48px;font-weight:800;color:{PALETTE["accent"]};">'
            f'₩ {esc(price)}</span>{change_html}</div>'
        )

    summary_text = corner_summary or summary
    summary_html = (
        f'<div class="corner-summary" style="margin-top:24px;">{esc(summary_text)}</div>'
        if summary_text else ""
    )

    lower_html = ""
    if catalysts or risks:
        cols = ""
        if catalysts:
            cols += bullet_column("투자 포인트", catalysts, PALETTE["up"])
        if risks:
            cols += bullet_column("리스크", risks, PALETTE["down"])
        lower_html = f'<div style="display:flex;gap:24px;margin-top:28px;">{cols}</div>'

    content = f"""
<div style="position:relative;">
  {logo_html}
  {hidden_badge}
  <div style="font-size:72px;font-weight:800;">{esc(stock_name)}</div>
  {price_html}
</div>
{summary_html}
{lower_html}
"""
    bar_label = f"숨은 종목 분석: {stock_name}" if is_hidden else f"종목 분석: {stock_name}"
    html = shell(bar_label, content, stock_tag=stock_name)
    return render_html_to_png(html, out_path)


# ── 종목 차트 슬라이드 ──────────────────────────────────────────────────────

def _build_stock_chart(sec, out_path, img_dir):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")

    briefing_chart = os.path.join(img_dir, f"briefing_chart_{stock_name}.png")
    if os.path.exists(briefing_chart):
        chart_path = briefing_chart
        print(f"  [chart] 브리핑 앱 차트 사용: {stock_name}")
    else:
        chart_path = build_chart_image(stock_name, img_dir)

    if chart_path:
        body = (f'<div class="card" style="padding:20px;text-align:center;">'
                f'<img src="{file_uri(chart_path)}" style="width:100%;border-radius:12px;"></div>')
    else:
        body = (f'<div class="card" style="height:600px;display:flex;align-items:center;'
                f'justify-content:center;font-size:34px;color:{PALETTE["muted"]};">'
                f'{esc(stock_name)} 차트 데이터 준비 중</div>')

    html = shell(f"2주간 주가 차트: {stock_name}", body, stock_tag=stock_name)
    return render_html_to_png(html, out_path)


# ── 언급(mention) 슬라이드 ─────────────────────────────────────────────────

def _build_mention_page(sec, out_path, page_idx):
    stock_name = sec.get("id", "").replace("stock_", "").replace("hidden_", "")
    mentions   = sec.get("mentions", [])

    if mentions:
        page_mentions = mentions[page_idx * 3: page_idx * 3 + 3]
        total_pages = max(1, (len(mentions) + 2) // 3)
    else:
        field = {0: "subtitle_mention_0", 1: "subtitle_mention_1", 2: "subtitle_mention_2"}.get(
            page_idx, "subtitle_mention"
        )
        raw = sec.get(field, sec.get("subtitle_mention", ""))
        paragraphs = numbered_bullets_from_text(raw, max_items=3)
        page_mentions = [
            {"speaker": "", "channel": stock_name, "quote_subtitle": p}
            for p in paragraphs
        ]
        total_pages = 1

    cards = ""
    for mi, m in enumerate(page_mentions):
        if isinstance(m, str):
            m = {"speaker": "", "channel": "", "quote_subtitle": m}
        speaker = (m.get("speaker") or "").strip()
        channel = (m.get("channel") or m.get("source") or "").strip()
        content = m.get("quote_subtitle", m.get("quote", m.get("content", "")))
        color = _ACCENT_CYCLE[mi % len(_ACCENT_CYCLE)]
        cards += quote_bubble(channel, speaker, content, color)

    body = (f'<div style="display:flex;flex-direction:column;gap:20px;">{cards}</div>'
            + page_dots(total_pages, page_idx))

    html = shell(f"전문가·방송 언급: {stock_name}", body, stock_tag=stock_name)
    return render_html_to_png(html, out_path)


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
# summary+chart+mention 개별 카드가 아니라 단일 슬라이드 한 장으로 구성.

def _build_aggregate_stock_slide(sec, out_dir, filename, title):
    corner_summary = sec.get("corner_summary", "")
    body_text = sec.get("subtitle", sec.get("narration", ""))

    corner_html = (
        f'<div class="corner-summary">{esc(corner_summary)}</div>' if corner_summary else ""
    )

    bullets = numbered_bullets_from_text(body_text, max_items=8)
    cards = "".join(
        point_card(i + 1, b, _ACCENT_CYCLE[i % len(_ACCENT_CYCLE)])
        for i, b in enumerate(bullets)
    )
    body_html = f'<div style="display:flex;flex-direction:column;gap:14px;">{cards}</div>'

    content = f"{corner_html}{body_html}"
    html = shell(title, content)
    return render_html_to_png(html, os.path.join(out_dir, filename))


def build_extra_watchlist(data, out_dir):
    sec = _find_section(data.get("sections", []), "stock_추가관심종목")
    if not sec:
        return None
    return _build_aggregate_stock_slide(sec, out_dir, "90_extra_watchlist.png", "추가 관심 종목")


def build_today_pick(data, out_dir):
    sec = _find_section(data.get("sections", []), "stock_오늘의픽")
    if not sec:
        return None
    return _build_aggregate_stock_slide(sec, out_dir, "91_today_pick.png", "오늘의 픽")


def build_brokerage_report(data, out_dir):
    sec = _find_section(data.get("sections", []), "stock_증권사리포트")
    if not sec:
        return None
    return _build_aggregate_stock_slide(sec, out_dir, "92_brokerage_report.png", "증권사 리포트")


# ── AI 투자 전략 ────────────────────────────────────────────────────────────

def build_ai_strategy(data, out_dir):
    sec = _find_section(data.get("sections", []), "ai_strategy")
    corner_summary = sec.get("corner_summary", "")
    bullet_points  = sec.get("bullet_points", sec.get("strategies", sec.get("items", [])))[:6]

    header = f"""
<div class="card" style="display:flex;align-items:center;gap:20px;padding:22px 28px;margin-bottom:24px;
  border-left:8px solid {PALETTE['accent']};">
  <div class="pill" style="background:{PALETTE['accent']};color:#fff;font-size:26px;">AI</div>
  <div>
    <div style="font-size:32px;font-weight:800;">오늘의 투자 전략 제안</div>
    {f'<div style="font-size:22px;color:{PALETTE["muted"]};margin-top:4px;">{esc(corner_summary)}</div>' if corner_summary else ''}
  </div>
</div>"""

    cards = ""
    for i, bp in enumerate(bullet_points):
        text = bp if isinstance(bp, str) else bp.get("strategy", bp.get("content", str(bp)))
        color = _ACCENT_CYCLE[i % len(_ACCENT_CYCLE)]
        if " — " in text:
            stock_part, strat_part = text.split(" — ", 1)
            body = (f'<div style="font-size:28px;font-weight:800;color:{color};">{esc(stock_part.strip())}</div>'
                    f'<div style="font-size:24px;margin-top:6px;line-height:1.5;">{esc(strat_part.strip())}</div>')
        else:
            body = f'<div style="font-size:26px;line-height:1.5;">{esc(text)}</div>'
        cards += (
            f'<div class="card" style="display:flex;gap:18px;padding:20px 24px;">'
            f'<div class="badge-num" style="background:{color}22;color:{color};'
            f'border:2px solid {color};">{i + 1}</div>'
            f'<div style="flex:1;">{body}</div></div>'
        )

    content = header + f'<div style="display:flex;flex-direction:column;gap:14px;">{cards}</div>'
    html = shell("AI 투자 전략", content)
    return render_html_to_png(html, os.path.join(out_dir, "98_ai_strategy.png"))


# ── 클로징 ─────────────────────────────────────────────────────────────────

def build_closing(data, out_dir):
    content = f"""
{kbs_badge()}
<div style="font-size:96px;font-weight:800;">감사합니다</div>
<div style="font-size:38px;font-weight:600;color:{PALETTE['accent']};">성공적인 투자 되시길 바랍니다</div>
<div class="card" style="border:2px solid {PALETTE['up']}55;background:#fff6f6;
  padding:28px 36px;max-width:1400px;margin-top:12px;">
  <div style="font-size:28px;font-weight:800;color:{PALETTE['up']};margin-bottom:14px;">투자 유의사항</div>
  <div style="font-size:22px;line-height:1.7;color:#5c3a3a;text-align:left;">
    본 브리핑은 AI가 공개 데이터를 분석한 참고용 정보입니다.<br>
    특정 종목의 매수·매도 권유가 아니며, 수익을 보장하지 않습니다.<br>
    주식 투자는 원금 손실 위험이 있으며, 최종 투자 결정과<br>
    모든 책임은 전적으로 투자자 본인에게 있습니다.
  </div>
</div>
"""
    html = centered_shell(content)
    return render_html_to_png(html, os.path.join(out_dir, "99_closing.png"))
