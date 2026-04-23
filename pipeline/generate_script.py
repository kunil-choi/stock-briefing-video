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
    f"이 브리핑은 뉴스와 유튜브 채널, 증권사 보고서를 분석한 "
    f"AI 기반의 자동 생성 자료이며, 종목별 주까 전망과 "
    f"오늘의 투자 전략을 소개해드립니다."
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

## ★★★ TTS 발음 규칙 (절대 준수 — 위반 시 영상이 깨집니다) ★★★

narration 필드의 모든 텍스트는 TTS(음성합성) 엔진이 읽을 발음 그대로 작성합니다.

### 숫자 → 반드시 한글로
- 65,400원 → 육만오천사백원
- 3,200원 → 삼천이백원
- 1,250,000원 → 백이십오만원
- 2,650 (지수) → 이천육백오십

### 퍼센트 → 반드시 한글로
- +3.3% → 플러스 삼쩜삼퍼센트
- -1.5% → 마이너스 일쩜오퍼센트
- +0.8% → 플러스 영쩜팔퍼센트
- 2% → 이퍼센트

### 소수점 → "쩜" 으로 (점 금지)
- 3.3 → 삼쩜삼 (3.3이라고 쓰지 말 것)
- 1.5 → 일쩜오

### 주가 관련 단어 → 반드시 발음대로
- 주가 → 주까
- 신고가 → 신고까
- 고가 → 고까
- 저가 → 저까

### 영어/약어 → 한글 발음
- KOSPI → 코스피
- KOSDAQ → 코스닥
- HBM → 에이치비엠
- ETF → 이티에프
- AI → 에이아이
- SK → 에스케이
- LG → 엘지
- KB → 케이비
- HD → 에이치디

### 잘못된 예시 vs 올바른 예시
❌ 틀림: "주가는 65,400원으로 +3.3% 상승했습니다."
✅ 맞음: "주까는 육만오천사백원으로 플러스 삼쩜삼퍼센트 상승했습니다."

❌ 틀림: "KOSPI가 2,650포인트를 기록했습니다."
✅ 맞음: "코스피가 이천육백오십포인트를 기록했습니다."

## 화면별 narration 분리 규칙 (핵심 — 반드시 준수)
stock_/hidden_ 섹션은 화면이 3개로 분리됩니다.
각 화면에 맞는 narration을 반드시 별도 필드로 작성하세요.

narration_summary (종목 소개 화면):
- 코너 도입 멘트 + 종목 한 줄 소개 + 현재 주까와 등락률
- 예: "다음은 삼성전자입니다. 삼성전자는 글로벌 반도체 및 전자기기 제조 기업입니다. 현재 주까는 육만오천사백원으로 전일 대비 플러스 일쩜이퍼센트 상승했습니다."

narration_chart (최근 2주 차트 화면):
- 최근 주까 흐름 + 상승 촉매 + 리스크
- 예: "최근 이주간 주까 흐름을 보겠습니다. 육만이천원에서 육만오천원까지 상승했습니다. 주요 상승 촉매로는 에이치비엠 수주 확대와 파운드리 회복 기대감이 있으며, 리스크로는 미중 무역 갈등 재점화 가능성이 있습니다."

narration_mention (전문가 멘션 화면):
- mentions의 채널/기사/애널리스트 언급 내용만
- 예: "한국경제 기사에 따르면 미래에셋 김정진 이사가 삼성전자 에스케이하이닉스 투자비중 오십퍼센트까지 늘려도 된다며 추가매수를 권고했습니다."

## 일반 섹션 narration 규칙
- market_summary 도입: "오늘의 주식시장 요약입니다."
- sectors 도입: "오늘의 주목할 섹터입니다."
- ai_strategy 도입: "마지막으로 에이아이가 제안하는 오늘의 투자전략입니다."

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
      "narration": "오늘의 주식시장 요약입니다. [시장 분석 내용 — 숫자 한글 발음으로]",
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
      "narration": "[narration_summary 내용과 동일]",
      "narration_summary": "코너 도입 + 종목 소개 + 현재 주까와 등락률 (숫자 한글)",
      "narration_chart": "최근 이주간 주까 흐름 + 상승 촉매 + 리스크 (숫자 한글)",
      "narration_mention": "전문가/채널/기사 언급 내용 (숫자 한글)",
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
      "narration": "[narration_summary 내용과 동일]",
      "narration_summary": "코너 도입 + 종목 소개 + 현재 주까와 등락률 (숫자 한글)",
      "narration_chart": "최근 이주간 주까 흐름 + 상승 촉매 + 리스크 (숫자 한글)",
      "narration_mention": "전문가/채널/기사 언급 내용 (숫자 한글)",
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
      "narration": "마지막으로 에이아이가 제안하는 오늘의 투자전략입니다. [전략 내용 — 숫자 한글]",
      "bullet_points": ["종목명 — 전략 내용"]
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
- opening narration은 반드시 "__OPENING__" 그대로 출력
- closing narration은 반드시 "__CLOSING__" 그대로 출력
- stock_/hidden_ 섹션은 narration_summary, narration_chart, narration_mention 세 필드를 반드시 모두 작성
- narration 필드는 narration_summary 와 동일하게 작성
- 반드시 순수 JSON만 출력, 마크다운 블록 없이
- ★ narration의 모든 숫자와 퍼센트는 반드시 한글 발음으로 작성 ★
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"다음 브리핑 데이터를 분석하여 JSON 원고를 생성하세요:\n\n{briefing_text}"}
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

    # 오프닝/클로징 고정 텍스트 교체
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
