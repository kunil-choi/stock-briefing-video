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
TODAY = datetime.now().strftime("%Y년 %m월 %d일")
TODAY_MONTH = datetime.now().strftime("%-m")
TODAY_DAY   = datetime.now().strftime("%-d")

STOCK_NAME_LIST = "\n".join(f"- {name}" for name in STOCK_CODES.keys())

OPENING_NARRATION = (
    f"안녕하세요. 머니올라 구독자 여러분. "
    f"{TODAY_MONTH}월 {TODAY_DAY}일 AI 주식 브리핑 시작하겠습니다. "
    f"이 브리핑은 최근 이십사 시간 이내의 경제 뉴스와 경제방송사 유튜브 채널 콘텐츠, "
    f"구독자수 기준 상위권 경제 유튜브 채널, 그리고 증권사 애널리스트 보고서를 분석해 "
    f"공통적으로 언급된 국내 투자 종목에 대한 주요 정보를 요약해 알려드리는 자료입니다. "
    f"AI 기반으로 자동 생성되며, 시장 흐름 요약과 관심 종목별 주까 흐름과 "
    f"상승 촉매 리스트 등을 분석합니다. "
    f"최종적으로는 오늘의 투자 전략도 소개해드립니다."
)

CLOSING_NARRATION = (
    "오늘 브리핑은 여기까지입니다. "
    "도움이 되셨다면 구독과 좋아요 부탁드립니다. "
    "본 브리핑은 AI가 자동 생성한 참고 자료이며, 투자 권유가 아닙니다. "
    "최종 투자 판단과 그 책임은 투자자 본인에게 있습니다. "
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

## 발음 규칙 (TTS용)
- 숫자는 한글로: 6226 → 육천이백이십육, 3% → 삼퍼센트
- 주가 관련: 주가→주까, 신고가→신고까, 고가→고까, 저가→저까
- 영어는 한글 발음: KOSPI→코스피, HBM→에이치비엠, ETF→이티에프
- 자연스럽고 명확한 구어체, 불필요한 간투어 없이

## narration 작성 규칙
각 섹션의 narration은 아나운서가 실제로 읽을 방송 멘트 전체를 작성합니다.
각 코너 시작 시 반드시 아래 코너 도입 멘트를 narration 맨 앞에 포함하세요.

- market_summary 코너 도입: "오늘의 주식시장 요약입니다."
- sectors 코너 도입: "오늘의 주목할 섹터입니다."
- 첫 번째 stock_ 코너 도입: "관심종목 브리핑 시작합니다. 첫 번째 종목은 [종목명]입니다."
- 두 번째 이후 stock_ 코너: "다음은 [종목명]입니다."
- 첫 번째 hidden_ 코너 도입: "채널 언급은 한 번이었지만 주목할 종목을 소개해드립니다. [종목명]입니다."
- 두 번째 이후 hidden_ 코너: "다음 주목 종목은 [종목명]입니다."
- ai_strategy 코너 도입: "마지막으로 AI가 제안하는 오늘의 투자전략입니다."

## stock_/hidden_ 섹션 narration 구성 (순서 준수)
1. 코너 도입 멘트
2. 종목 한 줄 소개 (summary)
3. 현재 주까와 등락률 언급
4. 상승 촉매 항목들을 자연스럽게 이어서 읽기
5. 리스크 항목들 언급
6. mentions에 있는 채널/증권사 언급 내용을 구체적으로 읽기
   예시: "한국경제 기사에 따르면 미래에셋 김정진 이사가 삼성전자 SK하이닉스 투자비중 오십퍼센트까지 늘려도 된다며 추가매수를 권고했고, 수익률 상위 일퍼센트 고수들의 순매수 일위도 삼성전자였습니다."
   → mentions의 source, reporter/analyst, quote/report 내용을 이런 방식으로 자연스럽게 문장으로 읽어줄 것

## 출력 JSON 구조
{{
  "title": "{TODAY} AI 주식 브리핑",
  "date": "{TODAY}",
  "sections": [
    {{
      "id": "opening",
      "label": "오프닝",
      "narration": "__OPENING__",
      "keywords": ["키워드1", "키워드2", "키워드3"]
    }},
    {{
      "id": "market_summary",
      "label": "시장 요약",
      "narration": "오늘의 주식시장 요약입니다. [시장 분석 내용]",
      "kospi_value": "2,650",
      "kospi_change": "+1.2%",
      "kospi_change_positive": true,
      "points": ["포인트1", "포인트2", "포인트3", "포인트4"]
    }},
    {{
      "id": "sectors",
      "label": "주목 섹터",
      "narration": "오늘의 주목할 섹터입니다. [섹터 분석 내용]",
      "sector_list": [
        {{"name": "섹터명", "desc": "설명", "icon": "이모지"}}
      ]
    }},
    {{
      "id": "stock_종목명",
      "label": "관심종목 - 종목명",
      "narration": "관심종목 브리핑 시작합니다. 첫 번째 종목은 [종목명]입니다. [전체 브리핑 멘트]",
      "summary": "기업 한 줄 소개",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "catalysts": ["촉매1", "촉매2", "촉매3", "촉매4"],
      "risks": ["리스크1", "리스크2", "리스크3"],
      "mentions": [
        {{"source": "채널명", "reporter": "기자/애널리스트명", "quote": "언급 내용"}}
      ]
    }},
    {{
      "id": "hidden_종목명",
      "label": "히든종목 - 종목명",
      "narration": "채널 언급은 한 번이었지만 주목할 종목을 소개해드립니다. [종목명]입니다. [전체 브리핑 멘트]",
      "summary": "기업 한 줄 소개",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "catalysts": ["촉매1", "촉매2"],
      "risks": ["리스크1", "리스크2"],
      "mentions": [
        {{"source": "채널명", "analyst": "애널리스트명", "report": "보고서 핵심"}}
      ]
    }},
    {{
      "id": "ai_strategy",
      "label": "AI 투자 전략",
      "narration": "마지막으로 AI가 제안하는 오늘의 투자전략입니다. [전략 내용]",
      "bullet_points": [
        "종목명 — 전략 내용"
      ]
    }},
    {{
      "id": "closing",
      "label": "클로징",
      "narration": "__CLOSING__",
      "disclaimer": "본 브리핑은 AI가 생성한 참고 자료이며 투자 권유가 아닙니다.\\n투자의 최종 판단과 책임은 본인에게 있습니다."
    }}
  ]
}}

## 주의사항
- opening narration은 반드시 "__OPENING__" 그대로 출력 (후처리로 교체됨)
- closing narration은 반드시 "__CLOSING__" 그대로 출력 (후처리로 교체됨)
- stock_ 섹션은 브리핑의 관심종목 수만큼 생성
- hidden_ 섹션은 히든종목 수만큼 생성
- mentions 내용은 구체적인 문장으로 narration에 녹여서 작성
- 반드시 순수 JSON만 출력, 마크다운 블록 없이
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"다음 브리핑 데이터를 분석하여 JSON 원고를 생성하세요:\n\n{briefing_text}"}
        ],
        temperature=0.7,
        max_tokens=8000
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    script = json.loads(raw)

    # 오프닝/클로징 narration 고정 텍스트로 교체
    for sec in script.get("sections", []):
        if sec.get("id") == "opening":
            sec["narration"] = OPENING_NARRATION
        elif sec.get("id") == "closing":
            sec["narration"] = CLOSING_NARRATION

    # 종목명 정규화
    for sec in script.get("sections", []):
        sec_id = sec.get("id", "")
        for prefix in ("stock_", "hidden_"):
            if sec_id.startswith(prefix):
                raw_name = sec_id[len(prefix):]
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

    script = generate_script(briefing_text)

    out_dir = "output/KO/scripts"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "script.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    sections = script.get("sections", [])
    print(f"\n✅ 원고 생성 완료!")
    print(f"   파일: {out_path}")
    print(f"   제목: {script.get('title', '')}")
    print(f"   섹션 수: {len(sections)}")
    for s in sections:
        narr = s.get("narration", "")
        print(f"   - [{s['id']}] {len(narr)}자")


if __name__ == "__main__":
    main()
