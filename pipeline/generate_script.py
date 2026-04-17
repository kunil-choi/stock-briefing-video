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
# 언어별 발음 규칙
# ─────────────────────────────────────────────

PRONUNCIATION_RULES = {
    "KO": """
=== 한국어 발음 규칙 (반드시 적용) ===

[경음화 규칙]
- 주가 → 주까 (주가는/주까는, 주가가/주까가, 주가를/주까를)
- 신고가 → 신고까
- 고가 → 고까
- 저가 → 저까
- 단가 → 단까
- 매도 → 매도 (그대로)
- 매수 → 매수 (그대로)
- 상장 → 상장 (그대로)

[숫자 읽기 규칙]
- 6,226 → 육천이백이십육
- 6,347 → 육천삼백사십칠
- 217,500원 → 이십일만 칠천오백원
- 1,155,000원 → 백십오만 오천원
- 3.08% → 3.08퍼센트
- 2.21% → 2.21퍼센트
- 25% → 이십오퍼센트
- 100% → 백퍼센트
- 1분기 → 일분기
- 2027년 → 이천이십칠년

[외래어 읽기 규칙]
- HBM → 에이치비엠
- AI → 에이아이
- ETF → 이티에프
- SMR → 에스엠알
- TSMC → 티에스엠씨
- PUBG → 펍지
- BTS → 비티에스
- IP → 아이피
- CEO → 씨이오

[띄어읽기 규칙]
- 문장 중간 쉼표(,) 앞뒤로 자연스러운 호흡 표시
- 숫자 뒤 단위는 붙여 읽기
  예) 육천이백이십육포인트 (X)
      육천이백이십육 포인트 (O)
""",

    "EN": """
=== English Pronunciation Rules (Must Apply) ===

[Korean Stock Market Terms in English]
- KOSPI → "KOS-pee" (not "KOS-pie")
- KOSDAQ → "KOS-dack"
- Samsung → "SAMS-ung"
- SK Hynix → "SK HIGH-nix"
- Hyundai → "HYUN-day" (not "HI-un-die")
- Kia → "KEE-ah"
- Chaebol → "CHAY-bol"

[Number Reading Rules]
- Always use natural English number phrasing
- 6,226 → "six thousand two hundred and twenty-six"
- 3.08% → "three point zero eight percent"
- $217,500 → "two hundred seventeen thousand five hundred dollars"
- Q1 → "first quarter"
- 2027 → "twenty twenty-seven"

[Financial Terms]
- ETF → spell out each letter "E-T-F"
- HBM → "H-B-M"
- AI → "A-I"
- IPO → "I-P-O"
- SMR → "S-M-R"
- TSMC → "T-S-M-C"

[Tone & Pacing]
- Use clear, confident broadcast English
- Pause naturally at commas and periods
- Stress key financial figures and stock names
""",

    "JA": """
=== 日本語発音規則（必ず適用）===

[韓国株式市場用語の日本語表記]
- KOSPI → コスピ
- Samsung → サムスン
- SK Hynix → SKハイニックス
- Hyundai → ヒョンデ
- HBM → エイチビーエム
- AI → エーアイ
- ETF → イーティーエフ
- SMR → エスエムアール
- TSMC → ティーエスエムシー
- PUBG → パブジー
- BTS → ビーティーエス

[数字の読み方]
- 6,226 → 六千二百二十六
- 3.08% → 3.08パーセント
- 217,500ウォン → 二十一万七千五百ウォン
- 1Q → 第一四半期
- 2027年 → 二千二十七年

[放送用語規則]
- 文末は「〜です」「〜ます」調で統一
- 専門用語は初出時に簡単な説明を追加
- 数字の後の単位は自然に読む
  例) 六千二百二十六ポイント

[ペースとイントネーション]
- ニュース放送のような明確な発音
- 読点（、）で自然な間を取る
- 重要な数字や銘柄名は明確に発音
"""
}

# ─────────────────────────────────────────────
# GPT-4o로 방송 원고 생성
# ─────────────────────────────────────────────

