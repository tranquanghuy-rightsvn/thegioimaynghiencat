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
SITE = ROOT / "html"  # deployable website (Cloudflare serves this folder)
BASE = "https://thegioimaynghienda.com"
CSS_VER = "20261108a"
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

# ---------------------------------------------------------------------------
# Site structure (main menu). Every article belongs to exactly one section,
# listed in tools/data/structure.tsv (generate/edit with tools/classify.py).
# URLs follow the menu (/san-pham/<nhóm>/, /giai-phap/<...>/, /dich-vu/<...>/,
# /kien-thuc/<...>/). Sections that already had an indexed URL on the old site
# keep it (/category/tin-tuc/, tu-van-ky-thuat, du-an-cong-trinh,
# sua-chua-lap-dat); old pagination that no longer exists is 301-redirected.
# ---------------------------------------------------------------------------
MENU = [  # (key, label, landing page, data-nav used for the active state)
    ("thiet-bi", "Thiết bị", "/san-pham/", "san-pham"),
    ("giai-phap", "Giải pháp", "/giai-phap/", "giai-phap"),
    ("du-an", "Dự án", "/category/du-an-cong-trinh/", "du-an"),
    ("dich-vu", "Dịch vụ", "/dich-vu/", "dich-vu"),
    ("kien-thuc", "Kiến thức", "/nhan-bao-gia/", "tin-tuc"),
]
MENU_BY_KEY = {m[0]: m for m in MENU}

