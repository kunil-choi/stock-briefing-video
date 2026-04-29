# pipeline/assets/image_fetch.py
import os
import requests
from typing import List, Optional
from .config import NEWS_IMAGE_FALLBACKS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _try_download(url: str, save_path: str) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        # ── [오류 6 수정] Content-Type 검증 추가 ──
        content_type = r.headers.get("Content-Type", "")
        if (
            r.status_code == 200
            and len(r.content) > 2000
            and "image" in content_type
        ):
            with open(save_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


def fetch_news_image(stock_name: str, img_dir: str,
                     extra_urls: Optional[List[str]] = None) -> Optional[str]:
    save_path = os.path.join(img_dir, f"news_{stock_name}.jpg")
    if os.path.exists(save_path):
        return save_path

    candidates = list(extra_urls or [])
    fallback = NEWS_IMAGE_FALLBACKS.get(stock_name)
    if fallback:
        candidates.append(fallback)

    for url in candidates:
        if _try_download(url, save_path):
            print(f"  [image] 이미지 성공: {stock_name} → {url[:60]}")
            return save_path

    print(f"  [image] 이미지 없음: {stock_name}")
    return None
