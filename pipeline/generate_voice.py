import os
import json
import requests
import time
import sys

MODEL_ID = "eleven_multilingual_v2"

VOICE_SETTINGS = {
    "stability":         0.75,
    "similarity_boost":  0.90,
    "style":             0.00,
    "use_speaker_boost": True
}


def text_to_speech(text: str, output_path: str) -> bool:
    api_key  = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")

    if not api_key or not voice_id:
        print("  ❌ ELEVENLABS_API_KEY 또는 ELEVENLABS_VOICE_ID 환경변수가 없습니다.")
        return False

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept":       "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key":   api_key
    }
    payload = {
        "text":           text,
        "model_id":       MODEL_ID,
        "voice_settings": VOICE_SETTINGS
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        return True
    else:
        print(f"  ❌ 실패: {response.status_code} - {response.text}")
        return False


def run(lang: str = "KO"):
    # ── [오류 2 수정] KO 하드코딩 → lang 파라미터 사용 ──
    lang = lang.upper()

    if not os.environ.get("ELEVENLABS_API_KEY"):
        raise EnvironmentError("❌ ELEVENLABS_API_KEY 환경변수가 설정되지 않았습니다.")
    if not os.environ.get("ELEVENLABS_VOICE_ID"):
        raise EnvironmentError("❌ ELEVENLABS_VOICE_ID 환경변수가 설정되지 않았습니다.")

    script_path = f"output/{lang}/scripts/script.json"
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    sections    = script["sections"]
    jobs        = []  # (narration_text, output_path, label)

    # 모든 섹션 순회하여 TTS 작업 목록 생성
    for section in sections:
        sid   = section.get("id", "")
        label = section.get("label", "")
        if not sid:
            continue

        is_stock = sid.startswith("stock_") or sid.startswith("hidden_")

        if is_stock:
            # 종목별 narration 3종 처리
            for suffix, field in [
                ("_summary", "narration_summary"),
                ("_chart",   "narration_chart"),
                ("_mention", "narration_mention"),
            ]:
                text = section.get(field, section.get("narration", ""))
                if text:
                    jobs.append((
                        text,
                        f"output/{lang}/audio/{sid}{suffix}.mp3",
                        f"{label} [{suffix.strip('_')}]"
                    ))
        else:
            # 일반 섹션: narration 단일 처리
            narration = section.get("narration", "")
            if narration:
                jobs.append((
                    narration,
                    f"output/{lang}/audio/{sid}.mp3",
                    label
                ))

    total = len(jobs)
    print(f"\n🎙️ TTS 생성 시작 — 총 {total}개 작업\n")

    success_count = 0
    audio_files   = []

    for i, (text, out_path, label) in enumerate(jobs, 1):
        print(f"  [{i}/{total}] {label}")
        print(f"    내용: {text[:40]}...")

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
