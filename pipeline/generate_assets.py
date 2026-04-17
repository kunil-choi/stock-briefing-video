# pipeline/generate_assets.py
"""
AI 주식 브리핑 — 에셋 생성 진입점
사용법: python pipeline/generate_assets.py [KO|ko|en]
"""
import os, sys, json

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from assets.builders import (
    build_opening,
    build_market_summary,
    build_sector,
    build_stock_cards,
    build_ai_strategy,
    build_closing,
)


def run(lang: str = "KO"):
    lang = lang.upper()

    root = os.path.join(_HERE, "..")
    script_path = os.path.join(root, "output", lang, "scripts", "script.json")
    out_dir = os.path.join(root, "output", lang, "frames")
    img_dir = os.path.join(root, "output", lang, "images")

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)

    if not os.path.isfile(script_path):
        print(f"❌ script.json을 찾을 수 없습니다: {script_path}")
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        data = json.load(f)

    sections = data.get("sections", [])
    print(f"📂 script.json 로드 완료 (섹션 수: {len(sections)})")

    asset_map = {"frames": [], "lang": lang}

    asset_map["frames"].append(build_opening(data, out_dir))
    asset_map["frames"].extend(build_market_summary(data, out_dir))
    asset_map["frames"].append(build_sector(data, out_dir))

    stock_secs = [
        s for s in sections
        if s.get("id", "").startswith("stock_") or s.get("id", "").startswith("hidden_")
    ]
    for i, sec in enumerate(stock_secs):
        sec_id = sec.get("id", f"stock_{i}")
        # ── 수정: data 서브키 없음, id에서 직접 종목명 추출 ──────────────
        name = sec_id.replace("stock_", "").replace("hidden_", "")
        prefix = f"{10 + i:02d}_{name}"
        frames = build_stock_cards(sec, out_dir, img_dir, prefix)
        asset_map["frames"].extend(frames)

    asset_map["frames"].append(build_ai_strategy(data, out_dir))
    asset_map["frames"].append(build_closing(data, out_dir))

    map_path = os.path.join(root, "output", lang, "asset_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료: {len(asset_map['frames'])}개 프레임 → {out_dir}")
    return asset_map


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
