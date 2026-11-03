#!/usr/bin/env python3
"""Generate the static clone of thegioimaynghienda.com.

Inputs
  urls.html                  audit list (only "Giữ lại" rows are built)
  tools/data/raw.pkl         scraped pages (see tools/scrape.py)
  tools/data/images.json     mirrored image map (see tools/images.py)

Outputs
  <slug>/index.html          articles, products, projects
  category/<slug>/...        category archives + pagination
  tag/<slug>/...             tag archives + pagination
  nhan-bao-gia/...           blog archive + pagination
  sitemap.xml, robots.txt

The visual shell (header/footer) is taken from index.html's layout markers and
rebased for each page depth, so the site keeps a single source of truth.
"""
from __future__ import annotations

import html
import json
import math
import os
import pickle
import posixpath
import re
import shutil
import unicodedata
import urllib.parse
from collections import defaultdict
from copy import copy
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://thegioimaynghienda.com"
CSS_VER = "20261103b"
JS_VER = "20261103b"
PER_PAGE = 10

EXISTING = {
    "/": "index.html",
    "/gioithieu/": "gioithieu/index.html",
    "/san-pham/": "san-pham/index.html",
    "/dich-vu/": "dich-vu/index.html",
    "/bao-gia/": "bao-gia/index.html",
    "/lien-he/": "lien-he/index.html",
}

CATEGORIES = {
    "tin-tuc": {
        "name": "Tin tức",
        "desc": "Tin hoạt động của Thanh Long JSC, thị trường cát – đá xây dựng và thiết bị nghiền sàng.",
        "nav": "tin-tuc",
    },
    "tu-van-ky-thuat": {
        "name": "Tư vấn kỹ thuật",
        "desc": "Kinh nghiệm chọn máy, cấu hình trạm nghiền, công nghệ làm cát nhân tạo và vận hành dây chuyền.",
        "nav": "tin-tuc",
    },
    "du-an-cong-trinh": {
        "name": "Dự án – Công trình",
        "desc": "Các công trình, trạm nghiền và dây chuyền Thanh Long JSC đã cung cấp, lắp đặt và bàn giao.",
        "nav": "du-an",
    },
    "sua-chua-lap-dat": {
        "name": "Sửa chữa – Lắp đặt",
        "desc": "Dịch vụ bảo trì, sửa chữa, thay thế vật tư và nâng cấp trạm nghiền đá, cát nhân tạo.",
        "nav": "dich-vu",
    },
    "video": {
        "name": "Video",
        "desc": "Video vận hành trạm nghiền, máy làm cát nhân tạo và các dự án tiêu biểu của Thanh Long JSC.",
        "nav": "tin-tuc",
    },
    "hinh-anh": {
        "name": "Hình ảnh",
        "desc": "Hình ảnh trạm nghiền, thiết bị và công trình do Thanh Long JSC cung cấp, lắp đặt.",
        "nav": "tin-tuc",
    },
}

PRODUCT_CATEGORIES = {
    "may-nghien-da": "Máy nghiền đá",
    "may-lam-cat": "Máy làm cát nhân tạo",
}

FEATURED_CATEGORIES = {
    "design": "Design",
    "lookbook": "Lookbook",
}
FEATURED_MEMBERS = {
    "design": {"another-print-package", "awesome-pencil-poster", "fl3-print-package",
               "flatsome-poster-print", "magazine", "portfolio-typography"},
    "lookbook": {"flat-t-shirt-company", "lookbook-summer"},
}

MONTHS = {1: "Th1", 2: "Th2", 3: "Th3", 4: "Th4", 5: "Th5", 6: "Th6",
          7: "Th7", 8: "Th8", 9: "Th9", 10: "Th10", 11: "Th11", 12: "Th12"}


# ---------------------------------------------------------------------------
# audit + data loading
# ---------------------------------------------------------------------------
def load_audit():
    text = (ROOT / "urls.html").read_text(encoding="utf-8")
    start = text.index("const D=") + len("const D=")
    rows, _ = json.JSONDecoder().raw_decode(text[start:])
    kept, seen = [], set()
    for url, status, kind, in_sitemap, rec, reason, merge in rows:
        if rec != "Giữ lại":
            continue
        url = url.strip().rstrip(".")
        if url in seen:
            continue
        seen.add(url)
        kept.append({"url": url, "path": url_path(url), "kind": kind,
                     "reason": reason, "in_sitemap": in_sitemap, "merge": merge})
    return rows, kept


def url_path(url: str) -> str:
    path = urllib.parse.urlparse(url).path or "/"
    return unquote_path(path)


def unquote_path(path: str) -> str:
    try:
        return urllib.parse.unquote(path)
    except Exception:
        return path


def esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def slug_key(value: str) -> str:
    value = unicodedata.normalize("NFD", clean(value).lower())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def fmt_date(dt) -> str:
    return dt.strftime("%d/%m/%Y") if dt else ""


def nice_tag(slug: str) -> str:
    return slug.replace("-", " ").strip().capitalize()


# ---------------------------------------------------------------------------
# layout shell
# ---------------------------------------------------------------------------
URL_ATTR = re.compile(r'(\s(?:href|src))="(?!https?:|//|#|tel:|mailto:|data:|javascript:)([^"]*)"')


def layout_blocks():
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    out = {}
    for name in ("header", "footer"):
        m = re.search(rf"[ \t]*<!-- layout:{name}\b.*?<!-- /layout:{name} -->", source, re.S)
        if not m:
            raise SystemExit(f"missing layout:{name} marker in index.html")
        out[name] = m.group(0)
    return out


def rebase(snippet: str, depth: int) -> str:
    if depth == 0:
        return snippet
    prefix = "../" * depth

    def fix(m):
        url = m.group(2)
        if url == "./":
            url = ""
        return f'{m.group(1)}="{prefix}{url}"'

    return URL_ATTR.sub(fix, snippet)


