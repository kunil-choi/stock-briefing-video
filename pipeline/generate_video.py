"""AI 주식 브리핑 — 동영상 합성  PNG 프레임 + MP3 오디오 → MP4"""
import os
import sys
import json
import re
import subprocess
import tempfile
import urllib.request

BGM_URL            = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
BGM_VOLUME         = 0.20
FONT_PATH          = "assets/fonts/NotoSansKR-Bold.ttf"
SUBTITLE_SIZE      = 28
SUBTITLE_COLOR     = "white"
SUBTITLE_BOX_COLOR = "0x000000@0.55"
SUBTITLE_Y_BASE    = "h-160"
SUBTITLE_MAX_CHARS = 20


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


# ── 자막 텍스트 정리 ──────────────────────────────────────────────────────
def _clean_subtitle(text: str) -> str:
    """
    subtitle 필드는 GPT가 이미 아라비아 숫자·영어 약어로 작성했으므로
    변환 없이 공백·줄바꿈만 정리합니다.
    혹시 구버전 script.json (subtitle 필드 없음) 과의 호환을 위해
    최소한의 한글 숫자 변환 fallback만 유지합니다.
    """
    if not text:
        return ""

    # 줄바꿈 → 공백
    text = text.replace('\n', ' ').replace('\r', ' ')

    # 연속 공백 정리
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


# ── 자막 줄 분할 ──────────────────────────────────────────────────────────
def _split_lines(text: str, max_chars: int = SUBTITLE_MAX_CHARS) -> list:
    """
    문장부호 위치를 우선 분할 기준으로 삼고,
    max_chars 초과하면 공백·글자 단위로 추가 분할.
    반환값은 순수 문자열 리스트 (줄바꿈 문자 없음).
    """
    sentences = re.split(r'(?<=[.!?。…])\s*', text.strip())
    sentences = [s.strip().replace('\n', ' ') for s in sentences if s.strip()]

    lines = []
    for sent in sentences:
        if len(sent) <= max_chars:
            lines.append(sent.strip())
        else:
            words = sent.split()
            cur = ""
            for w in words:
                w = w.replace('\n', '').strip()
                if not w:
                    continue
                candidate = (cur + " " + w).strip() if cur else w
                if len(candidate) <= max_chars:
                    cur = candidate
                else:
                    if cur:
                        lines.append(cur.strip())
                    while len(w) > max_chars:
                        lines.append(w[:max_chars].strip())
                        w = w[max_chars:]
                    cur = w
            if cur:
                lines.append(cur.strip())

    return lines if lines else [text[:max_chars].strip()]


