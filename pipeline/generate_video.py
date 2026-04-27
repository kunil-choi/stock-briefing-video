"""AI 주식 브리핑 — 동영상 합성  PNG 프레임 + MP3 오디오 → MP4"""
import os
import sys
import json
import re
import math
import subprocess
import tempfile
import urllib.request

BGM_URL            = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
BGM_VOLUME         = 0.20
FONT_PATH          = "assets/fonts/NotoSansKR-Bold.ttf"
SUBTITLE_SIZE      = 34
SUBTITLE_COLOR     = "white"
SUBTITLE_BOX_COLOR = "0x000000@0.55"
SUBTITLE_Y_BASE    = "h-160"
# 자막 한 줄 최대 글자 수 (한글 기준 약 20자 = 1920px 화면에 여백 포함)
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


# ── 내레이션 → 자막 텍스트 변환 ───────────────────────────────────────────
def _narration_to_subtitle(text: str) -> str:
    """TTS용 한글 발음 표기를 자막용 표준어·아라비아 숫자로 변환"""

    # 1) 발음 교정
    REPLACEMENTS = [
        ('주까',      '주가'),
        ('신고까',    '신고가'),
        ('고까',      '고가'),
        ('저까',      '저가'),
        ('에이치비엠','HBM'),
        ('이티에프',  'ETF'),
        ('코스피',    'KOSPI'),
        ('코스닥',    'KOSDAQ'),
        ('에스케이',  'SK'),
        ('엘지',      'LG'),
        ('케이비',    'KB'),
        ('엔에이치',  'NH'),
    ]
    for src, dst in REPLACEMENTS:
        text = text.replace(src, dst)

    # 2) 한글 숫자 → 아라비아 숫자
    HNUMS = {
        '영': 0, '일': 1, '이': 2, '삼': 3, '사': 4,
        '오': 5, '육': 6, '칠': 7, '팔': 8, '구': 9,
    }
    UNITS  = {'십': 10, '백': 100, '천': 1_000}
    BIG    = {'만': 10_000, '억': 100_000_000}
    KOR_PAT = r'[영일이삼사오육칠팔구십백천만억]+'

    def kor_to_int(s: str):
        s = s.strip()
        if not s:
            return None
        def _chunk(c):
            if not c:
                return 0
            res, cur = 0, 0
            for ch in c:
                if ch in HNUMS:
                    cur = HNUMS[ch]
                elif ch in UNITS:
                    res += (cur if cur else 1) * UNITS[ch]; cur = 0
                else:
                    return None
            return res + cur
        total = 0
        if '억' in s:
            i = s.index('억')
            v = _chunk(s[:i]);
            if v is None: return None
            total += v * 100_000_000; s = s[i+1:]
        if '만' in s:
            i = s.index('만')
            v = _chunk(s[:i])
            if v is None: return None
            total += v * 10_000; s = s[i+1:]
        v = _chunk(s)
        if v is None: return None
        return total + v

    # 소수점 처리: 삼점삼 / 삼쩜삼 → 3.3
    def repl_decimal(m):
        i_n = kor_to_int(m.group(1))
        if i_n is None: return m.group(0)
        dec = "".join(str(HNUMS[c]) for c in m.group(2) if c in HNUMS)
        if not dec: return m.group(0)
        return f"{i_n}.{dec}"
    text = re.sub(rf'({KOR_PAT})[점쩜]({KOR_PAT})', repl_decimal, text)

    # 퍼센트 처리
    def repl_pct(m):
        sign = "+" if "플러스" in (m.group(1) or "") else ("-" if "마이너스" in (m.group(1) or "") else "")
        num  = m.group(2)
        if re.match(r'^[\d.]+$', num):
            return f"{sign}{num}%"
        n = kor_to_int(num)
        return f"{sign}{n}%" if n is not None else m.group(0)
    text = re.sub(r'(플러스|마이너스)?([\d.영일이삼사오육칠팔구십백천만억]+)퍼센트', repl_pct, text)

    # 원화 금액
    def repl_won(m):
        kor = m.group(1)
        if re.match(r'^[\d,]+$', kor): return m.group(0)
        n = kor_to_int(kor)
        return f"{n:,}원" if n is not None else m.group(0)
    text = re.sub(rf'({KOR_PAT})원', repl_won, text)

    # 단위 앞 한글 숫자
    UNIT_SFX = r'(?=개|명|회|번|배|년|월|일|시|분|초|주|장|종목|시간|일간|주간|번째)'
    def repl_unit(m):
        n = kor_to_int(m.group(1))
        return f"{n:,}" if n else m.group(0)
    text = re.sub(rf'({KOR_PAT}){UNIT_SFX}', repl_unit, text)

    # 부호 정리
    text = re.sub(r'플러스\s*', '+', text)
    text = re.sub(r'마이너스\s*', '-', text)

    return text.strip()


