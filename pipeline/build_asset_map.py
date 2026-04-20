import os
import json
import glob

frames_dir = "output/KO/frames"
frames = sorted(glob.glob(os.path.join(frames_dir, "*.png")))
asset_map = {"frames": frames, "lang": "KO"}

out_path = "output/KO/asset_map.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(asset_map, f, ensure_ascii=False, indent=2)

print(f"✅ asset_map.json 생성 완료 ({len(frames)}개 프레임)")
for f in frames:
    print(f"   {f}")
