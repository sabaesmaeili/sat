#!/usr/bin/env python3
"""One-off: write bank/annotations/<section>.json from the original drill pages.

The drills as first imported (commit 120473f) carried our own additions inline: which
cheat-sheet card each question drills, the link to that card, and a hint. This reads them
from git and writes them out keyed by item id, in drill order, so the pages can be built
from bank/original/ (the College Board's text) plus bank/annotations/ (ours).

    python3 tools/extract_annotations.py            write both sections
    python3 tools/extract_annotations.py --check    exit 1 if the files differ from what git gives

Standard library only. Format: bank/README.md, "Annotations".
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "120473f"
PAGES = {"writing": "writing-drill.html", "math": "math-drill.html"}
OUT = ROOT / "bank" / "annotations"

ARTICLE = re.compile(r'<article class="q kk(\d+)" id="q-([0-9a-f]+)">(.*?)</article>', re.S)
LABEL = re.compile(r'<a class="lbl" href="([\w-]+)\.html#([\w-]+)"[^>]*><b>(\d+) · (.*?)</b> → (.*?)</a>')
HINT = re.compile(r'<div class="hint" hidden><span class="t">(.*?)</span><b>(.*?)</b><p>(.*?)</p><a href="([\w-]+)\.html#([\w-]+)"')
DATA = re.compile(r"var DATA = (\[.*?\]);")


def text(s):
    """Inner HTML of the original (escaped plain text) as a plain string."""
    if "<" in s:
        raise SystemExit(f"extract_annotations: unexpected markup in {s!r}")
    return html.unescape(s)


def extract(section):
    page = subprocess.run(["git", "show", f"{COMMIT}:{PAGES[section]}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    date = subprocess.run(["git", "log", "-1", "--format=%cs", COMMIT], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    key = {d["id"]: d for d in json.loads(DATA.search(page).group(1))}
    items = {}
    for kk, iid, body in ARTICLE.findall(page):
        lab, hint = LABEL.search(body), HINT.search(body)
        if not lab or not hint:
            raise SystemExit(f"extract_annotations: {section} {iid}: no label or hint")
        playbook, anchor, card, card_name, link = lab.groups()
        if int(card) != int(kk) or key[iid]["card"] != int(card):
            raise SystemExit(f"extract_annotations: {section} {iid}: card numbers disagree")
        if hint.group(4) != playbook:
            raise SystemExit(f"extract_annotations: {section} {iid}: hint links to another cheat sheet")
        items[iid] = {
            "card": int(card),
            "card_name": text(card_name),
            "anchor": anchor,
            "label": text(link),
            "hint": {"tag": text(hint.group(1)), "title": text(hint.group(2)), "text": text(hint.group(3)), "anchor": hint.group(5)},
            "by": f"original drill page ({PAGES[section]}, commit {COMMIT})",
            "date": date,
        }
    if len(items) != len(key):
        raise SystemExit(f"extract_annotations: {section}: {len(items)} articles but {len(key)} answer-key entries")
    return {"section": section, "origin": "annotation", "items": items}


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    bad = False
    for section in PAGES:
        data, path = extract(section), OUT / f"{section}.json"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != dump(data):
                print(f"extract_annotations: {path.relative_to(ROOT)} differs from commit {COMMIT}", file=sys.stderr)
                bad = True
            continue
        path.write_text(dump(data), encoding="utf-8")
        print(f"extract_annotations: wrote {path.relative_to(ROOT)} ({len(data['items'])} items)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