def depth_of(rel_path: str) -> int:
    return max(0, len(Path(rel_path).parent.parts))


def rel_url(from_dir: str, target_path: str) -> str:
    """Relative URL from a page directory to an internal path."""
    frm = from_dir.strip("/")
    tgt = target_path.strip("/")
    rel = posixpath.relpath("." if not tgt else tgt, "." if not frm else frm)
    if target_path.endswith("/"):
        if rel == ".":
            return "./"
        return rel + "/"
    return rel


def page_shell(*, path: str, title: str, description: str, canonical: str,
               body: str, nav: str, jsonld: list | None = None,
               noindex: bool = False, og_type: str = "website",
               image: str = "") -> str:
    rel_path = output_path(path)
    depth = depth_of(rel_path)
    parts = layout_blocks()
    header = rebase(parts["header"], depth)
    footer = rebase(parts["footer"], depth)
    og_image = image or "assets/img/sandvik.webp"
    if not og_image.startswith("http"):
        og_image = BASE + "/" + og_image.lstrip("/")
    ld = ""
    if jsonld:
        ld = '<script type="application/ld+json">\n' + json.dumps(jsonld, ensure_ascii=False, indent=2) + "\n</script>"
    robots = '\n  <meta name="robots" content="noindex,follow">' if noindex else ""
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">{robots}
  <meta property="og:locale" content="vi_VN">
  <meta property="og:type" content="{og_type}">
  <meta property="og:site_name" content="Thế Giới Máy Nghiền Đá">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta name="theme-color" content="#0059b1">
  <link rel="icon" href="{'../' * depth}assets/img/logo.webp" type="image/webp">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&family=Open+Sans:wght@400;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{'../' * depth}assets/css/style.css?v={CSS_VER}">
  {ld}
</head>
<body id="top" data-page="{esc(nav)}">
{header}

  <main id="main">
{body}
  </main>

{footer}

  <script src="{'../' * depth}assets/js/main.js?v={JS_VER}" defer></script>
