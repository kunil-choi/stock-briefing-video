"""AI 주식 브리핑 — 동영상 합성  PNG 프레임 + MP3 오디오 → MP4"""
import os
import sys
import json
import re
import subprocess
import urllib.request

# ── BGM 볼륨: 기존 0.20의 60% = 0.12 ─────────────────────────────────────
BGM_URL    = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
BGM_VOLUME = 0.12   # 요구 3: 음악 음량 60% 수준으로 낮춤


# ── BGM ──────────────────────────────────────────────────────────────────
def download_bgm(save_path: str):
    if os.path.exists(save_path):
        print(f"  [bgm] 캐시 사용: {save_path}")
        return
    print(f"  [bgm] 다운로드 중...")
    urllib.request.urlretrieve(BGM_URL, save_path)
    print(f"  [bgm] 완료: {save_path}")


# ── 오디오 길이 ───────────────────────────────────────────────────────────
def get_audio_duration(mp3_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        mp3_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except Exception:
        return 3.0


# ── 섹션 영상 생성 ────────────────────────────────────────────────────────
def build_section_video(
    png_path: str,
    mp3_path: str,
    out_path: str,
) -> bool:
    """
    PNG + MP3 → MP4 변환.
    자막은 builders.py가 PNG에 이미 그려 넣었으므로
    ffmpeg에서 별도 SRT 자막을 추가하지 않습니다. (요구 1)
    """
    duration = get_audio_duration(mp3_path)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-i",    mp3_path,
        "-c:v",  "libx264", "-tune", "stillimage",
        "-c:a",  "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-t", f"{duration:.3f}",
        out_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ 실패: {os.path.basename(out_path)}")
        print(result.stderr[-600:])
        return False

    print(f"  ✅ {os.path.basename(out_path)} ({duration:.1f}초)")
    return True


# ── 영상 합치기 ───────────────────────────────────────────────────────────
def concat_videos(video_list: list, out_path: str) -> bool:
    list_file = out_path.replace(".mp4", "_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for v in video_list:
            f.write(f"file '{os.path.abspath(v)}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)
    if result.returncode != 0:
        print("  ❌ 영상 합치기 실패")
        print(result.stderr[-400:])
        return False
    print("  ✅ 합치기 완료")
    return True


# ── BGM 믹싱 ─────────────────────────────────────────────────────────────
def mix_bgm(video_path: str, bgm_path: str, out_path: str) -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex",
        f"[1:a]volume={BGM_VOLUME}[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  ❌ BGM 믹싱 실패")
        print(result.stderr[-400:])
        return False
    print("  ✅ BGM 믹싱 완료")
    return True


# ── 무음 오디오 생성 ──────────────────────────────────────────────────────
def _make_silent_audio(tmp_dir: str, name: str) -> str:
    path = os.path.join(tmp_dir, f"silent_{name}.mp3")
    if not os.path.exists(path):
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "3", "-c:a", "libmp3lame", path
        ], capture_output=True)
    return path


# ── 오디오 ID 결정 ────────────────────────────────────────────────────────
def _resolve_audio_id(frame_stem: str, sections: list) -> str:
    fixed = {
        "opening":     "opening",
        "market":      "market_summary",
        "sector":      "sectors",
        "ai_strategy": "ai_strategy",
        "closing":     "closing",
    }
    for key, sid in fixed.items():
        if key in frame_stem:
            return sid

    suffix_map = {
        "_1_summary": "_summary",
        "_2_chart":   "_chart",
        "_3_mention": "_mention",
    }
    for sec in sections:
        sid  = sec.get("id", "")
        if not (sid.startswith("stock_") or sid.startswith("hidden_")):
            continue
        name = sid.replace("stock_", "").replace("hidden_", "")
        if not name:
            continue
        if not (frame_stem.startswith(name + "_") or
                f"_{name}_" in frame_stem or
                frame_stem == name):
            continue

        for fsuffix, asuffix in suffix_map.items():
            if fsuffix in frame_stem:
                # mention 페이지 인덱스 처리
                if fsuffix == "_3_mention":
                    page_match = re.search(r'_3_mention_(\d+)', frame_stem)
                    if page_match:
                        p = int(page_match.group(1))
                        mentions = sec.get("mentions", [])
                        if len(mentions) > 3 or sec.get(f"narration_mention_{p}"):
                            return f"{sid}_mention_{p:02d}"
                    return f"{sid}_mention"
                return f"{sid}{asuffix}"
        return sid

    return sections[0].get("id", "opening") if sections else "opening"


# ── 메인 실행 ─────────────────────────────────────────────────────────────
def run(lang: str = "KO"):
    lang           = lang.upper()
    root           = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    script_path    = os.path.join(root, "output", lang, "scripts", "script.json")
    audio_dir      = os.path.join(root, "output", lang, "audio")
    video_dir      = os.path.join(root, "output", lang, "video")
    asset_map_path = os.path.join(root, "output", lang, "asset_map.json")
    bgm_path       = os.path.join(root, "assets", "music", "bgm.mp3")

    os.makedirs(video_dir, exist_ok=True)

    if not os.path.isfile(script_path):
        print("❌ script.json 없음"); sys.exit(1)
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    sections = script.get("sections", [])
    print(f"📂 섹션 수: {len(sections)}")

    if not os.path.isfile(asset_map_path):
        print("❌ asset_map.json 없음"); sys.exit(1)
    with open(asset_map_path, encoding="utf-8") as f:
        asset_map = json.load(f)
    frames = asset_map.get("frames", [])
    print(f"📂 프레임 수: {len(frames)}")

    download_bgm(bgm_path)

    section_videos = []
    print(f"\n🎬 섹션 영상 생성 시작\n")

    for frame_path in frames:
        frame_name = os.path.basename(frame_path)
        frame_stem = os.path.splitext(frame_name)[0]

        audio_id = _resolve_audio_id(frame_stem, sections)
        mp3_path = os.path.join(audio_dir, f"{audio_id}.mp3")

        if not os.path.isfile(mp3_path):
            print(f"  ⚠️ MP3 없음 → 무음: {audio_id}")
            mp3_path = _make_silent_audio(video_dir, frame_stem)

        out_video = os.path.join(video_dir, f"{frame_stem}.mp4")
        # 자막은 PNG에 내장됨 — subtitle 인자 제거 (요구 1)
        ok = build_section_video(frame_path, mp3_path, out_video)
        if ok:
            section_videos.append(out_video)

    if not section_videos:
        print("❌ 생성된 섹션 영상 없음"); sys.exit(1)

    print(f"\n✂️ 영상 컷 연결 중...\n")
    merged_path = os.path.join(video_dir, "merged.mp4")
    if not concat_videos(section_videos, merged_path):
        sys.exit(1)

    print(f"\n🎵 BGM 믹싱 중...\n")
    final_path = os.path.join(video_dir, "final.mp4")
    if not mix_bgm(merged_path, bgm_path, final_path):
        sys.exit(1)

    os.remove(merged_path)
    for v in section_videos:
        try:
            os.remove(v)
        except Exception:
            pass

    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    print(f"\n✅ 최종 영상 완성! {size_mb:.1f} MB → {final_path}")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
