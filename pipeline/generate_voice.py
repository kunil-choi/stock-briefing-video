"""
pipeline/generate_voice.py
TTS 생성 모듈 — 목소리 설정은 pipeline/voice_config.py 에서 관리합니다.

목소리 변경 방법:
  1. pipeline/voice_config.py 열기
  2. DEFAULT_VOICE_PRESET 을 원하는 프리셋으로 변경 (matilda / rachel / charlie / daniel / custom)
  3. 또는 환경변수 ELEVENLABS_VOICE_ID 를 직접 설정
"""
import os
import json
import requests
import time
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from voice_config import get_voice_id, MODEL_ID, VOICE_SETTINGS, AUDIO_FORMAT, apply_phoneme_rules


def text_to_speech(text: str, output_path: str) -> bool:
    """텍스트를 TTS 오디오 파일로 변환합니다."""
    api_key  = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = get_voice_id()

    if not api_key:
        print("  ❌ ELEVENLABS_API_KEY 환경변수가 없습니다.")
        return False
    if not voice_id:
        print("  ❌ Voice ID가 설정되지 않았습니다. voice_config.py 를 확인하세요.")
        return False

    # 발음 교정 적용
    processed_text = apply_phoneme_rules(text)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept":       "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key":   api_key
    }
    payload = {
        "text":           processed_text,
        "model_id":       MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        return True
    else:
        print(f"  ❌ 실패: {response.status_code} - {response.text[:200]}")
        return False


def _build_jobs(sections: list, lang: str) -> list:
    """
    script.json 섹션을 순회하여 TTS 작업 목록을 생성합니다.

    mention 슬라이드 분할 규칙:
    - mentions 1~3개: narration_mention (단일)
    - mentions 4~6개: narration_mention_0, narration_mention_1
    - mentions 7~9개: narration_mention_0, narration_mention_1, narration_mention_2
    """
    jobs = []
    audio_base = f"output/{lang}/audio"

    for section in sections:
        sid   = section.get("id", "")
        label = section.get("label", sid)
        if not sid:
            continue

        is_stock = sid.startswith("stock_") or sid.startswith("hidden_")

        if is_stock:
            # ── summary 슬라이드 ─────────────────────────────────────────
            text = section.get("narration_summary", section.get("narration", ""))
            if text:
                jobs.append((text, f"{audio_base}/{sid}_summary.mp3", f"{label} [summary]"))

            # ── chart 슬라이드 ───────────────────────────────────────────
            text = section.get("narration_chart", section.get("narration", ""))
            if text:
                jobs.append((text, f"{audio_base}/{sid}_chart.mp3", f"{label} [chart]"))

            # ── mention 슬라이드 ─────────────────────────────────────────
            mentions  = section.get("mentions", [])
            n_mentions = len(mentions)

            if n_mentions > 0:
                pages = max(1, (n_mentions + 2) // 3)
                if pages == 1:
                    text = section.get("narration_mention", "")
                    if not text:
                        text = " ".join(
                            m.get("quote_narration", m.get("quote", ""))
                            for m in mentions[:3]
                        )
                    if text:
                        jobs.append((text, f"{audio_base}/{sid}_mention.mp3", f"{label} [mention]"))
                else:
                    for p in range(pages):
                        field = f"narration_mention_{p}"
                        text  = section.get(field, "")
                        if not text:
                            page_items = mentions[p * 3: p * 3 + 3]
                            text = " ".join(
                                m.get("quote_narration", m.get("quote", ""))
                                for m in page_items
                            )
                        if text:
                            jobs.append((text, f"{audio_base}/{sid}_mention_{p:02d}.mp3", f"{label} [mention_page{p}]"))
            else:
                text_0 = section.get("narration_mention_0", section.get("narration_mention", ""))
                text_1 = section.get("narration_mention_1", "")
                text_2 = section.get("narration_mention_2", "")

                if text_1:
                    for p, text in enumerate([text_0, text_1, text_2]):
                        if text:
                            jobs.append((text, f"{audio_base}/{sid}_mention_{p:02d}.mp3", f"{label} [mention_page{p}]"))
                elif text_0:
                    jobs.append((text_0, f"{audio_base}/{sid}_mention.mp3", f"{label} [mention]"))

        else:
            narration = section.get("narration", "")
            if narration:
                jobs.append((narration, f"{audio_base}/{sid}.mp3", label))

    return jobs


def run(lang: str = "KO"):
    lang = lang.upper()

    if not os.environ.get("ELEVENLABS_API_KEY"):
        raise EnvironmentError("❌ ELEVENLABS_API_KEY 환경변수가 설정되지 않았습니다.")

    voice_id = get_voice_id()
    print(f"🎙️ 사용 Voice ID: {voice_id}")
    print(f"🔊 TTS 모델: {MODEL_ID}")
    print(f"📁 출력 언어: {lang}")

    script_path = f"output/{lang}/scripts/script.json"
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    sections = script.get("sections", [])
    jobs     = _build_jobs(sections, lang)

    total = len(jobs)
    print(f"\n🎙️ TTS 생성 시작 — 총 {total}개 작업\n")

    success_count = 0
    audio_files   = []

    for i, (text, out_path, label) in enumerate(jobs, 1):
        print(f"  [{i}/{total}] {label}")
        print(f"    내용: {text[:60]}...")

        success = text_to_speech(text, out_path)

        if success:
            print(f"    ✅ 완료 → {out_path}")
            success_count += 1
            audio_files.append({"label": label, "path": out_path})
        else:
            print(f"    ❌ 실패 → {out_path}")

        time.sleep(1)

    summary = {
        "total":   total,
        "success": success_count,
        "failed":  total - success_count,
        "files":   audio_files
    }
    summary_path = f"output/{lang}/audio/summary.json"
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*40}")
    print(f"🎉 TTS 완료! 성공: {success_count}/{total}개")
    print(f"{'='*40}\n")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
