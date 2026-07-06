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
#
# ★ 설계 노트 (다중 호출 아키텍처): gpt-4o의 출력 토큰 상한은 16,384개로 고정돼
# 있습니다. 15분 분량(시장요약+업종분석+AI전략+대형주도주/상위종목 5개(종목당 최대
# 9개 발언 인용 포함)+집계 섹션)을 narration+subtitle 이중 표기로 모두 채우려면
# 실측상 25,000~55,000 토큰이 필요해, 한 번의 API 호출로는 절대 다 채울 수
# 없습니다. 프롬프트 글자 수 목표를 아무리 올려도 이 하드 리밋 때문에 실제로는
# 전혀 개선되지 않았던 것이 바로 이 문제입니다.
# 그래서 하나의 거대한 호출 대신, 섹션별로 여러 번의 작은 호출로 나눠 생성한 뒤
# 병합합니다. 각 호출은 개별적으로 16,384 토큰 상한에 여유 있게 들어갑니다.
# ─────────────────────────────────────────────────────────────────────────────

_NARRATION_SUBTITLE_RULES = """
## ★ narration vs subtitle 핵심 차이 (반드시 준수)

### narration/subtitle 문장 수 일치 (자막 동기화를 위해 반드시 준수)
- narration과 subtitle(및 narration_summary/subtitle_summary 등 모든 쌍)은 반드시 문장
  수가 동일해야 하고, 같은 순서로 같은 내용을 담아야 합니다. 표기(숫자/영문)만 다를 뿐
  내용과 문장 경계는 1:1로 대응해야 자막이 나레이션과 정확히 동기화됩니다.
- 문장 수를 맞추기 위해 임의로 문장을 합치거나 쪼개지 말고, 애초에 같은 문장 구조로
  narration과 subtitle을 나란히 작성하세요.

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
"""

_MENTION_RULES = """
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
- 인용부호로 감싼 문장 뒤에는 반드시 마침표를 찍어 문장이 명확히 끝나도록 하세요
  (자막 동기화 로직이 마침표 등 문장부호를 기준으로 문장을 구분합니다).
- 나쁜 예(과도한 축약): 코스피 6700 돌파 주도, 단기 과열 리스크 병존
- 좋은 예(발언 인용): "코스피 6700 돌파를 삼성전자가 주도했지만, 단기적으로는 과열
  신호도 함께 나타나고 있다고 봅니다."

### narration_mention_N / subtitle_mention_N 작성 규칙
- 언급 1~3개: narration_mention / subtitle_mention (접미사 없음) 필드 하나만 작성.
- 언급 4~6개: narration_mention_0/1, subtitle_mention_0/1 (페이지당 최대 3개 발언).
- 언급 7~9개: narration_mention_0/1/2, subtitle_mention_0/1/2.
- 각 페이지의 narration_mention_N은 그 페이지에 속한 mentions의 quote_narration을
  화자·채널 소개와 함께 순서대로 이어붙인 완결된 문단으로 작성하고, subtitle_mention_N도
  같은 순서·같은 문장 수로 대응하는 quote_subtitle들을 이어붙이세요(문장 수 일치 필수).
"""


def _call_json(system_prompt: str, user_content: str, max_tokens: int,
               temperature: float = 0.7, retries: int = 1) -> dict:
    """OpenAI Chat Completions를 호출해 JSON 객체를 반환합니다. 실패 시 1회 재시도."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            last_err = e
            print(f"  ⚠️ API 호출 실패(시도 {attempt + 1}/{retries + 1}): {e}")
    print(f"  ❌ API 호출 최종 실패: {last_err}")
    return {}


def _generate_core(briefing_text: str, market_data: dict) -> dict:
    """시장요약/업종분석/AI전략 코너와 종목 분류 목록을 생성하는 1차 호출.
    종목별 상세 섹션(mentions 포함)은 여기서 만들지 않아 토큰 상한에 여유가 큽니다."""
    system_prompt = f"""
