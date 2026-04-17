# pipeline/generate_assets.py
"""
AI 주식 브리핑 — 에셋 생성 진입점
사용법: python generate_assets.py KO
"""
import os
import sys
import json

from assets.builders import (
    build_opening,
    build_market_summary,
    build_sector,
    build_stock_cards,
    build_ai_strategy,
    build_closing,
)


def run(lang: str = "KO"):
    # 대소문자 통일 (KO / ko 둘 다 허용)
    lang = lang.upper()

    base    = os.path.dirname(os.path.abspath(__file__))
    script  = os.path.join(base, "..", "output", lang, "scripts", "script.json")
    out_dir = os.path.join(base, "..", "output", lang, "frames")
    img_dir = os.path.join(base, "..", "output", lang, "images")

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)

    # ── script.json 로드 ────────────────────────────────────────────────────
    if not os.path.exists(script):
        print(f"❌ script.json 없음: {script}")
        sys.exit(1)

    with open(script, encoding="utf-8") as f:
        data = json.load(f)

    print(f"✅ script.json 로드 완료 — 섹션 수: {len(data.get('sections', []))}")

    asset_map = {"frames": [], "lang": lang}

    # ── sections 배열을 id 기준으로 분류 ────────────────────────────────────
    sections     = data.get("sections", [])
    market_secs  = [s for s in sections if s["id"] == "market_summary"]
    sector_secs  = [s for s in sections if s["id"] == "sectors"]
    stock_secs   = [s for s in sections
                    if s["id"].startswith("stock_") or s["id"].startswith("hidden_")]
    strategy_sec = next((s for s in sections if s["id"] == "ai_strategy"), None)
    opening_sec  = next((s for s in sections if s["id"] == "opening"), None)
    closing_sec  = next((s for s in sections if s["id"] == "closing"), None)

    # ── 오프닝 ──────────────────────────────────────────────────────────────
    asset_map["frames"].append(
        build_opening(opening_sec or {}, data, out_dir)
    )

    # ── 시장 요약 ────────────────────────────────────────────────────────────
    asset_map["frames"].extend(
        build_market_summary(market_secs, out_dir)
    )

    # ── 섹터 ────────────────────────────────────────────────────────────────
    if sector_secs:
        asset_map["frames"].append(
            build_sector(sector_secs[0], out_dir)
        )

    # ── 종목 카드 ────────────────────────────────────────────────────────────
    for i, sec in enumerate(stock_secs):
        name   = sec.get("label", f"stock_{i}").replace("관심종목 - ", "").replace("히든종목 - ", "")
        prefix = f"{10 + i:02d}_{name}"
        is_hidden = sec["id"].startswith("hidden_")
        frames = build_stock_cards(sec, is_hidden, out_dir, img_dir, prefix)
        asset_map["frames"].extend(frames)

    # ── AI 전략 ──────────────────────────────────────────────────────────────
    if strategy_sec:
        asset_map["frames"].append(
            build_ai_strategy(strategy_sec, out_dir)
        )

    # ── 클로징 ──────────────────────────────────────────────────────────────
    asset_map["frames"].append(
        build_closing(closing_sec or {}, out_dir)
    )

    # ── asset_map.json 저장 ──────────────────────────────────────────────────
    map_path = os.path.join(base, "..", "output", lang, "asset_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료: {len(asset_map['frames'])}개 프레임 생성 → {out_dir}")
    return asset_map


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
