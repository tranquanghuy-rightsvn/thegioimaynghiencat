#!/usr/bin/env python3
"""One-off export: WordPress scrape (tools/data/raw.pkl) -> data/ (what the CMS manages).

Runs the old pipeline (build.main(source="scrape")) once, catching every article body right
after it is cleaned (build.sanitize), then writes:

  data/menu.json            menu groups + categories (from MENU / SECTIONS in build.py)
  data/posts.json           index of every article (CI trigger file)
  data/posts/<slug>.json    one article with its content_html
  data/tags.json            tag slug -> display name (all tags the audit kept)
  data/redirects.json       extra 301s managed by the CMS (old section pages)

Links and image paths inside content_html are stored root-absolute ("/assets/...",
"/slug/") so they do not depend on the page depth; tools/build.py turns them back
into relative URLs. After this export, tools/build.py builds only from data/.

Refuses to overwrite an existing data/ (the CMS owns it then) unless --force.
"""
from __future__ import annotations

import json
import posixpath
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as B  # noqa: E402

DATA = B.ROOT / "data"
URL_IN_HTML = re.compile(r'(\s(?:href|src))="([^"]*)"')


def to_absolute(html: str, from_dir: str) -> str:
    def fix(m):
        url = m.group(2)
        if not url or url.startswith(("http:", "https:", "//", "#", "tel:", "mailto:", "data:", "javascript:", "/")):
            return m.group(0)
        path, rest = re.match(r"([^?#]*)(.*)", url).groups()
        if not path:
            return m.group(0)
        absolute = posixpath.normpath(posixpath.join("/" + from_dir + "/", path))
        if path.endswith("/") or path in ("..", ".") or path.endswith("/.."):
            absolute = absolute.rstrip("/") + "/"
        return f'{m.group(1)}="{absolute}{rest}"'
    return URL_IN_HTML.sub(fix, html)


def main():
    if DATA.exists() and "--force" not in sys.argv:
        raise SystemExit("data/ đã có (CMS đang quản lý). Chạy lại với --force nếu thật sự muốn ghi đè.")

    captured = {}
    real_sanitize = B.sanitize

    def spy(node, *, from_dir, model, image_map, post=None):
        out = real_sanitize(node, from_dir=from_dir, model=model, image_map=image_map, post=post)
        if post is not None:
            captured[post["path"]] = (from_dir, out)
        return out

    B.sanitize = spy
    model_box = {}
    real_generate_section = B.generate_section

    def grab_model(key, members, total, model):
        model_box["m"] = model
        return real_generate_section(key, members, total, model)

    B.generate_section = grab_model
    B.main(source="scrape")
    model = model_box["m"]

    # ---- menu --------------------------------------------------------------
    groups = []
    for i, (key, label, landing, nav) in enumerate(B.MENU, 1):
        base = {"thiet-bi": "/san-pham/"}.get(key, landing if landing != "/nhan-bao-gia/" else "/kien-thuc/")
        groups.append({"key": key, "label": label, "landing": landing, "nav": nav, "base": base,
                       "order": i, "builtin": True, "intro": "",
                       "links": [{"name": n, "path": p} for n, p in B.GROUP_LINKS.get(key, [])]})
    categories = []
    order = {}
    for key, sec in B.SECTIONS.items():
        order[sec["parent"]] = order.get(sec["parent"], 0) + 1
        categories.append({
            "key": key, "parent": sec["parent"], "name": sec["name"], "path": sec["path"],
            "intro": sec.get("intro", ""), "order": order[sec["parent"]],
            "products": sec.get("products", []), "capacity": bool(sec.get("capacity")),
            "flow": [list(x) for x in B.SECTION_FLOWS.get(key, [])],
            "project_kw": B.SECTION_PROJECT_KW.get(key, []),
        })

    # ---- posts -------------------------------------------------------------
    index, details = [], {}
    for p in model["primary_posts"]:
        if p["path"] not in captured:
            raise SystemExit(f"không bắt được nội dung bài {p['path']}")
        from_dir, body = captured[p["path"]]
        slug = p["path"].strip("/")
        if "/" in slug:
            raise SystemExit(f"bài không nằm ở gốc site: {p['path']}")
        rec = {
            "slug": slug,
            "title": p["title"],
            "description": p["description"],
            "section": p["section"],
            "date": p["dt"].isoformat(),
            "modified": p["modified"],
            "thumb": p["thumb"],
            "tags": [t["slug"] for t in p["tags_data"]],
            "legacy_categories": [c["slug"] for c in p["categories_data"] if c["slug"] in B.LEGACY_CATEGORIES],
        }
        index.append(dict(rec))
        details[slug] = {**rec, "content_html": to_absolute(body, from_dir)}

    tags = {slug: model["tag_names"].get(slug) or B.nice_tag(slug) for slug in sorted(model["kept_tags"])}

    DATA.mkdir(exist_ok=True)
    (DATA / "posts").mkdir(exist_ok=True)
    for f in (DATA / "posts").glob("*.json"):
        f.unlink()
    dump = lambda path, obj: path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for slug, d in details.items():
        dump(DATA / "posts" / f"{slug}.json", d)
    dump(DATA / "tags.json", tags)
    dump(DATA / "redirects.json", dict(sorted(B.MOVED_SECTIONS.items())))
    dump(DATA / "menu.json", {"groups": groups, "categories": categories})
    dump(DATA / "posts.json", index)  # last: the CI trigger file
    print(f"data/: {len(groups)} nhóm menu, {len(categories)} danh mục, {len(index)} bài, {len(tags)} tag")


if __name__ == "__main__":
    main()