너는 KBS 머니올라 주식 방송 스크립트 작성 전문가입니다. 오늘 방송의 '시장 요약',
'업종 분석', 'AI 투자 전략' 코너와, 이후 종목별 섹션을 만들기 위한 종목 분류 목록을
JSON으로 작성하세요. 이 호출에서는 개별 종목의 상세 설명은 작성하지 마세요.
작성일: {TODAY}

{_NARRATION_SUBTITLE_RULES}

## ★ 섹션별 요구사항 (narration 글자 수, 공백 포함)
- market_summary: 480~600자 (목표 1분 30초~2분, 600자를 크게 넘기지 말 것).
  KOSPI·KOSDAQ·해외지수·환율의 등락과 핵심 원인 1~2가지만 짚고, 업종·개별 종목 상세
  설명은 하지 마세요(다음 코너에서 다룸). "먼저 오늘의 주식시장 전체 흐름을 요약해
  드리겠습니다."로 시작. points는 3~4개.
- sectors: 900자 이상. hot_sectors 각 섹터를 3~5문장으로 충분히 설명하고, market_summary와
  중복되는 지수·환율 코멘트는 반복하지 마세요. "오늘 시장에서 주목받는 핵심 업종들을
  살펴보겠습니다."로 시작. sector_list는 최대 6개.
- ai_strategy: 700자 이상. 오늘 시장 흐름을 종합한 투자 전략을 구체적으로 서술.
  "에이아이가 제안하는 오늘의 투자 전략입니다."로 시작. bullet_points는 4~6개.
- 위 세 섹션 모두 목표 글자 수 미달을 절대 허용하지 마세요. 미달 시 배경 설명, 수치,
  전망을 추가해서 채우세요. "간략히", "요약하면" 같은 축약 표현은 쓰지 마세요.

## ★ 종목 분류 (브리핑 원문에서 추출 — 본문 작성 없이 목록만)
- market_leaders: 브리핑에서 가장 비중 있게 다뤄진 대형 주도주 정확히 2개.
- top_stocks: market_leaders를 제외하고 weighted_score(또는 언급 비중)가 높은 상위 3개.
- remaining_stocks: 브리핑에 등장하는 나머지 관심 종목 전부 (생략 없이 모두 나열).
- hidden_picks: '오늘의 픽'/'숨은 종목' 성격의 종목 (없으면 빈 배열).
- 종목명은 아래 목록의 정확한 표기를 사용하세요.

## ★ 종목 목록 매핑
{STOCK_NAME_LIST}

## 출력 JSON 구조
{{
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "market_summary": {{
    "corner_summary": "오늘 시장의 핵심 한줄 요약",
    "narration": "...", "subtitle": "...",
    "points": ["포인트1", "포인트2", "포인트3"]
  }},
  "sectors": {{
    "corner_summary": "오늘의 핵심 섹터 한줄 요약",
    "narration": "...", "subtitle": "...",
    "sector_list": [{{"name": "섹터명", "desc": "설명", "momentum": "상승/보합/하락"}}]
  }},
  "ai_strategy": {{
    "corner_summary": "오늘의 AI 전략 핵심 요약",
    "narration": "...", "subtitle": "...",
    "bullet_points": ["전략1", "전략2"]
  }},
  "market_leaders": ["종목명", "종목명"],
  "top_stocks": ["종목명", "종목명", "종목명"],
  "remaining_stocks": ["종목명"],
  "hidden_picks": []
}}
"""
    user_content = (
        (f"## 실시간 시장 지표 (참고만 하고 narration/subtitle 서술에 반영하세요. "
         f"이 수치 필드를 JSON에 다시 출력할 필요는 없습니다)\n"
         f"{json.dumps(market_data, ensure_ascii=False, indent=2)}\n\n"
         if market_data else "")
        + briefing_text
    )
    data = _call_json(system_prompt, user_content, max_tokens=6000, temperature=0.7)

    market_summary = data.get("market_summary") or {}
    if market_data:
        market_summary = {**market_summary, **market_data}

    return {
        "keywords":          (data.get("keywords") or [])[:4],
        "market_summary":    market_summary,
        "sectors":           data.get("sectors") or {},
        "ai_strategy":       data.get("ai_strategy") or {},
        "market_leaders":    data.get("market_leaders") or [],
        "top_stocks":        data.get("top_stocks") or [],
        "remaining_stocks":  data.get("remaining_stocks") or [],
        "hidden_picks":      data.get("hidden_picks") or [],
    }


def _generate_stock_section(stock_name: str, briefing_text: str,
                             quotes: list, is_hidden: bool = False) -> dict:
    """종목 하나에 대한 완전한 섹션(summary+chart+mention+mentions)을 생성하는 호출.
    market_leaders/top_stocks 종목마다 별도로 호출해, 발언 인용이 많아도(최대 9개)
    토큰 상한에 안전하게 들어갑니다."""
    system_prompt = f"""
