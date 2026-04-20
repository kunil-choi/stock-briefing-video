"""
AI 주식 브리핑 — 동영상 합성
PNG 프레임 + MP3 오디오 → MP4
"""
import os
import sys
import json
import re
import subprocess
import urllib.request

BGM_URL            = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
BGM_VOLUME         = 0.20
FONT_PATH          = "assets/fonts/NotoSansKR-Bold.ttf"
SUBTITLE_SIZE      = 34
SUBTITLE_COLOR     = "white"
SUBTITLE_BOX_COLOR = "0x000000@0.55"
SUBTITLE_Y_BASE    = "h-160"


# ── BGM ───────────────────────────────────────────────────────────────────

def download_bgm(save_path: str):
    if os.path.exists(save_path):
        print(f"  [bgm] 캐시 사용: {save_path}")
        return
    print(f"  [bgm] 다운로드 중...")
    urllib.request.urlretrieve(BGM_URL, save_path)
    print(f"  [bgm] 완료: {save_path}")


# ── 오디오 길이 ────────────────────────────────────────────────────────────

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


# ── 텍스트 변환 ────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    """ffmpeg drawtext용 이스케이프"""
    return (
        text
        .replace("\\", "\\\\")
        .replace("'",  "\u2019")
        .replace(":",  "\\:")
        .replace(",",  "\\,")
        .replace("[",  "\\[")
        .replace("]",  "\\]")
        .replace("%",  "\\%")
        .replace("\n", " ")
        .replace("\r", "")
    )


def _narration_to_subtitle(text: str) -> str:
    """
    narration(TTS용 한글 발음)을 자막용 텍스트로 변환합니다.
    한글 숫자 표현을 아라비아 숫자로 역변환하고 발음용 표기를 표준어로 되돌립니다.
    """
    KOREAN_NUMS = {
        '영': 0, '일': 1, '이': 2, '삼': 3, '사': 4,
        '오': 5, '육': 6, '칠': 7, '팔': 8, '구': 9,
        '십': 10, '백': 100, '천': 1000, '만': 10000,
        '억': 100000000,
    }

    def korean_to_arabic(kor: str) -> str:
        try:
            result  = 0
            current = 0
            for ch in kor:
                if ch not in KOREAN_NUMS:
                    return kor
                val = KOREAN_NUMS[ch]
                if val >= 100000000:
                    result += (current if current else 1) * val
                    current = 0
                elif val >= 10000:
                    result += (current if current else 1) * val
                    current = 0
                elif val >= 10:
                    current = (current if current else 1) * val
                else:
                    current += val
            result += current
            return str(result) if result > 0 else kor
        except Exception:
            return kor

    def replace_percent(m):
        kor = m.group(1)
        try:
            if '점' in kor:
                parts    = kor.split('점', 1)
                int_part = korean_to_arabic(parts[0])
                dec_part = korean_to_arabic(parts[1])
                return f"{int_part}.{dec_part}%"
            else:
                return f"{korean_to_arabic(kor)}%"
        except Exception:
            return m.group(0)

    def replace_won(m):
        kor = m.group(1)
        try:
            arabic = korean_to_arabic(kor)
            if arabic != kor and arabic.isdigit():
                return f"{int(arabic):,}원"
            return m.group(0)
        except Exception:
            return m.group(0)

    text = re.sub(r'([가-힣]+)퍼센트', replace_percent, text)
    text = re.sub(r'([가-힣]+)원', replace_won, text)
    text = text.replace('주까', '주가')
    text = text.replace('신고까', '신고가')
    text = text.replace('고까', '고가')
    text = text.replace('저까', '저가')
    text = text.replace('에이치비엠', 'HBM')
    text = text.replace('이티에프', 'ETF')
    text = text.replace('코스피', 'KOSPI')
    text = text.replace('코스닥', 'KOSDAQ')

    return text


# ── 섹션 영상 생성 ─────────────────────────────────────────────────────────

