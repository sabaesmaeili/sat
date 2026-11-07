#!/usr/bin/env python3
"""Copy the website's design tokens into site/css/tokens.css.

The esaba.ca website owns every shared style value (its docs/design-system.xml and
src/styles/global.css). This script copies the token blocks of global.css, that is every
`:root { ... }` rule with the at-rule around it, into site/css/tokens.css. Component CSS is
never copied. It follows the French tool's _Workspace/scripts/sync_tokens.py.

The site switches theme only by the viewer's system setting; these pages also accept
`data-theme` on the root element to force a mode. So the light block is written twice:
inside the light-mode query, as `:root:not([data-theme="dark"])`, and on its own as
`:root[data-theme="light"]`. The dark values are the plain `:root`.

It also copies the French tool's own tokens (its _Workspace/tool/tool-tokens.css: the serif
reading face, its size and measure, the spacing it sets ahead of the website, --color-entry) into
site/css/tool-tokens.css, verbatim under a short header, so these pages follow the same convention.

Usage (from anywhere):
  python3 tools/sync_tokens.py           write site/css/tokens.css and site/css/tool-tokens.css
  python3 tools/sync_tokens.py --check   exit 1 if either copy has drifted

The website is looked for at ~/Documents/GitHub/Website (or --website PATH, or $WEBSITE_REPO),
the French tool at ~/Documents/GitHub/Projects/French (or $FRENCH_REPO). With --check, a repo
that is absent (as in CI) is skipped with a note.
"""
import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "css" / "tokens.css"
TOOL_OUT = ROOT / "site" / "css" / "tool-tokens.css"
DEFAULT_WEBSITE = Path.home() / "Documents" / "GitHub" / "Website"
DEFAULT_FRENCH = Path.home() / "Documents" / "GitHub" / "Projects" / "French"
TOOL_SOURCE = Path("_Workspace") / "tool" / "tool-tokens.css"
TOOL_HEADER = ("/* COPIED FILE. Never edit it by hand: it is the French tool's _Workspace/tool/tool-tokens.css, copied by\n"
               "   tools/sync_tokens.py (its --check fails when this copy has drifted). Everything below is that file. */\n\n")
SOURCE = Path("src") / "styles" / "global.css"
LIGHT_QUERY = "@media (prefers-color-scheme: light)"


def rules(css):
    """Yield (at-rule stack, selector, body) for every innermost rule."""
    stack, buffer, depth_has_child = [], "", []
    i = 0
    while i < len(css):
        if css.startswith("/*", i):
            end = css.index("*/", i) + 2
            buffer += css[i:end]
            i = end
            continue
        ch = css[i]
        if ch == "{":
            stack.append(strip_comment_prefix(buffer))
            depth_has_child.append(False)
            if len(depth_has_child) > 1:
                depth_has_child[-2] = True
            buffer = ""
        elif ch == "}":
            selector = stack.pop()
            had_child = depth_has_child.pop()
            if not had_child:
                yield list(stack), selector, buffer
            buffer = ""
        elif ch in "\"'":
            end = css.index(ch, i + 1)
            buffer += css[i:end + 1]
            i = end + 1
            continue
        else:
            buffer += ch
        i += 1


def strip_comment_prefix(selector):
    """A rule's selector text can start with the comments before it."""
    return re.sub(r"/\*.*?\*/", "", selector, flags=re.S).strip()


def token_body(body, where):
    """The block's declarations, one per line, comments kept; tokens only."""
    for declaration in re.sub(r"/\*.*?\*/", "", body, flags=re.S).split(";"):
        name = declaration.split(":", 1)[0].strip()
        if name and not (name.startswith("--") or name == "color-scheme"):
            sys.exit(f"sync_tokens: {where} sets {name}, which is not a token; only token blocks are copied.")
    lines = [raw.rstrip() for raw in body.strip("\n").split("\n")]
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    cut = min(indents) if indents else 0
    return "\n".join(("  " + l[cut:]) if l.strip() else "" for l in lines).strip("\n")