SECTIONS = {
    # Thiết bị: product cards (by name, from /san-pham/) + articles
    "tb-nghien-da": {"parent": "thiet-bi", "name": "Máy nghiền đá", "path": "/san-pham/may-nghien-da/",
                     "products": ["Máy nghiền hàm", "Máy nghiền côn", "Máy nghiền phản kích", "Máy nghiền búa"],
                     "intro": "Máy nghiền hàm, nghiền côn, phản kích và nghiền búa cho dây chuyền đá xây dựng 50 – 2.000 tấn/giờ: nghiền thô, nghiền trung và nghiền mịn theo loại đá và sản phẩm đầu ra."},
    "tb-lam-cat": {"parent": "thiet-bi", "name": "Máy làm cát nhân tạo VSI", "path": "/san-pham/may-lam-cat/",
                   "products": ["Máy làm cát VSI"],
                   "intro": "Máy làm cát VSI vo đá ra cát hạt khối, tỷ lệ cát 35 – 50%, tiền điện chỉ khoảng 3.750 đồng mỗi khối cát. Nghiền đá, sỏi sông, đá cát kết thành cát xây dựng."},
    "tb-rua-cat": {"parent": "thiet-bi", "name": "Máy rửa cát & thu hồi cát mịn", "path": "/san-pham/may-rua-cat/",
                   "products": ["Máy rửa cát dạng guồng", "Máy tách cát mịn", "Máy rửa cát McLanahan", "Máy ép bùn"],
                   "intro": "Máy rửa cát dạng guồng, máy tách cát mịn thu hồi hạt 0,16 – 3 mm, hệ thống rửa cát UltraWash của McLanahan và máy ép bùn xử lý nước thải sau rửa."},
    "tb-di-dong": {"parent": "thiet-bi", "name": "Trạm nghiền di động", "path": "/san-pham/tram-nghien-di-dong/",
                   "products": ["Trạm nghiền di động"],
                   "intro": "Trạm nghiền di động không cần móng, di chuyển theo mỏ và công trường: phù hợp mỏ đá trữ lượng nhỏ, rải rác, khu công nghiệp và nghiền tái chế tại chỗ."},
    "tb-tuyen-quang": {"parent": "thiet-bi", "name": "Thiết bị tuyển quặng", "path": "/san-pham/thiet-bi-tuyen-quang/",
                       "products": ["Máy nghiền bi"],
                       "intro": "Máy nghiền bi nghiền mịn quặng, khoáng sản và thiết bị tuyển từ, phân cấp cho trạm tuyển quặng sắt."},
    "tb-sang-phu-tung": {"parent": "thiet-bi", "name": "Sàng rung, cấp liệu & phụ tùng SKF", "path": "/san-pham/sang-rung-phu-tung/",
                         "products": ["Sàng rung phân loại", "Bạc đạn cầu rãnh sâu", "Bạc đạn đũa côn", "Bạc đạn tang trống", "Gối đỡ vòng bi SKF"],
                         "intro": "Sàng rung phân loại tách cỡ 0–5, 5–10, 10–20, 20–40 mm và vòng bi SKF chính hãng cho máy nghiền, sàng rung: bạc đạn cầu, đũa côn, tang trống, gối đỡ SNL, SY."},
    # Giải pháp: production lines by what the customer wants to make
    "gp-nghien-da": {"parent": "giai-phap", "name": "Dây chuyền nghiền đá xây dựng", "path": "/giai-phap/day-chuyen-nghien-da/",
                     "products": ["Dây chuyền nghiền đồng bộ"], "capacity": True,
                     "intro": "Dây chuyền nghiền sàng đá 1x2, 4x6, đá cấp phối, đá mi từ 50 đến 2.000 tấn/giờ, cung cấp trọn gói chìa khóa trao tay từ khảo sát mỏ, thiết kế, lắp đặt đến chuyển giao vận hành."},
    "gp-cat-nhan-tao": {"parent": "giai-phap", "name": "Dây chuyền sản xuất cát nhân tạo", "path": "/giai-phap/day-chuyen-cat-nhan-tao/",
                        "products": ["Dây chuyền cát nhân tạo", "Máy làm cát VSI"],
                        "intro": "Dây chuyền làm cát nhân tạo từ đá, sỏi sông, sỏi đồi và đá cát kết: nghiền, vo hạt bằng máy VSI, sàng phân loại, rửa và thu hồi cát mịn đạt tiêu chuẩn cát xây dựng."},
    "gp-rua-cat": {"parent": "giai-phap", "name": "Dây chuyền rửa cát", "path": "/giai-phap/day-chuyen-rua-cat/",
                   "products": ["Máy rửa cát dạng guồng", "Máy tách cát mịn", "Máy ép bùn"],
                   "intro": "Hệ thống rửa cát đồi, cát biển, cát lẫn cao lanh thành cát sạch: sàng rửa, guồng rửa, thu hồi cát mịn và xử lý nước thải, ép bùn để tuần hoàn nước."},
    "gp-tuyen-quang": {"parent": "giai-phap", "name": "Dây chuyền tuyển quặng sắt", "path": "/giai-phap/day-chuyen-tuyen-quang/",
                       "products": ["Dây chuyền nghiền quặng thô", "Máy nghiền bi"],
                       "intro": "Trạm nghiền, nghiền bi và tuyển từ quặng sắt: loại bỏ tạp chất, nâng hàm lượng quặng tinh cho mỏ quặng sắt, mangan và khoáng sản kim loại."},
    "gp-tai-che": {"parent": "giai-phap", "name": "Tái chế bê tông, phế thải xây dựng", "path": "/giai-phap/tai-che-phe-thai-xay-dung/",
                   "products": ["Trạm nghiền di động"],
                   "intro": "Nghiền tái chế bê tông, gạch đá thải từ công trường thành cốt liệu: giảm chi phí vận chuyển, đổ thải và tận dụng lại vật liệu ngay tại chỗ."},
    # Dự án
    "du-an": {"parent": "du-an", "name": "Dự án", "path": "/category/du-an-cong-trinh/",
              "intro": "Trạm nghiền đá, dây chuyền cát nhân tạo và trạm tuyển quặng Thanh Long JSC đã cung cấp, lắp đặt, chạy thử và bàn giao cho khách hàng."},
    # Dịch vụ
    "dv-bao-tri": {"parent": "dich-vu", "name": "Bảo trì, sửa chữa", "path": "/category/sua-chua-lap-dat/",
                   "intro": "Bảo trì định kỳ, sửa chữa, xử lý sự cố và thay thế vật tư cho máy nghiền hàm, nghiền côn, máy làm cát và trạm nghiền."},
    "dv-may-cu": {"parent": "dich-vu", "name": "Máy cũ & thanh lý", "path": "/dich-vu/may-cu-thanh-ly/",
                  "intro": "Kinh nghiệm mua máy nghiền đá, trạm nghiền cũ và thông tin thanh lý trạm nghiền."},
    # Kiến thức
    "kt-ky-thuat": {"parent": "kien-thuc", "name": "Kỹ thuật & vận hành", "path": "/category/tu-van-ky-thuat/",
                    "intro": "Chọn máy theo loại đá, quy trình khai thác và sản xuất đá xây dựng, vận hành an toàn và tối ưu năng suất máy nghiền."},
    "kt-cat-vlxd": {"parent": "kien-thuc", "name": "Cát nhân tạo & vật liệu xây dựng", "path": "/kien-thuc/cat-nhan-tao-vat-lieu-xay-dung/",
                    "intro": "Cát nhân tạo là gì, tiêu chuẩn cát nghiền, so sánh cát nhân tạo và cát tự nhiên, ứng dụng trong bê tông, cầu đường và gạch không nung."},
    "kt-thi-truong": {"parent": "kien-thuc", "name": "Thị trường & giá", "path": "/category/tin-tuc/",
                      "intro": "Giá đá, giá cát xây dựng, thị trường vật liệu theo từng tỉnh và nhu cầu vật liệu cho các dự án cao tốc, sân bay."},
}
SECTION_BY_PATH = {v["path"]: k for k, v in SECTIONS.items()}
# Dịch vụ menu also has the hand-built service page
SERVICE_LINKS = [("Lắp đặt & chuyển giao", "/dich-vu/")]
LEGACY_CATEGORIES = {"video"}  # old WordPress categories still kept as they were


def section_children(parent):
    return [(k, v) for k, v in SECTIONS.items() if v["parent"] == parent and k != parent]


def load_structure():
    path = ROOT / "tools" / "data" / "structure.tsv"
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        slug, section, *_ = line.split("\t")
        if section not in SECTIONS:
            raise SystemExit(f"structure.tsv: chuyên mục '{section}' của '{slug}' không có trong SECTIONS")
        out[unicodedata.normalize("NFC", slug)] = section
    return out


