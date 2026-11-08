#!/usr/bin/env python3
"""Chép header và footer dùng chung từ index.html sang mọi trang con.

index.html là nguồn duy nhất của hai khối:
  <!-- layout:header ... --> ... <!-- /layout:header -->
  <!-- layout:footer ... --> ... <!-- /layout:footer -->
Đường dẫn tương đối trong hai khối viết cho thư mục gốc; script tự thêm "../"
theo độ sâu thư mục của từng trang.

Cách dùng:  python3 tools/sync-layout.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "html"  # website folder
BLOCKS = ("header", "footer")
# Chỉ sửa đường dẫn tương đối: bỏ qua link tuyệt đối, giao thức, neo trong trang, data URL.
URL_ATTR = re.compile(r'(\s(?:href|src))="(?!https?:|//|#|tel:|mailto:|data:|/)([^"]*)"')


def block(html, name):
    m = re.search(rf"[ \t]*<!-- layout:{name}\b.*?<!-- /layout:{name} -->", html, re.S)
    if not m:
        raise SystemExit(f"thiếu marker layout:{name}")
    return m


def rebase(snippet, depth):
    if depth == 0:
        return snippet
    prefix = "../" * depth

    def fix(m):
        url = m.group(2)
        if url == "./":  # trang chủ
            url = ""
        return f'{m.group(1)}="{prefix}{url}"'

    return URL_ATTR.sub(fix, snippet)


def main():
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    parts = {name: block(source, name).group(0) for name in BLOCKS}
    pages = sorted(
        p for p in ROOT.rglob("index.html")
        if p != ROOT / "index.html"
        and not any(s.startswith(".") for s in p.relative_to(ROOT).parts)
        and "tools" not in p.parts
    )
    for page in pages:
        depth = len(page.relative_to(ROOT).parts) - 1
        html = page.read_text(encoding="utf-8")
        for name in BLOCKS:
            m = block(html, name)
            html = html[:m.start()] + rebase(parts[name], depth) + html[m.end():]
        page.write_text(html, encoding="utf-8")
        print(f"đã đồng bộ {page.relative_to(ROOT)} (độ sâu {depth})")


if __name__ == "__main__":
    main()
