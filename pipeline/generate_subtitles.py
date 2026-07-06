"""
pipeline/generate_subtitles.py
================================
ASS(Advanced SubStation Alpha) 자막 파일 생성 모듈

- 각 슬라이드의 오디오 길이에 맞춰 자막 타임라인을 자동 생성합니다.
- 나레이션이 나오는 타이밍에 동시에 자막이 화면 하단에 표출됩니다.
- 자막은 한글 맞춤법 준수, 숫자/영어 원문 표기, 뜻을 () 안에 병기합니다.
- 긴 자막은 적절한 길이로 자동 분할합니다.

프레임 파일명 → 오디오 ID 매핑 규칙:
  00_opening.png             → opening.mp3
  01_market_00.png           → market_summary.mp3
  02_sector.png              → sectors.mp3
  10_삼성전자_1_summary.png  → stock_삼성전자_summary.mp3
  10_삼성전자_2_chart.png    → stock_삼성전자_chart.mp3
  10_삼성전자_3_mention.png  → stock_삼성전자_mention.mp3
  10_삼성전자_3_mention_00.png → stock_삼성전자_mention_00.mp3
  90_extra_watchlist.png     → stock_추가관심종목.mp3
  91_today_pick.png          → stock_오늘의픽.mp3
  92_brokerage_report.png    → stock_증권사리포트.mp3
  98_ai_strategy.png         → ai_strategy.mp3
  99_closing.png             → closing.mp3
"""
import os
import sys
import json
import re
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

; MarginV=40 는 슬라이드 하단 190px 고정 자막 영역(pipeline/assets/config.py의
; SUBTITLE_ZONE_TOP)과 맞춰 카드/차트 등 콘텐츠와 겹치지 않도록 배치한 값입니다.
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,NotoSansCJK,42,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,40,1
Style: Highlight,NotoSansCJK,42,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,40,1
Style: Warning,NotoSansCJK,36,&H004040FF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

CHARS_PER_LINE = 45   # 자막 한 줄 최대 글자 수
MAX_LINES      = 2    # 자막 최대 줄 수
SILENT_DURATION = 3.0 # 오디오 없을 때 기본 슬라이드 길이

# summary+chart+mention 개별 카드가 아니라 단일 슬라이드로 렌더링되는 집계형 종목 섹션
AGGREGATE_STOCK_SECTION_IDS = {"stock_추가관심종목", "stock_오늘의픽", "stock_증권사리포트"}


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
    if not mp3_path or not os.path.isfile(mp3_path):
        return SILENT_DURATION
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            mp3_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        dur = float(result.stdout.strip())
        return dur if dur > 0 else SILENT_DURATION
    except Exception:
        return SILENT_DURATION


def _frame_stem_to_audio_id(stem: str, sections: list) -> str:
    """
    프레임 파일 스템(확장자 없는 파일명)을 오디오 ID로 변환합니다.

    매핑 규칙:
      00_opening             → opening
      01_market_00           → market_summary
      02_sector              → sectors
      NN_종목명_1_summary    → stock_종목명_summary
      NN_종목명_2_chart      → stock_종목명_chart
      NN_종목명_3_mention    → stock_종목명_mention
      NN_종목명_3_mention_MM → stock_종목명_mention_MM
      98_ai_strategy         → ai_strategy
      99_closing             → closing
    """
    # 고정 패턴 (정확한 매핑)
    fixed_patterns = [
        (r'^00_opening$',           'opening'),
        (r'^01_market',             'market_summary'),
        (r'^02_sector',             'sectors'),
        (r'^90_extra_watchlist$',   'stock_추가관심종목'),
        (r'^91_today_pick$',        'stock_오늘의픽'),
        (r'^92_brokerage_report$',  'stock_증권사리포트'),
        (r'^98_ai_strategy',        'ai_strategy'),
        (r'^99_closing',            'closing'),
    ]
    for pattern, audio_id in fixed_patterns:
        if re.match(pattern, stem):
            return audio_id

    # 종목 슬라이드 패턴: NN_종목명_1_summary / _2_chart / _3_mention / _3_mention_MM
    # 형식: {숫자2자리}_{종목명}_{슬라이드번호}_{타입}[_{페이지번호}]

    # mention 페이지 있음: NN_종목명_3_mention_MM
    m = re.match(r'^\d{2}_(.+)_3_mention_(\d{2})$', stem)
    if m:
        stock_name = m.group(1)
        page_num   = m.group(2)
        # sections에서 실제 ID 찾기
        sid = _find_stock_section_id(stock_name, sections)
        return f"{sid}_mention_{page_num}"

    # mention 단일 페이지: NN_종목명_3_mention
    # builders.py는 항상 _3_mention_{p:02d}.png 형식으로 생성하므로
    # 이 패턴은 실제로 도달 불가능하나, 방어적으로 _mention_00 반환
    m = re.match(r'^\d{2}_(.+)_3_mention$', stem)
    if m:
        stock_name = m.group(1)
        sid = _find_stock_section_id(stock_name, sections)
        return f"{sid}_mention_00"

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

    # fallback: 스템 그대로 반환
    print(f"  [subtitle] ⚠️ 매핑 실패 — 스템: {stem}")
    return stem