너는 KBS 머니올라 주식 방송 스크립트 작성 전문가입니다. 아래 종목 '{stock_name}' 하나에
대한 종목 분석 섹션만 작성하세요. 다른 종목은 절대 다루지 마세요.
작성일: {TODAY}

{_NARRATION_SUBTITLE_RULES}

{_MENTION_RULES}

## ★ 분량 요구사항 (요구사항: 종목별 설명을 더 자세히)
- narration_summary + narration_chart + narration_mention(_N 포함) 합산 900자 이상.
- narration_mention 계열 분량이 narration_summary보다 짧아지지 않도록 하세요. 이 코너의
  핵심은 "누가 무엇을 말했는지"이므로 mention 분량을 가장 충실하게 작성합니다.
- 목표 미달을 절대 허용하지 마세요. "간략히", "요약하면" 표현 금지.

## ★ 코너 멘트
- narration_summary 시작: "다음은 {stock_name} 분석입니다."
- narration_chart 시작: "최근 이주간 주까 차트를 보면,"
- 첫 mention 페이지 시작: "각 채널에서 언급한 내용을 보겠습니다."

## 출력 JSON 구조
{{
  "corner_summary": "{stock_name} 한줄 요약",
  "narration_summary": "...", "subtitle_summary": "...",
  "narration_chart": "...", "subtitle_chart": "...",
  "narration_mention": "...(언급 1~3개일 때만)", "subtitle_mention": "...",
  "narration_mention_0": "...(언급 4개 이상일 때만)", "subtitle_mention_0": "...",
  "narration_mention_1": "...", "subtitle_mention_1": "...",
  "narration_mention_2": "...(언급 7개 이상일 때만)", "subtitle_mention_2": "...",
  "price": "000,000", "change": "+0.00%", "change_positive": true,
  "summary": "한줄 요약", "catalysts": ["촉매1", "촉매2"], "risks": ["리스크1"],
  "mentions": [
    {{"speaker": "발화자명", "channel": "채널명",
      "quote_narration": "TTS 낭독용 — 발화자·채널 호명 후 인용",
      "quote_subtitle": "화면 카드용 — 발언 인용, 50~90자"}}
  ]
}}

이 종목에 대한 실제 발언 데이터(stock_quotes)가 비어 있으면 mentions는 빈 배열로 두고
narration_mention 계열 필드도 생략하세요.
"""
    user_content = (
        (f"## 이 종목의 실제 발언 인용 (mentions 필드는 이 데이터만 근거로 작성, 지어내기 금지)\n"
         f"{json.dumps(quotes, ensure_ascii=False, indent=2)}\n\n"
         if quotes else "이 종목에 대한 실제 발언 데이터가 없습니다. mentions는 빈 배열로 두세요.\n\n")
        + f"## 브리핑 원문 (이 중 '{stock_name}' 관련 내용만 참고하세요)\n{briefing_text}"
    )
    data = _call_json(system_prompt, user_content, max_tokens=6000, temperature=0.7)
    if not data:
        return {}
    data["id"] = f"{'hidden_' if is_hidden else 'stock_'}{stock_name}"
    data["label"] = f"{'숨은 ' if is_hidden else ''}종목 분석 - {stock_name}"
    return data


def _generate_aggregate_sections(remaining_stocks: list, hidden_picks: list,
                                  brokerage_reports: dict, briefing_text: str) -> list:
    """추가 관심 종목 / 오늘의 픽 / 증권사 리포트 3개 집계 섹션을 생성하는 호출."""
    if not remaining_stocks and not hidden_picks and not brokerage_reports:
        return []

    system_prompt = f"""
