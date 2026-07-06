# pipeline/generate_script.py
"""
AI 주식 브리핑 — 스크립트 생성 모듈 (v3)
- 데이터 소스: https://kunil-choi.github.io/stock-briefing-v3/
- 목표 영상 길이: 정확히 15분 내외
- 오프닝: 'KBS 머니올라' 멘트
- 발음 교정 / 나레이션·자막 완전 분리
- 목소리 관리: pipeline/voice_config.py 에서 통합 관리
"""

import os
import re
import sys
import json
from datetime import datetime
from openai import OpenAI
from playwright.sync_api import sync_playwright

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from assets.config import (
    STOCK_CODES, normalize_stock_name, classify_channel_type, resolve_channel_identity,
)

_api_key = os.environ.get("OPENAI_API_KEY")
if not _api_key:
    raise EnvironmentError("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
client = OpenAI(api_key=_api_key)

TODAY       = datetime.now().strftime("%Y년 %m월 %d일")
TODAY_MONTH = datetime.now().strftime("%-m")
TODAY_DAY   = datetime.now().strftime("%-d")

STOCK_NAME_LIST = "\n".join(f"- {name}" for name in STOCK_CODES.keys())

# ─────────────────────────────────────────────────────────────────────────────
# 오프닝 / 클로징 멘트
# ─────────────────────────────────────────────────────────────────────────────

OPENING_NARRATION = (
    "케이비에스 머니올라가 제공하는 오늘의 주식시장 브리핑입니다. "
    "지난 24시간 동안 조회수가 높았던 유튜브와 증권방송, 증권사 보고서를 정리했습니다. "
    "투자자들의 관심이 어디에 있는지 함께 확인해보시죠."
)

OPENING_SUBTITLE = (
    "KBS 머니올라가 제공하는 오늘의 주식시장 브리핑입니다. "
    "지난 24시간 동안 조회수가 높았던 유튜브와 증권방송, 증권사 보고서를 정리했습니다. "
    "투자자들의 관심이 어디에 있는지 함께 확인해보시죠."
)

# ─────────────────────────────────────────────────────────────────────────────
# 투자 경고 클로징 (요구사항 8번: 경고문 강화)
# ─────────────────────────────────────────────────────────────────────────────

CLOSING_NARRATION = (
    "이상으로 케이비에스 머니올라의 오늘의 주식시장 브리핑을 마치겠습니다. "
    "오늘도 함께해 주셔서 감사합니다. "
    "마지막으로 꼭 당부드릴 말씀이 있습니다. "
    "본 브리핑은 에이아이가 뉴스, 유튜브, 증권사 리포트 등 공개 데이터를 분석하여 제작한 참고용 정보입니다. "
    "특정 종목의 매수 또는 매도를 권유하는 것이 아니며, 수익을 보장하지 않습니다. "
    "주식 투자는 원금 손실의 위험이 있으므로 반드시 본인의 판단과 책임 하에 신중하게 결정하시기 바랍니다. "
    "투자의 최종 결정과 그에 따른 모든 책임은 전적으로 투자자 본인에게 있습니다. "
    "구독과 좋아요는 저희에게 큰 힘이 됩니다. 내일도 유익한 브리핑으로 찾아뵙겠습니다. 감사합니다."
)

CLOSING_SUBTITLE = (
    "이상으로 KBS 머니올라의 오늘의 주식시장 브리핑을 마치겠습니다. "
    "오늘도 함께해 주셔서 감사합니다. "
    "마지막으로 꼭 당부드릴 말씀이 있습니다. "
    "본 브리핑은 AI가 뉴스, 유튜브, 증권사 리포트 등 공개 데이터를 분석하여 제작한 참고용 정보입니다. "
    "특정 종목의 매수 또는 매도를 권유하는 것이 아니며, 수익을 보장하지 않습니다. "
    "주식 투자는 원금 손실의 위험이 있으므로 반드시 본인의 판단과 책임 하에 신중하게 결정하시기 바랍니다. "
    "투자의 최종 결정과 그에 따른 모든 책임은 전적으로 투자자 본인에게 있습니다. "
    "구독과 좋아요는 저희에게 큰 힘이 됩니다. 내일도 유익한 브리핑으로 찾아뵙겠습니다. 감사합니다."
)

DISCLAIMER = (
    "⚠️ 투자 유의사항 | 본 브리핑은 AI 분석 참고자료이며 투자 권유가 아닙니다. "
    "주식 투자는 원금 손실 위험이 있습니다. 투자 책임은 전적으로 본인에게 있습니다."
)


# ─────────────────────────────────────────────────────────────────────────────
# 자막 표기 안전망 — narration용 한글 발음/숫자 표기가 subtitle 필드에 잘못
# 섞여 들어온 경우 자동으로 원래 표기(숫자/로마자)로 되돌립니다.
# LLM이 프롬프트 지시를 놓쳤을 때의 최종 방어선이며, narration 필드에는
# 절대 적용하지 않습니다.
# ─────────────────────────────────────────────────────────────────────────────

# narration에서만 쓰이는 필드 — 자막 안전망을 적용하지 않음
_NARRATION_ONLY_KEYS = {
    "narration", "narration_summary", "narration_chart",
    "narration_mention", "quote_narration", "id", "title", "date",
}
_NARRATION_MENTION_PAGE_RE = re.compile(r"^narration_mention_\d+$")

# 영문 약어의 한글 발음 표기 → 원래 로마자 표기 (긴 복합어 먼저)
_ACRONYM_SUBTITLE_FIXES = [
    ("에이치디현대중공업", "HD현대중공업"),
    ("에이치디현대일렉트릭", "HD현대일렉트릭"),
    ("에이치디현대", "HD현대"),
    ("에스케이하이닉스", "SK하이닉스"),
    ("엘지에너지솔루션", "LG에너지솔루션"),
    ("엘지화학", "LG화학"),
    ("케이비금융", "KB금융"),
    ("에이치비엠", "HBM"),
    ("에이아이", "AI"),
    ("이티에프", "ETF"),
    ("이에스에스", "ESS"),
    ("피씨이", "PCE"),
    ("디에스알", "DSR"),
    ("오티티", "OTT"),
    ("에이디알", "ADR"),
    ("엠오유", "MOU"),
    ("비피에스", "BPS"),
    ("이피에스", "EPS"),
    ("피이알", "PER"),
    ("알오이", "ROE"),
    ("아이피오", "IPO"),
    ("엠앤에이", "M&A"),
    ("알앤디", "R&D"),
    ("와이오와이", "YoY"),
    ("큐오큐", "QoQ"),
    ("에스케이", "SK"),
    ("엘지", "LG"),
    ("케이비", "KB"),
]

_KR_DIGIT = {"영": 0, "일": 1, "이": 2, "삼": 3, "사": 4,
             "오": 5, "육": 6, "륙": 6, "칠": 7, "팔": 8, "구": 9}
_KR_SMALL_UNIT = {"십": 10, "백": 100, "천": 1000}
_KR_BIG_UNITS = "조억만"
_KR_NUM_CHARS = "".join(_KR_DIGIT) + "".join(_KR_SMALL_UNIT) + _KR_BIG_UNITS


def _parse_kr_number_group(chars: str):
    """4자리 미만 그룹(예: '이천사백')을 정수로 변환. 실패하면 None."""
    if not chars:
        return 0
    total = 0
    pending = None
    for ch in chars:
        if ch in _KR_DIGIT:
            pending = _KR_DIGIT[ch]
        elif ch in _KR_SMALL_UNIT:
            total += (pending if pending is not None else 1) * _KR_SMALL_UNIT[ch]
            pending = None
        else:
            return None
    if pending is not None:
        total += pending
    return total


def _korean_number_run_to_digits(run: str):
    """'십이조이천사백억' → '12조2400억' 처럼 조/억/만 단위는 유지한 채 각 자릿수
    구간만 아라비아 숫자로 변환합니다. 파싱 실패 시 None을 반환합니다."""
    parts = re.split(r"([조억만])", run)
    out, i = [], 0
    while i < len(parts):
        seg = parts[i]
        if i + 1 < len(parts) and parts[i + 1] in "조억만":
            val = _parse_kr_number_group(seg)
            if val is None:
                return None
            out.append(f"{val}{parts[i + 1]}")
            i += 2
        else:
            if seg:
                val = _parse_kr_number_group(seg)
                if val is None:
                    return None
                out.append(str(val))
            i += 1
    return "".join(out) if out else None


_DECIMAL_PERCENT_RE = re.compile(
    r"([영일이삼사오육륙칠팔구]+)쩜([영일이삼사오육륙칠팔구]+)퍼센트"
)


def _fix_decimal_percent(text: str) -> str:
    """'십이쩜오퍼센트' → '12.5%' / '영쩜팔퍼센트' → '0.8%'"""
    def repl(m):
        int_val = _parse_kr_number_group(m.group(1))
        dec_str = "".join(str(_KR_DIGIT[c]) for c in m.group(2))
        if int_val is None or not dec_str:
            return m.group(0)
        return f"{int_val}.{dec_str}%"
    return _DECIMAL_PERCENT_RE.sub(repl, text)


_PLAIN_NUMBER_RE = re.compile(
    f"([{_KR_NUM_CHARS}]+)(원|퍼센트|포인트|배)?"
)


# 숫자처럼 보이지만 실제로는 일반 어휘인 경우 (오탐 확인된 단어만 등록).
# 예: "구조"(9+조) → 구조적/구조원 등 실제 단어와 충돌하므로 절대 숫자로 변환하지 않음.
_NUMBER_RUN_DENYLIST = {"구조"}


def _fix_plain_numbers(text: str) -> str:
    """'삼천오백원' → '3500원' 처럼 뒤에 원/퍼센트/포인트/배 단위가 붙는 경우,
    또는 '십이조이천사백억'처럼 조/억/만 단위가 두 번 이상 나와 명백히 복합
    숫자 표기로 판단되는 경우만 변환합니다.

    한글에는 숫자 음절(일이삼사...구/십백천만억조)이 우연히 들어간 일반 단어가
    매우 많습니다 (구조, 오만, 천만에요, 구천 등). 그래서 "조/억/만으로 끝나기만
    하면 숫자"로 간주하던 이전 방식은 "구조적" → "9조적" 같은 오탐을 냈습니다.
    이제는 반드시 (1) 뒤에 명시적 단위 앵커가 붙거나 (2) 조/억/만이 한 런에서
    2회 이상 나타나 복합 숫자임이 명백한 경우에만 변환합니다.
    """
    def repl(m):
        run, trailing = m.group(1), m.group(2) or ""
        if len(run) < 2 or not any(c in "십백천만억조" for c in run):
            return m.group(0)
        if run in _NUMBER_RUN_DENYLIST:
            return m.group(0)
        big_unit_count = sum(run.count(u) for u in _KR_BIG_UNITS)
        if not trailing and big_unit_count < 2:
            return m.group(0)
        converted = _korean_number_run_to_digits(run)
        if converted is None:
            return m.group(0)
        trailing_out = "%" if trailing == "퍼센트" else trailing
        return converted + trailing_out
    return _PLAIN_NUMBER_RE.sub(repl, text)


def fix_subtitle_text(text: str) -> str:
    """자막(subtitle) 필드에 섞여 들어온 narration용 한글 발음/숫자 표기를
    원래의 숫자·로마자 표기로 되돌립니다. narration 필드에는 절대 호출하지 마세요."""
    if not text or not isinstance(text, str):
        return text
    try:
        fixed = text
        for src, dst in _ACRONYM_SUBTITLE_FIXES:
            fixed = fixed.replace(src, dst)
        fixed = _fix_decimal_percent(fixed)
        fixed = _fix_plain_numbers(fixed)
        return fixed
    except Exception:
        return text


def fix_subtitle_fields(obj, key: str = None):
    """script.json 트리를 순회하며 narration 계열이 아닌 모든 문자열 필드에
    fix_subtitle_text()를 적용합니다."""
    if isinstance(obj, dict):
        return {k: fix_subtitle_fields(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fix_subtitle_fields(v, key) for v in obj]
    if isinstance(obj, str):
        if key in _NARRATION_ONLY_KEYS or (key and _NARRATION_MENTION_PAGE_RE.match(key)):
            return obj
        return fix_subtitle_text(obj)
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# 브리핑 데이터 수집 (v3 URL)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_briefing():
    """https://kunil-choi.github.io/stock-briefing-v3/ 에서 브리핑 텍스트를 수집합니다."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(
                "https://kunil-choi.github.io/stock-briefing-v3/",
                wait_until="networkidle",
                timeout=30000
            )
            text = page.inner_text("body")

            img_dir = os.path.join(_HERE, "..", "output", "KO", "images")
            os.makedirs(img_dir, exist_ok=True)

            # 브리핑 앱 차트 캡처 (v3 구조)
            stock_sections = page.query_selector_all("section.stock-item, div.stock-card, article")
            if not stock_sections:
                chart_links = page.query_selector_all("a:has-text('차트보기')")
                for link in chart_links:
                    try:
                        parent = link.evaluate_handle(
                            "el => el.closest('section') || el.closest('div.stock') || el.parentElement.parentElement"
                        )
                        heading = parent.query_selector("h3, h4, strong")
                        if not heading:
                            continue
                        stock_name = heading.inner_text().strip().split("\n")[0]
                        normalized = normalize_stock_name(stock_name)
                        save_path = os.path.join(img_dir, f"briefing_chart_{normalized}.png")
                        if not os.path.exists(save_path):
                            chart_area = parent.query_selector("canvas, img.chart, div.chart-container")
                            if chart_area:
                                chart_area.screenshot(path=save_path)
                                print(f"  [briefing_chart] 캡처 완료: {normalized}")
                    except Exception as ce:
                        print(f"  [briefing_chart] 캡처 실패: {ce}")

            browser.close()
            return text
    except Exception as e:
        print(f"⚠️ 브리핑 데이터 로드 실패: {e}")
        return ""


def _kdate_to_iso(date_str: str) -> str:
    """'2026년 07월 06일' → '2026-07-06'. 매칭 실패 시 빈 문자열."""
    m = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", date_str or "")
    if not m:
        return ""
    y, mo, d = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def fetch_youtube_mentions() -> list:
    """data/youtube_mentions.json — 종목별 실제 발언(화자/채널/원문 인용) 원본 데이터."""
    try:
        import urllib.request
        url = "https://kunil-choi.github.io/stock-briefing-v3/data/youtube_mentions.json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"⚠️ youtube_mentions.json 로드 실패: {e}")
        return []


def build_stock_quotes(mentions: list, briefing_date_iso: str) -> dict:
    """
    종목명을 정규화해 stock_name → [{speaker, channel, channel_type, quote, timestamp_url, sentiment}] 로 그룹핑.
    briefing_date_iso가 있으면 같은 날짜의 발언만 사용 (V3 브리핑과 날짜 어긋남 방지).
    mention 슬라이드는 최대 3슬라이드(슬라이드당 3개)까지 지원하므로 종목당 최대 9개 발언까지 유지해
    출연진의 발언을 최대한 폭넓게 다룬다 (요구사항: 방송/유튜브 전문가 발언 종합이 이 영상의 핵심 목적).
    """
    grouped: dict = {}
    for m in mentions:
        if briefing_date_iso and m.get("date") and m.get("date") != briefing_date_iso:
            continue
        raw_name = (m.get("stock_name") or "").strip()
        if not raw_name:
            continue
        name = normalize_stock_name(raw_name)
        raw_channel = m.get("channel", "")
        raw_speaker = m.get("speaker") or m.get("main_speaker", "")
        channel, speaker = resolve_channel_identity(raw_channel, raw_speaker)
        grouped.setdefault(name, []).append({
            "speaker":       speaker,
            "channel":       channel,
            "channel_type":  classify_channel_type(channel),
            "quote":         m.get("quote", ""),
            "timestamp_url": m.get("timestamp_url") or m.get("video_url", ""),
            "sentiment":     m.get("sentiment", ""),
        })
    return {name: items[:9] for name, items in grouped.items()}


# ─────────────────────────────────────────────────────────────────────────────
# 스크립트 생성
# ─────────────────────────────────────────────────────────────────────────────

def generate_script(
    briefing_text: str,
    market_data: dict = None,
    brokerage_reports: dict = None,
    stock_quotes: dict = None,
) -> dict:
    system_prompt = f"""
너는 KBS 머니올라 주식 방송 스크립트 작성 전문가입니다.
증권 브리핑 데이터를 바탕으로 **15분짜리** 방송 스크립트를 JSON 형식으로 작성하세요.
작성일: {TODAY}

## ★ 15분 영상 분량 설계 (반드시 준수)
한국어 TTS 낭독 속도 기준(1.3배속 적용 시): 1분 = 약 310~320자
전체 목표: 오프닝+클로징 고정 텍스트 포함 총 5,800자 이상 — 반드시 이 이상을 채워서
실제 방송 분량이 15분에 최대한 가깝게 나오도록 하세요. 분량이 부족하면 영상 후반부가
음악만 나오는 빈 시간으로 채워지므로, 목표치 미달은 반드시 피해야 합니다.

### 섹션별 narration 목표 글자 수 (공백 포함):
- market_summary : 480~600자 (목표 1분 30초~2분, 이 범위 안에서는 자유롭게 서술)
  → KOSPI·KOSDAQ·해외지수·환율 수치와 등락 방향, 핵심 원인과 배경을 구체적으로 설명.
    600자를 크게 넘기지 않도록 하되, 이전처럼 900자 이상으로 장황해지는 것만 피하세요.

- sectors : 900자 이상 (약 3분)
  → hot_sectors 각 섹터를 3~5문장으로 충분히 설명.
  → market_summary에서 이미 언급한 지수 수치·환율·전반적 시황 코멘트는 반복하지 말 것.
    업종별 개별 동인(수급, 실적, 정책, 해외 이슈 등)과 관련 종목·테마 흐름 등
    market_summary에서 다루지 않은 새로운 내용 위주로 서술.

- 각 stock 섹션 narration : 900자 이상 (요구사항: 종목별 설명을 더 자세히)
  → summary, catalyst, risk, mention 모두 포함. 종목별로 구체적 수치와 전망까지 충분히 서술.
  → narration_mention(전문가 발언 소개) 분량이 narration_summary보다 짧아지지 않도록 하세요.
    이 코너의 핵심은 "누가 무엇을 말했는지"이므로 mention 분량을 가장 충실하게 작성합니다.
    발언 각각을 2~3문장으로 풀어 쓰고, 발언 원문의 뉘앙스와 근거·수치까지 살리세요.

- stock_추가관심종목 : 종목 수에 비례 (종목당 최소 100자, 전체 400자 이상)
  → "다음은 오늘의 추가 관심 종목입니다."로 시작.
    stocks 배열에서 개별 섹션으로 다루지 않은 나머지 종목을 전부 소개.
    각 종목: 등락 방향 + 핵심 이유 + 전망까지 2문장 이상으로 서술 (한 문장으로 끝내지 말 것).
  → items 배열 필수(아래 "집계형 섹션 items 규칙" 참고). 전체 시간이 부족하면 items 중 관심도가
    낮은 하위 종목들만 따로 "추가 관심 종목"으로 분리해 다뤄도 좋습니다.

- stock_오늘의픽 : hidden_picks 데이터가 있을 때만 생성 (전체 300자 이상)
  → "오늘의 숨은 픽을 소개합니다."로 시작.
    hidden_picks 종목 각각을 2~3문장으로 소개.
    hidden_picks가 비어 있으면 이 섹션 자체를 JSON에 포함하지 말 것.
  → items 배열 필수(아래 "집계형 섹션 items 규칙" 참고).

- stock_증권사리포트 : brokerage_reports 데이터가 있을 때만 생성 (전체 300자 이상)
  → "증권사 리포트에서 주목한 종목을 살펴보겠습니다."로 시작.
    동시언급 종목은 "여러 증권사에서 동시에 주목한 [종목명]입니다."로 소개.
    커버리지 개시 종목은 "[증권사]가 [종목명]에 대한 커버리지를 새로 시작했습니다."로 소개.
    brokerage_reports가 없거나 비어 있으면 이 섹션 자체를 JSON에 포함하지 말 것.
  → items 배열 필수(아래 "집계형 섹션 items 규칙" 참고).

### 집계형 섹션 items 규칙 (stock_추가관심종목 / stock_오늘의픽 / stock_증권사리포트 공통)
- narration/subtitle 전체 문단과 별도로, 종목 1개당 items 배열 원소 1개를 반드시 만드세요.
  문장 단위가 아니라 종목 단위로 나눠야 화면에 종목별로 정확히 번호가 매겨집니다.
  예: [{{"name": "종목명", "text": "이 종목 한 개에 대한 2~3문장 설명"}}, ...]
- items의 개수와 순서는 narration에서 종목을 언급한 개수·순서와 반드시 일치해야 합니다.
- 문장마다 번호를 매기지 말고, 반드시 종목(items 원소)마다 번호가 매겨지도록 하세요.

- ai_strategy : 700자 이상 (약 2분 20초)
  → 오늘 시장 흐름을 종합한 투자 전략을 구체적으로 서술.

### 분량 검증 규칙:
- 각 섹션 narration을 작성한 뒤 글자 수를 스스로 확인하세요.
- 모든 섹션이 목표치에 미달하면 반드시 추가 설명(배경·수치·전망·발언 인용 확장)을 붙여
  목표치를 채우세요. 목표 미달은 영상 후반부가 무음/음악만 나오는 결과로 이어지므로
  절대 피해야 합니다.
- market_summary만 600자를 넘기지 않도록 관리하고, 나머지 섹션은 목표치 이상으로
  풍부하게 작성하는 것을 권장합니다.
- "간략히", "짧게", "요약하면" 같은 표현으로 내용을 줄이지 마세요.

## ★ 종목 선별 기준
- market_leaders (2개): 반드시 모두 포함, summary+chart+mention 슬라이드 구성
- stocks: weighted_score 상위 3개는 개별 섹션으로 충실히 설명
- stocks: 나머지 종목도 반드시 전부 포함. "추가 관심 종목" 섹션(id: stock_추가관심종목)을
  하나 만들어 종목당 2~3문장으로 소개. 생략하지 말 것.
- hidden_picks: 데이터가 있으면 반드시 포함. "오늘의 픽" 섹션(id: stock_오늘의픽)으로 구성.
  데이터가 비어 있으면 해당 섹션 자체를 생략.
- brokerage_reports(JSON, 아래 별도 제공)가 있으면 세 카테고리를 모두 빠짐없이 반영해
  "증권사 리포트" 섹션(id: stock_증권사리포트)을 구성하세요.
  · simultaneous(동시언급): "여러 증권사에서 동시에 주목한 [종목명]입니다."로 소개
  · new_coverage(신규 커버리지 개시): "[증권사]가 [종목명]에 대한 커버리지를 새로 시작했습니다."로 소개
  · single_significant(유의미한 단독 언급): "[증권사]는 [종목명]에 대해 [의견/목표주가 요지]를 제시했습니다."로 소개
  각 항목은 ai_summary 필드가 있으면 그 내용을 근거로 종목당 1~2문장으로 간결히 소개하고,
  세 카테고리 배열이 모두 비어 있으면 이 섹션 자체를 생략하세요.

## ★ 종목 목록 매핑
{STOCK_NAME_LIST}

## ★ narration vs subtitle 핵심 차이 (반드시 준수)

### [narration — TTS 낭독용]
- 모든 숫자를 한글로 풀어서 읽습니다:
  · 6,700 → 육천칠백  |  133만 → 백삼십삼만  |  12조2400억 → 십이조 이천사백억
  · 85,400원 → 팔만오천사백원  |  +1.2% → 플러스 일쩜이퍼센트
- 소수점은 반드시 **"쩜"** (절대 "점" 금지):
  · 12.5% → 십이쩜오퍼센트  |  0.8% → 영쩜팔퍼센트
- 영문 약어를 한글 발음으로:
  · SK→에스케이 | LG→엘지 | KB→케이비 | AI→에이아이 | HBM→에이치비엠
  · ETF→이티에프 | ESS→이에스에스 | PCE→피씨이 | DSR→디에스알 | OTT→오티티
  · KOSPI→코스피 | KOSDAQ→코스닥 | MOU→엠오유 | ADR→에이디알
- 경음화 규칙:
  · 주가→주까 | 목표주가→목표주까 | 유가→유까 | 고유가→고유까
  · 실적→실쩍 | 적자→적짜 | 특징→특찡 | 격차→격짜
  · 국채→국째 | 역대→역때 | 발전→발쩐 | 결정→결쩡 | 절감→절깜
  · 신고가→신고까 | 최고가→최고까 | 할 것→할 껏 | 볼 수→볼 쑤
- 삼성전기 → "삼성 전기" (TTS 오독 방지, 자막은 원래대로)
- 숫자+단위 붙여 읽기: 170만원→백칠십만원 (절대 "백칠십만 원" 금지)

### [subtitle — 화면 자막용] — 절대 규칙 (narration을 그대로 베끼지 말 것)
- 숫자는 반드시 아라비아 숫자 그대로 표기:
  · 6,700 (❌ 육천칠백)  |  3,500원 (❌ 삼천오백원)  |  1.2% (❌ 일쩜이퍼센트)
  · 12조2400억 (❌ 십이조 이천사백억)
- 영문 약어·기업명은 반드시 원래 로마자 표기 그대로:
  · SK (❌ 에스케이)  |  AI (❌ 에이아이)  |  OTT (❌ 오티티)  |  LG (❌ 엘지)
  · KB (❌ 케이비)  |  HBM (❌ 에이치비엠)  |  ETF (❌ 이티에프)
- narration 필드를 작성한 뒤 숫자·영문 부분을 한글 발음으로 바꿔 놓았다면, subtitle
  필드에는 그 발음 표기를 절대 복사하지 말고 반드시 원래 숫자·로마자로 다시 바꿔서 쓰세요.
- 뜻이 생소한 용어는 **(뜻)** 을 괄호 안에 병기:
  · HBM(고대역폭 메모리) | PER(주가수익비율) | DSR(총부채원리금상환비율)
  · MOU(업무협약) | ADR(미국주식예탁증서) | PCE(개인소비지출) | ESS(에너지저장장치) | OTT(온라인 동영상 서비스)

## ★ mention 항목 규칙 — 이 방송의 핵심 목적
이 방송은 유튜브·증권방송에 출연한 전문가들이 각 종목에 대해 실제로 무엇을 말했는지
종합 정리해 전달하는 것이 가장 중요한 목적입니다. 종목 설명 자체보다 "누가, 어떤
채널에서, 무엇을 말했는지"에 더 많은 시간과 비중을 할애하세요.

### 실제 발언 근거 (반드시 준수 — 지어내기 금지)
- 아래 별도 제공되는 stock_quotes(JSON)에 해당 종목명이 있으면, 그 안의 speaker/channel/quote를
  그대로 근거로 사용해 quote_narration/quote_subtitle을 작성하세요. 숫자·발음 교정과 어미 다양화만
  적용하고, 발언의 내용·수치·논조는 절대 새로 창작하거나 다른 뜻으로 바꾸지 마세요.
- 해당 종목이 stock_quotes에 없으면 mentions 배열은 비워두거나 필드 자체를 생략하세요.
  없는 발언을 지어내는 것보다 mentions를 생략하는 것이 낫습니다.
- stock_quotes에 여러 발언이 있으면 가능한 한 모두 mentions에 포함하세요(슬라이드당 3개씩
  최대 3슬라이드, 종목당 최대 9개까지 지원). 발언을 임의로 줄이지 마세요.

### quote_narration (TTS 낭독용 — 발화자·채널을 부각하고 발언을 인용 형식으로)
- 반드시 화자명과 채널명을 먼저 호명하고, 발언 내용을 인용 형식으로 이어가세요:
  "[채널]의 [발화자]는 "(발언 원문을 존댓말로만 다듬어 그대로 인용)"라고 말했습니다." /
  화자가 없으면 "[채널]에서는 "(발언 원문)"라고 전했습니다."
- 발언 내용을 요약하거나 1문장으로 축약하지 말고, stock_quotes의 quote 필드 내용을
  최대한 원문 그대로 살려 2~3문장 분량으로 구체적으로 인용하세요 (근거·수치·전망까지 포함).
  이 방송의 핵심은 "누가 어떤 채널에서 무엇을 말했는지"이므로 발언을 재해석하지 말고
  실제로 한 말을 전달한다는 느낌으로 작성하세요.
- 종결어미 다양화 (같은 어미 2회 연속 금지):
  "~라고 전했습니다" | "~고 분석했습니다" | "~다고 밝혔습니다" | "~라고 진단했습니다"
  "~고 강조했습니다" | "~다고 내다봤습니다" | "~라고 언급했습니다" | "~고 보도했습니다"
  "~다고 전망했습니다" | "~라고 짚었습니다" | "~고 설명했습니다" | "~다고 판단했습니다"

### quote_subtitle (화면 카드 본문 — 발언 인용 자체, 헤드라인 축약 금지)
- 채널명·화자명은 카드 상단 배지에 별도로 크게 표시되므로 본문에는 채널/화자를
  다시 적지 말고 발언 내용 자체만 적습니다.
- 30자 헤드라인으로 압축하지 말고, 실제 발언의 핵심 문장을 인용부호(" ")로 감싸
  50~90자 내외로 구체적으로 제시하세요 (stock_quotes의 quote 필드를 근거로 함).
- 나쁜 예(과도한 축약): 코스피 6700 돌파 주도, 단기 과열 리스크 병존
- 좋은 예(발언 인용): "코스피 6700 돌파를 삼성전자가 주도했지만, 단기적으로는 과열
  신호도 함께 나타나고 있다고 봅니다"

### 코너 오프닝 멘트 (반드시 포함)
- opening: "__OPENING__" 플레이스홀더 사용
- market_summary: "먼저 오늘의 주식시장 전체 흐름을 요약해 드리겠습니다."
- sectors: "오늘 시장에서 주목받는 핵심 업종들을 살펴보겠습니다."
- 첫 번째 stock_: "지금부터 오늘의 관심 종목 분석입니다."
- 이후 stock_: "다음은 [종목명] 분석입니다."
- chart 슬라이드: "최근 이주간 주까 차트를 보면,"
- mention 슬라이드(첫 번째): "각 채널에서 언급한 내용을 보겠습니다."
- ai_strategy: "에이아이가 제안하는 오늘의 투자 전략입니다."
- closing: "__CLOSING__" 플레이스홀더 사용

## mention 슬라이드 분할 규칙
- 언급 1~3개: 단일 슬라이드
- 언급 4~6개: 2슬라이드 (_0/_1)
- 언급 7~9개: 3슬라이드 (_0/_1/_2)
- 각 슬라이드 최대 3개 언급

## 최종 JSON 구조
{{
  "title": "{TODAY} KBS 머니올라 주식 브리핑",
  "date": "{TODAY}",
  "sections": [
    {{
      "id": "opening",
      "label": "오프닝",
      "narration": "__OPENING__",
      "subtitle": "__OPENING_SUBTITLE__",
      "keywords": ["키워드1", "키워드2", "키워드3"]
    }},
    {{
      "id": "market_summary",
      "label": "시장 요약",
      "corner_summary": "오늘 시장의 핵심 한줄 요약",
      "narration": "먼저 오늘의 주식시장 전체 흐름을 요약해 드리겠습니다. ...",
      "subtitle": "먼저 오늘의 주식시장 전체 흐름을 요약해 드리겠습니다. ...",
      "kospi_value": "9,052",
      "kospi_change": "-0.13%",
      "kospi_change_positive": false,
      "kosdaq_value": "966",
      "kosdaq_change": "-3.43%",
      "kosdaq_change_positive": false,
      "nasdaq_value": "19,864",
      "nasdaq_change": "-0.24%",
      "nasdaq_positive": false,
      "sp500_value": "5,528",
      "sp500_change": "-0.05%",
      "sp500_positive": false,
      "usdkrw_value": "1,380",
      "usdkrw_change": "-0.74%",
      "usdkrw_positive": false,
      "points": ["포인트1", "포인트2", "포인트3"]
    }},
    {{
      "id": "sectors",
      "label": "업종 분석",
      "corner_summary": "오늘의 핵심 섹터 한줄 요약",
      "narration": "오늘 시장에서 주목받는 핵심 업종들을 살펴보겠습니다. ...",
      "subtitle": "오늘 시장에서 주목받는 핵심 업종들을 살펴보겠습니다. ...",
      "sector_list": [{{"name": "섹터명", "desc": "설명", "momentum": "상승/보합/하락"}}]
    }},
    {{
      "id": "stock_삼성전자",
      "label": "종목 분석 - 삼성전자",
      "corner_summary": "삼성전자 한줄 요약",
      "narration_summary": "지금부터 관심 종목 분석입니다. ...",
      "subtitle_summary": "지금부터 관심 종목 분석입니다. ...",
      "narration_chart": "최근 이주간 주까 차트를 보면, ...",
      "subtitle_chart": "최근 2주간 주가 차트를 보면, ...",
      "narration_mention": "각 채널에서 언급한 내용을 보겠습니다. ...",
      "subtitle_mention": "...",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "summary": "한줄 요약",
      "catalysts": ["촉매1", "촉매2"],
      "risks": ["리스크1"],
      "mentions": [
        {{
          "speaker": "발화자명",
          "channel": "채널명",
          "quote_narration": "TTS 낭독용 구어체",
          "quote_subtitle": "문어체 요약 30자 이내"
        }}
      ]
    }},
    {{
      "id": "stock_추가관심종목",
      "label": "추가 관심 종목",
      "corner_summary": "추가 관심 종목 한줄 요약",
      "narration": "다음은 오늘의 추가 관심 종목입니다. ...",
      "subtitle": "다음은 오늘의 추가 관심 종목입니다. ...",
      "items": [
        {{"name": "종목명", "text": "이 종목 1개에 대한 2~3문장 설명(등락 방향+이유+전망)"}}
      ]
    }},
    {{
      "id": "ai_strategy",
      "label": "AI 투자 전략",
      "corner_summary": "오늘의 AI 전략 핵심 요약",
      "narration": "에이아이가 제안하는 오늘의 투자 전략입니다. ...",
      "subtitle": "AI가 제안하는 오늘의 투자 전략입니다. ...",
      "bullet_points": ["전략1", "전략2"]
    }},
    {{
      "id": "closing",
      "label": "클로징",
      "narration": "__CLOSING__",
      "subtitle": "__CLOSING_SUBTITLE__",
      "disclaimer": "⚠️ 투자 유의사항 | 본 브리핑은 AI 분석 참고자료이며 투자 권유가 아닙니다. 주식 투자는 원금 손실 위험이 있습니다. 투자 책임은 전적으로 본인에게 있습니다."
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": (
                "15분 분량의 KBS 머니올라 방송 스크립트를 작성해주세요. 각 섹션은 최소 목표 글자 수를 반드시 초과해야 하며, "
                "분량이 부족하면 관련 배경 설명과 시장 맥락을 추가로 서술하세요.\n"
                "유튜브 출연진 멘트를 반드시 포함시켜 주세요. mentions는 아래 stock_quotes JSON에 있는 "
                "실제 발언만 사용하고, 없는 종목은 mentions를 생략하세요.\n\n"
                + (f"## 실시간 시장 지표 (market_summary JSON 필드에 그대로 사용하세요)\n"
                   f"{json.dumps(market_data, ensure_ascii=False, indent=2)}\n\n"
                   if market_data else "")
                + (f"## 증권사 리포트 데이터 (JSON, stock_증권사리포트 섹션에 반드시 반영)\n"
                   f"{json.dumps(brokerage_reports, ensure_ascii=False, indent=2)}\n\n"
                   if brokerage_reports else "")
                + (f"## 종목별 실제 발언 인용 (JSON, mentions 필드는 이 데이터만 근거로 작성)\n"
                   f"{json.dumps(stock_quotes, ensure_ascii=False, indent=2)}\n\n"
                   if stock_quotes else "")
                + briefing_text
            )}
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=16000,
    )

    raw  = response.choices[0].message.content
    data = json.loads(raw)

    def _replace(obj):
        if isinstance(obj, str):
            return (obj
                    .replace("__OPENING__",          OPENING_NARRATION)
                    .replace("__OPENING_SUBTITLE__",  OPENING_SUBTITLE)
                    .replace("__CLOSING__",           CLOSING_NARRATION)
                    .replace("__CLOSING_SUBTITLE__",  CLOSING_SUBTITLE))
        if isinstance(obj, dict):
            return {k: _replace(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_replace(v) for v in obj]
        return obj

    data = _replace(data)
    data = fix_subtitle_fields(data)

    # ── 분량 검증 로그 ──────────────────────────────────────────────────────
    sections = data.get("sections", [])
    total_chars = 0
    print("\n📏 섹션별 narration 글자 수:")
    for sec in sections:
        sid = sec.get("id", "")
        # narration 필드가 여러 이름으로 존재할 수 있음
        narr = (
            sec.get("narration")
            or (sec.get("narration_summary", "") + sec.get("narration_chart", "") + sec.get("narration_mention", ""))
        )
        chars = len(narr) if narr else 0
        total_chars += chars
        print(f"  {sid}: {chars:,}자")
    print(f"  ─────────────────")
    print(f"  합계: {total_chars:,}자  (목표: 5,800자 이상, 약 320자/분 기준 15분 분량)")
    if total_chars < 5800:
        print(f"  ⚠️  분량 부족! {5800 - total_chars:,}자 미달 — 영상 후반부가 무음 패딩으로 "
              f"채워질 위험이 있습니다")
    else:
        print(f"  ✅ 분량 목표 달성")

    market_sec = next((s for s in sections if s.get("id") == "market_summary"), None)
    if market_sec:
        ms_chars = len(market_sec.get("narration", "") or "")
        if ms_chars > 600:
            print(f"  ⚠️  market_summary가 목표(480~600자)를 초과했습니다: {ms_chars:,}자 "
                  f"(약 {ms_chars / 320 * 60:.0f}초 분량 — 2분 목표 초과)")

    return data


# ─────────────────────────────────────────────────────────────────────────────

def run(lang: str = "KO"):
    lang = lang.upper()
    briefing_text = fetch_briefing()
    if not briefing_text:
        print("❌ 브리핑 텍스트를 가져오지 못했습니다. 종료합니다.")
        sys.exit(1)

    print(f"✅ 브리핑 텍스트 수신 완료 ({len(briefing_text):,}자)")

    # briefing_data.json에서 market_data + brokerage_reports 직접 로드 (해외 지수/환율 포함)
    market_data = None
    brokerage_reports = None
    briefing_date_iso = ""
    try:
        import urllib.request
        url = "https://kunil-choi.github.io/stock-briefing-v3/data/briefing_data.json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw_json = json.loads(resp.read().decode("utf-8"))
        md = raw_json.get("market_data", {})
        briefing_date_iso = _kdate_to_iso(raw_json.get("briefing_date", ""))

        _br = raw_json.get("brokerage_reports") or {}
        if any(_br.get(k) for k in ("simultaneous", "new_coverage", "single_significant")):
            brokerage_reports = _br

        def _fmt_value(v):
            if v is None: return ""
            return f"{v:,.2f}" if isinstance(v, float) else str(v)

        def _fmt_change(pct, direction):
            if pct is None: return ""
            sign = "+" if direction == "up" else ("-" if direction == "down" else "")
            return f"{sign}{abs(pct):.2f}%"

        market_data = {
            "kospi_value":        _fmt_value(md.get("kospi", {}).get("value")),
            "kospi_change":       _fmt_change(md.get("kospi", {}).get("change_pct"), md.get("kospi", {}).get("direction")),
            "kospi_change_positive": md.get("kospi", {}).get("direction") == "up",
            "kosdaq_value":       _fmt_value(md.get("kosdaq", {}).get("value")),
            "kosdaq_change":      _fmt_change(md.get("kosdaq", {}).get("change_pct"), md.get("kosdaq", {}).get("direction")),
            "kosdaq_change_positive": md.get("kosdaq", {}).get("direction") == "up",
            "nasdaq_value":       _fmt_value(md.get("nasdaq", {}).get("value")),
            "nasdaq_change":      _fmt_change(md.get("nasdaq", {}).get("change_pct"), md.get("nasdaq", {}).get("direction")),
            "nasdaq_positive":    md.get("nasdaq", {}).get("direction") == "up",
            "sp500_value":        _fmt_value(md.get("sp500", {}).get("value")),
            "sp500_change":       _fmt_change(md.get("sp500", {}).get("change_pct"), md.get("sp500", {}).get("direction")),
            "sp500_positive":     md.get("sp500", {}).get("direction") == "up",
            "usdkrw_value":       _fmt_value(md.get("usd_krw", {}).get("value")),
            "usdkrw_change":      _fmt_change(md.get("usd_krw", {}).get("change_pct"), md.get("usd_krw", {}).get("direction")),
            "usdkrw_positive":    md.get("usd_krw", {}).get("direction") == "up",
        }
        print(f"✅ market_data 로드 완료: KOSPI {market_data['kospi_value']} / NASDAQ {market_data['nasdaq_value']} / USD/KRW {market_data['usdkrw_value']}")
    except Exception as e:
        print(f"⚠️ market_data 로드 실패 (briefing_data.json): {e} → 수치 없이 진행")

    # 종목별 실제 발언 인용 로드 (youtube_mentions.json)
    stock_quotes = None
    yt_mentions = fetch_youtube_mentions()
    if yt_mentions:
        grouped = build_stock_quotes(yt_mentions, briefing_date_iso)
        if grouped:
            stock_quotes = grouped
            total_quotes = sum(len(v) for v in grouped.values())
            print(f"✅ 종목별 실제 발언 로드 완료: {len(grouped)}개 종목 / {total_quotes}건")
    if not stock_quotes:
        print("⚠️ youtube_mentions.json 매칭 실패 또는 비어있음 → mentions는 생략될 수 있음")

    script = generate_script(briefing_text, market_data, brokerage_reports, stock_quotes)

    root     = os.path.join(_HERE, "..")
    out_dir  = os.path.join(root, "output", lang, "scripts")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "script.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    sections = script.get("sections", [])
    print(f"\n✅ 스크립트 생성 완료! 섹션 수: {len(sections)}개 → {out_path}")
    return script


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)

