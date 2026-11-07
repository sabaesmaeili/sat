#!/usr/bin/env python3
"""Check the bank, the annotations, the design tokens and the built site. Exit 1 on any problem.

    python3 tools/check.py

1. bank/original/<section>.json against bank/README.md (format, text, media files, references).
2. bank/annotations/<section>.json: every bank item has an annotation with its card; card names
   agree; every anchor (the card link's, the hint's) exists on that section's cheat sheet.
3. site/css/tokens.css matches the website's tokens (skipped when the Website repo is absent, as in
   CI) and site/css/palette.css is current and passes its contrast and distance checks.
4. The drills' grading of typed answers (tools/test_grading.js, with node; skipped without it).
5. The site, built into a temporary folder: no placeholder left; every internal link, stylesheet,
   script and image resolves, with its #anchor; external resources (stylesheets, scripts, images) only from cdnjs (MathJax);
   the drill pages, and only they, carry <meta name="robots" content="noindex">.
Standard library only.
"""
import html.parser
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urldefrag, urlparse

from bank import FORBIDDEN_TEX, MATH, ROOT, SECTIONS, bank_errors, bank_path, load, load_annotations

TOOLS = ROOT / "tools"
SITE = ROOT / "site"
EXTERNAL_HOSTS = {"cdnjs.cloudflare.com"}
ANNOTATION_KEYS = {"card", "card_name", "anchor", "label", "hint", "by", "date"}
HINT_KEYS = {"tag", "title", "text", "anchor"}


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.refs, self.noindex = set(), [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        for key in ("href", "src"):
            if a.get(key) is not None and tag in ("a", "link", "script", "img", "iframe", "source"):
                self.refs.append((tag, a[key]))
        if tag == "meta" and (a.get("name") or "").lower() == "robots" and "noindex" in (a.get("content") or "").lower():
            self.noindex = True


def parse(path):
    p = Page()
    p.feed(path.read_text(encoding="utf-8"))
    return p


def check_bank():
    errs = []
    for section in SECTIONS:
        if not bank_path(section).exists():
            errs.append(f"bank/original/{section}.json doesn't exist")
            continue
        errs += [f"bank/original/{section}.json: {e}" for e in bank_errors(load(section), section)]
    return errs


def check_annotations():
    errs = []
    for section in SECTIONS:
        where = f"bank/annotations/{section}.json"
        notes = load_annotations(section)
        if notes.get("section") != section or notes.get("origin") != "annotation" or not isinstance(notes.get("items"), dict):
            errs.append(f"{where}: must be {{section: {section!r}, origin: 'annotation', items: {{id: …}}}}")
            continue
        sheet = SITE / section / "cheat-sheet" / "index.html"
        anchors = parse(sheet).ids if sheet.exists() else set()
        names = {}
        for iid, a in notes["items"].items():
            if not isinstance(a, dict) or not set(a) <= ANNOTATION_KEYS or not {"card", "card_name", "anchor", "label"} <= set(a):
                errs.append(f"{where}: {iid}: needs card, card_name, anchor, label (optional hint, by, date), nothing else")
                continue
            if not isinstance(a["card"], int) or not 1 <= a["card"] <= 7:
                errs.append(f"{where}: {iid}: card must be 1 to 7")
            if names.setdefault(a["card"], a["card_name"]) != a["card_name"]:
                errs.append(f"{where}: {iid}: card {a['card']} is named {a['card_name']!r} here and {names[a['card']]!r} elsewhere")
            if a["anchor"] not in anchors:
                errs.append(f"{where}: {iid}: #{a['anchor']} isn't on {sheet.relative_to(ROOT)}")
            h = a.get("hint")
            if h is not None:
                if not isinstance(h, dict) or not {"tag", "title", "text"} <= set(h) or not set(h) <= HINT_KEYS or not all(isinstance(h[k], str) and h[k].strip() for k in h):
                    errs.append(f"{where}: {iid}: hint must be {{tag, title, text}} (optional anchor), all non-empty")
                elif h.get("anchor") and h["anchor"] not in anchors:
                    errs.append(f"{where}: {iid}: hint #{h['anchor']} isn't on {sheet.relative_to(ROOT)}")
                else:
                    for tex in MATH.findall(h["text"] + " " + h["title"]):
                        m = FORBIDDEN_TEX.search(tex)
                        if m:
                            errs.append(f"{where}: {iid}: hint math uses \\{m.group(1)}, which is not allowed")
        if bank_path(section).exists():
            for it in load(section)["items"]:
                if it.get("id") not in notes["items"]:
                    errs.append(f"{where}: no annotation for bank item {it.get('id')} (every item needs its card)")
    return errs


def check_design():
    errs = []
    for script in ("sync_tokens.py", "palette.py"):
        r = subprocess.run([sys.executable, str(TOOLS / script), "--check"], capture_output=True, text=True)
        if r.returncode:
            errs += [line for line in (r.stderr or r.stdout).strip().splitlines() if line]
        elif "skipping" in r.stdout:
            print(r.stdout.strip())
    return errs


def check_grading():
    node = shutil.which("node")
    if not node:
        print("grading: node isn't installed; skipping tools/test_grading.js.")
        return []
    r = subprocess.run([node, str(TOOLS / "test_grading.js")], capture_output=True, text=True)
    return [line for line in (r.stderr or r.stdout).strip().splitlines() if line] if r.returncode else []


def check_site():
    sys.path.insert(0, str(TOOLS))
    import build
    errs = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "_site"
        try:
            build.build(out=out, quiet=True)
        except build.BuildError as e:
            return [f"build: {e}"]
        pages = {p: parse(p) for p in out.rglob("*.html")}
        for page, info in sorted(pages.items()):
            rel = page.relative_to(out)
            text = page.read_text(encoding="utf-8")
            if "{{" in text:
                errs.append(f"{rel}: a {{{{placeholder}}}} is left")
            is_drill = len(rel.parts) == 3 and rel.parts[1] == "drill"
            if info.noindex != is_drill:
                errs.append(f"{rel}: {'missing' if is_drill else 'unexpected'} robots noindex")
            for tag, ref in info.refs:
                url = urlparse(ref)
                if url.scheme in ("mailto", "tel", "data"):
                    continue
                if url.scheme or ref.startswith("//"):
                    if tag != "a" and (url.scheme != "https" or url.hostname not in EXTERNAL_HOSTS):
                        errs.append(f"{rel}: external {tag} {ref} (only https://cdnjs.cloudflare.com is allowed)")
                    continue
                if ref.startswith("/"):
                    errs.append(f"{rel}: absolute link {ref} (links must be relative)")
                    continue
                path, frag = urldefrag(ref)
                target = (page.parent / path).resolve() if path else page
                if path.endswith("/") or (path and target.is_dir()):
                    target = target / "index.html"
                if not target.is_file() or out.resolve() not in target.resolve().parents:
                    errs.append(f"{rel}: {tag} {ref} doesn't resolve")
                    continue
                if frag:
                    ids = pages.get(target, None) or (parse(target) if target.suffix == ".html" else None)
                    if ids is None or frag not in ids.ids:
                        errs.append(f"{rel}: {ref}: no #{frag} there")
    return errs


def main():
    problems = []
    for name, fn in (("bank", check_bank), ("annotations", check_annotations), ("design", check_design), ("grading", check_grading), ("site", check_site)):
        errs = fn()
        print(f"{name}: {'ok' if not errs else f'{len(errs)} problem(s)'}")
        problems += errs
    for e in problems:
        print("  -", e)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