너는 KBS 머니올라 주식 방송 스크립트 작성 전문가입니다. 아래 세 집계형 코너를 JSON으로
작성하세요. 해당 데이터가 없는 코너는 결과 JSON에서 필드 자체를 생략하세요.
작성일: {TODAY}

{_NARRATION_SUBTITLE_RULES}

## ★ stock_추가관심종목 (remaining_stocks 목록에 있는 종목이 있을 때만 작성)
- narration/subtitle: "다음은 오늘의 추가 관심 종목입니다."로 시작, 종목 수에 비례해
  종목당 최소 100자, 전체 400자 이상. 각 종목: 등락 방향+핵심 이유+전망까지 2문장 이상.
- items: remaining_stocks의 종목을 전부(생략 없이) 다루고, 종목 1개당 items 배열 원소
  1개. [{{"name": "종목명", "text": "이 종목 1개에 대한 2~3문장 설명"}}, ...]
  items 순서·개수는 narration에서 언급한 순서·개수와 반드시 일치해야 합니다.

## ★ stock_오늘의픽 (hidden_picks가 있을 때만 작성)
- narration/subtitle: "오늘의 숨은 픽을 소개합니다."로 시작, hidden_picks 각각을
  2~3문장으로 소개, 전체 300자 이상.
- items: hidden_picks 종목 1개당 원소 1개, 위와 동일한 형식.

## ★ stock_증권사리포트 (brokerage_reports 데이터가 있을 때만 작성)
- narration/subtitle: "증권사 리포트에서 주목한 종목을 살펴보겠습니다."로 시작, 전체
  300자 이상.
  · simultaneous(동시언급): "여러 증권사에서 동시에 주목한 [종목명]입니다."로 소개
  · new_coverage(신규 커버리지 개시): "[증권사]가 [종목명]에 대한 커버리지를 새로
    시작했습니다."로 소개
  · single_significant(유의미한 단독 언급): "[증권사]는 [종목명]에 대해 [의견/목표주가
    요지]를 제시했습니다."로 소개
- items: 위 세 카테고리에 등장한 종목 1개당 원소 1개, 위와 동일한 형식.

## 문장마다 번호를 매기지 말고, 반드시 종목(items 원소)마다 번호가 매겨지도록 items를
작성하세요 (화면에 items 배열 순서대로 번호가 표시됩니다).

