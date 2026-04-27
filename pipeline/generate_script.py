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

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

TODAY       = datetime.now().strftime("%Y년 %m월 %d일")
TODAY_MONTH = datetime.now().strftime("%-m")
TODAY_DAY   = datetime.now().strftime("%-d")

STOCK_NAME_LIST = "\n".join(f"- {name}" for name in STOCK_CODES.keys())

OPENING_NARRATION = (
    f"안녕하세요. 머니올라 구독자 여러분. "
    f"{TODAY_MONTH}월 {TODAY_DAY}일 AI 주식 브리핑 시작하겠습니다. "
    f"이 브리핑은 최근 이십사 시간 이내의 경제 뉴스와 인기 경제 유튜브 채널, "
    f"그리고 증권사 애널리스트 보고서를 분석한 자료입니다. "
    f"AI 기반으로 자동 생성되며, 종목별 투자 전략을 소개해드립니다."
)

OPENING_SUBTITLE = (
    f"안녕하세요. 머니올라 구독자 여러분. "
    f"{TODAY_MONTH}월 {TODAY_DAY}일 AI 주식 브리핑 시작하겠습니다. "
    f"이 브리핑은 최근 24시간 이내의 경제 뉴스와 인기 경제 유튜브 채널, "
    f"그리고 증권사 애널리스트 보고서를 분석한 자료입니다. "
    f"AI 기반으로 자동 생성되며, 종목별 투자 전략을 소개해드립니다."
)

CLOSING_NARRATION = (
    "오늘 브리핑은 여기까지입니다. "
    "도움이 되셨다면 구독과 좋아요 부탁드립니다. "
    "본 브리핑은 AI가 자동 생성한 참고 자료이며, 투자 권유가 아닙니다. "
    "최종 투자 판단과 그 책임은 투자자 본인에게 있습니다. "
    "감사합니다."
)

CLOSING_SUBTITLE = CLOSING_NARRATION  # 클로징은 한글 숫자 없으므로 동일


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
        print(f"⚠️ 브리핑 페이지 로딩 실패: {e}")
        return ""


