#!/usr/bin/env python3
"""Download and optimise inline/featured images for the cloned site.

Local-hosted images are mirrored into assets/img/content as WebP. Third-party
images are left as remote URLs (they are mostly Google screenshots / old
promotional images embedded in legacy posts).
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import pickle
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "tools" / "data" / "raw.pkl"
CACHE = ROOT / "tools" / "cache" / "img"
OUT = ROOT / "assets" / "img" / "content"
MAP = ROOT / "tools" / "data" / "images.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
LOCAL_HOSTS = {"thegioimaynghienda.com", "www.thegioimaynghienda.com"}


def collect():
    urls = set()
    for page in pickle.load(open(RAW, "rb")):
        if page["image"]:
            urls.add(page["image"])
        for img in page["node"].find_all("img"):
            src = img.get("data-src") or img.get("src") or ""
            if src:
                urls.add(src)
    cleaned = {}
    for url in urls:
        url = url.split(" ")[0].strip()
        if not url.startswith("http"):
            continue
        host = urllib.parse.urlparse(url).netloc
        if host in LOCAL_HOSTS:
            cleaned[url] = True
    return sorted(cleaned)


def key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:14]


def download(url: str):
    k = key(url)
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"}:
        ext = ".jpg"
    path = CACHE / f"{k}{ext}"
    if path.exists() and path.stat().st_size > 100:
        return url, path
    for attempt in range(3):
        try:
            safe_url = urllib.parse.quote(url, safe=":/?&=#%+")
            req = urllib.request.Request(safe_url, headers={"User-Agent": UA, "Referer": "https://thegioimaynghienda.com/"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = resp.read()
            if len(data) < 100:
                raise ValueError("too small")
            path.write_bytes(data)
            return url, path
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                print(f"  skip {url}: {exc}", file=sys.stderr)
                return url, None
            time.sleep(1 + attempt)
    return url, None


def process(item):
    url, path = item
    if path is None:
        return url, None
    k = key(url)
    dst = OUT / f"{k}.webp"
    if not dst.exists():
        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                if getattr(im, "is_animated", False):
                    im.seek(0)
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
                if im.width > 1200:
                    h = round(im.height * 1200 / im.width)
                    im = im.resize((1200, h), Image.LANCZOS)
                if im.mode == "RGBA":
                    bg = Image.new("RGB", im.size, (255, 255, 255))
                    bg.paste(im, mask=im.split()[-1])
                    im = bg
                im.save(dst, "WEBP", quality=82, method=5)
        except Exception as exc:  # noqa: BLE001
            print(f"  image failed {url}: {exc}", file=sys.stderr)
            return url, None
    return url, f"assets/img/content/{k}.webp"


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    urls = collect()
    print(f"{len(urls)} local images")
    mapping = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        downloaded = list(pool.map(download, urls))
    print("downloaded; converting")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for url, rel in pool.map(process, downloaded):
            if rel:
                mapping[url] = rel
    MAP.write_text(json.dumps(mapping, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"mapped {len(mapping)}/{len(urls)} images")


if __name__ == "__main__":
    main()