def _find_stock_section_id(stock_name: str, sections: list) -> str:
    """
    종목명으로 sections에서 실제 section ID를 찾습니다.
    예: '삼성전자' → 'stock_삼성전자' 또는 'hidden_삼성전자'
    """
    # 정확히 일치하는 section 찾기
    for sec in sections:
        sid = sec.get("id", "")
        if sid in (f"stock_{stock_name}", f"hidden_{stock_name}"):
            return sid

    # 부분 일치 (종목명이 section ID에 포함되는 경우)
    for sec in sections:
        sid = sec.get("id", "")
        if stock_name in sid:
            return sid

    # 못 찾으면 기본값
    return f"stock_{stock_name}"


def _build_subtitle_map(sections: list, lang: str) -> dict:
    """
    섹션 ID → 자막 텍스트 매핑 딕셔너리를 생성합니다.
    오디오 ID와 동일한 키를 사용합니다.

    반환: {
        'opening': '자막텍스트',
        'market_summary': '자막텍스트',
        'sectors': '자막텍스트',
        'stock_삼성전자_summary': '자막텍스트',
        'stock_삼성전자_chart': '자막텍스트',
        'stock_삼성전자_mention_00': '자막텍스트',   # 항상 숫자 포함 (builders와 통일)
        'stock_삼성전자_mention_01': '자막텍스트',
        'ai_strategy': '자막텍스트',
        'closing': '자막텍스트',
    }
    """
    subtitle_map = {}
    audio_base = f"output/{lang}/audio"

    for section in sections:
        sid   = section.get("id", "")
        if not sid:
            continue

        is_stock = (
            (sid.startswith("stock_") or sid.startswith("hidden_"))
            and sid not in AGGREGATE_STOCK_SECTION_IDS
        )

        if is_stock:
            # summary
            sub = section.get("subtitle_summary", section.get("subtitle", ""))
            if sub:
                subtitle_map[f"{sid}_summary"] = sub

            # chart
            sub = section.get("subtitle_chart", section.get("subtitle", ""))
            if sub:
                subtitle_map[f"{sid}_chart"] = sub

            # mention
            mentions   = section.get("mentions", [])
            n_mentions = len(mentions)

            # builders.py는 항상 _3_mention_{p:02d}.png 형식 사용 (단일도 _mention_00)
            # voice.py도 동일하게 항상 _mention_{p:02d}.mp3 형식
            # → subtitle_map 키도 항상 _mention_{p:02d} 형식으로 통일
            if n_mentions > 0:
                pages = max(1, (n_mentions + 2) // 3)
                for p in range(pages):
                    sub = section.get(f"subtitle_mention_{p}", "")
                    if not sub and pages == 1:
                        # 단일 페이지: subtitle_mention 필드도 허용
                        sub = section.get("subtitle_mention", "")
                    if not sub:
                        page_items = mentions[p * 3: p * 3 + 3]
                        sub = " | ".join(
                            m.get("quote_subtitle", "") for m in page_items
                            if m.get("quote_subtitle", "")
                        )
                    if sub:
                        subtitle_map[f"{sid}_mention_{p:02d}"] = sub
            else:
                # mentions 배열 없는 경우: subtitle_mention_N 직접 필드
                text_0 = section.get("subtitle_mention_0", section.get("subtitle_mention", ""))
                text_1 = section.get("subtitle_mention_1", "")
                text_2 = section.get("subtitle_mention_2", "")
                for p, sub in enumerate([text_0, text_1, text_2]):
                    if sub:
                        subtitle_map[f"{sid}_mention_{p:02d}"] = sub

        elif sid == "closing":
            # 클로징 슬라이드는 투자 유의사항 전문을 화면에 이미 글자로 표시하므로
            # (builders.build_closing 참고) 하단 자막을 중복으로 넣지 않는다.
            continue

        else:
            # 일반 섹션
            sub = section.get("subtitle", "")
            if sub:
                subtitle_map[sid] = sub

    return subtitle_map


def _split_subtitle_text(text: str) -> list:
    """
    자막 텍스트를 화면 표출 단위로 분할합니다.
    반환: 자막 청크 리스트
    """
    if not text:
        return []

    sentences = re.split(r'(?<=[.。!?])\s*', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks  = []
    current = ""

    for sent in sentences:
        test = (current + " " + sent).strip()
        lines_needed = math.ceil(len(test) / CHARS_PER_LINE)
        if lines_needed > MAX_LINES and current:
            chunks.append(current)
            current = sent
        else:
            current = test

    if current:
        chunks.append(current)

    # 최대 길이 초과 청크 강제 분할
    final = []
    max_len = CHARS_PER_LINE * MAX_LINES
    for chunk in chunks:
        if len(chunk) <= max_len:
            final.append(chunk)
        else:
            for i in range(0, len(chunk), max_len):
                sub = chunk[i:i + max_len].strip()
                if sub:
                    final.append(sub)

    return final if final else [text[:max_len]]


def _format_ass_text(text: str) -> str:
    """ASS 텍스트: 긴 줄을 \\N 으로 분리합니다."""
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
    자막 텍스트를 duration에 맞게 분할하여 ASS Dialogue 이벤트 리스트를 반환합니다.

    각 청크의 표출 시간은 균등 분할이 아니라 글자 수에 비례해 배분합니다.
    나레이션은 실제로 각 문장 길이에 비례한 시간이 걸리므로, 균등 분할 시
    짧은 문장은 자막이 필요 이상으로 오래 남고 긴 문장은 나레이션이 끝나기
    전에 자막이 먼저 사라지는 동기화 오차가 발생합니다.
    """
    if not subtitle_text or duration <= 0:
        return []

    chunks = _split_subtitle_text(subtitle_text)
    if not chunks:
        return []

    total_len = sum(len(c) for c in chunks) or 1
    events = []
    t_cursor = start_time

    for i, chunk in enumerate(chunks):
        chunk_duration = duration * (len(chunk) / total_len)
        t_start  = t_cursor
        t_end    = t_start + chunk_duration - 0.08
        ass_text = _format_ass_text(chunk)
        events.append(
            f"Dialogue: 0,{_ts(t_start)},{_ts(t_end)},{style},,0,0,0,,{ass_text}"
        )
        t_cursor += chunk_duration

    return events


def generate_ass(sections: list, lang: str, out_path: str,
                 frame_order: list = None, time_scale: float = 1.0):
    """
    ASS 자막 파일을 생성합니다.

    Args:
        sections:    script.json의 섹션 목록
        lang:        언어 코드 (KO)
        out_path:    출력 ASS 파일 경로
        frame_order: asset_map.json의 frames 순서 (프레임 파일 절대/상대 경로 목록)
        time_scale:  최종 영상이 배속 조정(atempo/setpts)된 경우의 보정 계수.
                     예) 영상을 1.05배속으로 줄였다면 1/1.05를 전달해 자막
                     타임라인도 동일 비율로 줄여야 나레이션과 어긋나지 않습니다.
    """
    subtitle_map = _build_subtitle_map(sections, lang)
    audio_base   = os.path.join("output", lang, "audio")

    print(f"\n  [subtitle] 자막 맵 키 수: {len(subtitle_map)}")
    for k in list(subtitle_map.keys())[:5]:
        print(f"    · {k}: {subtitle_map[k][:30]}...")
    if time_scale != 1.0:
        print(f"  [subtitle] 배속 보정 적용: time_scale={time_scale:.4f}")

    events       = []
    current_time = 0.0

    if not frame_order:
        # frame_order 없으면 subtitle_map 순서대로 처리
        print("  [subtitle] ⚠️ frame_order 없음 — subtitle_map 순서로 처리")
        for audio_id, subtitle_text in subtitle_map.items():
            mp3_path = os.path.join(audio_base, f"{audio_id}.mp3")
            duration = _get_audio_duration(mp3_path) * time_scale
            style    = "Warning" if "closing" in audio_id else "Default"
            slide_events = _make_dialogue_events(subtitle_text, current_time, duration, style)
            events.extend(slide_events)
            print(f"    {audio_id}: {duration:.1f}s, {len(slide_events)}개 이벤트")
            current_time += duration
    else:
        for frame_path in frame_order:
            stem     = os.path.splitext(os.path.basename(frame_path))[0]
            audio_id = _frame_stem_to_audio_id(stem, sections)
            mp3_path = os.path.join(audio_base, f"{audio_id}.mp3")
            duration = _get_audio_duration(mp3_path) * time_scale

            subtitle_text = subtitle_map.get(audio_id, "")

            style = "Warning" if "closing" in audio_id else "Default"

            if subtitle_text:
                slide_events = _make_dialogue_events(subtitle_text, current_time, duration, style)
                events.extend(slide_events)
                print(f"  [subtitle] {stem} → {audio_id}: {duration:.1f}s, {len(slide_events)}개 이벤트")
            else:
                print(f"  [subtitle] {stem} → {audio_id}: {duration:.1f}s, 자막 없음")

            current_time += duration

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig") as f:
        f.write(ASS_HEADER)
        f.write("\n".join(events))
        f.write("\n")

    mins = int(current_time // 60)
    secs = int(current_time % 60)
    print(f"\n✅ ASS 자막 생성 완료: {out_path}")
    print(f"   이벤트: {len(events)}개 | 총 길이: {mins}분 {secs}초")
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
        print(f"📋 asset_map 로드: {len(frame_order)}개 프레임")
    else:
        print(f"⚠️ asset_map.json 없음: {asset_map_path} — 섹션 순서로 처리")

    generate_ass(sections, lang, out_path, frame_order)


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
