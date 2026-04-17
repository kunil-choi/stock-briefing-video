name: 📝 Generate Broadcast Script

on:
  # 매일 오전 8시 자동 실행 (KST)
  schedule:
    - cron: "0 23 * * 0-4"
  # 수동 실행도 가능
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: 📥 코드 체크아웃
        uses: actions/checkout@v4

      - name: 🐍 Python 설치
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: 📦 패키지 설치
        run: |
          pip install openai playwright
          playwright install chromium

      - name: 📝 원고 생성
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python pipeline/generate_script.py

      - name: 💾 결과물 저장
        uses: actions/upload-artifact@v4
        with:
          name: generated-script-${{ github.run_number }}
          path: output/KO/scripts/
          retention-days: 30
