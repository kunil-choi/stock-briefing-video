"""
AI 주식 브리핑 — 동영상 합성
PNG 프레임 + MP3 오디오 → MP4
"""
import os
import sys
import json
import subprocess
import urllib.request
import tempfile

# 저작권 없는 배경음악 (YouTube Audio Library / CC0)
BGM_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
BGM_VOLUME = 0.20          # 내레이션 대비 20%
FPS = 30                   # 프레임 유지 시간 계산용
FONT_PATH = "assets/fonts/NotoSansKR-Bold.ttf"
SUBTITLE_FONT_SIZE = 36
SUBTITLE_COLOR = "white"
SUBTITLE_BOX_COLOR = "0x000000@0.5"


def download_bgm(save_path: str):
    """저작권 없는 BGM 다운로드"""
    if os.path.exists(save_path):
        print(f"  [bgm] 캐시 사용: {save_path}")
        return
    print(f"  [bgm] 다운로드 중...")
    urllib.request.urlretrieve(BGM_URL, save_path)
    print(f"  [bgm] 완료: {save_path}")


def get_audio_duration(mp3_path: str) -> float:
    """ffprobe로 오디오 길이(초) 반환"""
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
        return 3.0  # 기본값 3초


def build_section_video(
    png_path: str,
    mp3_path: str,
    subtitle: str,
    out_path: str,
    font_path: str
):
    """PNG 1장 + MP3 1개 → 섹션 mp4 생성 (자막 포함)"""
    duration = get_audio_duration(mp3_path)

    # 자막 텍스트 이스케이프 처리
    safe_subtitle = (
        subtitle
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )

    # 폰트 경로 확인
    if os.path.exists(font_path):
        font_setting = f"fontfile={font_path}"
    else:
        font_setting = ""

    # drawtext 필터 구성
    if font_setting:
        drawtext = (
            f"drawtext={font_setting}"
            f":text='{safe_subtitle}'"
            f":fontsize={SUBTITLE_FONT_SIZE}"
            f":fontcolor={SUBTITLE_COLOR}"
            f":box=1:boxcolor={SUBTITLE_BOX_COLOR}:boxborderw=10"
            f":x=(w-text_w)/2:y=h-th-70"
            f":line_spacing=8"
        )
    else:
        drawtext = (
            f"drawtext=text='{safe_subtitle}'"
            f":fontsize={SUBTITLE_FONT_SIZE}"
            f":fontcolor={SUBTITLE_COLOR}"
            f":box=1:boxcolor={SUBTITLE_BOX_COLOR}:boxborderw=10"
            f":x=(w-text_w)/2:y=h-th-70"
            f":line_spacing=8"
        )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", png_path,
        "-i", mp3_path,
        "-vf", drawtext,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-t", str(duration),
        out_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ 섹션 영상 생성 실패: {os.path.basename(out_path)}")
        print(result.stderr[-300:])
        return False

    print(f"  ✅ {os.path.basename(out_path)} ({duration:.1f}초)")
    return True