# ── 자막 줄 분할 ──────────────────────────────────────────────────────────
def _split_lines(text: str, max_chars: int = SUBTITLE_MAX_CHARS) -> list[str]:
    """
    문장부호(。.!?…)와 접속사 앞에서 우선 끊고,
    그래도 max_chars를 초과하면 글자 수 기준으로 추가 분할.
    """
    # 1단계: 문장 단위 분할
    sentences = re.split(r'(?<=[.!?。…])\s*', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    lines = []
    for sent in sentences:
        # 2단계: max_chars 초과 시 공백 기준 재분할
        if len(sent) <= max_chars:
            lines.append(sent)
        else:
            words = sent.split()
            cur = ""
            for w in words:
                if len(cur) + len(w) + (1 if cur else 0) <= max_chars:
                    cur = (cur + " " + w).strip()
                else:
                    if cur:
                        lines.append(cur)
                    # 단어 자체가 max_chars 초과면 글자 단위로 강제 분할
                    while len(w) > max_chars:
                        lines.append(w[:max_chars])
                        w = w[max_chars:]
                    cur = w
            if cur:
                lines.append(cur)
    return lines


# ── SRT 파일 생성 ─────────────────────────────────────────────────────────
def _sec_to_srt_time(s: float) -> str:
    """초(float) → SRT 타임코드  00:00:00,000"""
    h  = int(s // 3600)
    m  = int((s % 3600) // 60)
    sc = int(s % 60)
    ms = int(round((s % 1) * 1000))
    return f"{h:02d}:{m:02d}:{sc:02d},{ms:03d}"


def _make_srt(subtitle_text: str, duration: float, srt_path: str):
    """
    자막 텍스트를 줄 단위로 분할하고 duration 을 균등 배분하여 SRT 파일 생성.
    마지막 자막은 duration 끝까지 표시.
    """
    lines = _split_lines(subtitle_text)
    if not lines:
        lines = [subtitle_text[:SUBTITLE_MAX_CHARS]] if subtitle_text else [""]

    n = len(lines)
    # 각 줄의 표시 시간 = 전체 duration / 줄 수  (최소 1.2초 보장)
    per = max(duration / n, 1.2)

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines):
            start = i * per
            # 마지막 줄은 duration 끝까지
            end   = duration if i == n - 1 else min((i + 1) * per, duration)
            # 끝 시간이 시작 시간보다 짧아지는 예외 방지
            if end <= start:
                end = start + 1.0
            f.write(f"{i+1}\n")
            f.write(f"{_sec_to_srt_time(start)} --> {_sec_to_srt_time(end)}\n")
            f.write(f"{line}\n\n")


# ── 섹션 영상 생성 (SRT 자막 방식) ───────────────────────────────────────
def build_section_video(
    png_path:  str,
    mp3_path:  str,
    subtitle:  str,
    out_path:  str,
    font_path: str
) -> bool:
    """PNG + MP3 → 섹션 MP4  (SRT 자막으로 순차 표시)"""
    duration = get_audio_duration(mp3_path)

    # 임시 SRT 파일 생성
    srt_fd, srt_path = tempfile.mkstemp(suffix=".srt")
    os.close(srt_fd)

    try:
        _make_srt(subtitle, duration, srt_path)

        # subtitles 필터 옵션
        font_opt = ""
        if os.path.exists(font_path):
            # ffmpeg subtitles 필터의 force_style 에서 폰트 파일 직접 지정은
            # ASS 스타일로만 가능 → FontName 으로 시스템 폰트명 지정 대신
            # fontsdir 옵션 사용
            font_dir = os.path.dirname(os.path.abspath(font_path))
            font_opt = f":fontsdir={font_dir}"

        sub_filter = (
            f"subtitles={srt_path}{font_opt}"
            f":force_style='"
            f"FontSize={SUBTITLE_SIZE},"
            f"PrimaryColour=&H00FFFFFF,"
            f"BackColour=&H8C000000,"
            f"BorderStyle=3,"
            f"Outline=0,"
            f"Shadow=0,"
            f"MarginV=60,"
            f"Alignment=2'"          # Alignment=2 → 하단 중앙
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

        print(f"  ✅ {os.path.basename(out_path)} ({duration:.1f}초, 자막 {len(_split_lines(subtitle))}줄)")
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
        print(f"  ❌ 영상 합치기 실패")
        print(result.stderr[-400:])
        return False
    print(f"  ✅ 합치기 완료")
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
        print(f"  ❌ BGM 믹싱 실패")
        print(result.stderr[-400:])
        return False
    print(f"  ✅ BGM 믹싱 완료")
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
            return sec.get("narration_summary") or sec.get("narration", "")
        elif "_2_chart" in frame_stem:
            return sec.get("narration_chart")   or sec.get("narration", "")
        elif "_3_mention" in frame_stem:
            return sec.get("narration_mention") or sec.get("narration", "")
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
    lang = lang.upper()
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

    # libass 설치 확인 (subtitles 필터 의존)
    probe = subprocess.run(
        ["ffmpeg", "-filters"],
        capture_output=True, text=True
    )
    if "subtitles" not in probe.stdout:
        print("⚠️  ffmpeg subtitles 필터 없음 → libass 설치 필요")
        print("   Ubuntu: sudo apt-get install -y libass-dev")

    section_videos = []
    print(f"\n🎬 섹션 영상 생성 시작\n")

    for frame_path in frames:
        frame_name = os.path.basename(frame_path)
        frame_stem = os.path.splitext(frame_name)[0]

        audio_id  = _resolve_audio_id(frame_stem, sections)
        mp3_path  = os.path.join(audio_dir, f"{audio_id}.mp3")
        narration = _resolve_subtitle(frame_stem, sections)
        subtitle  = _narration_to_subtitle(narration)

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
        try: os.remove(v)
        except Exception: pass

    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    print(f"\n✅ 최종 영상 완성! {size_mb:.1f} MB → {final_path}")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
