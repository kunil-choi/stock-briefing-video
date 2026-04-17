import os
import json
import requests
import time

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
VOICE_ID           = os.environ["ELEVENLABS_VOICE_ID"]
MODEL_ID           = "eleven_multilingual_v2"

VOICE_SETTINGS = {
    "stability":         0.55,
    "similarity_boost":  0.90,
    "style":             0.20,
    "use_speaker_boost": True
}

# ─────────────────────────────────────────────
# 텍스트 → 음성 변환
# ─────────────────────────────────────────────

def text_to_speech(text: str, output_path: str) -> bool:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "Accept":       "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key":   ELEVENLABS_API_KEY
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
        print(f"  ❌ 오류: {response.status_code} - {response.text}")
        return False

# ─────────────────────────────────────────────
# 전체 섹션 더빙
# ─────────────────────────────────────────────

def run():
    # 원고 로드
    script_path = "output/KO/scripts/script.json"
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    sections = script["sections"]
    total    = len(sections)

    print(f"\n🎙️ 더빙 시작 — 총 {total}개 섹션\n")

    success_count = 0
    audio_files   = []

    for i, section in enumerate(sections, 1):
        sid       = section["id"]
        label     = section["label"]
        narration = section["narration"]
        out_path  = f"output/KO/audio/{sid}.mp3"

        print(f"  [{i}/{total}] {label}")
        print(f"    내레이션: {narration[:40]}...")

        success = text_to_speech(narration, out_path)

        if success:
            print(f"    ✅ 완료 → {out_path}")
            success_count += 1
            audio_files.append({
                "id":    sid,
                "label": label,
                "path":  out_path
            })
        else:
            print(f"    ❌ 실패 → {sid}")

        # API 요청 간격 (과부하 방지)
        time.sleep(1)

    # ── 결과 요약 저장
    summary = {
        "total":   total,
        "success": success_count,
        "failed":  total - success_count,
        "files":   audio_files
    }
    summary_path = "output/KO/audio/summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*40}")
    print(f"🎉 더빙 완료!")
    print(f"   성공: {success_count}/{total}개")
    print(f"   저장 위치: output/KO/audio/")
    print(f"{'='*40}\n")

if __name__ == "__main__":
    run()