## 출력 JSON 구조 (해당 데이터 없는 코너는 키 자체를 생략)
{{
  "stock_추가관심종목": {{
    "corner_summary": "추가 관심 종목 한줄 요약",
    "narration": "...", "subtitle": "...",
    "items": [{{"name": "종목명", "text": "..."}}]
  }},
  "stock_오늘의픽": {{
    "corner_summary": "오늘의 픽 한줄 요약",
    "narration": "...", "subtitle": "...",
    "items": [{{"name": "종목명", "text": "..."}}]
  }},
  "stock_증권사리포트": {{
    "corner_summary": "증권사 리포트 한줄 요약",
    "narration": "...", "subtitle": "...",
    "items": [{{"name": "종목명", "text": "..."}}]
  }}
}}
"""
    user_content = (
        f"## 추가 관심 종목 목록\n{json.dumps(remaining_stocks, ensure_ascii=False)}\n\n"
        f"## 오늘의 픽 목록\n{json.dumps(hidden_picks, ensure_ascii=False)}\n\n"
        + (f"## 증권사 리포트 데이터\n{json.dumps(brokerage_reports, ensure_ascii=False, indent=2)}\n\n"
           if brokerage_reports else "")
        + f"## 브리핑 원문\n{briefing_text}"
    )
    data = _call_json(system_prompt, user_content, max_tokens=8000, temperature=0.7)

    sections = []
    for sid, title in (
        ("stock_추가관심종목", "추가 관심 종목"),
        ("stock_오늘의픽", "오늘의 픽"),
        ("stock_증권사리포트", "증권사 리포트"),
    ):
        sec = data.get(sid)
        if sec:
            sec["id"] = sid
            sec["label"] = title
            sections.append(sec)
    return sections


def generate_script(
    briefing_text: str,
    market_data: dict = None,
    brokerage_reports: dict = None,
    stock_quotes: dict = None,
) -> dict:
    stock_quotes = stock_quotes or {}

    print("\n🧩 1/3 — 시장요약/업종분석/AI전략 + 종목 분류 생성 중...")
    core = _generate_core(briefing_text, market_data)
    print(f"   대형 주도주: {core['market_leaders']}")
    print(f"   상위 관심종목: {core['top_stocks']}")
    print(f"   추가 관심종목: {len(core['remaining_stocks'])}개 / 오늘의 픽: {len(core['hidden_picks'])}개")

    # 개별 섹션으로 다룰 종목 목록 (대형 주도주 + 상위 관심종목, 중복 제거)
    seen = set()
    major_stocks = []
    for name in core["market_leaders"] + core["top_stocks"]:
        norm = normalize_stock_name(name)
        if norm and norm not in seen:
            seen.add(norm)
            major_stocks.append(norm)

    print(f"\n🧩 2/3 — 종목별 상세 섹션 생성 중... ({len(major_stocks)}개)")
    stock_sections = []
    for i, stock_name in enumerate(major_stocks, 1):
        print(f"   [{i}/{len(major_stocks)}] {stock_name}")
        sec = _generate_stock_section(stock_name, briefing_text, stock_quotes.get(stock_name, []))
        if sec:
            stock_sections.append(sec)
        else:
            print(f"   ⚠️ {stock_name} 섹션 생성 실패 — 건너뜁니다")

    # 개별 섹션에서 다룬 종목은 추가 관심 종목 목록에서 제외
    covered = set(major_stocks)
    remaining_stocks = [
        normalize_stock_name(n) for n in core["remaining_stocks"]
        if normalize_stock_name(n) not in covered
    ]

    print(f"\n🧩 3/3 — 집계 섹션(추가 관심종목/오늘의픽/증권사리포트) 생성 중...")
    aggregate_sections = _generate_aggregate_sections(
        remaining_stocks, core["hidden_picks"], brokerage_reports, briefing_text
    )

    opening_section = {
        "id": "opening", "label": "오프닝",
        "narration": "__OPENING__", "subtitle": "__OPENING_SUBTITLE__",
        "keywords": core["keywords"],
    }
    market_summary_section = {"id": "market_summary", "label": "시장 요약", **core["market_summary"]}
    sectors_section = {"id": "sectors", "label": "업종 분석", **core["sectors"]}
    ai_strategy_section = {"id": "ai_strategy", "label": "AI 투자 전략", **core["ai_strategy"]}
    closing_section = {
        "id": "closing", "label": "클로징",
        "narration": "__CLOSING__", "subtitle": "__CLOSING_SUBTITLE__",
        "disclaimer": DISCLAIMER,
    }

    sections = (
        [opening_section, market_summary_section, sectors_section]
        + stock_sections
        + aggregate_sections
        + [ai_strategy_section, closing_section]
    )
    data = {"title": f"{TODAY} KBS 머니올라 주식 브리핑", "date": TODAY, "sections": sections}

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