FEATURED_CATEGORIES = {
    "design": "Design",
    "lookbook": "Lookbook",
}
FEATURED_MEMBERS = {
    "design": {"another-print-package", "awesome-pencil-poster", "fl3-print-package",
               "flatsome-poster-print", "magazine", "portfolio-typography"},
    "lookbook": {"flat-t-shirt-company", "lookbook-summer"},
}

# Misspelt tags folded into the correct one (both marked in urls.html).
TAG_MERGE = {
    "nghien-ca": "nghien-cat",
    "may-lam": "may-lam-cat",
    "may-nghien-han": "may-nghien-ham",
}

# The only outside sites articles may still link to: the company's own
# Zalo / Facebook / YouTube channels. Every other outbound link is unwrapped.
ALLOWED_EXTERNAL = {"zalo.me", "chat.zalo.me", "youtube.com", "m.youtube.com", "youtu.be",
                    "facebook.com", "m.facebook.com", "fb.com"}

# Old sister site labcare.com.vn: send its links to the matching page here.
# Paths with no equivalent are unwrapped (text kept, link dropped).
LABCARE_MAP = {
    "": "/",
    "nhan-bao-gia": "/bao-gia/",
    "gioi-thieu": "/gioithieu/",
    "tu-van-ky-thuat": "/category/tu-van-ky-thuat/",
    "may-nghien-con": "/product/may-nghien-con/",
    "may-kep-ham": "/cau-tao-may-kep-ham/",
    "may-rua-cat-kieu-guong": "/may-rua-cat-guong-quay-trong-cong-nghe-san-xuat-cat/",
    "may-rua-cat-kieu-guong-quay-banh-xe": "/may-rua-cat-guong-quay-trong-cong-nghe-san-xuat-cat/",
    "thu-hoi-cat-min-tu-nuoc-rua-cat": "/may-thu-hoi-cat-min/",
    "4nhasanxuatmaynghiendalonnhatthegioiholaai": "/bao-gia-day-chuyen-nghien-da-xay-dung/",
    "4-nha-san-xuat-may-nghien-da-lon-nhat-the-gioi-ho-la-ai": "/bao-gia-day-chuyen-nghien-da-xay-dung/",
    "may-rua-cat-mclanahan-dong-ultrawash": "/may-rua-cat-xay-dung-mclanahan-thiet-bi-rua-cat-hien-dai-nhat-the-gioi/",
    "12-meo-toi-uu-nang-suat-may-nghien-con": "/toi-uu-hieu-suat-may-nghien-con/",
    "cat-nhan-tao-la-gi-so-sanh-cat-nhan-tao-va-cat-tu-nhien": "/may-nghien-cat-nhan-tao-la-gi-so-sanh-cat-nhan-tao-cat-tu-nhien/",
    "quy-trinh-san-xuat-cat-nhan-tao": "/cong-nghe-san-xuat-cat-nhan-tao/",
    "may-nghien-bua": "/may-nghien-bua-truc-ngang/",
    "cat-nghien-tu-da-cat-ket-vsi-barmac-metso": "/cat-nghien-nhan-tao-tu-da-cat-ket/",
    "day-chuyen-rua-cat-doi": "/day-chuyen-rua-cat-doi-va-cac-cong-nghe-san-co/",
}

PHONE_TEXT = re.compile(r"\+?[\d][\d\s.\-()]{7,}\d")

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


