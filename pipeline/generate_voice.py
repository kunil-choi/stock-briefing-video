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


def _build_jobs(sections: list, lang: str) -> list:
    """
    script.json의 sections를 순회하며 TTS 작업 목록을 생성합니다.

    mention 슬라이드 분할 규칙:
    - mentions 배열 길이 1~3  → narration_mention  단일 파일
    - mentions 배열 길이 4~6  → narration_mention_0, narration_mention_1
    - mentions 배열 길이 7~9  → narration_mention_0, narration_mention_1, narration_mention_2
    - mentions 배열이 없을 때  → narration_mention 계열 필드가 있으면 그대로 사용
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
            # ── 1) summary 슬라이드 ──────────────────────────────────────
            text = section.get("narration_summary", section.get("narration", ""))
            if text:
                jobs.append((
                    text,
                    f"{audio_base}/{sid}_summary.mp3",
                    f"{label} [summary]"
                ))

            # ── 2) chart 슬라이드 ────────────────────────────────────────
            text = section.get("narration_chart", section.get("narration", ""))
            if text:
                jobs.append((
                    text,
                    f"{audio_base}/{sid}_chart.mp3",
                    f"{label} [chart]"
                ))

            # ── 3) mention 슬라이드 — 언급 수에 따라 페이지 분할 ────────
            mentions = section.get("mentions", [])
            n_mentions = len(mentions)

            if n_mentions > 0:
                # mentions 배열이 있을 때: 3개씩 끊어 페이지별 narration 필드 사용
                pages = max(1, (n_mentions + 2) // 3)
                if pages == 1:
                    # 단일 슬라이드
                    text = section.get("narration_mention", "")
                    if not text:
                        # narration_mention 필드 없으면 quote_narration 이어붙이기
                        text = " ".join(
                            m.get("quote_narration", m.get("quote", ""))
                            for m in mentions[:3]
                        )
                    if text:
                        jobs.append((
                            text,
                            f"{audio_base}/{sid}_mention.mp3",
                            f"{label} [mention]"
                        ))
                else:
                    # 복수 슬라이드: narration_mention_0, _1, _2 ...
                    for p in range(pages):
                        field = f"narration_mention_{p}"
                        text  = section.get(field, "")
                        if not text:
                            # 필드 없으면 해당 페이지 quotes 이어붙이기
                            page_items = mentions[p * 3: p * 3 + 3]
                            text = " ".join(
                                m.get("quote_narration", m.get("quote", ""))
                                for m in page_items
                            )
                        if text:
                            jobs.append((
                                text,
                                f"{audio_base}/{sid}_mention_{p:02d}.mp3",
                                f"{label} [mention_page{p}]"
                            ))
            else:
                # mentions 배열 없음 — narration_mention 계열 필드를 직접 사용
                # 0번 페이지
                text_0 = section.get("narration_mention_0",
                              section.get("narration_mention", ""))
                text_1 = section.get("narration_mention_1", "")
                text_2 = section.get("narration_mention_2", "")

                if text_1:
                    # 복수 페이지
                    for p, text in enumerate([text_0, text_1, text_2]):
                        if text:
                            jobs.append((
                                text,
                                f"{audio_base}/{sid}_mention_{p:02d}.mp3",
                                f"{label} [mention_page{p}]"
                            ))
                elif text_0:
                    # 단일 페이지
                    jobs.append((
                        text_0,
                        f"{audio_base}/{sid}_mention.mp3",
                        f"{label} [mention]"
                    ))

        else:
            # ── 일반 섹션: narration 단일 처리 ──────────────────────────
            narration = section.get("narration", "")
            if narration:
                jobs.append((
                    narration,
                    f"{audio_base}/{sid}.mp3",
                    label
                ))

    return jobs


def run(lang: str = "KO"):
    lang = lang.upper()

    if not os.environ.get("ELEVENLABS_API_KEY"):
        raise EnvironmentError("❌ ELEVENLABS_API_KEY 환경변수가 설정되지 않았습니다.")
    if not os.environ.get("ELEVENLABS_VOICE_ID"):
        raise EnvironmentError("❌ ELEVENLABS_VOICE_ID 환경변수가 설정되지 않았습니다.")

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
