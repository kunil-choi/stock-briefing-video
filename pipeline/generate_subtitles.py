"""
pipeline/generate_subtitles.py
================================
ASS(Advanced SubStation Alpha) 자막 파일 생성 모듈

- 각 슬라이드의 오디오 길이에 맞춰 자막 타임라인을 자동 생성합니다.
- 나레이션이 나오는 타이밍에 동시에 자막이 화면 하단에 표출됩니다.
- 자막은 한글 맞춤법 준수, 숫자/영어 원문 표기, 뜻을 () 안에 병기합니다.
- 긴 자막은 적절한 길이로 자동 분할합니다.
"""
import os
import sys
import json
import subprocess
import math

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── ASS 스타일 정의 ────────────────────────────────────────────────────────

ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
Title: KBS 머니올라 자막

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,NotoSansCJK,42,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,24,1
Style: Highlight,NotoSansCJK,42,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,24,1
Style: Warning,NotoSansCJK,36,&H004040FF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,24,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

CHARS_PER_LINE = 45   # 자막 한 줄 최대 글자 수
MAX_LINES      = 2    # 자막 최대 줄 수


def _ts(seconds: float) -> str:
    """초를 ASS 타임코드 형식(H:MM:SS.CC)으로 변환합니다."""
    total = max(0.0, seconds)
    h     = int(total // 3600)
    m     = int((total % 3600) // 60)
    s     = int(total % 60)
    cs    = int((total - int(total)) * 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _get_audio_duration(mp3_path: str) -> float:
    """ffprobe로 MP3 파일 길이를 가져옵니다."""
    if not os.path.isfile(mp3_path):
        return 3.0
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            mp3_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 3.0


def _split_subtitle_text(text: str, max_chars: int = CHARS_PER_LINE,
                          max_lines: int = MAX_LINES) -> list:
    """
    자막 텍스트를 적절한 길이로 분할합니다.
    반환: 여러 자막 청크 리스트 (각 청크는 max_lines 줄 이하)
    """
    if not text:
        return []

    # 문장 단위로 우선 분할
    import re
    sentences = re.split(r'(?<=[.。!?])\s*', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks  = []
    current = ""

    for sent in sentences:
        test = current + (" " if current else "") + sent
        lines_needed = math.ceil(len(test) / max_chars)
        if lines_needed > max_lines and current:
            chunks.append(current)
            current = sent
        else:
            current = test

    if current:
        chunks.append(current)

    # 각 청크를 max_chars*max_lines 이하로 자르기
    final = []
    for chunk in chunks:
        if len(chunk) <= max_chars * max_lines:
            final.append(chunk)
        else:
            # 강제 분할
            for i in range(0, len(chunk), max_chars * max_lines):
                final.append(chunk[i:i + max_chars * max_lines])

    return final if final else [text[:max_chars * max_lines]]


def _format_ass_text(text: str) -> str:
    """ASS 텍스트 형식 처리: 줄바꿈 처리."""
    lines = []
    remaining = text
    while remaining:
        if len(remaining) <= CHARS_PER_LINE:
            lines.append(remaining)
            break
        cut = remaining[:CHARS_PER_LINE]
        lines.append(cut)
        remaining = remaining[CHARS_PER_LINE:]
    return r"\N".join(lines[:MAX_LINES])


def _make_dialogue_events(subtitle_text: str,
                           start_time: float,
                           duration: float,
                           style: str = "Default") -> list:
    """
    하나의 자막 텍스트를 duration에 맞게 분할하여 ASS Dialogue 이벤트 리스트를 반환합니다.
    """
    if not subtitle_text or duration <= 0:
        return []

    chunks = _split_subtitle_text(subtitle_text)
    if not chunks:
        return []

    events = []
    chunk_duration = duration / len(chunks)

    for i, chunk in enumerate(chunks):
        t_start = start_time + i * chunk_duration
        t_end   = t_start + chunk_duration - 0.08  # 약간의 갭
        ass_text = _format_ass_text(chunk)
        events.append(
            f"Dialogue: 0,{_ts(t_start)},{_ts(t_end)},{style},,0,0,0,,{ass_text}"
        )

    return events


def _build_subtitle_jobs(sections: list, lang: str) -> list:
    """
    script.json 섹션을 순회하여 자막 작업 목록을 생성합니다.
    반환: [(subtitle_text, mp3_path, label), ...]
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
            # summary
            subtitle = section.get("subtitle_summary", section.get("subtitle", ""))
            if subtitle:
                jobs.append((subtitle, f"{audio_base}/{sid}_summary.mp3", f"{label} [summary]", sid + "_summary"))

            # chart
            subtitle = section.get("subtitle_chart", section.get("subtitle", ""))
            if subtitle:
                jobs.append((subtitle, f"{audio_base}/{sid}_chart.mp3", f"{label} [chart]", sid + "_chart"))

            # mention
            mentions   = section.get("mentions", [])
            n_mentions = len(mentions)

            if n_mentions > 0:
                pages = max(1, (n_mentions + 2) // 3)
                if pages == 1:
                    subtitle = section.get("subtitle_mention", "")
                    if not subtitle and mentions:
                        subtitle = " ".join(
                            m.get("quote_subtitle", "") for m in mentions[:3]
                        )
                    if subtitle:
                        jobs.append((subtitle, f"{audio_base}/{sid}_mention.mp3",
                                     f"{label} [mention]", sid + "_mention"))
                else:
                    for p in range(pages):
                        field    = f"subtitle_mention_{p}"
                        subtitle = section.get(field, "")
                        if not subtitle:
                            page_items = mentions[p * 3: p * 3 + 3]
                            subtitle   = " ".join(
                                m.get("quote_subtitle", "") for m in page_items
                            )
                        if subtitle:
                            jobs.append((subtitle, f"{audio_base}/{sid}_mention_{p:02d}.mp3",
                                         f"{label} [mention_page{p}]", f"{sid}_mention_{p:02d}"))
            else:
                sub_0 = section.get("subtitle_mention_0", section.get("subtitle_mention", ""))
                sub_1 = section.get("subtitle_mention_1", "")
                sub_2 = section.get("subtitle_mention_2", "")
                if sub_1:
                    for p, sub in enumerate([sub_0, sub_1, sub_2]):
                        if sub:
                            jobs.append((sub, f"{audio_base}/{sid}_mention_{p:02d}.mp3",
                                         f"{label} [mention_page{p}]", f"{sid}_mention_{p:02d}"))
                elif sub_0:
                    jobs.append((sub_0, f"{audio_base}/{sid}_mention.mp3",
                                 f"{label} [mention]", sid + "_mention"))
        else:
            subtitle = section.get("subtitle", "")
            if subtitle:
                jobs.append((subtitle, f"{audio_base}/{sid}.mp3", label, sid))

    return jobs


def generate_ass(sections: list, lang: str, out_path: str,
                 frame_order: list = None):
    """
    ASS 자막 파일을 생성합니다.

    Args:
        sections:    script.json의 섹션 목록
        lang:        언어 코드 (KO)
        out_path:    출력 ASS 파일 경로
        frame_order: asset_map.json의 frames 순서 (선택사항, 타임라인 동기화용)
    """
    jobs = _build_subtitle_jobs(sections, lang)

    # 프레임 순서가 있으면 그에 맞춰 타임라인 재정렬
    ordered_jobs = []
    if frame_order:
        import re
        for frame_path in frame_order:
            stem = os.path.splitext(os.path.basename(frame_path))[0]
            # 프레임 스템으로 자막 작업 매칭
            matched = None
            for job in jobs:
                job_id = job[3]  # subtitle_id
                if job_id in stem or stem.endswith(job_id.split("_")[-1]):
                    matched = job
                    break
                # 더 정밀한 매칭
                if stem.replace("-", "_").endswith(job_id.replace("-", "_")):
                    matched = job
                    break
            if matched:
                ordered_jobs.append(matched)
            else:
                # 매칭 안 되면 무음 더미
                ordered_jobs.append(("", "", f"no_match:{stem}", stem))
    else:
        ordered_jobs = jobs

    events = []
    current_time = 0.0

    for subtitle_text, mp3_path, label, job_id in ordered_jobs:
        duration = _get_audio_duration(mp3_path) if mp3_path else 3.0

        if subtitle_text:
            # 클로징 섹션은 Warning 스타일 (빨간색 배경)
            style = "Warning" if "closing" in job_id else "Default"
            slide_events = _make_dialogue_events(
                subtitle_text, current_time, duration, style=style
            )
            events.extend(slide_events)
            print(f"  [subtitle] {label}: {duration:.1f}s, {len(slide_events)}개 이벤트")

        current_time += duration

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig") as f:
        f.write(ASS_HEADER)
        f.write("\n".join(events))
        f.write("\n")

    print(f"\n✅ ASS 자막 생성 완료: {out_path} ({len(events)}개 이벤트, 총 {current_time:.1f}초)")
    return out_path


def run(lang: str = "KO"):
    lang = lang.upper()

    script_path    = f"output/{lang}/scripts/script.json"
    asset_map_path = f"output/{lang}/asset_map.json"
    out_path       = f"output/{lang}/subtitles/subtitle.ass"

    if not os.path.isfile(script_path):
        print(f"❌ script.json 없음: {script_path}")
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    sections = script.get("sections", [])

    frame_order = None
    if os.path.isfile(asset_map_path):
        with open(asset_map_path, encoding="utf-8") as f:
            asset_map = json.load(f)
        frame_order = asset_map.get("frames", [])

    generate_ass(sections, lang, out_path, frame_order)


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
