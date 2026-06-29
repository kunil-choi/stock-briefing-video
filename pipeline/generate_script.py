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
import sys
import json
from datetime import datetime
from openai import OpenAI
from playwright.sync_api import sync_playwright

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from assets.config import STOCK_CODES, normalize_stock_name

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
    "안녕하세요, 케이비에스 머니올라에서 제공하는 오늘의 주식시장 브리핑입니다. "
    f"오늘은 {TODAY_MONTH}월 {TODAY_DAY}일, 지금부터 오늘의 시장 흐름과 주요 종목을 함께 살펴보겠습니다. "
    "시청자 여러분이 가장 궁금해하실 핵심 내용만 골라 알기 쉽게 전달해 드리겠습니다."
)

OPENING_SUBTITLE = (
    "안녕하세요, KBS 머니올라에서 제공하는 오늘의 주식시장 브리핑입니다. "
    f"오늘은 {TODAY_MONTH}월 {TODAY_DAY}일, 지금부터 오늘의 시장 흐름과 주요 종목을 함께 살펴보겠습니다. "
    "시청자 여러분이 가장 궁금해하실 핵심 내용만 골라 알기 쉽게 전달해 드리겠습니다."
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
    "케이비에스 머니올라는 투자 결과에 대해 어떠한 법적 책임도 지지 않습니다. "
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
    "KBS 머니올라는 투자 결과에 대해 어떠한 법적 책임도 지지 않습니다. "
    "구독과 좋아요는 저희에게 큰 힘이 됩니다. 내일도 유익한 브리핑으로 찾아뵙겠습니다. 감사합니다."
)

DISCLAIMER = (
    "⚠️ 투자 유의사항 | 본 브리핑은 AI 분석 참고자료이며 투자 권유가 아닙니다. "
    "주식 투자는 원금 손실 위험이 있습니다. 투자 책임은 전적으로 본인에게 있습니다."
)


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


# ─────────────────────────────────────────────────────────────────────────────
# 스크립트 생성
# ─────────────────────────────────────────────────────────────────────────────