def build_section_video(
    png_path: str,
    mp3_path: str,
    subtitle: str,
    out_path: str,
    font_path: str
) -> bool:
    """PNG + MP3 → 섹션 mp4 (자막 하단 중앙 고정)"""
    duration = get_audio_duration(mp3_path)
    safe_sub = _escape(subtitle)
    font_part = f"fontfile={font_path}:" if os.path.exists(font_path) else ""

    drawtext = (
        f"drawtext={font_part}"
        f"text='{safe_sub}':"
        f"fontsize={SUBTITLE_SIZE}:"
        f"fontcolor={SUBTITLE_COLOR}:"
        f"box=1:boxcolor={SUBTITLE_BOX_COLOR}:boxborderw=14:"
        f"x=(w-text_w)/2:"
        f"y={SUBTITLE_Y_BASE}:"
        f"line_spacing=8"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-i", mp3_path,
        "-vf", drawtext,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest", "-t", str(duration),
        out_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ 실패: {os.path.basename(out_path)}")
        print(result.stderr[-400:])
        return False

    print(f"  ✅ {os.path.basename(out_path)} ({duration:.1f}초)")
    return True


# ── 영상 합치기 ────────────────────────────────────────────────────────────

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
        print(f"  ❌ 영상 합치기 실패")
        print(result.stderr[-400:])
        return False

    print(f"  ✅ 합치기 완료")
    return True


# ── BGM 믹싱 ──────────────────────────────────────────────────────────────

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
        print(f"  ❌ BGM 믹싱 실패")
        print(result.stderr[-400:])
        return False

    print(f"  ✅ BGM 믹싱 완료")
    return True


# ── 오디오 ID 결정 (화면별 분리) ──────────────────────────────────────────

def _resolve_audio_id(frame_stem: str, sections: list) -> str:
    """
    프레임 파일명으로부터 오디오 파일명(확장자 제외)을 결정합니다.
    stock_/hidden_ 종목은 화면별 suffix(_summary/_chart/_mention)를 붙입니다.
    """
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
        sid = sec.get("id", "")
        if not (sid.startswith("stock_") or sid.startswith("hidden_")):
            continue
        name = sid.replace("stock_", "").replace("hidden_", "")
        if name and (frame_stem.startswith(name + "_") or f"_{name}_" in frame_stem):
            continue
        for frame_suffix, audio_suffix in suffix_map.items():
            if frame_suffix in frame_stem:
                return f"{sid}{audio_suffix}"
        return sid

    return sections[0].get("id", "opening") if sections else "opening"


# ── 자막 텍스트 결정 (화면별 분리) ────────────────────────────────────────

def _resolve_subtitle(frame_stem: str, sections: list) -> str:
    """프레임에 맞는 자막 텍스트를 반환합니다."""
    for sec in sections:
        sid = sec.get("id", "")
        if not (sid.startswith("stock_") or sid.startswith("hidden_")):
            continue
        name = sid.replace("stock_", "").replace("hidden_", "")
        if not name or name not in frame_stem:
            continue
        if "_1_summary" in frame_stem:
            return sec.get("narration_summary", sec.get("narration", ""))
        elif "_2_chart" in frame_stem:
            return sec.get("narration_chart", sec.get("narration", ""))
        elif "_3_mention" in frame_stem:
            return sec.get("narration_mention", sec.get("narration", ""))
        return sec.get("narration", "")

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
                    return sec.get("narration", "")
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
    lang = lang.upper()
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

    script_path    = os.path.join(root, "output", lang, "scripts", "script.json")
    audio_dir      = os.path.join(root, "output", lang, "audio")
    video_dir      = os.path.join(root, "output", lang, "video")
    asset_map_path = os.path.join(root, "output", lang, "asset_map.json")
    bgm_path       = os.path.join(root, "assets", "music", "bgm.mp3")
    font_path      = os.path.join(root, FONT_PATH)

    os.makedirs(video_dir, exist_ok=True)

    if not os.path.isfile(script_path):
        print(f"❌ script.json 없음")
        sys.exit(1)
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    sections = script.get("sections", [])
    print(f"📂 섹션 수: {len(sections)}")

    if not os.path.isfile(asset_map_path):
        print(f"❌ asset_map.json 없음")
        sys.exit(1)
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

        audio_id  = _resolve_audio_id(frame_stem, sections)
        mp3_path  = os.path.join(audio_dir, f"{audio_id}.mp3")
        narration = _resolve_subtitle(frame_stem, sections)
        subtitle  = _narration_to_subtitle(narration)

        if not os.path.isfile(mp3_path):
            print(f"  ⚠️ MP3 없음 → 무음: {audio_id}")
            mp3_path = _make_silent_audio(video_dir, frame_stem)

        out_video = os.path.join(video_dir, f"{frame_stem}.mp4")
        ok = build_section_video(frame_path, mp3_path, subtitle, out_video, font_path)
        if ok:
            section_videos.append(out_video)

    if not section_videos:
        print("❌ 생성된 섹션 영상 없음")
        sys.exit(1)

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