def generate_script(briefing_text):
    system_prompt = f"""
당신은 경제 방송 작가입니다. 주식 브리핑 데이터를 분석하여 방송용 내레이션 원고와 화면 구성 데이터를 JSON으로 생성하세요.
오늘 날짜: {TODAY}

## 종목명 표기 규칙 (반드시 준수)
종목명을 JSON의 id 필드에 사용할 때는 아래 목록의 정확한 표기를 그대로 사용하세요.
[허용 종목명 목록]
{STOCK_NAME_LIST}
위 목록에 없는 종목이 등장하면 가장 유사한 목록의 종목명을 사용하세요.

## narration 필드 — TTS 발음 규칙 (반드시 준수)
narration 필드는 TTS(음성 합성)용입니다. 사람이 소리 내어 읽는 것처럼 작성하세요.
- 숫자는 반드시 한글로: 65,400원 → 육만오천사백원, 3% → 삼퍼센트, 2.5% → 이점오퍼센트
- 주가 관련 발음: 주가→주까, 신고가→신고까, 고가→고까, 저가→저까
- 영어는 한글 발음: KOSPI→코스피, HBM→에이치비엠, ETF→이티에프, SK→에스케이, LG→엘지
- 자연스럽고 명확한 구어체로 작성

## subtitle 필드 — 자막 표기 규칙 (반드시 준수)
subtitle 필드는 화면에 표시되는 자막용입니다. 시청자가 읽기 편하게 작성하세요.
- 숫자는 반드시 아라비아 숫자로: 육만오천사백원 → 65,400원, 삼퍼센트 → 3%
- 영어 약어는 그대로: KOSPI, HBM, ETF, SK, LG, KB, NH
- 상승/하락 부호 사용: 플러스 → +, 마이너스 → -
- 주가 관련 표기: 주까 → 주가, 신고까 → 신고가, 고까 → 고가, 저까 → 저가
- narration과 동일한 내용이지만 표기 방식만 다르게 작성
- 문장 내용과 순서는 narration과 완전히 동일하게 유지

## 브리핑 데이터 활용 원칙 (핵심)
- 브리핑 데이터에 등장하는 모든 종목을 빠짐없이 설명하세요. stock_ 섹션과 hidden_ 섹션 모두 포함합니다.
- 각 종목의 내레이션은 브리핑 원본의 내용을 최대한 충실하게, 충분히 길게 작성하세요.
- 전체 영상이 20분 이내가 되도록 충분히 상세하게 작성하세요.

## 기자·전문가 이름 표기 규칙 (반드시 준수)
- 브리핑 원문에 기자명 또는 애널리스트명이 명확하게 기재된 경우에만 이름을 사용하세요.
- 이름이 확실하지 않거나 원문에 없는 경우, 이름을 절대 임의로 만들지 말고 매체명(source)만 사용하세요.
- 올바른 예: "한국경제에 따르면, [내용]을 보도했습니다."
- 금지 예: "한국경제 홍길동 기자에 따르면..." (원문에 이름이 없는 경우)

## 히든픽 순번 규칙 (반드시 준수)
- hidden_ 섹션이 여러 개인 경우, 각 섹션의 narration_summary 도입부에 반드시 순번을 명시하세요.
- 첫 번째 hidden_ 섹션 → narration_summary: "오늘의 히든픽 첫 번째는..."
- 두 번째 hidden_ 섹션 → narration_summary: "오늘의 히든픽 두 번째는..."
- 세 번째 hidden_ 섹션 → narration_summary: "오늘의 히든픽 세 번째는..."
- subtitle_summary도 동일하게: "오늘의 히든픽 첫 번째는..."
- hidden_ 섹션이 1개뿐인 경우 → "오늘의 히든픽은..."

## 전문가 멘션 페이지별 분리 규칙 (핵심 — 반드시 준수)
- mentions 배열의 멘션 수에 따라 화면 페이지가 자동으로 나뉩니다.
  - 멘션 1~3개 → 1페이지
  - 멘션 4~6개 → 2페이지 (1페이지: 0~2번, 2페이지: 3~5번)
  - 멘션 7~9개 → 3페이지 (1페이지: 0~2번, 2페이지: 3~5번, 3페이지: 6~8번)
- narration/subtitle 모두 해당 페이지에 표시되는 멘션만 읽어야 합니다. 페이지 간 내용 중복 절대 금지.
- 멘션 1~3개(1페이지): narration_mention / subtitle_mention 필드 1개씩만 작성.
- 멘션 4개 이상(2페이지 이상): narration_mention_0/1, subtitle_mention_0/1 등 페이지별로 분리 작성.

## 화면별 narration/subtitle 분리 규칙 (핵심 — 반드시 준수)
stock_/hidden_ 섹션은 화면이 3개 이상으로 분리됩니다.
각 화면마다 narration_XXX (TTS용)과 subtitle_XXX (자막용)을 쌍으로 작성하세요.

narration_summary / subtitle_summary (종목 소개 화면):
- 코너 도입 멘트 + 종목 상세 소개 + 현재 주가와 등락률 + 투자 포인트 전체 설명
- 분량: 최소 5문장 이상

narration_chart / subtitle_chart (최근 2주 차트 화면):
- 최근 주가 흐름 상세 설명 + 주요 변곡점 + 상승/하락 원인 분석 + 리스크 요인 전체 설명
- 분량: 최소 5문장 이상

narration_mention / subtitle_mention (전문가 멘션 — 멘션 3개 이하):
- 해당 페이지 멘션 전체 상세 읽기, 최소 3문장 이상

narration_mention_0 / subtitle_mention_0, narration_mention_1 / subtitle_mention_1 (멘션 4개 이상):
- 각 페이지의 멘션만 읽기, 절대 중복 없이

## 일반 섹션 narration/subtitle 규칙
- market_summary: narration + subtitle 모두 작성 (동일 내용, 표기만 다름)
- sectors: narration + subtitle 모두 작성
- ai_strategy: narration + subtitle 모두 작성
- opening/closing: 별도 고정값으로 교체되므로 "__OPENING__" / "__CLOSING__" 그대로 출력

## 출력 JSON 구조
{{
  "title": "{TODAY} AI 주식 브리핑",
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
      "narration": "오늘의 주식시장 요약입니다. [TTS용 — 숫자 한글, 영어 한글 발음]",
      "subtitle": "오늘의 주식시장 요약입니다. [자막용 — 아라비아 숫자, 영어 약어]",
      "kospi_value": "2,650",
      "kospi_change": "+1.2%",
      "kospi_change_positive": true,
      "points": ["포인트1", "포인트2", "포인트3", "포인트4"]
    }},
    {{
      "id": "sectors",
      "label": "주목 섹터",
      "narration": "오늘의 주목할 섹터입니다. [TTS용]",
      "subtitle": "오늘의 주목할 섹터입니다. [자막용]",
      "sector_list": [
        {{"name": "섹터명", "desc": "설명", "icon": "이모지"}}
      ]
    }},
    {{
      "id": "stock_종목명",
      "label": "관심종목 - 종목명",
      "narration": "[narration_summary와 동일]",
      "subtitle": "[subtitle_summary와 동일]",
      "narration_summary": "[TTS용 — 코너 도입 + 종목 소개 + 주까와 등락률 + 투자포인트, 최소 5문장]",
      "subtitle_summary": "[자막용 — narration_summary와 동일 내용, 아라비아 숫자·영어 약어 사용]",
      "narration_chart": "[TTS용 — 최근 2주 주까 흐름 + 변곡점 + 촉매 + 리스크, 최소 5문장]",
      "subtitle_chart": "[자막용 — narration_chart와 동일 내용, 아라비아 숫자·영어 약어 사용]",
      "narration_mention": "[TTS용 — 멘션 3개 이하일 때만]",
      "subtitle_mention": "[자막용 — 멘션 3개 이하일 때만]",
      "narration_mention_0": "[TTS용 — 멘션 4개 이상일 때 1페이지]",
      "subtitle_mention_0": "[자막용 — 멘션 4개 이상일 때 1페이지]",
      "narration_mention_1": "[TTS용 — 멘션 4개 이상일 때 2페이지]",
      "subtitle_mention_1": "[자막용 — 멘션 4개 이상일 때 2페이지]",
      "summary": "기업 한 줄 소개",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "catalysts": ["촉매1", "촉매2", "촉매3", "촉매4"],
      "risks": ["리스크1", "리스크2", "리스크3"],
      "mentions": [
        {{"source": "매체명", "reporter": "확인된 이름만 (불확실하면 빈 문자열 \"\")", "quote": "언급 내용 상세"}}
      ]
    }},
    {{
      "id": "hidden_종목명",
      "label": "히든종목 - 종목명",
      "narration": "[narration_summary와 동일]",
      "subtitle": "[subtitle_summary와 동일]",
      "narration_summary": "[TTS용 — 히든픽 순번 + 종목 소개 + 주까와 등락률 + 투자포인트, 최소 5문장]",
      "subtitle_summary": "[자막용 — narration_summary와 동일 내용, 아라비아 숫자·영어 약어 사용]",
      "narration_chart": "[TTS용 — 최근 2주 주까 흐름 + 촉매 + 리스크, 최소 5문장]",
      "subtitle_chart": "[자막용 — narration_chart와 동일 내용, 아라비아 숫자·영어 약어 사용]",
      "narration_mention": "[TTS용 — 멘션 3개 이하일 때만]",
      "subtitle_mention": "[자막용 — 멘션 3개 이하일 때만]",
      "narration_mention_0": "[TTS용 — 멘션 4개 이상일 때 1페이지]",
      "subtitle_mention_0": "[자막용 — 멘션 4개 이상일 때 1페이지]",
      "narration_mention_1": "[TTS용 — 멘션 4개 이상일 때 2페이지]",
      "subtitle_mention_1": "[자막용 — 멘션 4개 이상일 때 2페이지]",
      "summary": "기업 한 줄 소개",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "catalysts": ["촉매1", "촉매2"],
      "risks": ["리스크1", "리스크2"],
      "mentions": [
        {{"source": "매체명", "analyst": "확인된 이름만 (불확실하면 빈 문자열 \"\")", "report": "보고서 핵심 상세"}}
      ]
    }},
    {{
      "id": "ai_strategy",
      "label": "AI 투자 전략",
      "narration": "[TTS용 — 마지막으로 AI가 제안하는 오늘의 투자전략입니다. + 종목별 전략]",
      "subtitle": "[자막용 — 동일 내용, 아라비아 숫자·영어 약어 사용]",
      "bullet_points": ["종목명 — 전략 내용"]
    }},
    {{
      "id": "closing",
      "label": "클로징",
      "narration": "__CLOSING__",
      "subtitle": "__CLOSING_SUBTITLE__",
      "disclaimer": "본 브리핑은 AI가 생성한 참고 자료이며 투자 권유가 아닙니다.\\n투자의 최종 판단과 책임은 본인에게 있습니다."
    }}
  ]
}}

## 주의사항
- opening narration은 반드시 "__OPENING__" 그대로 출력 (subtitle은 "__OPENING_SUBTITLE__")
- closing narration은 반드시 "__CLOSING__" 그대로 출력 (subtitle은 "__CLOSING_SUBTITLE__")
- stock_/hidden_ 섹션은 narration_summary, subtitle_summary, narration_chart, subtitle_chart, narration_mention(또는 _0/_1), subtitle_mention(또는 _0/_1) 반드시 작성
- narration 필드는 narration_summary와 동일하게, subtitle 필드는 subtitle_summary와 동일하게 작성
- 브리핑에 등장하는 모든 종목 반드시 포함
- 반드시 순수 JSON만 출력, 마크다운 블록 없이
- max_tokens 한도 내에서 최대한 상세하게 작성
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"다음 브리핑 데이터를 분석하여 JSON 원고를 생성하세요:\n\n{briefing_text}"}
        ],
        temperature=0.7,
        max_tokens=16000
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    script = json.loads(raw)

    # 오프닝/클로징 고정 텍스트 교체
    for sec in script.get("sections", []):
        if sec.get("id") == "opening":
            sec["narration"] = OPENING_NARRATION
            sec["subtitle"]  = OPENING_SUBTITLE
        elif sec.get("id") == "closing":
            sec["narration"] = CLOSING_NARRATION
            sec["subtitle"]  = CLOSING_SUBTITLE

    # 종목명 정규화
    for sec in script.get("sections", []):
        sec_id = sec.get("id", "")
        for prefix in ("stock_", "hidden_"):
            if sec_id.startswith(prefix):
                raw_name   = sec_id[len(prefix):]
                normalized = normalize_stock_name(raw_name)
                if raw_name != normalized:
                    print(f"  [정규화] {sec_id} → {prefix}{normalized}")
                    sec["id"] = f"{prefix}{normalized}"
                break

    return script


def main():
    print(f"📋 브리핑 원고 생성 시작 — {TODAY}")
    briefing_text = fetch_briefing()
    if not briefing_text:
        print("❌ 브리핑 데이터 없음")
        return
    print(f"✅ 브리핑 로딩 완료 ({len(briefing_text)}자)")

    script  = generate_script(briefing_text)
    out_dir = "output/KO/scripts"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "script.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    sections = script.get("sections", [])
    print(f"\n✅ 원고 생성 완료!")
    print(f"  파일: {out_path}")
    print(f"  제목: {script.get('title', '')}")
    print(f"  섹션 수: {len(sections)}")
    for s in sections:
        narr = s.get("narration", "")
        print(f"  - [{s['id']}] {len(narr)}자")


if __name__ == "__main__":
    main()
