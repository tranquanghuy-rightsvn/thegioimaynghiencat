# -*- coding: utf-8 -*-
"""Smart content rendering (GAS.md mục XI), shared by the article and category generators.

The CSS scoper is html/assets/js/smart-scope.js - the very file the Admin preview loads - run with
`node`, so build and preview can never disagree.

    from smart import render_many
    out = render_many({"/slug/": post["smart"], ...})   # {key: (html, css)} for valid ones
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOPE_JS = ROOT / "html" / "assets" / "js" / "smart-scope.js"

_NODE = r"""
const s = require(process.argv[1]);
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(input.map((c) => s.smcScopeCss(c))));
"""


def valid(smart) -> bool:
    return isinstance(smart, dict) and str(smart.get("html") or "").strip() != ""


def scope_css_many(css_list):
    if not any(css_list):
        return ["" for _ in css_list]
    r = subprocess.run(["node", "-e", _NODE, str(SCOPE_JS)], input=json.dumps(css_list),
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def render_many(smarts: dict) -> dict:
    """{key: smart_obj} -> {key: (wrapped_html, scoped_css)} for entries that have smart.html."""
    keys = [k for k, v in smarts.items() if valid(v)]
    scoped = scope_css_many([str(smarts[k].get("css") or "") for k in keys])
    return {k: (f'<div class="smc-root smc-a">{smarts[k]["html"]}</div>', css) for k, css in zip(keys, scoped)}


def head_tags(css: str, depth: int) -> str:
    """Tags for <head> of a page that shows Smart content (paths relative to the page)."""
    up = "../" * depth
    style = f"\n  <style>{css}</style>" if css else ""
    return f'<link rel="stylesheet" href="{up}assets/css/smart.css">{style}'


def body_tags(depth: int) -> str:
    return f'<script src="{"../" * depth}assets/js/smart.js" defer></script>'
