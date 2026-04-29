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
    f"{TODAY_MONTH}월 {TODAY_DAY}일 AI 증권 브리핑을 시작하겠습니다. "
    f"이번 브리핑에는 시장 전체 흐름부터 개별 종목 분석까지 담았습니다. "
    f"기업별 최신 이슈와 투자 포인트를 짚어보며 빠르게 시장을 파악해 드리겠습니다. "
    f"AI 기반의 분석이니만큼 참고 자료로 활용하시고, 투자 결정은 신중하게 내리시기 바랍니다."
)

OPENING_SUBTITLE = OPENING_NARRATION

CLOSING_NARRATION = (
    "이상으로 브리핑을 마치겠습니다. "
    "내일도 좋은 하루 되시고 성공적인 투자 되시기 바랍니다. "
    "더욱 브리핑은 AI를 통해 매일 제작되고 있습니다, 투자 결정은 직접 판단하시고, 투자의 책임은 본인에게 있음을 유의하시기 바랍니다. "
    "구독과 좋아요는 큰 힘이 됩니다. "
    "감사합니다."
)

CLOSING_SUBTITLE = CLOSING_NARRATION


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

## 종목 목록 섹션 구성 (필수 작성 항목)
종목에 대한 JSON의 id 형태를 아래 목록에서 선택하여 없는 종목의 경우에도 이름을 기반으로 유추하여 매핑해야 합니다.
[사용 가능한 종목 목록]
{STOCK_NAME_LIST}
위 목록에 없는 종목은 해당 섹션에 종목 목록에 없는 종목임을 명시하고 가능하면 유사 종목으로 대체합니다.

## narration 작성 지침 — TTS 낭독 최적화 (필수 작성 항목)
narration 작성은 TTS(문자 음성 변환) 낭독에 최적화되게 작성해야 합니다. 주로 쓰이는 단위를 아래와 같이 작성합니다.
- 주가/지수 낭독 기준 (가장 중요): 숫자를 반드시 한글로 풀어 씁니다.
  - 6,700 → 육천칠백, 6,700포인트 → 육천칠백 포인트, 6,700선 → 육천칠백 선
  - 85,400원 → 팔만오천사백원, 75,300원 → 칠만오천삼백원
  - 숫자를 절대 "6,700" 같은 숫자 형태로 narration에 남기지 않습니다. 반드시 한글 읽기로 변환합니다.
- 시가총액의 낭독 기준: 65,400억 → 육만오천사백억원, 12조 → 십이조원
- 퍼센트 낭독 기준: 3% → 삼퍼센트, 2.5% → 이점오퍼센트, +1.2% → 플러스 일점이퍼센트
- 거래소 구분 낭독 형태: 코스피→코스피, 코스닥→코스닥, ETF→이티에프, SK→에스케이, LG→엘지
- kospi_value 필드에 들어가는 값은 화면 표시용이므로 숫자 그대로 "6,700" 형식을 유지합니다.
  단, narration 텍스트 안에서 지수를 언급할 때는 반드시 "육천칠백"처럼 한글로 씁니다.

## subtitle 작성 지침 — 내레이션과 동일한 내용 (필수 작성 항목)
subtitle은 narration과 완전히 동일한 내용을 그대로 복사하여 작성합니다.
- subtitle_summary = narration_summary 와 동일한 내용
- subtitle_chart = narration_chart 와 동일한 내용
- subtitle_mention = narration_mention 와 동일한 내용
- subtitle_mention_0 = narration_mention_0 와 동일한 내용
- subtitle_mention_1 = narration_mention_1 와 동일한 내용
- subtitle (섹션 공통) = narration 와 동일한 내용
- 별도로 요약하거나 다르게 작성하지 않습니다. 내레이션 원문 그대로입니다.

## 주식 브리핑 섹션 구성 지침 (필수 작성 항목)
- 주식 브리핑 섹션은 주식시장 전체 흐름에 관심이 있는 시청자들의 관심을 끌만한 내용으로 최대 20대 섹션으로 구성하여 충분히 길게 브리핑을 제작해야 합니다. stock_ 섹션과 hidden_ 섹션 모두 포함합니다.
- 각각의 섹션은 구성 내용으로 브리핑을 적절히 나눠서 서로 다른 섹션이 서로 다른 내용을 다루도록 구성하여 충분히 길게 브리핑 내용이 나뉘도록 작성해야 합니다.
- 기본적인 기대 브리핑 20대에 달하는 것 외에도 추가적으로 보완이 필요하다 싶은 내용은 섹션을 추가하여 적절히 작성해야 합니다.

## 기술적 분석 섹션 구성 지침 (필수 작성 항목)
- 주식 브리핑 섹션은 주식시장 전체 흐름에 관심이 있는 시청자들의 관심을 끌만한 내용으로 최대 20대 섹션으로 구성합니다.
- 섹션을 구성함에 있어서 브리핑 데이터에서 종목에 관련 내용을 충분히 다루도록 하여 충분히 길게 최대한 섹션을 많이 다루도록 작성해야 합니다.

