import os
import json
from datetime import datetime
from openai import OpenAI
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────
# 브리핑 페이지 데이터 수집
# ─────────────────────────────────────────────

def fetch_briefing():
    print("📡 브리핑 페이지 수집 중...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(
            "https://kunil-choi.github.io/stock-briefing-v2/",
            wait_until="networkidle"
        )
        content = page.inner_text("body")
        browser.close()
    print("✅ 브리핑 데이터 수집 완료")
    return content

# ─────────────────────────────────────────────
# GPT-4o로 방송 원고 생성
# ─────────────────────────────────────────────

def generate_script(briefing_text: str) -> dict:
    print("📝 방송 원고 생성 중...")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    today = datetime.now().strftime("%Y년 %m월 %d일")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": f"""
당신은 10년 경력의 경제 전문 방송 작가입니다.
오늘 날짜는 {today}입니다.

아래 브리핑 데이터를 실제 방송에서 바로 사용할 수 있는
완벽한 수준의 내레이션 원고로 변환해주세요.

=== 원고 작성 규칙 ===

[공통]
- 시청자에게 직접 말하는 자연스러운 구어체
- 각 섹션 전환 시 자연스러운 브릿지 멘트 포함
- 숫자는 반드시 한글로 읽기 쉽게 변환
  예) 6,226 → 육천이백이십육
  예) 3.08% → 3.08퍼센트
  예) 217,500원 → 이십일만 칠천오백원
- 전문 용어는 쉽게 풀어서 설명
- 각 섹션 내레이션은 최소 150자 이상 작성

[오프닝]
- 시청자 인사 및 오늘 브리핑 핵심 키워드 3개 예고
- 기대감을 높이는 톤으로 작성

[시장 요약]
- 코스피/코스닥 지수 흐름 상세 설명
- 외국인/기관/개인 수급 동향
- 글로벌 시장 동향 연계
- 오늘 시장의 핵심 키워드 강조

[주목 섹터]
- 각 섹터별 왜 주목해야 하는지 이유 설명
- 섹터 간 연관성 설명

[관심 종목 - 종목별 개별 섹션]
- 브리핑에 나온 모든 관심 종목을
  반드시 각각 별도 섹션으로 생성
- 각 종목 섹션에 반드시 포함할 내용:
  1) 기업 소개 (어떤 회사인지)
  2) 오늘 주가 흐름 (등락률, 특징)
  3) 상승 촉매 (왜 오르고 있는지)
  4) 리스크 (조심해야 할 점)
  5) 전문가/채널 언급 내용 요약

[히든 종목 - 종목별 개별 섹션]
- 관심 종목과 동일한 구성으로 작성
- 각 히든 종목도 반드시 별도 섹션으로 생성

[AI 투자 전략]
- 오늘 브리핑 내용 기반의 구체적 전략
- bullet_points에 핵심 전략 5~6개
  각 전략은 종목명 + 구체적 행동 + 조건 포함
  예) "SK하이닉스 — 신고가 경신 후
      5% 조정 시 분할 매수 권장"

[클로징]
- 오늘 핵심 내용 1줄 요약
- 투자 유의사항 멘트
- 다음 방송 예고 톤으로 마무리

=== 출력 JSON 형식 ===
{{
  "title": "오늘 브리핑 제목 (날짜 포함)",
  "date": "{today}",
  "sections": [
    {{
      "id": "opening",
      "label": "오프닝",
      "narration": "내레이션 텍스트"
    }},
    {{
      "id": "market_summary",
      "label": "시장 요약",
      "narration": "내레이션 텍스트"
    }},
    {{
      "id": "sectors",
      "label": "주목 섹터",
      "narration": "내레이션 텍스트"
    }},
    {{
      "id": "stock_{{종목명}}",
      "label": "관심종목 - {{종목명}}",
      "narration": "종목별 상세 내레이션"
    }},
    {{
      "id": "hidden_{{종목명}}",
      "label": "히든종목 - {{종목명}}",
      "narration": "종목별 상세 내레이션"
    }},
    {{
      "id": "ai_strategy",
      "label": "AI 투자 전략",
      "narration": "전략 내레이션",
      "bullet_points": [
        "종목명 — 구체적 전략 및 조건",
        "종목명 — 구체적 전략 및 조건",
        "종목명 — 구체적 전략 및 조건",
        "종목명 — 구체적 전략 및 조건",
        "종목명 — 구체적 전략 및 조건",
        "종목명 — 구체적 전략 및 조건"
      ]
    }},
    {{
      "id": "closing",
      "label": "클로징",
      "narration": "내레이션 텍스트"
    }}
  ]
}}

※ 절대 종목을 생략하거나 합치지 말 것
※ 브리핑 원문에 나온 모든 종목은
   반드시 개별 섹션으로 생성할 것
※ 내레이션은 실제 방송에서 바로
   읽을 수 있는 수준으로 작성할 것
"""
            },
            {
                "role": "user",
                "content": f"다음 브리핑 데이터를 완벽한 방송 원고로 작성해주세요:\n\n{briefing_text}"
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=8000
    )

    script = json.loads(response.choices[0].message.content)
    print("✅ 방송 원고 생성 완료")
    return script

# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────

def main():
    # 브리핑 데이터 수집
    briefing_text = fetch_briefing()

    # 원고 생성
    script = generate_script(briefing_text)

    # 저장
    os.makedirs("output/KO/scripts", exist_ok=True)
    out_path = "output/KO/scripts/script.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    # 섹션 목록 출력
    print(f"\n💾 원고 저장 완료 → {out_path}")
    print(f"📌 제목: {script['title']}")
    print(f"📋 총 섹션 수: {len(script['sections'])}개\n")
    print("=== 섹션 목록 ===")
    for s in script["sections"]:
        narration_len = len(s["narration"])
        print(f"  {s['label']} ({narration_len}자)")

if __name__ == "__main__":
    main()
