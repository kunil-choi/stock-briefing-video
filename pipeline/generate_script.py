# pipeline/generate_script.py
# 변경 1: OPENING_NARRATION — "안녕하세요..." 첫 문장 삭제
# 변경 2: OPENING_SUBTITLE  — 동일하게 첫 문장 삭제
# 변경 3: mention quote_subtitle → 문어체 요약 문장으로 작성 규칙 추가
# 변경 4: mention narration 종결어미 다양화 규칙 추가

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

# ── 변경 1·2: 오프닝 첫 문장 "안녕하세요..." 삭제 ─────────────────────────
OPENING_NARRATION = (
    f"{TODAY_MONTH}월 {TODAY_DAY}일 에이아이 증권 브리핑을 시작하겠습니다. "
    f"이번 브리핑에는 시장 전체 흐름부터 개별 종목 분석까지 담았습니다. "
    f"기업별 최신 이슈와 투자 포인트를 짚어보며 빠르게 시장을 파악해 드리겠습니다. "
    f"에이아이 기반의 분석이니만큼 참고 자료로 활용하시고, 투자 결정은 신중하게 내리시기 바랍니다."
)

OPENING_SUBTITLE = (
    f"{TODAY_MONTH}월 {TODAY_DAY}일 AI 증권 브리핑을 시작하겠습니다. "
    f"이번 브리핑에는 시장 전체 흐름부터 개별 종목 분석까지 담았습니다. "
    f"기업별 최신 이슈와 투자 포인트를 짚어보며 빠르게 시장을 파악해 드리겠습니다. "
    f"AI 기반의 분석이니만큼 참고 자료로 활용하시고, 투자 결정은 신중하게 내리시기 바랍니다."
)

CLOSING_NARRATION = (
    "이상으로 브리핑을 마치겠습니다. "
    "내일도 좋은 하루 되시고 성공적인 투자 되시기 바랍니다. "
    "브리핑은 에이아이를 통해 매일 제작되고 있습니다. 투자 결정은 직접 판단하시고, 투자의 책임은 본인에게 있음을 유의하시기 바랍니다. "
    "구독과 좋아요는 큰 힘이 됩니다. "
    "감사합니다."
)

CLOSING_SUBTITLE = (
    "이상으로 브리핑을 마치겠습니다. "
    "내일도 좋은 하루 되시고 성공적인 투자 되시기 바랍니다. "
    "브리핑은 AI를 통해 매일 제작되고 있습니다. 투자 결정은 직접 판단하시고, 투자의 책임은 본인에게 있음을 유의하시기 바랍니다. "
    "구독과 좋아요는 큰 힘이 됩니다. "
    "감사합니다."
)


def fetch_briefing():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(
                "https://kunil-choi.github.io/stock-briefing-v2/",
                wait_until="networkidle",
                timeout=30000
            )
            text = page.inner_text("body")

            img_dir = os.path.join(_HERE, "..", "output", "KO", "images")
            os.makedirs(img_dir, exist_ok=True)

            stock_sections = page.query_selector_all("section.stock-item, div.stock-card, article")
            if not stock_sections:
                chart_links = page.query_selector_all("a:has-text('차트보기')")
                for link in chart_links:
                    try:
                        parent = link.evaluate_handle("el => el.closest('section') || el.closest('div.stock') || el.parentElement.parentElement")
                        heading = parent.query_selector("h3, h4, strong")
                        if not heading:
                            continue
                        stock_name = heading.inner_text().strip().split("\n")[0]
                        normalized = normalize_stock_name(stock_name)
                        save_path  = os.path.join(img_dir, f"briefing_chart_{normalized}.png")
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