</body>
</html>
"""


def output_path(path: str) -> str:
    if path in EXISTING:
        return EXISTING[path]
    clean_path = path.strip("/")
    return (clean_path + "/index.html") if clean_path else "index.html"


def write_page(path: str, content: str):
    out = ROOT / output_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def page_dir(path: str) -> str:
    return str(Path(output_path(path)).parent).replace(".", "").strip("/")


# ---------------------------------------------------------------------------
# content model
# ---------------------------------------------------------------------------
def build_model(raw, kept):
    image_map = json.loads((ROOT / "tools" / "data" / "images.json").read_text(encoding="utf-8"))
    kept_tags = {k["path"].rstrip("/").split("/tag/")[-1]: k for k in kept if k["kind"] == "tag"}
    kept_paths = {k["path"] for k in kept}

    posts = [p for p in raw if p["kind"] == "post/page" and p["path"] not in EXISTING and p["path"] != "/nhan-bao-gia/"]
    products = [p for p in raw if p["kind"] == "product"]
    featured = [p for p in raw if p["kind"] == "featured_item" and p["path"] not in {"/featured_item/"}]

    # Duplicate detection: same headline + same publish date. The URL that is
    # the redirect target wins; the others become canonical aliases.
    groups = defaultdict(list)
    for p in posts:
        dt = parse_date(p["date"])
        if dt:
            groups[(slug_key(p["title"]), dt.date().isoformat())].append(p)
    primary_of = {}
    for key, group in groups.items():
        if len(group) == 1:
            primary_of[group[0]["path"]] = group[0]["path"]
            continue
        chosen = None
        for p in group:
            final_path = url_path(p["final_url"]) if p["final_url"].startswith("http") else p["final_url"]
            if p["path"] == final_path:
                chosen = p
                break
        chosen = chosen or group[0]
        for p in group:
            primary_of[p["path"]] = chosen["path"]

    post_by_path = {}
    for p in posts:
        dt = parse_date(p["date"])
        cats = [c for c in p["categories"] if c["slug"] in CATEGORIES]
        tags = [t for t in p["tags"] if t["slug"] in kept_tags]
        primary_cat = cats[0]["slug"] if cats else "tin-tuc"
        image = p.get("image") or ""
        mapped = image_map.get(image)
        if not mapped:
            for img in p["node"].find_all("img"):
                src = (img.get("data-src") or img.get("src") or "").split(" ")[0]
                if image_map.get(src):
                    mapped = image_map[src]
                    break
        post_by_path[p["path"]] = {
            **p,
            "dt": dt,
            "date_txt": fmt_date(dt),
            "categories_data": cats,
            "primary_cat": primary_cat,
            "tags_data": tags,
            "thumb": mapped or "",
            "is_primary": primary_of.get(p["path"], p["path"]) == p["path"],
            "primary_path": primary_of.get(p["path"], p["path"]),
            "is_article": bool(dt),
        }

    # Primary articles only, newest first.
    primary_posts = sorted([p for p in post_by_path.values() if p["is_primary"] and p["is_article"]],
                           key=lambda p: p["dt"], reverse=True)

    # Tag display names, from the corpus first.
    tag_names = {}
    for p in posts:
        for t in p["tags"]:
            if t["slug"] in kept_tags and t["name"]:
                name = clean(t["name"])
                tag_names.setdefault(t["slug"], name[:1].upper() + name[1:] if name else name)
    for slug in kept_tags:
        tag_names.setdefault(slug, nice_tag(slug))

    return {
        "image_map": image_map,
        "kept_tags": kept_tags,
        "kept_paths": kept_paths,
        "posts": post_by_path,
        "primary_posts": primary_posts,
        "products": products,
        "featured": featured,
        "tag_names": tag_names,
    }


# ---------------------------------------------------------------------------
# HTML sanitising
# ---------------------------------------------------------------------------
ALLOWED = {
    "p", "br", "hr", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table",
    "thead", "tbody", "tfoot", "tr", "th", "td", "blockquote", "figure",
    "figcaption", "img", "iframe", "a", "strong", "em", "b", "i", "u", "small",
    "code", "pre", "dl", "dt", "dd", "video", "source", "span", "div", "section",
}
DROP = {"script", "style", "form", "nav", "aside", "noscript", "svg", "button",
        "input", "select", "textarea", "link", "meta"}


def sanitize(node, *, from_dir: str, model, image_map: dict) -> str:
    if node is None:
        return ""
    soup = BeautifulSoup(str(node), "lxml")
    root = soup.body or soup
    for tag in root.find_all(list(DROP)):
        tag.decompose()
    for sel in (".social-icons", ".share", ".entry-meta", ".entry-header", ".author-box",
                ".post-navigation", ".related-posts", ".related", ".comments-area",
                ".comment-respond", ".nav-links", ".yarpp-related", ".heateor_sss_sharing_container",
                ".crunchify-social", ".post-share", ".blog-share"):
        for tag in root.select(sel):
            tag.decompose()
    for comment in root.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    allowed_tags = ALLOWED
    for tag in list(root.find_all(True)):
        if tag.parent is None or tag.decomposed:
            continue
        name = tag.name.lower()
        if name not in allowed_tags:
            tag.unwrap()
            continue
        attrs = {}
        if name == "a":
            href = (tag.get("href") or "").strip()
            new_href = internal_href(href, from_dir, model)
            if new_href is None:
                tag.unwrap()
                continue
            if not tag.get_text(strip=True) and not tag.find("img"):
                tag.decompose()
                continue
            if new_href in ("#", "mailto:#") or "enteryour@addresshere" in new_href:
                tag.unwrap()
                continue
            attrs["href"] = new_href
            if new_href.startswith(("http://", "https://")):
                attrs["rel"] = "noopener"
                attrs["target"] = "_blank"
        elif name == "img":
            src = (tag.get("data-src") or tag.get("src") or "").split(" ")[0]
            if not src:
                tag.decompose()
                continue
            mapped = image_map.get(src)
            if mapped:
                attrs["src"] = rel_url(from_dir, mapped)
            elif src.startswith(BASE) or src.startswith("/"):
                tag.decompose()
                continue
            else:
                attrs["src"] = src
            alt = clean(tag.get("alt"))
            if alt:
                attrs["alt"] = alt
            attrs["loading"] = "lazy"
            attrs["decoding"] = "async"
        elif name == "iframe":
            src = tag.get("src", "")
            if "youtube" in src or "vimeo" in src:
                attrs["src"] = src.replace("www.youtube.com", "www.youtube-nocookie.com")
                attrs["loading"] = "lazy"
                attrs["title"] = clean(tag.get("title")) or "Video"
                attrs["allowfullscreen"] = ""
                attrs["referrerpolicy"] = "no-referrer-when-downgrade"
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
        elif name == "a" and tag.get("name"):
            attrs["name"] = tag["name"]
        tag.attrs = attrs
        if name in {"div", "section", "span"}:
            if name == "span":
                tag.unwrap()
            else:
                tag.unwrap()

    # Drop empty paragraphs and images without source.
    for p in list(root.find_all("p")):
        if not p.get_text(strip=True) and not p.find(["img", "iframe", "video"]):
            p.decompose()
    for img in list(root.find_all("img")):
        if not img.get("src"):
            img.decompose()

    out = "".join(str(child) for child in root.contents)
    out = re.sub(r"<p>\s*</p>", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def internal_href(href: str, from_dir: str, model) -> str | None:
    if not href:
        return None
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return href if href.startswith(("#", "mailto:", "tel:")) else None
    if href.startswith("//"):
        return "https:" + href
    parsed = urllib.parse.urlparse(href)
    if parsed.scheme in ("http", "https"):
        if parsed.netloc not in ("thegioimaynghienda.com", "www.thegioimaynghienda.com"):
            return href
        path = unquote_path(parsed.path) or "/"
        if path in ("/wp-login.php", "/xmlrpc.php", "/feed/") or "/wp-admin" in path:
            return None
    else:
        path = unquote_path(parsed.path)
        if not path:
            return href if href.startswith("#") else None
        if not path.startswith("/"):
            path = "/" + path

    if not path.endswith("/") and "." not in Path(path).name:
        path += "/"
    if path in model["kept_paths"]:
        return rel_url(from_dir, path)
    # Alias/duplicate post -> canonical target.
    if path in model["posts"]:
        target = model["posts"][path]["primary_path"]
        return rel_url(from_dir, target)
    # Internal page that the audit did not keep: keep the words, drop the link.
    if path.startswith(("/category/", "/tag/", "/product/", "/featured_item",
                        "/author/", "/blocks/", "/shop/", "/cart", "/checkout",
                        "/my-account", "/classic-shop", "/trang-chu")):
        return None
    if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}:
        return None
    if path == "/":
        return rel_url(from_dir, "/")
    return None


# ---------------------------------------------------------------------------
# cards + listings
# ---------------------------------------------------------------------------
def thumb_src(post, from_dir: str) -> str:
    if post.get("thumb"):
        return rel_url(from_dir, post["thumb"])
    return rel_url(from_dir, "assets/img/hero-plant.webp")


def post_card(post, from_dir: str, *, meta: str | None = None) -> str:
    dt = post.get("dt")
    date_badge = ""
    date_text = ""
    if dt:
        date_badge = f'<span class="date"><b>{dt.day:02d}</b>{MONTHS[dt.month]}</span>'
        date_text = fmt_date(dt)
    cat = meta
    if cat is None:
        cat = CATEGORIES[post["primary_cat"]]["name"] if post.get("primary_cat") in CATEGORIES else "Tin tức"
    meta_line = " · ".join(x for x in (date_text, cat) if x)
    return f"""<a class="post reveal" href="{esc(rel_url(from_dir, post['path']))}">
            <div class="post__img"><img src="{esc(thumb_src(post, from_dir))}" alt="{esc(post['title'])}" width="640" height="400" loading="lazy">{date_badge}</div>
            <h3>{esc(post['title'])}</h3>
            <p class="post__meta"><svg class="ico"><use href="#i-clock"/></svg>{esc(meta_line)}</p>
          </a>"""


def product_card(product, from_dir: str, image_map: dict) -> str:
    image = image_map.get(product.get("image", ""))
    if not image:
        for img in product["node"].find_all("img"):
            src = (img.get("data-src") or img.get("src") or "").split(" ")[0]
            if image_map.get(src):
                image = image_map[src]
                break
    img = rel_url(from_dir, image) if image else rel_url(from_dir, "assets/img/vat-lieu.webp")
    return f"""<a class="product reveal" href="{esc(rel_url(from_dir, product['path']))}">
            <span class="product__img product__img--white"><img src="{esc(img)}" alt="{esc(product['title'])}" width="400" height="400" loading="lazy"></span>
            <span class="product__txt"><h4>{esc(product['title'])}</h4><p>Thiết bị nghiền sàng</p><span class="product__btn">Xem chi tiết</span></span>
          </a>"""


def page_url(base_path: str, page_no: int) -> str:
    if page_no <= 1:
        return base_path
    return base_path.rstrip("/") + f"/page/{page_no}/"


def pagination(base_path: str, current: int, total: int, from_dir: str) -> str:
    if total <= 1:
        return ""
    links = []
    prev_disabled = " is-disabled" if current == 1 else ""
    if current > 1:
        links.append(f'<a href="{esc(rel_url(from_dir, page_url(base_path, current - 1)))}" aria-label="Trang trước">‹</a>')
    else:
        links.append('<span class="is-disabled" aria-hidden="true">‹</span>')
    page_nos = sorted({1, total, *range(max(1, current - 2), min(total, current + 2) + 1)})
    previous = 0
    for n in page_nos:
        if n - previous > 1:
            links.append('<span class="gap" aria-hidden="true">…</span>')
        if n == current:
            links.append(f'<span class="is-active" aria-current="page">{n}</span>')
        else:
            links.append(f'<a href="{esc(rel_url(from_dir, page_url(base_path, n)))}">{n}</a>')
        previous = n
    if current < total:
        links.append(f'<a href="{esc(rel_url(from_dir, page_url(base_path, current + 1)))}" aria-label="Trang sau">›</a>')
    else:
        links.append('<span class="is-disabled" aria-hidden="true">›</span>')
    return '<nav class="pagination" aria-label="Phân trang">' + "".join(links) + "</nav>"


def crumbs(items, from_dir: str) -> str:
    out = []
    for name, path in items:
        if path is None:
            out.append(f'<li><span aria-current="page">{esc(name)}</span></li>')
        else:
            out.append(f'<li><a href="{esc(rel_url(from_dir, path))}">{esc(name)}</a></li>')
    return '<ol class="crumbs" aria-label="Breadcrumb">' + "".join(out) + "</ol>"


def cta_band(from_dir: str) -> str:
    return f"""    <section class="cta-band">
      <div class="container cta-band__in">
        <div><h2>Cần tư vấn cấu hình trạm nghiền?</h2><p>Gửi công suất, vật liệu và sản phẩm đầu ra — kỹ sư Thanh Long sẽ đề xuất phương án phù hợp.</p></div>
        <div class="cta-band__btns"><a class="button button--white" href="{esc(rel_url(from_dir, '/bao-gia/'))}">Nhận báo giá</a><a class="button button--ghost" href="tel:0912712772">0912 712 772</a></div>
      </div>
    </section>"""


def archive_page(*, base_path: str, page_no: int, total_pages: int, h1: str,
                  intro: str, posts: list, from_dir: str, crumbs_items,
                  canonical: str, title: str, description: str,
                  nav: str, noindex: bool, item_label: str = "bài viết") -> str:
    cards = "\n          ".join(post_card(p, from_dir) for p in posts)
    empty = '<p class="list-empty" hidden>Không tìm thấy bài viết phù hợp.</p>'
    if not posts:
        empty = '<p class="list-empty">Chưa có bài viết trong chuyên mục này.</p>'
    pager = pagination(base_path, page_no, total_pages, from_dir)
    count = len(posts)
    list_tools = f"""<div class="list-tools reveal">
          <p>{count} {item_label} · trang {page_no}/{max(total_pages, 1)}</p>
        </div>""" if posts else ""
    body = f"""    <div class="page-title">
      <div class="container">
        <h1>{esc(h1)}</h1>
        {crumbs(crumbs_items, from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <p class="intro reveal">{intro}</p>
        {list_tools}
        <div class="posts posts--3">
          {cards}
        </div>
        {empty}
        {pager}
      </div>
    </section>
{cta_band(from_dir)}"""
    item_list = {
        "@type": "ItemList",
        "numberOfItems": len(posts),
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1,
             "url": BASE + p["path"], "name": p["title"]}
            for i, p in enumerate(posts)
        ],
    }
    jsonld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n,
                              "item": BASE + (pth or canonical)} for i, (n, pth) in enumerate(crumbs_items)]},
        {"@context": "https://schema.org", "@type": "CollectionPage",
         "name": h1, "description": description, "url": canonical,
         "mainEntity": item_list},
    ]
    return page_shell(path=base_path if page_no == 1 else page_url(base_path, page_no),
                      title=title, description=description, canonical=canonical,
                      body=body, nav=nav, jsonld=jsonld, noindex=noindex)


# ---------------------------------------------------------------------------
# generation
# ---------------------------------------------------------------------------
def main():
    rows, kept = load_audit()
    raw = pickle.load(open(ROOT / "tools" / "data" / "raw.pkl", "rb"))
    model = build_model(raw, kept)
    image_map = model["image_map"]
    primary_posts = model["primary_posts"]
    post_by_path = model["posts"]

    routes = {}  # path -> {"kind", "canonical", "title", ...}

    def add_route(path, kind, title, **kw):
        routes[path] = {"path": path, "kind": kind, "title": title, **kw}

    for path, rel in EXISTING.items():
        add_route(path, "existing", "Trang chủ" if path == "/" else Path(rel).parent.name, existing=True)

    # --- posts -------------------------------------------------------------
    for path, post in post_by_path.items():
        add_route(path, "post", post["title"], post=post,
                  canonical=post["path"] if post["is_primary"] else post["primary_path"],
                  index=post["is_primary"] and post["is_article"])

    # --- categories + pagination ------------------------------------------
    cat_pages = {}
    for slug, meta in CATEGORIES.items():
        members = [p for p in primary_posts if any(c["slug"] == slug for c in p["categories_data"])]
        total = max(1, math.ceil(len(members) / PER_PAGE))
        cat_pages[slug] = (members, total)
        base = f"/category/{slug}/"
        add_route(base, "category", meta["name"], members=members, total=total, slug=slug, index=True)
        for n in range(2, total + 1):
            add_route(page_url(base, n), "pagination", f"{meta['name']} – Trang {n}",
                      members=members, total=total, page=n, base=base, slug=slug, index=False)

    # --- blog archive ------------------------------------------------------
    blog_members = primary_posts
    blog_total = max(1, math.ceil(len(blog_members) / PER_PAGE))
    add_route("/nhan-bao-gia/", "blog", "Tin tức & tư vấn", members=blog_members,
              total=blog_total, index=True)
    for n in range(2, blog_total + 1):
        add_route(f"/nhan-bao-gia/page/{n}/", "blog-pagination", f"Tin tức & tư vấn – Trang {n}",
                  members=blog_members, total=blog_total, page=n, base="/nhan-bao-gia/", index=False)

    # --- tags --------------------------------------------------------------
    tag_members = defaultdict(list)
    for p in primary_posts:
        for t in p["tags_data"]:
            tag_members[t["slug"]].append(p)
    tag_pages = {}
    for slug in model["kept_tags"]:
        members = sorted(tag_members.get(slug, []), key=lambda p: p["dt"], reverse=True)
        total = max(1, math.ceil(len(members) / PER_PAGE))
        tag_pages[slug] = (members, total)
        name = model["tag_names"].get(slug, nice_tag(slug))
        base = f"/tag/{slug}/"
        add_route(base, "tag", name, members=members, total=total, slug=slug, index=True)
        for n in range(2, total + 1):
            add_route(page_url(base, n), "tag-pagination", f"{name} – Trang {n}",
                      members=members, total=total, page=n, base=base, slug=slug, index=False)

    # --- products ----------------------------------------------------------
    for product in model["products"]:
        add_route(product["path"], "product", product["title"], product=product, index=True)
    for slug, name in PRODUCT_CATEGORIES.items():
        add_route(f"/product-category/{slug}/", "product-category", name,
                  members=model["products"], slug=slug, index=True)

    # --- featured items ----------------------------------------------------
    for item in model["featured"]:
        if item["path"].startswith("/featured_item_category/"):
            continue
        add_route(item["path"], "featured", item["title"], item=item, index=False)
    add_route("/featured_item/", "featured-archive", "Dự án tiêu biểu",
              members=[i for i in model["featured"] if not i["path"].startswith("/featured_item_category/")],
              index=False)
    for slug, name in FEATURED_CATEGORIES.items():
        members = [i for i in model["featured"]
                   if i["path"].startswith("/featured_item/")
                   and any(slug in (t["slug"] if isinstance(t, dict) else "") for t in [])]
        add_route(f"/featured_item_category/{slug}/", "featured-category", name,
                  members=[], slug=slug, index=False)

    model["routes"] = routes

    # ------------------------------------------------------------------
    # static pages that are not articles (theme demos etc.)
    # ------------------------------------------------------------------
    for path, post in post_by_path.items():
        if post["is_article"]:
            continue
        if routes.get(path, {}).get("kind", "post") != "post":
            continue
        from_dir = page_dir(path)
        body_html = sanitize(post["node"], from_dir=from_dir, model=model, image_map=image_map)
        title = post["title"]
        desc = post["description"] or f"{title} – Thế Giới Máy Nghiền Đá."
        body = f"""    <div class="page-title">
      <div class="container">
        <h1>{esc(title)}</h1>
        {crumbs([("Trang chủ", "/"), ("Báo giá" if path.startswith("/bao-gia/") else "Giới thiệu", "/bao-gia/" if path.startswith("/bao-gia/") else "/gioithieu/"), (title, None)], from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <article class="article-wrap">
          <div class="prose reveal">{body_html or '<p>Nội dung đang được cập nhật.</p>'}</div>
        </article>
      </div>
    </section>
{cta_band(from_dir)}"""
        jsonld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title,
                   "url": BASE + path, "description": desc}]
        write_page(path, page_shell(path=path, title=title + " | Thế Giới Máy Nghiền Đá",
                                    description=desc, canonical=BASE + path, body=body,
                                    nav="bao-gia" if path.startswith("/bao-gia/") else "gioithieu",
                                    jsonld=jsonld, noindex=True))

    # ------------------------------------------------------------------
    # articles
    # ------------------------------------------------------------------
    by_cat = defaultdict(list)
    for p in primary_posts:
        for c in p["categories_data"]:
            by_cat[c["slug"]].append(p)

    for path, post in post_by_path.items():
        if not post["is_article"]:
            continue
        generate_article(path, post, model, by_cat, routes)

    # ------------------------------------------------------------------
    # category archives (+ pagination)
    # ------------------------------------------------------------------
    for slug, (members, total) in cat_pages.items():
        meta = CATEGORIES[slug]
        base = f"/category/{slug}/"
        for n in range(1, total + 1):
            from_dir = page_dir(base if n == 1 else page_url(base, n))
            start = (n - 1) * PER_PAGE
            chunk = members[start:start + PER_PAGE]
            page_path = base if n == 1 else page_url(base, n)
            cr = [("Trang chủ", "/"), (meta["name"], base if n > 1 else None)]
            if n > 1:
                cr.append((f"Trang {n}", None))
            title = meta["name"] if n == 1 else f"{meta['name']} – Trang {n}"
            out = archive_page(
                base_path=base, page_no=n, total_pages=total,
                h1=meta["name"] if n == 1 else f"{meta['name']} – Trang {n}",
                intro=meta["desc"] if n == 1 else f"Tiếp tục danh sách {meta['name'].lower()} – trang {n}/{total}.",
                posts=chunk, from_dir=from_dir, crumbs_items=cr,
                canonical=BASE + page_path, title=title + " | Thế Giới Máy Nghiền Đá",
                description=meta["desc"], nav=meta["nav"], noindex=n > 1)
            write_page(page_path, out)

    # ------------------------------------------------------------------
    # blog archive
    # ------------------------------------------------------------------
    for n in range(1, blog_total + 1):
        base = "/nhan-bao-gia/"
        page_path = base if n == 1 else f"/nhan-bao-gia/page/{n}/"
        from_dir = page_dir(page_path)
        chunk = blog_members[(n - 1) * PER_PAGE:n * PER_PAGE]
        cr = [("Trang chủ", "/"), ("Tin tức & tư vấn", base if n > 1 else None)]
        if n > 1:
            cr.append((f"Trang {n}", None))
        out = archive_page(
            base_path=base, page_no=n, total_pages=blog_total,
            h1="Tin tức & tư vấn" if n == 1 else f"Tin tức & tư vấn – Trang {n}",
            intro="Tổng hợp tin hoạt động, kinh nghiệm chọn thiết bị và tư vấn kỹ thuật từ Thanh Long JSC.",
            posts=chunk, from_dir=from_dir, crumbs_items=cr,
            canonical=BASE + page_path,
            title=("Tin tức & tư vấn | Thế Giới Máy Nghiền Đá" if n == 1 else f"Tin tức & tư vấn – Trang {n} | Thế Giới Máy Nghiền Đá"),
            description="Tin tức, kinh nghiệm và tư vấn kỹ thuật về máy nghiền đá, cát nhân tạo, dây chuyền nghiền sàng.",
            nav="tin-tuc", noindex=n > 1)
        write_page(page_path, out)

    # ------------------------------------------------------------------
    # tag archives
    # ------------------------------------------------------------------
    for slug, (members, total) in tag_pages.items():
        name = model["tag_names"].get(slug, nice_tag(slug))
        base = f"/tag/{slug}/"
        intro = (f"Tổng hợp {len(members)} bài viết về chủ đề <b>{esc(name)}</b> từ Thế Giới Máy Nghiền Đá."
                 if members else f"Chưa có bài viết cho chủ đề <b>{esc(name)}</b>.")
        desc = f"Bài viết về {name}: kinh nghiệm chọn máy, cấu hình trạm nghiền và tư vấn kỹ thuật từ Thanh Long JSC."
        for n in range(1, total + 1):
            page_path = base if n == 1 else page_url(base, n)
            from_dir = page_dir(page_path)
            chunk = members[(n - 1) * PER_PAGE:n * PER_PAGE]
            cr = [("Trang chủ", "/"), ("Tin tức", "/nhan-bao-gia/"), (name, base if n > 1 else None)]
            if n > 1:
                cr.append((f"Trang {n}", None))
            out = archive_page(
                base_path=base, page_no=n, total_pages=total,
                h1=name if n == 1 else f"{name} – Trang {n}",
                intro=intro if n == 1 else f"Tiếp tục danh sách bài viết về {name} – trang {n}/{total}.",
                posts=chunk, from_dir=from_dir, crumbs_items=cr,
                canonical=BASE + page_path,
                title=(f"{name} – Tổng hợp bài viết | Thế Giới Máy Nghiền Đá" if n == 1
                       else f"{name} – Trang {n} | Thế Giới Máy Nghiền Đá"),
                description=desc, nav="tin-tuc", noindex=n > 1, item_label="bài viết")
            write_page(page_path, out)

    # ------------------------------------------------------------------
    # products
    # ------------------------------------------------------------------
    for product in model["products"]:
        generate_product(product, model)

    for slug, name in PRODUCT_CATEGORIES.items():
        path = f"/product-category/{slug}/"
        from_dir = page_dir(path)
        cards = "\n          ".join(product_card(p, from_dir, image_map) for p in model["products"])
        body = f"""    <div class="page-title">
      <div class="container">
        <h1>{esc(name)}</h1>
        {crumbs([("Trang chủ", "/"), ("Sản phẩm", "/san-pham/"), (name, None)], from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <p class="intro reveal">Thiết bị do Thanh Long JSC cung cấp, lắp đặt và bảo hành tại Việt Nam. Liên hệ 0912 712 772 để được tư vấn cấu hình.</p>
        <div class="products">
          {cards}
        </div>
      </div>
    </section>
{cta_band(from_dir)}"""
        jsonld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": name,
                   "url": BASE + path, "description": f"Danh mục {name} – Thanh Long JSC."}]
        write_page(path, page_shell(path=path, title=f"{name} | Thế Giới Máy Nghiền Đá",
                                    description=f"Danh mục {name}: máy nghiền đá, máy làm cát nhân tạo, thiết bị nghiền sàng Thanh Long JSC.",
                                    canonical=BASE + path, body=body, nav="san-pham", jsonld=jsonld))

    # ------------------------------------------------------------------
    # featured items / categories
    # ------------------------------------------------------------------
    generate_featured(model, image_map)

    # ------------------------------------------------------------------
    # sitemap + robots
    # ------------------------------------------------------------------
    sitemap_urls = []
    for path, route in routes.items():
        if path in EXISTING:
            sitemap_urls.append(path)
        elif route.get("index"):
            sitemap_urls.append(path)
    # Stable order: home, fixed pages, categories, posts, tags, products.
    def sort_key(p):
        order = 0 if p == "/" else 1 if p in EXISTING else 2 if p.startswith("/category/") else 3 if p.startswith("/nhan-bao-gia") else 4 if p.startswith("/tag/") else 5
        return (order, p)
    sitemap_urls = sorted(set(sitemap_urls), key=sort_key)
    today = datetime.now().strftime("%Y-%m-%d")
    entries = []
    for p in sitemap_urls:
        priority = "1.0" if p == "/" else "0.7" if p.startswith("/tag/") else "0.8"
        entries.append(f"  <url><loc>{esc(BASE + p)}</loc><lastmod>{today}</lastmod><priority>{priority}</priority></url>")
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries) + "\n</urlset>\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: " + BASE + "/sitemap.xml\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # audit report
    # ------------------------------------------------------------------
    kept_paths = {k["path"] for k in kept}
    missing = sorted(p for p in kept_paths if p not in routes)
    extra = sorted(p for p in routes if p not in kept_paths and p not in EXISTING)
    report = {
        "kept": len(kept_paths),
        "generated_routes": len(routes),
        "missing_kept": missing,
        "extra_generated": extra,
        "primary_posts": len(primary_posts),
        "tags": len(tag_pages),
    }
    (ROOT / "tools" / "data" / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def generate_article(path, post, model, by_cat, routes):
    from_dir = page_dir(path)
    image_map = model["image_map"]
    body_html = sanitize(post["node"], from_dir=from_dir, model=model, image_map=image_map)
    if not body_html:
        body_html = f"<p>{esc(post['description'] or post['title'])}</p><p>Nội dung chi tiết đang được cập nhật. Quý khách cần tư vấn cấu hình, vui lòng gọi <a href=\"tel:0912712772\">0912 712 772</a>.</p>"

    cat_slug = post["primary_cat"]
    cat_name = CATEGORIES.get(cat_slug, {}).get("name", "Tin tức")
    cat_link = f"/category/{cat_slug}/" if cat_slug in CATEGORIES else "/category/tin-tuc/"
    cr = [("Trang chủ", "/"), (cat_name, cat_link), (post["title"], None)]

    tags_html = ""
    if post["tags_data"]:
        chips = " ".join(f'<a href="{esc(rel_url(from_dir, "/tag/" + t["slug"] + "/"))}">{esc(clean(t["name"]) or nice_tag(t["slug"]))}</a>'
                         for t in post["tags_data"] if ("/tag/" + t["slug"] + "/") in model["kept_paths"])
        if chips:
            tags_html = f'<div class="article__tags"><span>Chủ đề:</span>{chips}</div>'

    # related: three newest in the same primary category
    related = [p for p in by_cat.get(cat_slug, []) if p["path"] != path][:3]
    related_html = ""
    if related and post["is_primary"]:
        cards = "\n          ".join(post_card(p, from_dir) for p in related)
        related_html = f"""    <section class="section section--gray">
      <div class="container">
        <h2 class="block-title">Bài viết liên quan</h2>
        <div class="posts posts--3">
          {cards}
        </div>
      </div>
    </section>"""

    canonical = BASE + (post["path"] if post["is_primary"] else post["primary_path"])
    meta_line = " · ".join(x for x in (post["date_txt"],
        f'<a href="{esc(rel_url(from_dir, cat_link))}">{esc(cat_name)}</a>') if x)
    body = f"""    <div class="page-title">
      <div class="container">
        <h1>{esc(post['title'])}</h1>
        {crumbs(cr, from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <article class="article-wrap">
          <p class="article__meta"><svg class="ico"><use href="#i-clock"/></svg>{meta_line}</p>
          <div class="article__body prose reveal">{body_html}</div>
          {tags_html}
          <div class="article__cta">
            <div><b>Cần báo giá thiết bị hoặc cấu hình dây chuyền?</b><span>Gửi vật liệu, công suất và sản phẩm đầu ra để được tư vấn.</span></div>
            <a class="button button--primary" href="{esc(rel_url(from_dir, '/bao-gia/'))}">Nhận báo giá</a>
          </div>
        </article>
      </div>
    </section>
{related_html}
{cta_band(from_dir)}"""

    desc = post["description"] or f"{post['title']} – tư vấn kỹ thuật và báo giá từ Thanh Long JSC."
    dt = post["dt"]
    jsonld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "name": name,
              "item": BASE + (pth or post["path"])}
             for i, (name, pth) in enumerate(cr)
         ]},
        {"@context": "https://schema.org", "@type": "Article",
         "headline": post["title"], "description": desc,
         "image": [BASE + "/" + post["thumb"]] if post["thumb"] else [],
         "datePublished": dt.isoformat() if dt else "",
         "dateModified": dt.isoformat() if dt else "",
         "author": {"@type": "Organization", "name": "Thanh Long JSC"},
         "publisher": {"@type": "Organization", "name": "Thanh Long JSC",
                        "logo": {"@type": "ImageObject", "url": BASE + "/assets/img/logo.webp"}},
         "mainEntityOfPage": {"@type": "WebPage", "@id": BASE + post["path"]}},
    ]
    noindex = (not post["is_primary"]) or (not post["is_article"])
    page_title = post["title"] + " | Thế Giới Máy Nghiền Đá"
    write_page(path, page_shell(path=path, title=page_title, description=desc,
                                canonical=canonical, body=body, nav="tin-tuc" if cat_slug != "du-an-cong-trinh" else "du-an",
                                jsonld=jsonld, noindex=noindex, og_type="article",
                                image=post["thumb"]))


def generate_product(product, model):
    path = product["path"]
    from_dir = page_dir(path)
    body_html = sanitize(product["node"], from_dir=from_dir, model=model, image_map=model["image_map"])
    cr = [("Trang chủ", "/"), ("Sản phẩm", "/san-pham/"), (product["title"], None)]
    body = f"""    <div class="page-title">
      <div class="container">
        <h1>{esc(product['title'])}</h1>
        {crumbs(cr, from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <article class="article-wrap">
          <div class="article__body prose reveal">{body_html or '<p>Thông tin sản phẩm đang được cập nhật.</p>'}</div>
          <div class="article__cta">
            <div><b>Nhận catalogue và báo giá thiết bị</b><span>Kỹ sư Thanh Long tư vấn theo vật liệu và công suất thực tế.</span></div>
            <a class="button button--primary" href="{esc(rel_url(from_dir, '/bao-gia/'))}">Nhận báo giá</a>
          </div>
        </article>
      </div>
    </section>
{cta_band(from_dir)}"""
    desc = product["description"] or f"{product['title']} – thiết bị nghiền sàng Thanh Long JSC."
    jsonld = [{"@context": "https://schema.org", "@type": "Product",
               "name": product["title"], "description": desc,
               "brand": {"@type": "Brand", "name": "Thanh Long JSC"},
               "url": BASE + path}]
    write_page(path, page_shell(path=path, title=f"{product['title']} | Thế Giới Máy Nghiền Đá",
                                description=desc, canonical=BASE + path, body=body,
                                nav="san-pham", jsonld=jsonld, image=model["image_map"].get(product.get("image", ""), "")))


def generate_featured(model, image_map):
    # Build category membership from the scraped page markup.
    for item in model["featured"]:
        if item["path"].startswith("/featured_item_category/"):
            continue
        path = item["path"]
        from_dir = page_dir(path)
        body_html = sanitize(item["node"], from_dir=from_dir, model=model, image_map=image_map)
        title = item["title"]
        body = f"""    <div class="page-title">
      <div class="container">
        <h1>{esc(title)}</h1>
        {crumbs([("Trang chủ", "/"), ("Dự án", "/featured_item/"), (title, None)], from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <article class="article-wrap">
          <div class="prose reveal">{body_html or '<p>Nội dung đang được cập nhật.</p>'}</div>
        </article>
      </div>
    </section>
{cta_band(from_dir)}"""
        jsonld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title,
                   "url": BASE + path}]
        write_page(path, page_shell(path=path, title=f"{title} | Thế Giới Máy Nghiền Đá",
                                    description=f"{title} – dự án tiêu biểu của Thanh Long JSC.",
                                    canonical=BASE + path, body=body, nav="du-an",
                                    jsonld=jsonld, noindex=True))

    items = [i for i in model["featured"] if not i["path"].startswith("/featured_item_category/")]
    path = "/featured_item/"
    from_dir = page_dir(path)
    cards = "\n          ".join(post_card({**i, "dt": None, "primary_cat": "du-an-cong-trinh",
                                          "thumb": image_map.get(i.get("image", ""), "")}, from_dir, meta="Dự án")
                               for i in items)
    body = f"""    <div class="page-title">
      <div class="container">
        <h1>Dự án tiêu biểu</h1>
        {crumbs([("Trang chủ", "/"), ("Dự án", None)], from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <p class="intro reveal">Một số hình ảnh và hồ sơ dự án tiêu biểu của Thanh Long JSC.</p>
        <div class="posts posts--3">
          {cards}
        </div>
      </div>
    </section>
{cta_band(from_dir)}"""
    write_page(path, page_shell(path=path, title="Dự án tiêu biểu | Thế Giới Máy Nghiền Đá",
                                description="Dự án tiêu biểu của Thanh Long JSC.",
                                canonical=BASE + path, body=body, nav="du-an", noindex=True))

    for slug, name in FEATURED_CATEGORIES.items():
        path = f"/featured_item_category/{slug}/"
        from_dir = page_dir(path)
        members = [i for i in items if i["path"].rstrip("/").split("/")[-1] in FEATURED_MEMBERS[slug]]
        cards = "\n          ".join(post_card({**i, "dt": None, "primary_cat": "du-an-cong-trinh",
                                              "thumb": image_map.get(i.get("image", ""), "")}, from_dir, meta=name)
                                   for i in members)
        body = f"""    <div class="page-title">
      <div class="container">
        <h1>{esc(name)}</h1>
        {crumbs([("Trang chủ", "/"), ("Dự án", "/featured_item/"), (name, None)], from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <div class="posts posts--3">
          {cards}
        </div>
      </div>
    </section>
{cta_band(from_dir)}"""
        write_page(path, page_shell(path=path, title=f"{name} | Thế Giới Máy Nghiền Đá",
                                    description=f"Dự án {name} – Thanh Long JSC.",
                                    canonical=BASE + path, body=body, nav="du-an", noindex=True))


if __name__ == "__main__":
    main()