# ── SRT 파일 생성 ─────────────────────────────────────────────────────────
def _sec_to_srt_time(s: float) -> str:
    h  = int(s // 3600)
    m  = int((s % 3600) // 60)
    sc = int(s % 60)
    ms = int(round((s % 1) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{sc:02d},{ms:03d}"


def _make_srt(subtitle_text: str, duration: float, srt_path: str):
    """
    자막을 줄 단위로 분할 → 오디오 시간 균등 배분 → SRT 파일 저장.
    각 줄 최소 1.2초 보장, 마지막 줄은 duration 끝까지.
    """
    lines = _split_lines(subtitle_text)
    n   = len(lines)
    per = max(duration / n, 1.2)

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines):
            clean_line = line.replace('\n', ' ').replace('\r', '').strip()
            start = i * per
            end   = duration if i == n - 1 else min((i + 1) * per, duration)
            if end <= start:
                end = start + 1.0
            f.write(f"{i + 1}\n")
            f.write(f"{_sec_to_srt_time(start)} --> {_sec_to_srt_time(end)}\n")
            f.write(f"{clean_line}\n\n")


# ── 섹션 영상 생성 ────────────────────────────────────────────────────────
def build_section_video(
    png_path:  str,
    mp3_path:  str,
    subtitle:  str,
    out_path:  str,
    font_path: str
) -> bool:
    duration = get_audio_duration(mp3_path)

    srt_fd, srt_path = tempfile.mkstemp(suffix=".srt")
    os.close(srt_fd)

    try:
        _make_srt(subtitle, duration, srt_path)

        abs_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        font_dir_opt = ""
        if os.path.exists(font_path):
            font_dir = os.path.dirname(os.path.abspath(font_path)).replace("\\", "/")
            font_dir_opt = f":fontsdir={font_dir}"

        sub_filter = (
            f"subtitles='{abs_srt}'{font_dir_opt}"
            f":force_style='"
            f"FontSize={SUBTITLE_SIZE},"
            f"PrimaryColour=&H00FFFFFF,"
            f"BackColour=&H8C000000,"
            f"BorderStyle=3,"
            f"Outline=0,"
            f"Shadow=0,"
            f"MarginV=60,"
            f"Alignment=2'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", png_path,
            "-i",    mp3_path,
            "-vf",   sub_filter,
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

        n_lines = len(_split_lines(subtitle))
        print(f"  ✅ {os.path.basename(out_path)} ({duration:.1f}초, 자막 {n_lines}줄)")
        return True

    finally:
        try:
            os.remove(srt_path)
        except Exception:
            pass


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
                return f"{sid}{asuffix}"
        return sid

    return sections[0].get("id", "opening") if sections else "opening"


# ── 자막 텍스트 결정 ──────────────────────────────────────────────────────
def _resolve_subtitle(frame_stem: str, sections: list) -> str:
    """
    프레임 이름 기반으로 subtitle_* 필드를 우선 참조.
    subtitle_* 필드가 없으면 narration_* 필드로 fallback.
    """

    def _pick(sec: dict, narr_key: str, sub_key: str) -> str:
        """subtitle 필드 우선, 없으면 narration 필드 사용"""
        return sec.get(sub_key) or sec.get(narr_key) or sec.get("subtitle") or sec.get("narration", "")

    # ── stock_ / hidden_ 섹션 매칭 ───────────────────────────────────────
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

        if "_1_summary" in frame_stem:
            return _pick(sec, "narration_summary", "subtitle_summary")

        elif "_2_chart" in frame_stem:
            return _pick(sec, "narration_chart", "subtitle_chart")

        elif "_3_mention" in frame_stem:
            # 페이지 인덱스 파싱: _3_mention_00 → 0, _3_mention_01 → 1
            page_match = re.search(r'_3_mention_(\d+)', frame_stem)
            if page_match:
                page_idx = int(page_match.group(1))
                sub_key  = f"subtitle_mention_{page_idx}"
                narr_key = f"narration_mention_{page_idx}"
                val = sec.get(sub_key) or sec.get(narr_key)
                if val:
                    return val
            # 인덱스 없거나 키 없으면 단수 필드 사용
            return _pick(sec, "narration_mention", "subtitle_mention")

        # 그 외 (프레임이 종목명과 직접 매칭)
        return _pick(sec, "narration_summary", "subtitle_summary")

    # ── 고정 섹션 매칭 ────────────────────────────────────────────────────
    fixed = {
        "opening":     "opening",
        "market":      "market_summary",
        "sector":      "sectors",
        "ai_strategy": "ai_strategy",
        "closing":     "closing",
    }
    for key, sid in fixed.items():
        if key in frame_stem:
            for sec in sections:
                if sec.get("id") == sid:
                    return sec.get("subtitle") or sec.get("narration", "")
            break

    print(f"  ⚠️ 자막 매칭 실패: {frame_stem}")
    return ""


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


# ── 메인 실행 ─────────────────────────────────────────────────────────────
def run(lang: str = "KO"):
    lang           = lang.upper()
    root           = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    script_path    = os.path.join(root, "output", lang, "scripts", "script.json")
    audio_dir      = os.path.join(root, "output", lang, "audio")
    video_dir      = os.path.join(root, "output", lang, "video")
    asset_map_path = os.path.join(root, "output", lang, "asset_map.json")
    bgm_path       = os.path.join(root, "assets", "music", "bgm.mp3")
    font_path      = os.path.join(root, FONT_PATH)

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

        # ✅ subtitle 필드 직접 사용 (변환 없음)
        raw_subtitle = _resolve_subtitle(frame_stem, sections)
        subtitle     = _clean_subtitle(raw_subtitle)

        if not subtitle.strip():
            print(f"  ⚠️ 빈 자막: {frame_stem}")

        if not os.path.isfile(mp3_path):
            print(f"  ⚠️ MP3 없음 → 무음: {audio_id}")
            mp3_path = _make_silent_audio(video_dir, frame_stem)

        out_video = os.path.join(video_dir, f"{frame_stem}.mp4")
        ok = build_section_video(frame_path, mp3_path, subtitle, out_video, font_path)
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
