# pipeline/generate_assets.py
"""
AI 주식 브리핑 — 에셋 생성 진입점
사용법: python pipeline/generate_assets.py [ko|en]
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


def run(lang: str = "ko"):
    base    = os.path.dirname(os.path.abspath(__file__))
    script  = os.path.join(base, "..", "output", lang, "scripts", "script.json")
    out_dir = os.path.join(base, "..", "output", lang, "frames")
    img_dir = os.path.join(base, "..", "output", lang, "images")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)

    with open(script, encoding="utf-8") as f:
        data = json.load(f)

    asset_map = {"frames": [], "lang": lang}

    # ── 오프닝 ──────────────────────────────────────────────────────────────
    asset_map["frames"].append(build_opening(data, out_dir))

    # ── 시장 요약 ────────────────────────────────────────────────────────────
    asset_map["frames"].extend(build_market_summary(data, out_dir))

    # ── 섹터 ────────────────────────────────────────────────────────────────
    asset_map["frames"].append(build_sector(data, out_dir))

    # ── 종목 카드 ────────────────────────────────────────────────────────────
    for i, sec in enumerate(data.get("stocks", [])):
        prefix = f"{10 + i:02d}_{sec.get('name','stock')}"
        frames = build_stock_cards(sec, out_dir, img_dir, prefix)
        asset_map["frames"].extend(frames)

    # ── AI 전략 ──────────────────────────────────────────────────────────────
    asset_map["frames"].append(build_ai_strategy(data, out_dir))

    # ── 클로징 ──────────────────────────────────────────────────────────────
    asset_map["frames"].append(build_closing(data, out_dir))

    # ── asset_map.json 저장 ──────────────────────────────────────────────────
    map_path = os.path.join(base, "..", "output", lang, "asset_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료: {len(asset_map['frames'])}개 프레임 생성 → {out_dir}")
    return asset_map


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "ko"
    run(lang)