def generate_script(briefing_text):
    system_prompt = f"""
너는 주식 방송 스크립트 작성 전문가입니다. 증권 브리핑 데이터를 바탕으로 오늘의 주식 방송 스크립트를 JSON 형태로 작성해야 합니다.
작성일: {TODAY}

## 종목 목록 매핑 (필수)
종목 id는 아래 목록 기준으로 매핑합니다. 목록에 없는 종목은 유사 종목으로 대체하고 명시합니다.
[사용 가능한 종목 목록]
{STOCK_NAME_LIST}

## ★ narration vs subtitle 핵심 차이 (반드시 준수)

[narration — TTS 낭독용]
- 숫자를 반드시 한글로 풀어씁니다.
  · 6,700 → 육천칠백  /  133만 → 백삼십삼만  /  12조2400억 → 십이조 이천사백억
  · 85,400원 → 팔만오천사백원  /  +1.2% → 플러스 일점이퍼센트
- 영문 약어를 한글 발음으로 읽습니다.
  · SK → 에스케이  /  LG → 엘지  /  KB → 케이비  /  ETF → 이티에프
  · AI → 에이아이  /  HBM → 에이치비엠  /  ESS → 이에스에스
  · KOSPI → 코스피  /  KOSDAQ → 코스닥
- ★ 한국어 경음화 발음 교정 규칙:
  · 신고가 → 신고까  /  목표가 → 목표까  /  배당금 → 배당끔
  · 실적 → 실쩍  /  적자 → 적짜  /  격차 → 격짜  /  약세 → 약쎄
  · 특징 → 특찡  /  국채 → 국째  /  역대 → 역때
  · 유가 → 유까  /  고유가 → 고유까  /  저유가 → 저유까
- 구어체로 자연스럽게 작성합니다.

[subtitle — 화면 자막용 (ASS burn-in 방식)]
- 숫자는 아라비아 숫자 원형 그대로.
- 영문 약어는 원래 표기 그대로.
- "유가"는 자막에서 "유가" 그대로 유지.

## ★ mention 항목의 narration / subtitle / quote_narration / quote_subtitle 규칙

### quote_narration (TTS 낭독용 — 구어체)
- 채널명을 먼저 호명하고 내용을 구어체로 낭독.
- 발화자가 있으면: "[채널명]의 [발화자]는, [내용]"
- 발화자가 없으면: "[채널명]에서는, [내용]"
- ★ 종결어미를 매 항목마다 다양하게 사용 (같은 어미 2회 연속 금지):
  · 가능한 종결어미 목록: "~라고 전했습니다", "~고 분석했습니다", "~다고 밝혔습니다",
    "~라고 진단했습니다", "~고 강조했습니다", "~다고 내다봤습니다",
    "~라고 언급했습니다", "~고 보도했습니다", "~다고 전망했습니다",
    "~라고 짚었습니다", "~고 설명했습니다", "~다고 판단했습니다"
  · 한 종목의 mention 슬라이드 내에서 동일한 어미가 절대 반복되지 않도록.

### quote_subtitle (화면 그래픽용 — ★ 문어체 요약 문장)
- ★ 반드시 문어체 요약 형식으로 작성. 구어체 낭독문이 아님.
- 채널명을 본문에 포함하지 않음 (채널명은 header로 별도 표시됨).
- 핵심 내용을 짧고 명확하게 요약 (1~2문장, 30자 이내 권장).
- 예시:
  · (나쁜 예) "서울경제에서는, 구글 딥마인드 CEO가 현대차를 방문하여 AI 생태계 협력 기대를 높였다고 전했습니다."
  · (좋은 예) "구글 딥마인드 CEO 방문, AI 생태계 협력 기대 상승"
  · (나쁜 예) "한국경제TV에서는, 현대차의 파죽지세를 언급하며 장중 코스피 6700 돌파를 주도했다고 평가했습니다."
  · (좋은 예) "코스피 6700 돌파 주도, 단기 과열·차익실현 리스크 병존"
  · (나쁜 예) "815머니톡에서는, 구글과 엔비디아가 현대차를 선택한 이유를 집중 분석하며 긍정적으로 평가했습니다."
  · (좋은 예) "구글·엔비디아 선택 이유 분석, 로봇·AI 빅호재로 주가 급등 전망"

### narration_mention / narration_mention_0 / narration_mention_1 (섹션 narration 필드)
- 해당 페이지의 모든 quote_narration을 자연스럽게 이어 작성.
- 코너 오프닝 문장 포함 (첫 페이지: "각 채널에서 언급한 내용을 보겠습니다.", 이후: "이어서 추가 언급 내용입니다.").

### subtitle_mention / subtitle_mention_0 / subtitle_mention_1 (섹션 subtitle 필드)
- 해당 페이지의 quote_subtitle들을 줄바꿈 없이 이어 쓴 자막 텍스트.
- 화면 자막이므로 간결하게.

## ★ 코너 오프닝 멘트 규칙 (필수)
각 섹션의 narration 첫 문장에는 반드시 해당 코너를 소개하는 오프닝 멘트를 포함합니다.

- market_summary: "먼저 오늘의 주식시장 요약입니다."로 시작
- sectors: "오늘 주목할 업종을 살펴보겠습니다."로 시작
- stock_XXX (첫 번째 종목의 summary): "지금부터 관심 종목 분석입니다."로 시작
  이후 종목들의 summary: "다음은 [종목명] 분석입니다."로 시작
- hidden_XXX (첫 번째 히든 종목의 summary): "이번에는 숨은 종목을 소개해 드립니다."로 시작
  이후 히든 종목들의 summary: "다음 숨은 종목은 [종목명]입니다."로 시작
- chart 슬라이드: "최근 이주간 주가 차트를 보면,"으로 시작
- mention 슬라이드 (첫 번째): "각 채널에서 언급한 내용을 보겠습니다."로 시작
  이후 mention 슬라이드: "이어서 추가 언급 내용입니다."로 시작
- ai_strategy: "에이아이가 제안하는 오늘의 투자 전략입니다."로 시작

## 종목 섹션 구성 (필수)
- 관심 종목(stock_)과 히든 종목(hidden_) 모두를 브리핑 원문 등장 순서 그대로 처리.
- 각 종목마다 summary / chart / mention 슬라이드 3종 필수 작성.

## mention 슬라이드 분할 규칙 (필수)
- 언급 1~3개: 단일 슬라이드
- 언급 4~6개: 2슬라이드 (_0/_1)
- 언급 7~9개: 3슬라이드 (_0/_1/_2)
- 각 슬라이드 최대 3개 언급.

## mention 항목 구조
{{
  "speaker": "발화자 이름 (확인된 경우만, 불명확하면 빈 문자열)",
  "channel": "채널명 또는 매체명",
  "quote_narration": "낭독용 구어체 (채널명 포함, 경음화 적용, 다양한 종결어미)",
  "quote_subtitle": "★ 문어체 요약 (채널명 미포함, 핵심만 30자 이내)"
}}

## 기타 섹션 규칙
- market_summary: kospi_value는 화면 표시용 숫자 그대로("6,700")
- opening/closing: "__OPENING__" / "__OPENING_SUBTITLE__" / "__CLOSING__" / "__CLOSING_SUBTITLE__" 플레이스홀더 사용

## 최종 JSON 구조
{{
  "title": "{TODAY} AI 증권 브리핑",
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
      "narration": "먼저 오늘의 주식시장 요약입니다. ...",
      "subtitle": "먼저 오늘의 주식시장 요약입니다. ...",
      "kospi_value": "6,700",
      "kospi_change": "+1.2%",
      "kospi_change_positive": true,
      "points": ["포인트1", "포인트2"]
    }},
    {{
      "id": "sectors",
      "label": "업종 분석",
      "narration": "오늘 주목할 업종을 살펴보겠습니다. ...",
      "subtitle": "오늘 주목할 업종을 살펴보겠습니다. ...",
      "sector_list": [{{"name": "섹터명", "desc": "설명"}}]
    }},
    {{
      "id": "stock_종목명",
      "label": "종목 분석 - 종목명",
      "narration": "...",
      "subtitle": "...",
      "narration_summary": "지금부터 관심 종목 분석입니다. ...",
      "subtitle_summary": "지금부터 관심 종목 분석입니다. ...",
      "narration_chart": "최근 이주간 주가 차트를 보면, ...",
      "subtitle_chart": "최근 2주간 주가 차트를 보면, ...",
      "narration_mention": "각 채널에서 언급한 내용을 보겠습니다. [채널명]에서는, ... [채널명2]의 [발화자]는, ...",
      "subtitle_mention": "...",
      "narration_mention_0": "각 채널에서 언급한 내용을 보겠습니다. ...",
      "subtitle_mention_0": "...",
      "narration_mention_1": "이어서 추가 언급 내용입니다. ...",
      "subtitle_mention_1": "...",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "summary": "한줄 요약",
      "catalysts": ["촉매1", "촉매2"],
      "risks": ["리스크1", "리스크2"],
      "mentions": [
        {{
          "speaker": "발화자명 (확인된 경우만)",
          "channel": "채널명",
          "quote_narration": "[채널명]에서는, [내용] ~라고 전했습니다.",
          "quote_subtitle": "핵심 내용 요약 문어체 (30자 이내)"
        }}
      ]
    }},
    {{
      "id": "ai_strategy",
      "label": "AI 투자 전략",
      "narration": "에이아이가 제안하는 오늘의 투자 전략입니다. ...",
      "subtitle": "AI가 제안하는 오늘의 투자 전략입니다. ...",
      "bullet_points": ["전략1", "전략2"]
    }},
    {{
      "id": "closing",
      "label": "클로징",
      "narration": "__CLOSING__",
      "subtitle": "__CLOSING_SUBTITLE__",
      "disclaimer": "본 영상은 AI를 통해 제작되었으며, 투자 결정은 직접 판단하시기 바랍니다."
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"다음 브리핑 데이터를 바탕으로 스크립트를 작성해주세요:\n\n{briefing_text}"}
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

    return _replace(data)


def run(lang: str = "KO"):
    lang = lang.upper()
    briefing_text = fetch_briefing()
    if not briefing_text:
        print("❌ 브리핑 텍스트를 가져오지 못했습니다. 종료합니다.")
        sys.exit(1)

    print(f"✅ 브리핑 텍스트 수신 완료 ({len(briefing_text):,}자)")

    script  = generate_script(briefing_text)

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
