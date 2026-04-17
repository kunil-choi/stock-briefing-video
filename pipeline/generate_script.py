import os
import json
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

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """
당신은 경제 유튜브 채널의 전문 방송 작가입니다.
주식 브리핑 데이터를 받아 자연스럽고 신뢰감 있는
방송용 내레이션 원고로 변환합니다.

원고 작성 규칙:
1. 시청자에게 직접 말하는 구어체 사용
2. 각 섹션은 명확한 전환 멘트로 구분
3. 숫자는 읽기 쉽게 변환
   예) 6091 → 육천구십일 포인트
4. 섹션 구조 유지

반드시 아래 JSON 형식으로 출력:
{
  "title": "오늘의 브리핑 제목",
  "date": "날짜",
  "sections": [
    {
      "id": "opening",
      "label": "오프닝",
      "narration": "내레이션 텍스트"
    },
    {
      "id": "market_summary",
      "label": "시장 요약",
      "narration": "내레이션 텍스트"
    },
    {
      "id": "sectors",
      "label": "주목 섹터",
      "narration": "내레이션 텍스트"
    },
    {
      "id": "stocks",
      "label": "관심 종목",
      "narration": "내레이션 텍스트"
    },
    {
      "id": "hidden_stocks",
      "label": "히든 종목",
      "narration": "내레이션 텍스트"
    },
    {
      "id": "ai_strategy",
      "label": "AI 투자 전략",
      "narration": "내레이션 텍스트"
    },
    {
      "id": "closing",
      "label": "클로징",
      "narration": "내레이션 텍스트"
    }
  ]
}
"""
            },
            {
                "role": "user",
                "content": f"다음 브리핑 데이터를 방송 원고로 작성해주세요:\n\n{briefing_text}"
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.7
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

    print(f"💾 원고 저장 완료 → {out_path}")
    print(f"📋 섹션 수: {len(script['sections'])}개")
    print(f"📌 제목: {script['title']}")

if __name__ == "__main__":
    main()
