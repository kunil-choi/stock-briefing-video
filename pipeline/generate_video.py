"""
pipeline/generate_video.py
===========================
KBS 머니올라 — 동영상 합성 모듈
PNG 프레임 + MP3 오디오 + ASS 자막 → MP4

프레임 → 오디오 매핑 규칙:
  00_opening.png             → opening.mp3
  01_market_00.png           → market_summary.mp3
  02_sector.png              → sectors.mp3
  NN_종목명_1_summary.png    → stock_종목명_summary.mp3
  NN_종목명_2_chart.png      → stock_종목명_chart.mp3
  NN_종목명_3_mention.png    → stock_종목명_mention.mp3
  NN_종목명_3_mention_MM.png → stock_종목명_mention_MM.mp3
  98_ai_strategy.png         → ai_strategy.mp3
  99_closing.png             → closing.mp3

자막 처리:
  - ASS burn-in 방식: ffmpeg libass 필터로 자막을 영상에 직접 합성
  - 나레이션 타이밍과 동기화된 하단 자막 표출
  - 자막 텍스트: subtitle 필드 (한글 맞춤법, 숫자 원문, 용어 설명 병기)
"""
import os
import sys
import json
import re
import subprocess
import urllib.request

# BGM 볼륨 설정 (0.0~1.0)
BGM_URL    = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
BGM_VOLUME = 0.065   # 주 오디오를 방해하지 않는 낮은 볼륨


# ── BGM 다운로드 ──────────────────────────────────────────────────────────

def download_bgm(save_path: str):
    if os.path.exists(save_path):
        print(f"  [bgm] 캐시 사용: {save_path}")
        return
    print(f"  [bgm] 다운로드 중...")
    try:
        urllib.request.urlretrieve(BGM_URL, save_path)
        print(f"  [bgm] 완료: {save_path}")
    except Exception as e:
        print(f"  [bgm] 다운로드 실패: {e}")


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
        dur = float(result.stdout.strip())
        return dur if dur > 0 else 3.0
    except Exception:
        return 3.0


# ── 프레임 스템 → 오디오 ID 변환 ─────────────────────────────────────────

def _frame_stem_to_audio_id(stem: str, sections: list) -> str:
    """
    프레임 파일 스템(확장자 없는 파일명)을 오디오 ID로 변환합니다.
    generate_subtitles.py 와 동일한 로직을 사용합니다.
    """
    # 고정 패턴
    fixed_patterns = [
        (r'^00_opening$',    'opening'),
        (r'^01_market',      'market_summary'),
        (r'^02_sector',      'sectors'),
        (r'^98_ai_strategy', 'ai_strategy'),
        (r'^99_closing',     'closing'),
    ]
    for pattern, audio_id in fixed_patterns:
        if re.match(pattern, stem):
            return audio_id

    # mention 페이지 있음: NN_종목명_3_mention_MM
    m = re.match(r'^\d{2}_(.+)_3_mention_(\d{2})$', stem)
    if m:
        stock_name = m.group(1)
        page_num   = m.group(2)
        sid = _find_stock_section_id(stock_name, sections)
        return f"{sid}_mention_{page_num}"

    # mention 단일: NN_종목명_3_mention
    m = re.match(r'^\d{2}_(.+)_3_mention$', stem)
    if m:
        stock_name = m.group(1)
        sid = _find_stock_section_id(stock_name, sections)
        return f"{sid}_mention"

    # chart: NN_종목명_2_chart
    m = re.match(r'^\d{2}_(.+)_2_chart$', stem)
    if m:
        stock_name = m.group(1)
        sid = _find_stock_section_id(stock_name, sections)
        return f"{sid}_chart"

    # summary: NN_종목명_1_summary
    m = re.match(r'^\d{2}_(.+)_1_summary$', stem)
    if m:
        stock_name = m.group(1)
        sid = _find_stock_section_id(stock_name, sections)
        return f"{sid}_summary"

    # fallback
    print(f"  ⚠️ 오디오 ID 매핑 실패 — 스템: {stem}")
    return stem


def _find_stock_section_id(stock_name: str, sections: list) -> str:
    """종목명으로 sections에서 실제 section ID를 찾습니다."""
    for sec in sections:
        sid = sec.get("id", "")
        if sid in (f"stock_{stock_name}", f"hidden_{stock_name}"):
            return sid
    for sec in sections:
        sid = sec.get("id", "")
        if stock_name in sid:
            return sid
    return f"stock_{stock_name}"


# ── 섹션 영상 생성 (PNG + MP3 → MP4) ─────────────────────────────────────

def build_section_video(png_path: str, mp3_path: str, out_path: str) -> bool:
    """PNG + MP3 → 섹션 MP4 변환."""
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


# ── ASS 자막 burn-in ──────────────────────────────────────────────────────

def burn_subtitles(video_path: str, ass_path: str, out_path: str) -> bool:
    """
    ASS 자막 파일을 영상에 burn-in합니다.
    자막이 나레이션 타이밍에 맞춰 화면 하단에 표출됩니다.
    """
    if not os.path.isfile(ass_path):
        print(f"  ⚠️ ASS 자막 파일 없음: {ass_path}")
        return False

    # ASS 경로 이스케이프 (libass 요구사항)
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass={ass_escaped}",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "copy",
        out_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  ❌ ASS burn-in 실패")
        print(result.stderr[-800:])
        return False

    print("  ✅ ASS 자막 burn-in 완료")
    return True


