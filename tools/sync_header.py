#!/usr/bin/env python3
"""Copy the website's header script into site/js/header-path.js.

The esaba.ca website owns how the header's @esaba mark and address shorten on a narrow screen
(its docs/design-system.xml, header): the menu first moves to a row of its own, then @esaba
becomes @, then the address folds from its start into one … crumb (~/lab/sat/writing/drill
becomes ~/…/sat/writing/drill, then ~/…/writing/drill; owner decision, 2026-11-25). The rule is its src/lib/headerPath.ts and
the measuring its src/scripts/headerPath.ts. These pages run that same code: this script bundles
the two files into one plain script with the website's own esbuild (from its node_modules), so
the behaviour exists once, on the website, and is never retyped here.

Usage (from anywhere):
  python3 tools/sync_header.py           write site/js/header-path.js
  python3 tools/sync_header.py --check   exit 1 if the copy has drifted

The website is looked for at ~/GitHub/Website (or --website PATH, or $WEBSITE_REPO). With
--check, a website that is absent, or has no node_modules (as in CI), is skipped with a note.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "js" / "header-path.js"
DEFAULT_WEBSITE = Path.home() / "GitHub" / "Website"
ENTRY = Path("src") / "scripts" / "headerPath.ts"
ESBUILD = Path("node_modules") / ".bin" / "esbuild"
# es2020 keeps ?. and ?? as written; every browser the website supports has them.
FLAGS = ["--bundle", "--format=iife", "--target=es2020", "--legal-comments=none", "--log-level=warning"]
HEADER = ("/* GENERATED FILE. Never edit it by hand: it is the esaba.ca website's header script\n"
          "   (src/lib/headerPath.ts, the rule; src/scripts/headerPath.ts, the measuring), bundled by\n"
          "   tools/sync_header.py, whose --check fails when this copy has drifted. */\n")


def build(website):
    # Run from the website, so the bundle's file comments name the website's own paths.
    r = subprocess.run([str(website / ESBUILD), ENTRY.as_posix(), *FLAGS], cwd=website, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"sync_header: esbuild failed:\n{r.stderr.strip()}")
    return HEADER + r.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the copy differs from the website's")
    parser.add_argument("--website", type=Path, default=None)
    args = parser.parse_args()
    website = Path(args.website or os.environ.get("WEBSITE_REPO") or DEFAULT_WEBSITE)
    if not (website / ENTRY).exists() or not (website / ESBUILD).exists():
        if args.check:
            print(f"sync_header: no website with node_modules at {website}; skipping the check.")
            return
        sys.exit(f"sync_header: no {ENTRY} and {ESBUILD} under {website}; pass --website PATH.")
    text = build(website)
    current = OUT.exists() and OUT.read_text(encoding="utf-8") == text
    if args.check:
        if not current:
            sys.exit(f"sync_header: {OUT.relative_to(ROOT)} has drifted from the website's header script; run tools/sync_header.py.")
        print(f"sync_header: {OUT.relative_to(ROOT)} matches the website's header script.")
        return
    if current:
        print("sync_header: already current.")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"sync_header: wrote {OUT.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