def generate_script(briefing_text: str, market_data: dict = None) -> dict:
    system_prompt = f"""
너는 KBS 머니올라 주식 방송 스크립트 작성 전문가입니다.
증권 브리핑 데이터를 바탕으로 **15분짜리** 방송 스크립트를 JSON 형식으로 작성하세요.
작성일: {TODAY}

## ★ 15분 영상 분량 설계 (반드시 준수)
한국어 TTS 낭독 속도 기준: 1분 = 약 250자
전체 목표: 오프닝+클로징 고정 텍스트 포함 총 3,750자 이상

### 섹션별 narration 목표 글자 수 (공백 포함):
- market_summary : 550자 이상 (약 2분 10초)
  → 코스피·코스닥·미국 3대 지수·환율 수치를 모두 언급하고,
    오늘 시장의 주요 흐름과 배경을 구체적으로 설명합니다.

- sectors : 500자 이상 (약 2분)
  → hot_sectors 5개 섹터 각각 2~3문장으로 설명합니다.
    단순 나열이 아닌, 왜 오늘 주목받는지 이유까지 설명합니다.

- stock_[market_leader 1번] : 400자 이상 (약 1분 30초)
  → summary + catalyst + risk + mentions 전부 포함.
    mentions는 채널명을 호명하며 구어체로 전달합니다.

- stock_[market_leader 2번] : 400자 이상 (약 1분 30초)
  → 위와 동일.

- stock_[stocks 상위 3개, weighted_score 높은 순] : 각 300자 이상 (각 약 1분 10초)
  → summary + catalyst + 핵심 mention 1개 포함.

- stock_[stocks 하위 종목들] : 전체 묶어서 300자 이상 (약 1분 10초)
  → "다음은 오늘의 추가 관심 종목입니다."로 시작하여
    남은 종목들을 종목당 1~2문장으로 빠르게 소개합니다.
    (hidden_picks가 비어 있으면 이 섹션은 생략합니다.)

- ai_strategy : 400자 이상 (약 1분 30초)
  → 핵심 시나리오 + 섹터 로테이션 전략을 구체적으로 설명합니다.

### 분량 검증 규칙:
- 각 섹션 narration을 작성한 뒤 글자 수를 스스로 확인하세요.
- 목표치에 미달하면 반드시 추가 설명을 붙여 목표치를 채우세요.
- "간략히", "짧게", "요약하면" 같은 표현으로 내용을 줄이지 마세요.

## ★ 종목 선별 기준
- market_leaders (2개): 반드시 모두 포함, 충실히 설명
- stocks: weighted_score 상위 3개는 개별 섹션으로 충실히 설명
- stocks: 나머지는 하나의 섹션에 묶어 빠르게 소개
- hidden_picks: 데이터가 비어 있으면 완전 제외

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
  · ETF→이티에프 | ESS→이에스에스 | PCE→피씨이 | DSR→디에스알
  · KOSPI→코스피 | KOSDAQ→코스닥 | MOU→엠오유 | ADR→에이디알
- 경음화 규칙:
  · 주가→주까 | 목표주가→목표주까 | 유가→유까 | 고유가→고유까
  · 실적→실쩍 | 적자→적짜 | 특징→특찡 | 격차→격짜
  · 국채→국째 | 역대→역때 | 발전→발쩐 | 결정→결쩡 | 절감→절깜
  · 신고가→신고까 | 최고가→최고까 | 할 것→할 껏 | 볼 수→볼 쑤
- 삼성전기 → "삼성 전기" (TTS 오독 방지, 자막은 원래대로)
- 숫자+단위 붙여 읽기: 170만원→백칠십만원 (절대 "백칠십만 원" 금지)

### [subtitle — 화면 자막용]
- 숫자는 아라비아 숫자 그대로 (예: 6,700 / 1.2%)
- 영문 약어는 원래 표기 그대로 (AI, HBM, ETF 등)
- 기업명은 원래 표기 그대로
- 뜻이 생소한 용어는 **(뜻)** 을 괄호 안에 병기:
  · HBM(고대역폭 메모리) | PER(주가수익비율) | DSR(총부채원리금상환비율)
  · MOU(업무협약) | ADR(미국주식예탁증서) | PCE(개인소비지출) | ESS(에너지저장장치)

## ★ mention 항목 규칙

### quote_narration (TTS 낭독용 — 구어체)
- 채널명을 먼저 호명: "발화자가 있으면 [채널]의 [발화자]는," / 없으면 "[채널]에서는,"
- 종결어미 다양화 (같은 어미 2회 연속 금지):
  "~라고 전했습니다" | "~고 분석했습니다" | "~다고 밝혔습니다" | "~라고 진단했습니다"
  "~고 강조했습니다" | "~다고 내다봤습니다" | "~라고 언급했습니다" | "~고 보도했습니다"
  "~다고 전망했습니다" | "~라고 짚었습니다" | "~고 설명했습니다" | "~다고 판단했습니다"

### quote_subtitle (화면 그래픽용 — 문어체 요약)
- 채널명 미포함, 핵심만 30자 이내, 문어체
- 나쁜 예: "한국경제TV에서는 현대차가 코스피 6700 돌파를 주도했다고 했습니다."
- 좋은 예: "코스피 6700 돌파 주도, 단기 과열 리스크 병존"

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
                "다음 브리핑 데이터를 바탕으로 15분 분량의 KBS 머니올라 방송 스크립트를 작성해주세요.\n"
                "반드시 각 섹션의 목표 글자 수를 채워야 합니다. 분량이 부족하면 배경 설명, 시장 맥락, "
                "투자자 유의사항 등을 추가하여 목표치를 맞춰주세요.\n"
                "유튜브 출연진 멘트를 반드시 포함시켜 주세요.\n\n"
                + (f"## 실시간 시장 지표 (market_summary JSON 필드에 그대로 사용하세요)\n"
                   f"{json.dumps(market_data, ensure_ascii=False, indent=2)}\n\n"
                   if market_data else "")
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
    print(f"  합계: {total_chars:,}자  (목표: 3,750자 이상)")
    if total_chars < 3750:
        print(f"  ⚠️  분량 부족! {3750 - total_chars:,}자 미달")
    else:
        print(f"  ✅ 분량 목표 달성")

    return data


# ─────────────────────────────────────────────────────────────────────────────

def run(lang: str = "KO"):
    lang = lang.upper()
    briefing_text = fetch_briefing()
    if not briefing_text:
        print("❌ 브리핑 텍스트를 가져오지 못했습니다. 종료합니다.")
        sys.exit(1)

    print(f"✅ 브리핑 텍스트 수신 완료 ({len(briefing_text):,}자)")

    # briefing_data.json에서 market_data 직접 로드 (해외 지수/환율 포함)
    market_data = None
    try:
        import urllib.request
        url = "https://kunil-choi.github.io/stock-briefing-v3/data/briefing_data.json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw_json = json.loads(resp.read().decode("utf-8"))
        md = raw_json.get("market_data", {})

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

    script = generate_script(briefing_text, market_data)

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

