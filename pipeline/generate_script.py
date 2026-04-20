import os
import json
from datetime import datetime
from openai import OpenAI
from playwright.sync_api import sync_playwright
from assets.config import STOCK_CODES, normalize_stock_name

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
TODAY = datetime.now().strftime("%Y년 %m월 %d일")

# STOCK_CODES 키 목록을 프롬프트에 주입
STOCK_NAME_LIST = "\n".join(f"- {name}" for name in STOCK_CODES.keys())


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
띄어쓰기, 대소문자, 특수문자 하나도 변경하지 마세요.

[허용 종목명 목록]
{STOCK_NAME_LIST}

위 목록에 없는 종목이 브리핑에 등장하면 가장 유사한 목록의 종목명을 사용하세요.

## 발음 규칙 (TTS용)
- 숫자는 한글로: 6226 → 육천이백이십육, 3% → 삼퍼센트
- 주가 관련: 주가→주까, 신고가→신고까, 고가→고까, 저가→저까
- 영어는 한글 발음: KOSPI→코스피, HBM→에이치비엠, ETF→이티에프
- 자연스러운 구어체 사용

## 출력 JSON 구조 (반드시 이 구조로)
{{
  "title": "날짜 주식 브리핑",
  "date": "{TODAY}",
  "sections": [
    {{
      "id": "opening",
      "label": "오프닝",
      "narration": "방송용 내레이션 텍스트",
      "keywords": ["핵심키워드1", "핵심키워드2", "핵심키워드3"]
    }},
    {{
      "id": "market_summary",
      "label": "시장 요약",
      "narration": "방송용 내레이션 텍스트",
      "kospi_value": "6,226",
      "kospi_change": "+2.21%",
      "kospi_change_positive": true,
      "points": [
        "33거래일 만에 6,200선 완전 회복",
        "외국인 순매수 전환",
        "AI 반도체·방산 섹터 주도",
        "전고점 6,347 돌파 여부 관건"
      ]
    }},
    {{
      "id": "sectors",
      "label": "주목 섹터",
      "narration": "방송용 내레이션 텍스트",
      "sector_list": [
        {{"name": "AI 반도체 & HBM", "desc": "TSMC 실적, 수요 폭발적 증가", "icon": "🤖"}},
        {{"name": "피지컬AI & 로보틱스", "desc": "현대차 보스턴다이내믹스 Atlas", "icon": "🦾"}},
        {{"name": "원자력 & 에너지", "desc": "SMR·대형 원전 수주 확대", "icon": "⚛️"}}
      ]
    }},
    {{
      "id": "stock_종목명",
      "label": "관심종목 - 종목명",
      "narration": "방송용 내레이션 텍스트",
      "summary": "기업 한 줄 소개 (30자 이내)",
      "price": "217,500",
      "change": "+3.08%",
      "change_positive": true,
      "catalysts": ["촉매1", "촉매2", "촉매3", "촉매4"],
      "risks": ["리스크1", "리스크2", "리스크3"],
      "mentions": [
        {{"source": "한국경제TV", "reporter": "김OO 기자", "quote": "실제 언급한 핵심 내용 50자 이내"}},
        {{"source": "미래에셋증권", "analyst": "박OO", "report": "보고서 제목 또는 핵심 문장"}}
      ]
    }},
    {{
      "id": "hidden_종목명",
      "label": "히든종목 - 종목명",
      "narration": "방송용 내레이션 텍스트",
      "summary": "기업 한 줄 소개 (30자 이내)",
      "price": "000,000",
      "change": "+0.00%",
      "change_positive": true,
      "catalysts": ["촉매1", "촉매2"],
      "risks": ["리스크1", "리스크2"],
      "mentions": [
        {{"source": "증권사명", "analyst": "애널리스트명", "report": "보고서 핵심 문장"}}
      ]
    }},
    {{
      "id": "ai_strategy",
      "label": "AI 투자 전략",
      "narration": "방송용 내레이션 텍스트",
      "bullet_points": [
        "종목명 — 구체적 전략 내용",
        "종목명 — 구체적 전략 내용",
        "종목명 — 구체적 전략 내용",
        "종목명 — 구체적 전략 내용",
        "종목명 — 구체적 전략 내용",
        "종목명 — 구체적 전략 내용"
      ]
    }},
    {{
      "id": "closing",
      "label": "클로징",
      "narration": "방송용 내레이션 텍스트",
      "disclaimer": "본 브리핑은 AI가 생성한 참고 자료이며 투자 권유가 아닙니다.\\n투자의 최종 판단과 책임은 본인에게 있습니다."
    }}
  ]
}}

## 주의사항
- stock_ 섹션은 브리핑의 관심종목 수만큼 생성 (id: stock_종목명)
- hidden_ 섹션은 히든종목 수만큼 생성 (id: hidden_종목명)
- 종목명은 반드시 위 [허용 종목명 목록]에서 정확히 그대로 가져올 것
- mentions는 브리핑에 언급된 채널/증권사 정보 기반으로 작성
- price와 change는 브리핑 데이터에서 추출
- catalysts와 risks는 각 4개씩 작성
- 반드시 순수 JSON만 출력, 마크다운 블록 없이
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"다음 브리핑 데이터를 분석하여 JSON 원고를 생성하세요:\n\n{briefing_text}"}
        ],
        temperature=0.7,
        max_tokens=6000
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    script = json.loads(raw)

    # GPT가 혹시라도 다르게 표기한 종목명을 후처리로 정규화
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
        narr = s.get('narration', '')
        print(f"   - [{s['id']}] {len(narr)}자")


if __name__ == "__main__":
    main()