## 언급 횟수 분배 지침 (필수 — TTS 및 자막 공통)
- mentions 키워드에 대한 언급 횟수를 아래 기준에 따라 분배하여 동일한 종목을 여러번 언급하는 형식의 스크립트를 구성해야 합니다.
  - 언급 횟수 1~3회 → 1슬라이드
  - 언급 횟수 4~6회 → 2슬라이드 (1슬라이드: 0~2회, 2슬라이드: 3~5회)
  - 언급 횟수 7~9회 → 3슬라이드 (1슬라이드: 0~2회, 2슬라이드: 3~5회, 3슬라이드: 6~8회)
- narration/subtitle 각각의 언급 횟수에 맞게 전체 슬라이드에서 분배하여 배치해야 합니다. 슬라이드 간격 기준 없이 자연스럽게 분배합니다.
- 언급 횟수 1~3회(1슬라이드): narration_mention / subtitle_mention 섹션에 1회씩 단독으로 언급.
- 언급 횟수 4회 이상(2슬라이드): narration_mention_0/1, subtitle_mention_0/1 각 1번씩 두 섹션에 분배하여 작성합니다.

## 종목별 narration/subtitle 섹션 구성 지침 (필수 — 필수 작성 항목)
stock_/hidden_ 섹션에는 종목별로 3회에 걸쳐서 섹션을 나눠야 합니다.
각 종목별로 1개인 narration_XXX (TTS용)과 subtitle_XXX (자막용, narration_XXX와 동일 내용)을 짝으로 작성해야 합니다.

narration_summary / subtitle_summary (종목 소개 슬라이드):
- 주가 정보 요약 내용 + 종목 소개 내용 + 실적/매출 정보 + 투자 결정에 중요한 매출 성장률 + 시가총액, 시장 5단계로 나눈 내용 + 수익률 설명

narration_chart / subtitle_chart (최근 2주 주가 슬라이드):
- 최근 2주 실적 정보 요약 내용 + 실적/분기 매출 정보 + 분기/연간 성장 + 최근 이슈/트렌드 + 핵심 사업과 시장 성장률

narration_mention / subtitle_mention (공통 언급 횟수 — 언급 횟수 3회 이하):
- 1번째 언급 횟수 기본 정보, 시장 3단계로 나눈 내용 정도

narration_mention_0 / subtitle_mention_0, narration_mention_1 / subtitle_mention_1 (언급 횟수 4회 이상):
- 각 언급 횟수에 맞는 정보, 시가 기준 잠재 정보

## 기타 섹션 narration/subtitle 구성
- market_summary: narration + subtitle 각각 작성 (필수, 짧게 작성, 시장 전반적인 내용, 짧게 나눠서)
- sectors: narration + subtitle 각각 작성
- ai_strategy: narration + subtitle 각각 작성
- opening/closing: 특정 고정 상수를 사용하며 "__OPENING__" / "__CLOSING__" 문자열로 대체

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
      "narration": "오늘 코스피는 육천칠백 포인트를 돌파하며 [TTS용 — 지수, 등락 모두 한글로]",
      "subtitle": "오늘 코스피는 육천칠백 포인트를 돌파하며 [narration과 동일]",
      "kospi_value": "6,700",
      "kospi_change": "+1.2%",
      "kospi_change_positive": true,
      "points": ["포인트1", "포인트2", "포인트3", "포인트4"]
    }},
    {{
      "id": "sectors",
      "label": "업종 분석",
      "narration": "오늘의 업종 분석을 알아보겠습니다. [TTS용]",
      "subtitle": "오늘의 업종 분석을 알아보겠습니다. [narration과 동일]",
      "sector_list": [
        {{"name": "섹터이름", "desc": "설명", "icon": "이모지"}}
      ]
    }},
    {{
      "id": "stock_종목명",
      "label": "종목 분석 - 종목명",
      "narration": "[narration_summary와 동일]",
      "subtitle": "[narration과 동일]",
      "narration_summary": "[TTS용 — 주가/시총 모두 한글 읽기로 변환]",
      "subtitle_summary": "[narration_summary와 완전히 동일한 내용]",
      "narration_chart": "[TTS용 — 주가/시총 모두 한글 읽기로 변환]",
      "subtitle_chart": "[narration_chart와 완전히 동일한 내용]",
      "narration_mention": "[TTS용]",
      "subtitle_mention": "[narration_mention와 완전히 동일한 내용]",
      "narration_mention_0": "[TTS용]",
      "subtitle_mention_0": "[narration_mention_0와 완전히 동일한 내용]",
      "narration_mention_1": "[TTS용]",
      "subtitle_mention_1": "[narration_mention_1와 완전히 동일한 내용]",
      "summary": "한줄 핵심 요약",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "catalysts": ["촉매1", "촉매2", "촉매3", "촉매4"],
      "risks": ["리스크1", "리스크2", "리스크3"]
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

    raw = response.choices[0].message.content
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

    script = generate_script(briefing_text)

    root       = os.path.join(_HERE, "..")
    out_dir    = os.path.join(root, "output", lang, "scripts")
    os.makedirs(out_dir, exist_ok=True)
    out_path   = os.path.join(out_dir, "script.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    sections = script.get("sections", [])
    print(f"\n✅ 스크립트 생성 완료! 섹션 수: {len(sections)}개 → {out_path}")
    return script


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
