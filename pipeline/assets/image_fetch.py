# pipeline/assets/image_fetch.py
import os
import requests
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
        if r.status_code == 200 and len(r.content) > 2000:
            with open(save_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


def fetch_news_image(stock_name: str, img_dir: str,
                     extra_urls: list[str] = None) -> str | None:
    """
    우선순위: extra_urls → Wikimedia 로고 fallback → None
    성공 시 저장 경로 반환.
    """
    save_path = os.path.join(img_dir, f"news_{stock_name}.jpg")
    if os.path.exists(save_path):
        return save_path

    candidates = list(extra_urls or [])

    # Wikimedia / 공식 로고 fallback
    fallback = NEWS_IMAGE_FALLBACKS.get(stock_name)
    if fallback:
        candidates.append(fallback)

    for url in candidates:
        if _try_download(url, save_path):
            print(f"  [image] 수신 성공: {stock_name} ← {url[:60]}")
            return save_path

    print(f"  [image] 이미지 없음: {stock_name}")
    return None