def tag_key(slug: str) -> str:
    return unicodedata.normalize("NFC", unquote_path(slug))


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
    source = (SITE / "index.html").read_text(encoding="utf-8")
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
    out = SITE / output_path(path)
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
    # Scraped tag slugs keep the site's raw percent-encoding (e.g.
    # "ba%cc%89o-tri-..."), while audit paths are decoded and may use another
    # Unicode normalisation form. Map each scraped slug onto the audit's exact
    # spelling, or every Vietnamese-diacritic tag silently drops out.
    by_key = {tag_key(slug): slug for slug in kept_tags}
    for p in raw:
        for t in p.get("tags", []):
            t["slug"] = by_key.get(tag_key(t["slug"]), t["slug"])
            t["slug"] = TAG_MERGE.get(t["slug"], t["slug"])
    kept_paths = {k["path"] for k in kept}

    posts = [p for p in raw if p["kind"] == "post/page" and p["path"] not in EXISTING and p["path"] != "/nhan-bao-gia/"]
    products = [p for p in raw if p["kind"] == "product"]
    catalog = load_catalog()
    kept_paths |= {v["path"] for v in SECTIONS.values()} | {"/giai-phap/"}
    featured = [p for p in raw if p["kind"] == "featured_item" and p["path"] not in {"/featured_item/"}
                and p["path"] in kept_paths]

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
        tags = list({t["slug"]: t for t in reversed(p["tags"]) if t["slug"] in kept_tags}.values())[::-1]
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

    # Section of each article (one per article; aliases follow their primary).
    structure = load_structure()
    unplaced = []
    for p in post_by_path.values():
        key = unicodedata.normalize("NFC", p["primary_path"].strip("/"))
        p["section"] = structure.get(key)
        if p["section"] is None:
            p["section"] = "kt-ky-thuat"
            if p["is_primary"] and p["is_article"]:
                unplaced.append(p["path"])
    if unplaced:
        print(f"structure.tsv: {len(unplaced)} bài chưa xếp chuyên mục (tạm vào kt-ky-thuat), chạy tools/classify.py: {unplaced[:5]}")

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
        "catalog": catalog,
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
            text = tag.get_text(" ", strip=True)
            if PHONE_TEXT.fullmatch(text) and not href.startswith(("tel:", "https://zalo.me", "http://zalo.me")):
                href = "tel:" + re.sub(r"[^\d+]", "", text)
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
        host = parsed.netloc.lower().removeprefix("www.")
        if host == "labcare.com.vn":
            target = LABCARE_MAP.get(unquote_path(parsed.path).strip("/"))
            if target is None and ("/" + unquote_path(parsed.path).strip("/") + "/") in model["kept_paths"]:
                target = "/" + unquote_path(parsed.path).strip("/") + "/"
            return internal_href(target, from_dir, model) if target else None
        if host != "thegioimaynghienda.com":
            return href if host in ALLOWED_EXTERNAL else None
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
    routes = model.get("routes")
    if routes is not None and path not in routes:
        m = re.match(r"^(.*/)page/\d+/$", path)
        if m and m.group(1) in routes:  # pagination that no longer exists
            return rel_url(from_dir, m.group(1))
    if path in model["kept_paths"]:
        return rel_url(from_dir, path)
    if path in model.get("redirect_to", {}):
        return rel_url(from_dir, model["redirect_to"][path])
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
        cat = SECTIONS[post["section"]]["name"] if post.get("section") in SECTIONS else "Kiến thức"
    meta_line = " · ".join(x for x in (date_text, cat) if x)
    return f"""<a class="post reveal" href="{esc(rel_url(from_dir, post['path']))}">
            <div class="post__img"><img src="{esc(thumb_src(post, from_dir))}" alt="{esc(post['title'])}" width="640" height="400" loading="lazy">{date_badge}</div>
            <h3>{esc(post['title'])}</h3>
            <p class="post__meta"><svg class="ico"><use href="#i-clock"/></svg>{esc(meta_line)}</p>
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
                  nav: str, noindex: bool, item_label: str = "bài viết",
                  lead_html: str = "", hide_empty: bool = False) -> str:
    cards = "\n          ".join(post_card(p, from_dir) for p in posts)
    empty = '<p class="list-empty" hidden>Không tìm thấy bài viết phù hợp.</p>'
    if not posts:
        empty = "" if hide_empty else '<p class="list-empty">Chưa có bài viết trong chuyên mục này.</p>'
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
        {lead_html}
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
    # URLs the old site already 301-redirects (urls.html: "Xoá" + merge target)
    model["redirect_to"] = {}
    for url, status, kind, in_sitemap, rec, reason, merge in rows:
        if rec == "Xoá" and merge and str(status) == "301":
            src, dst = url_path(url.strip().rstrip(".")), url_path(merge)
            if not src.endswith("/") and "." not in Path(src).name:
                src += "/"
            if src != dst:
                model["redirect_to"][src] = dst
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
        if path not in model["kept_paths"]:
            continue
        add_route(path, "post", post["title"], post=post,
                  canonical=post["path"] if post["is_primary"] else post["primary_path"],
                  index=post["is_primary"] and post["is_article"])

    # --- categories + pagination ------------------------------------------
    cat_pages = {}
    for slug, meta in CATEGORIES.items():
        if slug not in LEGACY_CATEGORIES:
            continue  # replaced by SECTIONS
        if f"/category/{slug}/" not in model["kept_paths"]:
            continue  # dropped by the audit (e.g. empty category)
        members = [p for p in primary_posts if any(c["slug"] == slug for c in p["categories_data"])]
        total = max(1, math.ceil(len(members) / PER_PAGE))
        cat_pages[slug] = (members, total)
        base = f"/category/{slug}/"
        add_route(base, "category", meta["name"], members=members, total=total, slug=slug, index=True)
        for n in range(2, total + 1):
            add_route(page_url(base, n), "pagination", f"{meta['name']} – Trang {n}",
                      members=members, total=total, page=n, base=base, slug=slug, index=False)

    # --- sections (main menu) + pagination ---------------------------------
    section_pages = {}
    for key, sec in SECTIONS.items():
        members = [p for p in primary_posts if p["section"] == key]
        total = max(1, math.ceil(len(members) / PER_PAGE))
        section_pages[key] = (members, total)
        base = sec["path"]
        add_route(base, "section", sec["name"], members=members, total=total, section=key, index=True)
        for n in range(2, total + 1):
            add_route(page_url(base, n), "section-pagination", f"{sec['name']} – Trang {n}",
                      members=members, total=total, page=n, base=base, section=key, index=False)
    add_route("/giai-phap/", "solutions", "Giải pháp", index=True)

    # --- blog archive ------------------------------------------------------
    blog_members = primary_posts
    blog_total = max(1, math.ceil(len(blog_members) / PER_PAGE))
    add_route("/nhan-bao-gia/", "blog", "Kiến thức", members=blog_members,
              total=blog_total, index=True)
    for n in range(2, blog_total + 1):
        add_route(f"/nhan-bao-gia/page/{n}/", "blog-pagination", f"Kiến thức – Trang {n}",
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
        if product["path"] in model["kept_paths"]:
            add_route(product["path"], "product", product["title"], product=product, index=True)

    # --- featured items ----------------------------------------------------
    for item in model["featured"]:
        if item["path"].startswith("/featured_item_category/"):
            continue
        add_route(item["path"], "featured", item["title"], item=item, index=False)
    if "/featured_item/" in model["kept_paths"]:
        add_route("/featured_item/", "featured-archive", "Dự án tiêu biểu",
                  members=[i for i in model["featured"] if not i["path"].startswith("/featured_item_category/")],
                  index=False)
    for slug, name in FEATURED_CATEGORIES.items():
        if f"/featured_item_category/{slug}/" not in model["kept_paths"]:
            continue
        add_route(f"/featured_item_category/{slug}/", "featured-category", name,
                  members=[], slug=slug, index=False)

    model["routes"] = routes

    # ------------------------------------------------------------------
    # static pages that are not articles (theme demos etc.)
    # ------------------------------------------------------------------
    for path, post in post_by_path.items():
        if post["is_article"] or path not in model["kept_paths"]:
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
    by_section = defaultdict(list)
    for p in primary_posts:
        by_section[p["section"]].append(p)

    for path, post in post_by_path.items():
        if not post["is_article"] or path not in routes:
            continue
        generate_article(path, post, model, by_section, routes)

    # ------------------------------------------------------------------
    # section pages (main menu) + "Giải pháp" landing
    # ------------------------------------------------------------------
    for key, (members, total) in section_pages.items():
        generate_section(key, members, total, model)
    generate_solutions_landing(section_pages)

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
        cr = [("Trang chủ", "/"), ("Kiến thức", base if n > 1 else None)]
        if n > 1:
            cr.append((f"Trang {n}", None))
        out = archive_page(
            base_path=base, page_no=n, total_pages=blog_total,
            h1="Kiến thức" if n == 1 else f"Kiến thức – Trang {n}",
            intro="Toàn bộ bài viết của Thanh Long JSC: kinh nghiệm chọn thiết bị, công nghệ làm cát nhân tạo, vận hành trạm nghiền và thị trường vật liệu xây dựng.",
            lead_html=section_nav("kien-thuc", None, from_dir) if n == 1 else "",
            posts=chunk, from_dir=from_dir, crumbs_items=cr,
            canonical=BASE + page_path,
            title=("Kiến thức máy nghiền, cát nhân tạo | Thế Giới Máy Nghiền Đá" if n == 1 else f"Kiến thức – Trang {n} | Thế Giới Máy Nghiền Đá"),
            description="Kiến thức về máy nghiền đá, cát nhân tạo, dây chuyền nghiền sàng, vận hành trạm nghiền và thị trường vật liệu xây dựng.",
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
        if product["path"] in routes:
            generate_product(product, model)

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
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries) + "\n</urlset>\n", encoding="utf-8")
    # old pagination of re-scoped listings (e.g. /category/tu-van-ky-thuat/page/15/)
    gone_pages = {p: re.sub(r"page/\d+/$", "", p) for p in model["kept_paths"]
                  if p not in routes and re.search(r"/page/\d+/$", p) and re.sub(r"page/\d+/$", "", p) in routes}
    write_redirects(rows, routes, gone_pages)
    remove_stale_pages(routes)
    (SITE / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: " + BASE + "/sitemap.xml\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # audit report
    # ------------------------------------------------------------------
    kept_paths = {k["path"] for k in kept}
    missing = sorted(p for p in kept_paths if p not in routes and p not in gone_pages)
    product_paths = {v["path"] for v in SECTIONS.values()} | {"/giai-phap/"}
    product_paths |= {p for p in routes if any(p.startswith(v["path"] + "page/") for v in SECTIONS.values())}
    extra = sorted(p for p in routes if p not in kept_paths and p not in EXISTING and p not in product_paths)
    report = {
        "kept": len(kept_paths),
        "generated_routes": len(routes),
        "missing_kept": missing,
        "redirected_pagination": len(gone_pages),
        "extra_generated": extra,
        "primary_posts": len(primary_posts),
        "tags": len(tag_pages),
    }
    (ROOT / "tools" / "data" / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Cloudflare redirects (_redirects, read by Cloudflare Pages / Workers assets)
# ---------------------------------------------------------------------------
REDIRECT_FALLBACK = {
    "tag": "/nhan-bao-gia/", "author": "/nhan-bao-gia/", "category": "/nhan-bao-gia/",
    "bao-gia": "/bao-gia/", "product": "/san-pham/", "product-category": "/san-pham/",
    "featured_item": "/category/du-an-cong-trinh/", "featured_item_category": "/category/du-an-cong-trinh/",
}
REDIRECT_SKIP = {"/xmlrpc.php", "/wp-login.php"}
# old WooCommerce product slugs -> catalogue page, by keyword in the slug
REDIRECT_PRODUCT_KW = [
    ("vo-da", "/product/may-lam-cat-nhan-tao/"), ("may-nghien-cat", "/product/may-lam-cat-nhan-tao/"),
    ("may-nghien-con", "/product/may-nghien-con/"), ("may-nghien-ham", "/san-pham/may-nghien-da/"),
    ("may-kep-ham", "/san-pham/may-nghien-da/"), ("sang-rung", "/san-pham/sang-rung-phu-tung/"),
    ("cap-lieu", "/san-pham/sang-rung-phu-tung/"), ("mclanahan", "/product/may-rua-cat/"),
    ("may-tach-nuoc", "/san-pham/may-rua-cat/"),
]


def cf_path(path: str) -> str:
    """Percent-encode a path the way browsers send it (UTF-8, NFC kept as given)."""
    return urllib.parse.quote(path, safe="/%-._~!$&'()*+,;=:@")


def write_redirects(rows, routes, extra=None):
    import difflib
    live = set(routes)
    # page paths keep the old site's Unicode form (often NFD); match on NFC
    live_nfc = {unicodedata.normalize("NFC", p): p for p in live}
    by_seg = defaultdict(list)
    for pth in live:
        by_seg[pth.strip("/").split("/")[0] if pth.count("/") > 2 else ""].append(pth)

    def norm(url: str) -> str:
        pth = unicodedata.normalize("NFC", url_path(url.strip().rstrip(".")))
        if not pth.endswith("/") and "." not in Path(pth).name:
            pth += "/"
        return pth

    def canonical(t: str) -> str:
        c = routes.get(t, {}).get("canonical")
        return c if c in live else t

    def target_for(path: str, merge: str, depth: int = 0) -> str:
        return canonical(_target_for(path, merge, depth))

    def _target_for(path: str, merge: str, depth: int = 0) -> str:
        if merge:
            t = norm(merge)
            if t in live_nfc:
                return live_nfc[t]
            if depth < 3:
                return _target_for(t, "", depth + 1)
        if path in live_nfc and depth:
            return live_nfc[path]
        m = re.match(r"^(.*/)page/\d+/$", path)
        if m and m.group(1) in live_nfc:
            return live_nfc[m.group(1)]
        if m:
            path = m.group(1)
        parts = path.strip("/").split("/")
        seg = parts[0] if len(parts) > 1 else ""
        # closest live page in the same section (old product/post slugs)
        if seg == "product":
            for kw, dest in REDIRECT_PRODUCT_KW:
                if kw in parts[-1] and dest in live:
                    return dest
        if seg in ("product", ""):
            pool = [p for p in by_seg[seg]] + ([p for p in by_seg["product"]] if seg == "" else [])
            leaf = parts[-1]
            prefix = [p for p in pool if leaf.startswith(p.strip("/").split("/")[-1] + "-")]
            if prefix:
                return max(prefix, key=len)
            near = difflib.get_close_matches(path, pool, n=1, cutoff=0.75)
            if near:
                return near[0]
        parent = "/" + "/".join(parts[:-1]) + "/" if len(parts) > 1 else "/"
        if parent in live and parent != "/":
            return parent
        return REDIRECT_FALLBACK.get(seg or parts[0], "/")

    lines, seen = [], set()
    for url, status, kind, in_sitemap, rec, reason, merge in rows:
        if rec != "Xoá":
            continue
        raw = urllib.parse.urlparse(url.strip().rstrip(".")).path or "/"
        if not raw.endswith("/") and "." not in Path(raw).name:
            raw += "/"
        path = norm(url)
        if path in REDIRECT_SKIP or raw in REDIRECT_SKIP:
            continue
        dest = cf_path(target_for(path, merge))
        # the URL as the old site printed it, and as a browser would encode it
        sources = {cf_path(raw), re.sub(r"%[0-9a-f]{2}", lambda m: m.group(0).upper(), cf_path(raw))}
        for src in sorted(sources):
            if src == dest or src in seen or urllib.parse.unquote(src) in live:
                continue
            seen.add(src)
            lines.append(f"{src} {dest} 301")
    # kept URLs that no longer exist after the restructure
    for src_path, dest_path in sorted((extra or {}).items()):
        src = cf_path(src_path)
        if src not in seen:
            seen.add(src)
            lines.append(f"{src} {cf_path(dest_path)} 301")
    # typed / NFC-encoded spelling of a page whose real path is NFD
    for nfc, real in sorted(live_nfc.items()):
        src = cf_path(nfc)
        if nfc != real and src not in seen and nfc not in live:
            seen.add(src)
            lines.append(f"{src} {cf_path(real)} 301")
    header = ("# Cloudflare redirects - generated by tools/build.py from urls.html (rows marked \"Xoá\").\n"
              "# Do not edit by hand. Format: <from> <to> <status>\n")
    (SITE / "_redirects").write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"_redirects: {len(lines)} rules")


def generate_article(path, post, model, by_section, routes):
    from_dir = page_dir(path)
    image_map = model["image_map"]
    body_html = sanitize(post["node"], from_dir=from_dir, model=model, image_map=image_map)
    if not body_html:
        body_html = f"<p>{esc(post['description'] or post['title'])}</p><p>Nội dung chi tiết đang được cập nhật. Quý khách cần tư vấn cấu hình, vui lòng gọi <a href=\"tel:0912712772\">0912 712 772</a>.</p>"

    sec_key = post["section"]
    sec = SECTIONS[sec_key]
    cat_name, cat_link = sec["name"], sec["path"]
    cr = [("Trang chủ", "/")] + section_crumbs(sec_key) + [(post["title"], None)]

    tags_html = ""
    if post["tags_data"]:
        chips = " ".join(f'<a href="{esc(rel_url(from_dir, "/tag/" + t["slug"] + "/"))}">{esc(clean(t["name"]) or nice_tag(t["slug"]))}</a>'
                         for t in post["tags_data"] if ("/tag/" + t["slug"] + "/") in model["kept_paths"])
        if chips:
            tags_html = f'<div class="article__tags"><span>Chủ đề:</span>{chips}</div>'

    # related: three newest in the same primary category
    related = [p for p in by_section.get(sec_key, []) if p["path"] != path][:3]
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
                                canonical=canonical, body=body, nav=MENU_BY_KEY[sec["parent"]][3],
                                jsonld=jsonld, noindex=noindex, og_type="article",
                                image=post["thumb"]))


def load_catalog():
    """Product cards from the hand-built /san-pham/ page, in page order."""
    text = (SITE / "san-pham" / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(text, "lxml")
    out = []
    for card in soup.select("article.product[data-group]"):
        img_link = card.select_one(".product__img")
        img = img_link.find("img")
        learn = card.select_one(".product__acts .product__btn:not(.product__btn--fill)")
        out.append({
            "name": card.select_one(".h4").get_text(" ", strip=True),
            "group": card["data-group"],
            "spec": card.select_one(".product__txt p").get_text(" ", strip=True),
            "image": img["src"].replace("../", "", 1),
            "white": "product__img--white" in img_link.get("class", []),
            "quote": "/" + card.select_one(".product__btn--fill")["href"].replace("../", "", 1),
            "learn": "/" + learn["href"].replace("../", "", 1) if learn and learn["href"].startswith("../") else "/san-pham/",
        })
    return out


def product_tile(product, from_dir: str) -> str:
    """Same card as on /san-pham/: image -> quote form, 'Tìm hiểu' -> article."""
    quote = esc(rel_url(from_dir, product["quote"].split("?")[0]) + ("?" + product["quote"].split("?", 1)[1] if "?" in product["quote"] else ""))
    learn = esc(rel_url(from_dir, product["learn"]))
    white = " product__img--white" if product["white"] else ""
    return f"""<article class="product reveal">
            <a class="product__img{white}" href="{quote}"><img src="{esc(rel_url(from_dir, product['image']))}" alt="{esc(product['name'])}" width="600" height="600" loading="lazy"></a>
            <div class="product__txt">
              <h2 class="h4">{esc(product['name'])}</h2>
              <p>{esc(product['spec'])}</p>
              <div class="product__acts">
                <a class="product__btn product__btn--fill" href="{quote}">Báo giá</a>
                <a class="product__btn" href="{learn}">Tìm hiểu</a>
              </div>
            </div>
          </article>"""


def generate_product(product, model):
    path = product["path"]
    from_dir = page_dir(path)
    body_html = sanitize(product["node"], from_dir=from_dir, model=model, image_map=model["image_map"])
    cr = [("Trang chủ", "/"), ("Thiết bị", "/san-pham/"), (product["title"], None)]
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


def capacity_block(from_dir: str) -> str:
    """Capacity table + process steps, taken from /san-pham/ (#day-chuyen)."""
    text = (SITE / "san-pham" / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<section class="section section--gray" id="day-chuyen">.*?<div class="container">(.*?)</div>\s*</section>', text, re.S)
    if not m:
        return ""
    inner = re.sub(r'\s*<div class="section-title reveal">.*?</div>\s*<p class="section-lead reveal">.*?</p>', "", m.group(1), count=1, flags=re.S)
    inner = re.sub(r'href="\.\./([^"]*)"', lambda x: f'href="{rel_url(from_dir, "/" + x.group(1))}"', inner)
    return f"""<h2 class="block-title sec-block">Cấu hình theo công suất</h2>
        {inner.strip()}"""


# ---------------------------------------------------------------------------
# sections (main menu)
# ---------------------------------------------------------------------------
def section_crumbs(key: str, current: bool = False):
    """Breadcrumb items for a section: [menu group,] section."""
    sec = SECTIONS[key]
    _, label, landing, _ = MENU_BY_KEY[sec["parent"]]
    items = [] if landing == sec["path"] else [(label, landing)]
    return items + [(sec["name"], None if current else sec["path"])]


def section_nav(parent: str, current: str | None, from_dir: str) -> str:
    """Pills linking the sections of one menu group."""
    links = [(v["name"], v["path"], k == current) for k, v in section_children(parent)]
    if parent == "dich-vu":
        links = [(n, pth, False) for n, pth in SERVICE_LINKS] + links
    if len(links) < 2:
        return ""
    cur = ' aria-current="page"'
    pills = "".join(f'<a href="{esc(rel_url(from_dir, pth))}"{cur if on else ""}>{esc(n)}</a>'
                    for n, pth, on in links)
    return f'<nav class="pcat-nav" aria-label="{esc(MENU_BY_KEY[parent][1])}">{pills}</nav>'


def generate_section(key, members, total, model):
    sec = SECTIONS[key]
    base = sec["path"]
    nav = MENU_BY_KEY[sec["parent"]][3]
    catalog = {p["name"]: p for p in model["catalog"]}
    for n in range(1, total + 1):
        page_path = base if n == 1 else page_url(base, n)
        from_dir = page_dir(page_path)
        chunk = members[(n - 1) * PER_PAGE:n * PER_PAGE]
        lead = ""
        if n == 1:
            lead = section_nav(sec["parent"], key, from_dir)
            tiles = [product_tile(catalog[name], from_dir) for name in sec.get("products", []) if name in catalog]
            if tiles:
                lead += f"""
        <h2 class="block-title sec-block">Thiết bị</h2>
        <div class="products">
          {"".join(tiles)}
        </div>"""
            if sec.get("capacity"):
                lead += "\n        " + capacity_block(from_dir)
            if members and (tiles or sec.get("capacity")):
                lead += '\n        <h2 class="block-title sec-block">Bài viết</h2>'
        cr = [("Trang chủ", "/")] + section_crumbs(key, current=n == 1)
        if n > 1:
            cr.append((f"Trang {n}", None))
        title = sec["name"] if n == 1 else f"{sec['name']} – Trang {n}"
        write_page(page_path, archive_page(
            base_path=base, page_no=n, total_pages=total, h1=title,
            intro=esc(sec["intro"]) if n == 1 else f"Tiếp tục danh sách {esc(sec['name'].lower())} – trang {n}/{total}.",
            posts=chunk, from_dir=from_dir, crumbs_items=cr,
            canonical=BASE + page_path, title=title + " | Thế Giới Máy Nghiền Đá",
            description=sec["intro"], nav=nav, noindex=n > 1,
            lead_html=lead, hide_empty=bool(lead)))


def generate_solutions_landing(section_pages):
    path = "/giai-phap/"
    from_dir = page_dir(path)
    boxes = []
    for key, sec in section_children("giai-phap"):
        count = len(section_pages[key][0])
        boxes.append(f"""<a class="line-box reveal" href="{esc(rel_url(from_dir, sec['path']))}">
            <h3>{esc(sec['name'])}</h3>
            <p>{esc(sec['intro'])}</p>
            <span class="line-box__more">Xem giải pháp · {count} bài viết<svg class="ico ico--sm"><use href="#i-right"/></svg></span>
          </a>""")
    cr = [("Trang chủ", "/"), ("Giải pháp", None)]
    intro = "Chọn dây chuyền theo sản phẩm bạn cần làm ra: đá xây dựng, cát nhân tạo, cát rửa sạch, quặng tinh hay cốt liệu tái chế. Cấu hình cuối cùng được kỹ sư chốt sau khi khảo sát mỏ."
    body = f"""    <div class="page-title">
      <div class="container">
        <h1>Giải pháp</h1>
        {crumbs(cr, from_dir)}
      </div>
    </div>
    <section class="section">
      <div class="container">
        <p class="intro reveal">{esc(intro)}</p>
        <div class="lines lines--page">
          {"".join(boxes)}
        </div>
      </div>
    </section>
    <section class="section section--gray">
      <div class="container">
        {capacity_block(from_dir)}
      </div>
    </section>
{cta_band(from_dir)}"""
    jsonld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Trang chủ", "item": BASE + "/"},
                             {"@type": "ListItem", "position": 2, "name": "Giải pháp", "item": BASE + path}]},
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Giải pháp dây chuyền nghiền sàng",
         "url": BASE + path, "description": intro},
    ]
    write_page(path, page_shell(path=path, title="Giải pháp dây chuyền nghiền đá, cát nhân tạo | Thế Giới Máy Nghiền Đá",
                                description=intro, canonical=BASE + path, body=body, nav="giai-phap", jsonld=jsonld))


def remove_stale_pages(routes):
    """Delete generated pages that no longer have a route (STALE_DRY=1 only lists them)."""
    live = {unicodedata.normalize("NFC", output_path(p)) for p in routes}
    removed = 0
    dry = os.environ.get("STALE_DRY") == "1"
    for f in sorted(SITE.rglob("index.html"), reverse=True):
        parts = f.relative_to(SITE).parts
        if parts[0] in ("assets",) or parts[0].startswith("."):
            continue
        rel = unicodedata.normalize("NFC", f.relative_to(SITE).as_posix())
        if rel not in live:
            if dry:
                print("  sẽ xoá:", rel)
                removed += 1
                continue
            f.unlink()
            removed += 1
            d = f.parent
            while d != SITE and not any(d.iterdir()):
                d.rmdir()
                d = d.parent
    if removed:
        print(f"{'sẽ xoá' if dry else 'đã xoá'} {removed} trang cũ không còn dùng")


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
    if path not in model["kept_paths"]:
        return
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
        if path not in model["kept_paths"]:
            continue
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
