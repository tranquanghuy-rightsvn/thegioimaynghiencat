#!/usr/bin/env python3
"""Scrape kept URLs from urls.html into tools/data/pages.json.

Only URLs marked "Giữ lại" in urls.html are fetched. The script is intentionally
dependency-light (requests is optional; urllib is the fallback) and caches every
response under tools/cache so re-runs are cheap.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://thegioimaynghienda.com"
CACHE = ROOT / "tools" / "cache"
DATA = ROOT / "tools" / "data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def load_audit():
    text = (ROOT / "urls.html").read_text(encoding="utf-8")
    start = text.index("const D=") + len("const D=")
    rows, _ = json.JSONDecoder().raw_decode(text[start:])
    return rows


def kept_urls(rows):
    out, seen = [], set()
    for url, status, kind, in_sitemap, rec, reason, merge in rows:
        if rec != "Giữ lại":
            continue
        url = url.strip()
        # Normalise the one malformed URL in the audit (".../.",).
        url = url.rstrip(".")
        if url in seen:
            continue
        seen.add(url)
        out.append({
            "url": url,
            "kind": kind,
            "in_sitemap": in_sitemap,
            "reason": reason,
            "merge": merge,
        })
    return out


def cache_name(url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", urllib.parse.urlparse(url).path).strip("-")[:80]
    return CACHE / f"{slug or 'home'}-{digest}.html"


def fetch(url: str, force=False) -> tuple[str, int, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = cache_name(url)
    meta = path.with_suffix(".url")
    if path.exists() and not force:
        final = meta.read_text(encoding="utf-8").strip() if meta.exists() else url
        return path.read_text(encoding="utf-8", errors="replace"), 200, final
    last_error = ""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "vi,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=40) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                final = resp.geturl()
                path.write_text(body, encoding="utf-8")
                meta.write_text(final, encoding="utf-8")
                time.sleep(0.05)
                return body, resp.status, final
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code in (404, 410):
                break
        except Exception as exc:  # noqa: BLE001 - network failures are expected
            last_error = repr(exc)
        time.sleep(1.2 * (attempt + 1))
    return "", 0, last_error


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def site_title(doc: BeautifulSoup) -> str:
    node = doc.select_one("h1.entry-title") or doc.select_one("h1")
    if node:
        return clean_text(node.get_text(" ", strip=True))
    og = doc.select_one('meta[property="og:title"]')
    title = clean_text(og.get("content")) if og else clean_text(doc.title.string if doc.title else "")
    return re.sub(r"\s*[–|-]\s*Thế Giới Máy Nghiền.*$", "", title).strip()


def description(doc: BeautifulSoup) -> str:
    for sel in ['meta[name="description"]', 'meta[property="og:description"]']:
        node = doc.select_one(sel)
        if node and clean_text(node.get("content")):
            return clean_text(node.get("content"))
    return ""


def body_node(doc: BeautifulSoup):
    entry = doc.select_one(".entry-content")
    if entry and len(entry.get_text(" ", strip=True)) > 250:
        return entry
    main = doc.select_one("main#main") or doc.select_one("main")
    if main:
        for sel in [".sidebar", ".widget-area", "#secondary", ".comments-area", ".comment-respond",
                    ".related", ".post-related", ".share", ".entry-meta", ".entry-header",
                    ".woocommerce-tabs", ".product_meta", ".breadcrumb", ".page-title",
                    ".blog-wrapper .row", ".navigation", ".nav-links"]:
            for node in main.select(sel):
                node.decompose()
        return main
    return doc.body


ALLOWED = {
    "p", "br", "hr", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table", "thead",
    "tbody", "tr", "th", "td", "blockquote", "figure", "figcaption", "img", "iframe",
    "a", "strong", "em", "b", "i", "u", "small", "code", "pre", "dl", "dt", "dd", "video",
    "source", "picture", "span", "div", "section",
}
DROP = {"script", "style", "form", "nav", "aside", "noscript", "svg", "button", "input", "select", "textarea"}


def sanitize(node, doc: BeautifulSoup, image_map: dict[str, str], link_prefix: str) -> str:
    if node is None:
        return ""
    for tag in node.find_all(list(DROP)):
        tag.decompose()
    for comment in node.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    for tag in node.find_all(True):
        name = tag.name.lower()
        if name not in ALLOWED:
            tag.unwrap()
            continue
        attrs = {}
        if name == "a":
            href = tag.get("href", "")
            if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                if href.startswith(BASE):
                    rel = href[len(BASE):]
                    attrs["href"] = link_prefix + rel.lstrip("/") if rel else link_prefix
                elif href.startswith("/"):
                    attrs["href"] = link_prefix + href.lstrip("/")
                elif not href.startswith("http"):
                    attrs["href"] = link_prefix + href
                else:
                    attrs["href"] = href
            elif href:
                attrs["href"] = href
        elif name == "img":
            src = tag.get("data-src") or tag.get("src") or ""
            if not src and tag.get("srcset"):
                src = tag["srcset"].split(",")[0].strip().split(" ")[0]
            if src:
                attrs["src"] = image_map.get(src, src)
            alt = clean_text(tag.get("alt"))
            if alt:
                attrs["alt"] = alt
            attrs["loading"] = "lazy"
            attrs["decoding"] = "async"
        elif name == "iframe":
            src = tag.get("src", "")
            if "youtube" in src or "vimeo" in src:
                attrs["src"] = src.replace("www.youtube.com", "www.youtube-nocookie.com")
                attrs["loading"] = "lazy"
                attrs["title"] = clean_text(tag.get("title")) or "Video"
                attrs["allowfullscreen"] = ""
            else:
                tag.decompose()
                continue
        elif name == "video" and tag.get("src"):
            attrs["src"] = tag["src"]
            attrs["controls"] = ""
        elif name == "source" and tag.get("src"):
            attrs["src"] = tag["src"]
            if tag.get("type"):
                attrs["type"] = tag["type"]
        tag.attrs = attrs
        if name in {"div", "section"}:
            tag.name = "div"
            tag.attrs = {"class": "prose__block"}

    # Turn bare divs into paragraphs would destroy tables/images; keep only if they
    # actually wrap block content, otherwise unwrap.
    for div in list(node.find_all("div", class_="prose__block")):
        if div.find(["div", "p", "figure", "table", "ul", "ol", "h2", "h3", "h4", "blockquote"]):
            div.attrs = {}
        else:
            div.unwrap()

    for img in node.find_all("img"):
        if not img.get("src"):
            img.decompose()

    out = "".join(str(child) for child in node.contents)
    out = re.sub(r"<p>\s*</p>", "", out)
    out = re.sub(r"<div>\s*</div>", "", out)
    return out.strip()


def extract(url: str, body_html: str):
    doc = BeautifulSoup(body_html, "lxml")
    title = site_title(doc)
    desc = description(doc)
    node = body_node(doc)

    cats, tags = [], []
    for a in doc.select('a[rel~="category"]'):
        href = a.get("href", "")
        if "/category/" in href:
            slug = href.rstrip("/").split("/category/")[-1]
            name = clean_text(a.get_text(" ", strip=True))
            if slug and name and not any(c["slug"] == slug for c in cats):
                cats.append({"slug": slug, "name": name})
    for a in doc.select('a[rel="tag"]'):
        href = a.get("href", "")
        if "/tag/" in href:
            slug = href.rstrip("/").split("/tag/")[-1]
            name = clean_text(a.get_text(" ", strip=True))
            if slug and name and not any(t["slug"] == slug for t in tags):
                tags.append({"slug": slug, "name": name})

    date = ""
    for sel in ['meta[property="article:published_time"]', "time[datetime]"]:
        el = doc.select_one(sel)
        if el:
            date = el.get("content") or el.get("datetime") or ""
            if date:
                break
    image = ""
    og = doc.select_one('meta[property="og:image"]')
    if og:
        image = og.get("content", "")

    return {
        "title": title,
        "description": desc,
        "date": date,
        "image": image,
        "categories": cats,
        "tags": tags,
        "node": node,
        "doc": doc,
    }


def url_path(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    return path or "/"


def is_content_kind(item):
    return item["kind"] in {"post/page", "product", "featured_item"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--kind", default="", help="comma-separated kinds to scrape")
    args = ap.parse_args()

    rows = load_audit()
    items = kept_urls(rows)
    if args.kind:
        kinds = set(args.kind.split(","))
        items = [i for i in items if i["kind"] in kinds]
    else:
        items = [i for i in items if is_content_kind(i)]
    if args.limit:
        items = items[: args.limit]
    DATA.mkdir(parents=True, exist_ok=True)

    def work(item):
        html_text, status, final = fetch(item["url"], force=args.force)
        return item, html_text, status, final

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(work, item) for item in items]
        for n, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            item, body, status, final = fut.result()
            print(f"[{n}/{len(items)}] {status} {item['url']}", flush=True)
            if not body:
                continue
            try:
                data = extract(item["url"], body)
            except Exception as exc:  # noqa: BLE001
                print("  parse failed:", exc, file=sys.stderr)
                continue
            results.append({
                **item,
                "path": url_path(item["url"]),
                "final_url": final,
                "status": status,
                "title": data["title"],
                "description": data["description"],
                "date": data["date"],
                "image": data["image"],
                "categories": data["categories"],
                "tags": data["tags"],
                "node": data["node"],
            })

    # Threads finish in random order; keep the audit order so builds are
    # reproducible (duplicate resolution and listing order depend on it).
    order = {item["url"]: n for n, item in enumerate(items)}
    results.sort(key=lambda r: order[r["url"]])

    # Save raw parsed nodes separately so sanitisation/downloading can iterate
    # without re-fetching. Pickle keeps BeautifulSoup nodes intact.
    import pickle
    with (DATA / "raw.pkl").open("wb") as fh:
        pickle.dump(results, fh)
    summary = [{k: v for k, v in r.items() if k != "node"} for r in results]
    (DATA / "pages.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {len(results)} pages")


if __name__ == "__main__":
    main()
