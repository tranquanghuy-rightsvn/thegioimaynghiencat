#!/usr/bin/env python3
"""Ghi menu chính (máy tính + điện thoại) và cột "Menu" ở chân trang vào html/index.html
từ MENU / SECTIONS trong tools/build.py. Sau đó chạy tools/sync-layout.py rồi tools/build.py.
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

INDEX = build.SITE / "index.html"


def rel(path):  # links in index.html are written for the site root
    return path.lstrip("/") or "./"


def children(key):
    items = [(n, p) for n, p in build.SERVICE_LINKS] if key == "dich-vu" else []
    items += [(v["name"], v["path"]) for _, v in build.section_children(key)]
    return [(html.escape(n), p) for n, p in items]


def desktop():
    # no "Trang chủ" on desktop: the logo links home and the bar must fit 1200px
    out = ['            <li><a data-nav="gioithieu" href="gioithieu/">Giới thiệu</a></li>']
    for key, label, landing, nav in build.MENU:
        sub = children(key)
        if not sub:
            out.append(f'            <li><a data-nav="{nav}" href="{rel(landing)}">{label}</a></li>')
            continue
        out.append('            <li class="has-dropdown">')
        out.append(f'              <a data-nav="{nav}" href="{rel(landing)}" aria-haspopup="true">{label}<svg class="ico ico--sm"><use href="#i-down"/></svg></a>')
        out.append('              <ul class="dropdown">')
        out += [f'                <li><a href="{rel(p)}">{n}</a></li>' for n, p in sub]
        out.append('              </ul>')
        out.append('            </li>')
    out.append('            <li><a data-nav="lien-he" href="lien-he/">Liên hệ</a></li>')
    out.append('            <li class="nav__cta"><a data-nav="bao-gia" href="bao-gia/">Báo giá</a></li>')
    return "\n".join(out)


def mobile():
    out = ['        <li><a data-nav="home" href="./">Trang chủ</a></li>',
           '        <li><a data-nav="gioithieu" href="gioithieu/">Giới thiệu</a></li>']
    for key, label, landing, nav in build.MENU:
        sub = children(key)
        if not sub:
            out.append(f'        <li><a data-nav="{nav}" href="{rel(landing)}">{label}</a></li>')
            continue
        out.append('        <li class="mnav__sub">')
        out.append(f'          <a data-nav="{nav}" href="{rel(landing)}">{label}</a>')
        out.append(f'          <button class="mnav__toggle" aria-expanded="false" aria-label="Mở danh mục {label.lower()}"><svg class="ico"><use href="#i-down"/></svg></button>')
        out.append('          <ul>')
        out += [f'            <li><a href="{rel(p)}">{n}</a></li>' for n, p in sub]
        out.append('          </ul>')
        out.append('        </li>')
    out.append('        <li><a data-nav="lien-he" href="lien-he/">Liên hệ</a></li>')
    out.append('        <li><a data-nav="bao-gia" href="bao-gia/">Nhận báo giá</a></li>')
    return "\n".join(out)


def footer():
    items = [("Trang chủ", "/"), ("Giới thiệu", "/gioithieu/")] + [(m[1], m[2]) for m in build.MENU] + \
            [("Báo giá", "/bao-gia/"), ("Liên hệ", "/lien-he/")]
    return "\n".join(f'          <li><a href="{rel(p)}">{n}</a></li>' for n, p in items)


def main():
    h = INDEX.read_text(encoding="utf-8")
    h, a = re.subn(r'(<nav class="nav" aria-label="Menu chính">\s*<ul>\n).*?(\n\s*</ul>\s*</nav>)',
                   lambda m: m.group(1) + desktop() + m.group(2), h, count=1, flags=re.S)
    h, b = re.subn(r'(<ul class="mnav">\n).*?(\n      </ul>\s*<a class="offcanvas__call")',
                   lambda m: m.group(1) + mobile() + m.group(2), h, count=1, flags=re.S)
    h, c = re.subn(r'(<h3 class="footer__title">Menu</h3>\s*<ul class="footer__links">\n).*?(\n\s*</ul>)',
                   lambda m: m.group(1) + footer() + m.group(2), h, count=1, flags=re.S)
    if (a, b, c) != (1, 1, 1):
        raise SystemExit(f"không tìm thấy vị trí menu trong index.html: {(a, b, c)}")
    INDEX.write_text(h, encoding="utf-8")
    print("đã ghi menu vào html/index.html")


if __name__ == "__main__":
    main()