def concat_videos(video_list: list, out_path: str):
    """섹션 mp4들을 단순 컷 연결"""
    list_file = out_path.replace(".mp4", "_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for v in video_list:
            abs_path = os.path.abspath(v)
            f.write(f"file '{abs_path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)

    if result.returncode != 0:
        print(f"  ❌ 영상 합치기 실패")
        print(result.stderr[-300:])
        return False

    print(f"  ✅ 영상 합치기 완료: {out_path}")
    return True


def mix_bgm(video_path: str, bgm_path: str, out_path: str):
    """완성 영상에 BGM 믹싱 (내레이션 대비 20%)"""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", bgm_path,
        "-filter_complex",
        f"[1:a]volume={BGM_VOLUME}[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ BGM 믹싱 실패")
        print(result.stderr[-300:])
        return False

    print(f"  ✅ BGM 믹싱 완료: {out_path}")
    return True


def run(lang: str = "KO"):
    lang = lang.upper()
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

    # 경로 설정
    script_path = os.path.join(root, "output", lang, "scripts", "script.json")
    frames_dir  = os.path.join(root, "output", lang, "frames")
    audio_dir   = os.path.join(root, "output", lang, "audio")
    video_dir   = os.path.join(root, "output", lang, "video")
    bgm_path    = os.path.join(root, "assets", "music", "bgm.mp3")
    font_path   = os.path.join(root, FONT_PATH)

    os.makedirs(video_dir, exist_ok=True)

    # script.json 로드
    if not os.path.isfile(script_path):
        print(f"❌ script.json 없음: {script_path}")
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    sections = script.get("sections", [])
    print(f"📂 섹션 수: {len(sections)}")

    # asset_map.json 로드 (프레임 순서 기준)
    asset_map_path = os.path.join(root, "output", lang, "asset_map.json")
    if not os.path.isfile(asset_map_path):
        print(f"❌ asset_map.json 없음: {asset_map_path}")
        sys.exit(1)

    with open(asset_map_path, encoding="utf-8") as f:
        asset_map = json.load(f)

    frames = asset_map.get("frames", [])
    print(f"📂 프레임 수: {len(frames)}")

    # BGM 다운로드
    download_bgm(bgm_path)

    # 섹션별 내레이션 맵 구성 (id → narration)
    narration_map = {}
    for sec in sections:
        sid = sec.get("id", "")
        narration_map[sid] = sec.get("narration", "")

    # 각 프레임별 섹션 mp4 생성
    section_videos = []
    print(f"\n🎬 섹션 영상 생성 시작\n")

    for frame_path in frames:
        frame_name = os.path.basename(frame_path)           # e.g. 00_opening.png
        frame_stem = os.path.splitext(frame_name)[0]        # e.g. 00_opening

        # 해당 프레임의 섹션 ID 추정
        sec_id = _guess_section_id(frame_stem, sections)
        mp3_path = os.path.join(audio_dir, f"{sec_id}.mp3")
        narration = narration_map.get(sec_id, "")

        # MP3 없으면 무음 3초 생성
        if not os.path.isfile(mp3_path):
            mp3_path = _make_silent_audio(video_dir, frame_stem)

        out_video = os.path.join(video_dir, f"{frame_stem}.mp4")

        ok = build_section_video(
            png_path=frame_path,
            mp3_path=mp3_path,
            subtitle=narration,
            out_path=out_video,
            font_path=font_path
        )
        if ok:
            section_videos.append(out_video)

    if not section_videos:
        print("❌ 생성된 섹션 영상 없음")
        sys.exit(1)

    # 단순 컷 연결
    print(f"\n✂️ 영상 컷 연결 중...\n")
    merged_path = os.path.join(video_dir, "merged.mp4")
    if not concat_videos(section_videos, merged_path):
        sys.exit(1)

    # BGM 믹싱
    print(f"\n🎵 BGM 믹싱 중...\n")
    final_path = os.path.join(video_dir, "final.mp4")
    if not mix_bgm(merged_path, bgm_path, final_path):
        sys.exit(1)

    # 임시 파일 정리
    os.remove(merged_path)
    for v in section_videos:
        os.remove(v)

    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    print(f"\n✅ 최종 영상 완성!")
    print(f"   파일: {final_path}")
    print(f"   크기: {size_mb:.1f} MB")


def _guess_section_id(frame_stem: str, sections: list) -> str:
    """프레임 파일명으로부터 섹션 ID 추정"""
    # 파일명 패턴: 00_opening, 01_market_00, 02_sector,
    #              10_삼성전자_1_summary, 10_삼성전자_2_chart 등
    for sec in sections:
        sid = sec.get("id", "")
        # stock_/hidden_ 종목명이 파일명에 포함되어 있으면 매칭
        name = sid.replace("stock_", "").replace("hidden_", "")
        if name and name in frame_stem:
            return sid
        # opening, market_summary, sectors, ai_strategy, closing 직접 매칭
        if sid in frame_stem or frame_stem.startswith(sid[:6]):
            return sid

    # fallback: opening
    return sections[0].get("id", "opening") if sections else "opening"


def _make_silent_audio(tmp_dir: str, name: str) -> str:
    """MP3가 없을 경우 3초 무음 오디오 생성"""
    path = os.path.join(tmp_dir, f"silent_{name}.mp3")
    if not os.path.exists(path):
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "3",
            "-c:a", "libmp3lame",
            path
        ], capture_output=True)
    return path


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