def build(website):
    source = website / SOURCE
    css = source.read_text(encoding="utf-8")
    blocks = []
    for parents, selector, body in rules(css):
        if strip_comment_prefix(selector) != ":root":
            continue
        where = " ".join(parents + [":root"])
        blocks.append((parents, token_body(body, where)))
    if not blocks or blocks[0][0]:
        sys.exit(f"sync_tokens: {source} has no top-level :root block.")
    out = [
        "/*",
        "  GENERATED FILE. Never edit it by hand: edit the website, then re-run the script.",
        f"  Source: the token blocks (:root rules) of ~/Documents/GitHub/Website/{SOURCE.as_posix()},",
        "  whose values and roles are documented in that repository's docs/design-system.xml.",
        "  Written by tools/sync_tokens.py; its --check fails when this copy has drifted.",
        "  The light block appears twice, so data-theme on <html> can force either mode.",
        "*/",
        "",
    ]
    for parents, body in blocks:
        if not parents:
            out += [":root {", body, "}", ""]
        elif parents == [LIGHT_QUERY]:
            nested = "\n".join(("  " + l) if l else "" for l in body.split("\n"))
            out += [f"{LIGHT_QUERY} {{", '  :root:not([data-theme="dark"]) {', nested, "  }", "}", ""]
            out += [':root[data-theme="light"] {', body, "}", ""]
        else:
            nested = "\n".join(("  " + l) if l else "" for l in body.split("\n"))
            head = " { ".join(parents)
            out += [f"{head} {{", "  :root {", nested, "  }", "}" * len(parents), ""]
    return "\n".join(out).rstrip("\n") + "\n"


def website_path(arg=None):
    return Path(arg or os.environ.get("WEBSITE_REPO") or DEFAULT_WEBSITE)


def drifted(website):
    """None when the website is absent; else True when tokens.css differs from what the website gives."""
    if not (website / SOURCE).exists():
        return None
    return not OUT.exists() or OUT.read_text(encoding="utf-8") != build(website)


def sync_tool(check):
    """Copy (or check) the French tool's tool-tokens.css; returns False when the copy has drifted."""
    french = Path(os.environ.get("FRENCH_REPO") or DEFAULT_FRENCH)
    source = french / TOOL_SOURCE
    if not source.exists():
        if check:
            print(f"sync_tokens: no French tool at {french}; skipping the tool-tokens check.")
            return True
        sys.exit(f"sync_tokens: no {TOOL_SOURCE} under {french}; set FRENCH_REPO.")
    text = TOOL_HEADER + source.read_text(encoding="utf-8")
    current = TOOL_OUT.exists() and TOOL_OUT.read_text(encoding="utf-8") == text
    if check:
        if not current:
            print(f"sync_tokens: {TOOL_OUT.relative_to(ROOT)} has drifted from the French tool's; run tools/sync_tokens.py.", file=sys.stderr)
        return current
    if not current:
        TOOL_OUT.write_text(text, encoding="utf-8")
        print(f"sync_tokens: wrote {TOOL_OUT.relative_to(ROOT)}.")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if a copy differs from its source")
    parser.add_argument("--website", type=Path, default=None)
    args = parser.parse_args()
    tool_ok = sync_tool(args.check)
    website = website_path(args.website)
    if not (website / SOURCE).exists():
        if args.check:
            print(f"sync_tokens: no website at {website}; skipping the check.")
            sys.exit(0 if tool_ok else 1)
        sys.exit(f"sync_tokens: no {SOURCE} under {website}; pass --website PATH.")
    text = build(website)
    current = OUT.exists() and OUT.read_text(encoding="utf-8") == text
    if args.check:
        if not current:
            print(f"sync_tokens: {OUT.relative_to(ROOT)} has drifted from the website's tokens; run tools/sync_tokens.py.", file=sys.stderr)
        if not (current and tool_ok):
            sys.exit(1)
        print(f"sync_tokens: {OUT.relative_to(ROOT)} and {TOOL_OUT.relative_to(ROOT)} match their sources.")
        return
    if current:
        print("sync_tokens: already current.")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"sync_tokens: wrote {OUT.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