# ── BGM 믹싱 ─────────────────────────────────────────────────────────────

def mix_bgm(video_path: str, bgm_path: str, out_path: str) -> bool:
    if not os.path.isfile(bgm_path):
        print(f"  ⚠️ BGM 없음 → BGM 없이 진행")
        import shutil
        shutil.copy2(video_path, out_path)
        return True

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

def _make_silent_audio(tmp_dir: str, name: str, duration: float = 3.0) -> str:
    path = os.path.join(tmp_dir, f"silent_{name}.mp3")
    if not os.path.exists(path):
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration), "-c:a", "libmp3lame", path
        ], capture_output=True)
    return path


# ── ASS 자막 자동 생성 ────────────────────────────────────────────────────

def _auto_generate_subtitles(lang: str, root: str, sections: list, frames: list) -> str:
    """자막 파일이 없으면 자동 생성합니다."""
    sub_dir  = os.path.join(root, "output", lang, "subtitles")
    ass_path = os.path.join(sub_dir, "subtitle.ass")

    if os.path.isfile(ass_path):
        print(f"  [subtitle] 기존 ASS 파일 사용: {ass_path}")
        return ass_path

    print(f"  [subtitle] ASS 자막 자동 생성 중...")
    try:
        sys.path.insert(0, os.path.join(root, "pipeline"))
        from generate_subtitles import generate_ass
        generate_ass(sections, lang, ass_path, frames)
        return ass_path
    except Exception as e:
        print(f"  [subtitle] 자막 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return ""


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

    # script.json 로드
    if not os.path.isfile(script_path):
        print("❌ script.json 없음"); sys.exit(1)
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    sections = script.get("sections", [])
    print(f"📂 섹션 수: {len(sections)}")

    # asset_map.json 로드
    if not os.path.isfile(asset_map_path):
        print("❌ asset_map.json 없음"); sys.exit(1)
    with open(asset_map_path, encoding="utf-8") as f:
        asset_map = json.load(f)
    frames = asset_map.get("frames", [])
    print(f"📂 프레임 수: {len(frames)}")

    # BGM 다운로드
    os.makedirs(os.path.dirname(bgm_path), exist_ok=True)
    download_bgm(bgm_path)

    # ── 섹션 영상 생성 ─────────────────────────────────────────────────
    section_videos = []
    print(f"\n🎬 섹션 영상 생성 시작\n")

    for frame_path in frames:
        frame_name = os.path.basename(frame_path)
        frame_stem = os.path.splitext(frame_name)[0]

        audio_id = _frame_stem_to_audio_id(frame_stem, sections)
        mp3_path = os.path.join(audio_dir, f"{audio_id}.mp3")

        if not os.path.isfile(mp3_path):
            print(f"  ⚠️ MP3 없음 [{audio_id}] → 무음 처리")
            mp3_path = _make_silent_audio(video_dir, frame_stem)

        out_video = os.path.join(video_dir, f"{frame_stem}.mp4")
        ok = build_section_video(frame_path, mp3_path, out_video)
        if ok:
            section_videos.append(out_video)

    if not section_videos:
        print("❌ 생성된 섹션 영상 없음"); sys.exit(1)

    # ── 영상 합치기 ────────────────────────────────────────────────────
    print(f"\n✂️ 영상 컷 연결 중...\n")
    merged_path = os.path.join(video_dir, "merged.mp4")
    if not concat_videos(section_videos, merged_path):
        sys.exit(1)

    # ── ASS 자막 자동 생성 및 burn-in ──────────────────────────────────
    print(f"\n📝 자막 처리 중...\n")
    ass_path = _auto_generate_subtitles(lang, root, sections, frames)
    subtitled_path = os.path.join(video_dir, "with_subtitles.mp4")

    if ass_path and os.path.isfile(ass_path):
        sub_ok = burn_subtitles(merged_path, ass_path, subtitled_path)
        if sub_ok:
            try:
                os.remove(merged_path)
            except Exception:
                pass
            source_for_bgm = subtitled_path
        else:
            print("  ⚠️ 자막 burn-in 실패 → 자막 없는 영상으로 진행")
            source_for_bgm = merged_path
    else:
        print("  ⚠️ 자막 파일 없음 → 자막 없는 영상으로 진행")
        source_for_bgm = merged_path

    # ── BGM 믹싱 ───────────────────────────────────────────────────────
    print(f"\n🎵 BGM 믹싱 중...\n")
    final_path = os.path.join(video_dir, "final.mp4")
    if not mix_bgm(source_for_bgm, bgm_path, final_path):
        sys.exit(1)

    # 임시 파일 정리
    for temp in [merged_path, subtitled_path]:
        if os.path.isfile(temp):
            try:
                os.remove(temp)
            except Exception:
                pass
    for v in section_videos:
        try:
            os.remove(v)
        except Exception:
            pass

    size_mb = os.path.getsize(final_path) / (1024 * 1024)

    # 영상 길이 확인
    total_duration = get_audio_duration(final_path)
    mins = int(total_duration // 60)
    secs = int(total_duration % 60)

    print(f"\n{'='*50}")
    print(f"✅ 최종 영상 완성!")
    print(f"   파일: {final_path}")
    print(f"   크기: {size_mb:.1f} MB")
    print(f"   길이: {mins}분 {secs}초 (목표: 약 10분)")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