def generate_script(briefing_text: str, lang: str = "KO",
                    ko_script: dict = None) -> dict:
    print(f"📝 방송 원고 생성 중 ({lang})...")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    today = datetime.now().strftime("%Y년 %m월 %d일")
    pronunciation_rules = PRONUNCIATION_RULES[lang]

    if lang == "KO":
        system_prompt = f"""
당신은 10년 경력의 경제 전문 방송 작가입니다.
오늘 날짜는 {today}입니다.

아래 브리핑 데이터를 실제 방송에서 바로 사용할 수 있는
완벽한 수준의 내레이션 원고로 변환해주세요.

{pronunciation_rules}

=== 원고 작성 규칙 ===

[공통]
- 시청자에게 직접 말하는 자연스러운 구어체
- 각 섹션 전환 시 자연스러운 브릿지 멘트 포함
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
  2) 오늘 주까 흐름 (등락률, 특징)
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

[클로징]
- 오늘 핵심 내용 1줄 요약
- 투자 유의사항 멘트
- 다음 방송 예고 톤으로 마무리

=== 출력 JSON 형식 ===
{{
  "title": "오늘 브리핑 제목 (날짜 포함)",
  "date": "{today}",
  "lang": "KO",
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
※ 발음 규칙은 반드시 모든 내레이션에
   빠짐없이 적용할 것
"""
        user_content = f"다음 브리핑 데이터를 완벽한 방송 원고로 작성해주세요:\n\n{briefing_text}"

    elif lang == "EN":
        system_prompt = f"""
You are a professional financial broadcast writer with 10 years of experience.
Today's date is {today}.

Translate and localize the following Korean stock briefing script into
a perfect English broadcast narration.

{pronunciation_rules}

=== Script Writing Rules ===
- Natural, confident broadcast English
- All Korean company names properly localized
- All Korean financial terms explained in English context
- Each section narration minimum 150 characters
- All stock sections must be individual sections
- bullet_points must contain 5~6 specific strategies

Output in same JSON structure as input,
with "lang": "EN" and all narration in English.

※ Never skip or merge any stock sections
※ Apply all pronunciation rules throughout
"""
        user_content = f"Translate this Korean broadcast script to English:\n\n{json.dumps(ko_script, ensure_ascii=False, indent=2)}"

    else:  # JA
        system_prompt = f"""
あなたは10年のキャリアを持つ金融放送ライターです。
今日の日付は{today}です。

以下の韓国株式ブリーフィング原稿を
完璧な日本語放送ナレーション原稿に翻訳・現地化してください。

{pronunciation_rules}

=== 原稿作成規則 ===
- 自然で信頼感のある放送日本語
- 韓国企業名は適切に日本語表記
- 韓国固有の金融用語は日本語で説明
- 各セクションのナレーションは最低150文字以上
- すべての銘柄セクションは個別セクションで作成
- bullet_pointsは5〜6個の具体的な戦略を含める

入力と同じJSON構造で出力し、
"lang": "JA"とすべてのナレーションを日本語で記述。

※ 銘柄セクションを省略・統合しないこと
※ 発音規則をすべてのナレーションに適用すること
"""
        user_content = f"この韓国語放送原稿を日本語に翻訳してください:\n\n{json.dumps(ko_script, ensure_ascii=False, indent=2)}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content}
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=8000
    )

    script = json.loads(response.choices[0].message.content)
    print(f"✅ 방송 원고 생성 완료 ({lang})")
    return script

# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────

def main():
    lang = os.environ.get("SCRIPT_LANG", "KO")

    # 브리핑 데이터 수집 (KO만)
    briefing_text = fetch_briefing()

    # KO 원고 생성
    ko_script = generate_script(briefing_text, lang="KO")

    # KO 저장
    os.makedirs("output/KO/scripts", exist_ok=True)
    ko_path = "output/KO/scripts/script.json"
    with open(ko_path, "w", encoding="utf-8") as f:
        json.dump(ko_script, f, ensure_ascii=False, indent=2)

    print(f"\n💾 KO 원고 저장 완료 → {ko_path}")
    print(f"📌 제목: {ko_script['title']}")
    print(f"📋 총 섹션 수: {len(ko_script['sections'])}개\n")
    print("=== 섹션 목록 ===")
    for s in ko_script["sections"]:
        print(f"  {s['label']} ({len(s['narration'])}자)")

if __name__ == "__main__":
    main()
