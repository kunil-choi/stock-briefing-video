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

OPENING_NARRATION = (
    f"안녕하세요. 오늘도 주식 시장에 오신 것을 환영합니다. "
    f"{TODAY_MONTH}월 {TODAY_DAY}일 에이아이 증권 브리핑을 시작하겠습니다. "
    f"이번 브리핑에는 시장 전체 흐름부터 개별 종목 분석까지 담았습니다. "
    f"기업별 최신 이슈와 투자 포인트를 짚어보며 빠르게 시장을 파악해 드리겠습니다. "
    f"에이아이 기반의 분석이니만큼 참고 자료로 활용하시고, 투자 결정은 신중하게 내리시기 바랍니다."
)

OPENING_SUBTITLE = (
    f"안녕하세요. 오늘도 주식 시장에 오신 것을 환영합니다. "
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
            page = browser.new_page()
            page.goto(
                "https://kunil-choi.github.io/stock-briefing-v2/",
                wait_until="networkidle",
                timeout=30000
            )
            text = page.inner_text("body")
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

두 필드는 소리 내어 읽으면 동일하게 들리지만, 글자 표기 방식이 다릅니다.

[narration — TTS 낭독용, 귀로 듣는 텍스트]
- 숫자를 반드시 한글로 풀어씁니다.
  · 6,700 → 육천칠백  /  133만 → 백삼십삼만  /  12조2400억 → 십이조 이천사백억
  · 85,400원 → 팔만오천사백원  /  +1.2% → 플러스 일점이퍼센트
  · 숫자를 절대 아라비아 숫자로 남기지 않습니다.
- 영문 약어를 한글 발음으로 읽습니다.
  · SK → 에스케이  /  LG → 엘지  /  KB → 케이비  /  ETF → 이티에프
  · AI → 에이아이  /  HBM → 에이치비엠  /  ESS → 이에스에스
  · KOSPI → 코스피  /  KOSDAQ → 코스닥  (이 두 개는 발음 그대로)
- 구어체로 자연스럽게 작성합니다. (~입니다, ~했습니다 등)

[subtitle — 화면 자막용, 눈으로 보는 텍스트]
- 숫자는 아라비아 숫자 원형 그대로 유지합니다.
  · 6,700  /  133만원  /  12조 2,400억  /  +1.2%
- 영문 약어는 원래 표기 그대로 유지합니다.
  · SK하이닉스  /  LG전자  /  KB금융  /  ETF  /  AI  /  HBM
- 구어체 조사나 표현을 문어체로 바꿉니다.
  · narration: "에스케이하이닉스의 현재 주가는 백삼십삼만원으로..."
  · subtitle:  "SK하이닉스의 현재 주가는 133만원으로..."

## 종목 섹션 구성 (필수)
- AI 브리핑의 관심 종목(stock_)과 히든 종목(hidden_) 모두를 브리핑 원문에 등장하는 순서 그대로 처리합니다.
- 각 종목마다 아래 슬라이드 3종을 반드시 작성합니다:
  1) summary 슬라이드: 주가·시총·사업 소개·실적·투자포인트 중심
  2) chart 슬라이드: 최근 2주 주가 흐름·분기 실적·핵심 이슈 중심
  3) mention 슬라이드(들): 채널별 언급 내용 — 아래 별도 규칙 참고

## ★ mention(채널별 언급) 슬라이드 규칙 (필수)

AI 브리핑의 "채널별 언급 내용" 항목을 그대로 사용합니다.

[슬라이드 분할 규칙]
- 언급 1~3개: mention 슬라이드 1장  (mention 배열에 최대 3개 항목)
- 언급 4~6개: mention 슬라이드 2장  (0번 슬라이드: 1~3번째, 1번 슬라이드: 4~6번째)
- 언급 7~9개: mention 슬라이드 3장  (0번: 1~3, 1번: 4~6, 2번: 7~9)
- 각 슬라이드에는 정확히 최대 3개의 언급 항목이 들어갑니다.

[mention 항목 구조]
각 언급 항목을 아래 형식으로 작성합니다:
{{
  "speaker": "발화자 이름 (확인된 경우만, 불명확하면 빈 문자열)",
  "channel": "채널명 또는 매체명",
  "quote_narration": "낭독용 텍스트 — 숫자 한글, 영문 한글 발음",
  "quote_subtitle": "자막용 텍스트 — 숫자·영문 원형 유지"
}}

[발화자 표시 규칙]
- AI 브리핑 원문에 이름이 명시된 경우만 speaker 필드에 기입합니다.
  예: "현대차증권 노근창 센터장" → speaker: "노근창 센터장", channel: "현대차증권"
- 원문에 발화자가 없고 채널명만 있는 경우 → speaker: "", channel: "채널명"

[mention narration 작성 규칙]
- narration_mention (1장짜리, 또는 0번 슬라이드): 해당 슬라이드에 담긴 1~3개 언급 내용 전체를 자연스럽게 이어 읽는 문장
- narration_mention_0, narration_mention_1 ... : 각 슬라이드 페이지에 담긴 내용만 포함
- 각 슬라이드의 narration은 그 슬라이드에 표시되는 언급 내용과 1:1로 대응합니다.

## 기타 섹션 규칙
- market_summary: narration/subtitle 각각 작성. kospi_value는 화면 표시용 숫자 그대로("6,700")
- sectors: narration/subtitle 각각
- ai_strategy: narration/subtitle 각각
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
      "narration": "[TTS용 — 지수 육천칠백, 등락 한글]",
      "subtitle": "[자막용 — 지수 6,700, 등락 원형]",
      "kospi_value": "6,700",
      "kospi_change": "+1.2%",
      "kospi_change_positive": true,
      "points": ["포인트1", "포인트2"]
    }},
    {{
      "id": "sectors",
      "label": "업종 분석",
      "narration": "[TTS용]",
      "subtitle": "[자막용]",
      "sector_list": [{{"name": "섹터명", "desc": "설명"}}]
    }},
    {{
      "id": "stock_종목명",
      "label": "종목 분석 - 종목명",
      "narration": "[narration_summary와 동일]",
      "subtitle": "[subtitle_summary와 동일]",
      "narration_summary": "[TTS용 — 숫자 한글, 영문 한글 발음]",
      "subtitle_summary": "[자막용 — 숫자·영문 원형]",
      "narration_chart": "[TTS용]",
      "subtitle_chart": "[자막용]",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "summary": "한줄 요약",
      "catalysts": ["촉매1", "촉매2"],
      "risks": ["리스크1", "리스크2"],
      "mentions": [
        {{
          "speaker": "발화자명 (확인된 경우만, 없으면 빈 문자열)",
          "channel": "채널명",
          "quote_narration": "[TTS용 언급 내용]",
          "quote_subtitle": "[자막용 언급 내용]"
        }}
      ],
      "narration_mention": "[언급 1~3개짜리 단일 슬라이드 전체 narration]",
      "subtitle_mention": "[위 narration의 subtitle 버전]",
      "narration_mention_0": "[4개 이상일 때 0번 슬라이드 narration — 1~3번째 언급]",
      "subtitle_mention_0": "[위 narration의 subtitle 버전]",
      "narration_mention_1": "[1번 슬라이드 narration — 4~6번째 언급]",
      "subtitle_mention_1": "[위 narration의 subtitle 버전]"
    }},
    {{
      "id": "ai_strategy",
      "label": "AI 투자 전략",
      "narration": "[TTS용]",
      "subtitle": "[자막용]",
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
