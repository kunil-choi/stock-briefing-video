""" AI 주식 브리핑 — 동영상 합성  PNG 프레임 + MP3 오디오 → MP4 """
import os
import sys
import json
import re
import subprocess
import urllib.request

BGM_URL        = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
BGM_VOLUME     = 0.20
FONT_PATH      = "assets/fonts/NotoSansKR-Bold.ttf"
SUBTITLE_SIZE  = 34
SUBTITLE_COLOR = "white"
SUBTITLE_BOX_COLOR = "0x000000@0.55"
SUBTITLE_Y_BASE    = "h-160"

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

# ── 텍스트 변환 ───────────────────────────────────────────────────────────
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
    한글 숫자 표현 → 아라비아 숫자, 발음 표기 → 표준어로 복원.
    """

    # ── 1) 발음 교정 (가장 먼저 처리) ────────────────────────────────────
    # 주가 관련 발음 교정
    text = text.replace('주까',   '주가')
    text = text.replace('신고까', '신고가')
    text = text.replace('고까',   '고가')
    text = text.replace('저까',   '저가')

    # 영문 약어 복원
    text = text.replace('에이치비엠', 'HBM')
    text = text.replace('이티에프',   'ETF')
    text = text.replace('코스피',     'KOSPI')
    text = text.replace('코스닥',     'KOSDAQ')
    text = text.replace('에스케이',   'SK')
    text = text.replace('엘지',       'LG')
    text = text.replace('케이비',     'KB')
    text = text.replace('엔에이치',   'NH')

    # ── 2) 한글 숫자 → 아라비아 숫자 변환 ────────────────────────────────
    HNUMS = {
        '영': 0, '일': 1, '이': 2, '삼': 3, '사': 4,
        '오': 5, '육': 6, '칠': 7, '팔': 8, '구': 9,
    }

    def kor_to_int(s: str) -> int | None:
        """
        순수 한글 숫자 문자열을 정수로 변환.
        지원 패턴: 십/백/천/만/억 단위 조합.
        실패 시 None 반환.
        """
        s = s.strip()
        if not s:
            return None

        UNITS = {'십': 10, '백': 100, '천': 1_000}
        BIG   = {'만': 10_000, '억': 100_000_000}

        def _parse_chunk(chunk: str) -> int | None:
            """만/억 미만 구간(0~9999) 파싱"""
            if not chunk:
                return 0
            result = 0
            current = 0
            for ch in chunk:
                if ch in HNUMS:
                    current = HNUMS[ch]
                elif ch in UNITS:
                    result += (current if current else 1) * UNITS[ch]
                    current = 0
                else:
                    return None          # 알 수 없는 문자
            result += current
            return result

        # 억 단위 분리
        total = 0
        if '억' in s:
            idx = s.index('억')
            eok_part = _parse_chunk(s[:idx])
            if eok_part is None:
                return None
            total += eok_part * 100_000_000
            s = s[idx + 1:]

        # 만 단위 분리
        if '만' in s:
            idx = s.index('만')
            man_part = _parse_chunk(s[:idx])
            if man_part is None:
                return None
            total += man_part * 10_000
            s = s[idx + 1:]

        # 나머지
        rest = _parse_chunk(s)
        if rest is None:
            return None
        total += rest
        return total

    def format_number(n: int) -> str:
        """4자리 이상이면 콤마 포맷"""
        return f"{n:,}"

    # ── 2-a) 소수점 처리: "삼점삼" / "일점이오" → "3.3" / "1.25"
    # '점' 또는 '쩜' 앞뒤의 한글 숫자 처리
    def replace_decimal(m):
        int_kor = m.group(1)
        dec_kor = m.group(2)
        int_n = kor_to_int(int_kor)
        if int_n is None:
            return m.group(0)
        # 소수점 이하는 각 글자를 개별 숫자로
        dec_str = ""
        for ch in dec_kor:
            if ch in HNUMS:
                dec_str += str(HNUMS[ch])
            else:
                return m.group(0)
        return f"{int_n}.{dec_str}"

    # 패턴: 한글숫자 + (점|쩜) + 한글숫자
    KOR_NUM_PAT = r'[영일이삼사오육칠팔구십백천만억]+'
    text = re.sub(
        rf'({KOR_NUM_PAT})[점쩜]({KOR_NUM_PAT})',
        replace_decimal, text
    )

    # ── 2-b) 퍼센트 처리 ─────────────────────────────────────────────────
    # "삼퍼센트" / "일점이퍼센트"(소수점 이미 변환됨) / "플러스삼퍼센트" 등
    def replace_percent(m):
        prefix = m.group(1) or ""   # 플러스/마이너스
        num_str = m.group(2)        # 이미 아라비아 or 한글
        # 아라비아 숫자면 그대로
        if re.match(r'^[\d.]+$', num_str):
            sign = "+" if "플러스" in prefix else ("-" if "마이너스" in prefix else "")
            return f"{sign}{num_str}%"
        # 한글 숫자
        n = kor_to_int(num_str)
        if n is None:
            return m.group(0)
        sign = "+" if "플러스" in prefix else ("-" if "마이너스" in prefix else "")
        return f"{sign}{n}%"

    text = re.sub(
        r'(플러스|마이너스)?([\d.영일이삼사오육칠팔구십백천만억]+)퍼센트',
        replace_percent, text
    )

    # ── 2-c) 원화 금액 처리 ──────────────────────────────────────────────
    # "육만오천사백원" → "65,400원"
    def replace_won(m):
        kor = m.group(1)
        # 이미 아라비아 숫자인 경우
        if re.match(r'^[\d,]+$', kor):
            return m.group(0)
        n = kor_to_int(kor)
        if n is None:
            return m.group(0)
        return f"{format_number(n)}원"

    text = re.sub(rf'({KOR_NUM_PAT})원', replace_won, text)

    # ── 2-d) 남은 단독 한글 숫자 처리 ────────────────────────────────────
    # 예: "이십사 시간" → "24시간",  "오십퍼센트" (위에서 처리됨)
    # 단어 경계 기반으로 처리 (조사 앞 한글 숫자만)
    def replace_standalone_korean_num(m):
        kor = m.group(1)
        n = kor_to_int(kor)
        if n is None or n == 0:
            return m.group(0)
        return format_number(n)

    # 한글 숫자 뒤에 조사/단위가 오는 경우 변환
    UNITS_SUFFIX = r'(개|명|회|번|배|년|월|일|시|분|초|주|장|종목|시간|일간|주간|만에|번째)'
    text = re.sub(
        rf'({KOR_NUM_PAT})(?={UNITS_SUFFIX})',
        replace_standalone_korean_num, text
    )

    # ── 3) 부호 표기 정리 ────────────────────────────────────────────────
    text = re.sub(r'플러스\s*', '+', text)
    text = re.sub(r'마이너스\s*', '-', text)

    return text


# ── 자막 줄바꿈 처리 ──────────────────────────────────────────────────────
def _wrap_subtitle(text: str, max_chars: int = 28) -> str:
    """
    한 줄 최대 max_chars 글자 기준으로 자막을 줄바꿈합니다.
    ffmpeg drawtext는 \\n 으로 줄바꿈합니다.
    """
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + (1 if current else 0) <= max_chars:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return r"\n".join(lines)


# ── 섹션 영상 생성 ────────────────────────────────────────────────────────
def build_section_video(
    png_path: str,
    mp3_path: str,
    subtitle: str,
    out_path: str,
    font_path: str
) -> bool:
    """PNG + MP3 → 섹션 mp4 (자막 하단 중앙 고정, 여백 확보)"""
    duration = get_audio_duration(mp3_path)

    # 자막 전처리: 줄바꿈 적용 후 이스케이프
    wrapped  = _wrap_subtitle(subtitle, max_chars=30)
    safe_sub = _escape(wrapped)

    font_part = f"fontfile={font_path}:" if os.path.exists(font_path) else ""

    # boxborderw: 상하 16, 좌우 여백은 x 오프셋으로 확보
    drawtext = (
        f"drawtext={font_part}"
        f"text='{safe_sub}':"
        f"fontsize={SUBTITLE_SIZE}:"
        f"fontcolor={SUBTITLE_COLOR}:"
        f"box=1:boxcolor={SUBTITLE_BOX_COLOR}:boxborderw=16:"
        f"x=(w-text_w)/2:"
        f"y={SUBTITLE_Y_BASE}:"
        f"line_spacing=10"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-i", mp3_path,
        "-vf", drawtext,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-t", f"{duration:.3f}",
        out_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ 실패: {os.path.basename(out_path)}")
        print(result.stderr[-400:])
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
    """
    프레임 파일명으로부터 오디오 파일명(확장자 제외)을 결정합니다.
    """
    fixed = {
        "opening":    "opening",
        "market":     "market_summary",
        "sector":     "sectors",
        "ai_strategy":"ai_strategy",
        "closing":    "closing",
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
        if not name:
            continue
        # 이름이 프레임 파일명에 포함되는지 확인
        if not (frame_stem.startswith(name + "_") or f"_{name}_" in frame_stem or frame_stem == name):
            continue
        # 매칭된 종목 — suffix로 어떤 화면인지 결정
        for frame_suffix, audio_suffix in suffix_map.items():
            if frame_suffix in frame_stem:
                return f"{sid}{audio_suffix}"
        return sid

    return sections[0].get("id", "opening") if sections else "opening"


# ── 자막 텍스트 결정 ──────────────────────────────────────────────────────
def _resolve_subtitle(frame_stem: str, sections: list) -> str:
    """
    프레임에 맞는 자막 원문(narration)을 반환합니다.
    반환값은 _narration_to_subtitle 처리 전의 원문입니다.
    """
    # stock_ / hidden_ 섹션 매칭
    for sec in sections:
        sid = sec.get("id", "")
        if not (sid.startswith("stock_") or sid.startswith("hidden_")):
            continue
        name = sid.replace("stock_", "").replace("hidden_", "")
        if not name:
            continue
        if not (frame_stem.startswith(name + "_") or f"_{name}_" in frame_stem or frame_stem == name):
            continue
        # 화면 종류별 narration 선택
        if "_1_summary" in frame_stem:
            return sec.get("narration_summary") or sec.get("narration", "")
        elif "_2_chart" in frame_stem:
            return sec.get("narration_chart") or sec.get("narration", "")
        elif "_3_mention" in frame_stem:
            return sec.get("narration_mention") or sec.get("narration", "")
        return sec.get("narration", "")

    # 고정 섹션 매칭
    fixed = {
        "opening":    "opening",
        "market":     "market_summary",
        "sector":     "sectors",
        "ai_strategy":"ai_strategy",
        "closing":    "closing",
    }
    for key, sid in fixed.items():
        if key in frame_stem:
            for sec in sections:
                if sec.get("id") == sid:
                    return sec.get("narration", "")
            break

    # 매칭 실패 시 빈 문자열 대신 경고와 함께 첫 섹션 반환
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
    root        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    script_path = os.path.join(root, "output", lang, "scripts", "script.json")
    audio_dir   = os.path.join(root, "output", lang, "audio")
    video_dir   = os.path.join(root, "output", lang, "video")
    asset_map_path = os.path.join(root, "output", lang, "asset_map.json")
    bgm_path    = os.path.join(root, "assets", "music", "bgm.mp3")
    font_path   = os.path.join(root, FONT_PATH)

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
        frame_name  = os.path.basename(frame_path)
        frame_stem  = os.path.splitext(frame_name)[0]

        audio_id    = _resolve_audio_id(frame_stem, sections)
        mp3_path    = os.path.join(audio_dir, f"{audio_id}.mp3")

        narration   = _resolve_subtitle(frame_stem, sections)
        subtitle    = _narration_to_subtitle(narration)

        # 자막이 비어 있으면 프레임명을 힌트로 표시 (디버그용)
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
