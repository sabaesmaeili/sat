#!/usr/bin/env python3
"""Build the site into _site/ (generated, never committed). Standard library only.

    python3 tools/build.py                       build _site/ from site/ and bank/
    python3 tools/build.py --serve               build, then preview at http://localhost:8000
    python3 tools/build.py --bank DIR --out DIR  build from another bank folder into another folder (tests)

_site/ is site/ with every {{…}} filled in. The site is one folder tree (the French tool's way):
/ lists everything, <section>/ lists its cheat sheet and drill, <section>/cheat-sheet/ and
<section>/drill/ are the pages. Every page gets {{root}} (the relative path to the site's root) and
{{header}} (the mark, the address with a link per segment, and, inside a section, the menu of its
cheat sheet and drill). The drills (<section>/drill/index.html) get their questions from
bank/original/<section>.json, in `number` order, and our card links and hints from
bank/annotations/<section>.json; the list pages get the drills' question counts. Only the figures
the pages use are copied (into media/<section>/); the screenshots in img/ are not.
"""
import argparse
import html
import json
import re
import shutil
import struct
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bank import BANK, ROOT, SECTIONS, load, load_annotations

SITE = ROOT / "site"
OUT = ROOT / "_site"
STORAGE_KEY = {"writing": "sat-drill80-writing", "math": "sat-drill80-math"}  # the original pages' keys: saved progress survives
MATHJAX = ('<script>window.MathJax={tex:{inlineMath:[["\\\\(","\\\\)"]]},svg:{fontCache:"global"},options:{ignoreHtmlClass:"mj-wait"}};</script>\n'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.js" async></script>')
MATH = re.compile(r"(\\\(.*?\\\)|\\\[.*?\\\])", re.S)
MEDIA = re.compile(r"\[\[media:(\d+)\]\]")


class BuildError(Exception):
    pass


def esc(s):
    return html.escape(s, quote=True)


def png_size(path):
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def inline(s):
    """A text value's inline HTML: prose passes through (bank/README.md allows only plain markup there), a blank becomes
    a drawn line, \\$ in prose a dollar sign; math keeps its TeX for MathJax, with <, > and & escaped for HTML."""
    out = []
    for i, part in enumerate(MATH.split(s)):
        if i % 2:
            out.append(part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        else:
            part = part.replace("\\$", "$")
            out.append(part.replace("______", '<span class="blank"><span class="vh">blank</span></span>'))
    return "".join(out)


def figure(item, n, section, used, cls="fig"):
    media = item["media"]
    if not 1 <= n <= len(media):
        raise BuildError(f"{item['id']}: [[media:{n}]] has no media entry")
    md = media[n - 1]
    src = BANK / md["file"]
    if not src.is_file():
        raise BuildError(f"{item['id']}: bank/{md['file']} doesn't exist")
    used.add(md["file"])
    size = png_size(src)
    dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
    img = f'<img src="../../{esc(md["file"])}" alt="{esc(md["note"])}"{dims} loading="lazy">'
    return f'<figure class="{cls} figure-panel">{img}</figure>' if cls else f'<span class="figure-panel">{img}</span>'


def paragraphs(s, item, section, used):
    out = []
    for para in s.split("\n\n"):
        m = MEDIA.fullmatch(para)
        if m:
            out.append(figure(item, int(m.group(1)), section, used))
        elif para.startswith("<table>"):
            out.append(f'<div class="tbl">{inline(para)}</div>')
        elif para.startswith("<ul>"):
            out.append(inline(para))
        elif re.fullmatch(r"\\\[.*?\\\]", para, re.S):
            out.append(f'<div class="disp">{inline(para)}</div>')
        else:
            out.append(f"<p>{inline(para)}</p>")
    return "\n".join(out)


def has_math(s):
    return "\\(" in s or "\\[" in s


def render_item(item, stimulus, ann, pos, section, used):
    iid, mc = item["id"], item["format"] == "mcq"
    playbook = "../cheat-sheet/"
    label = (f'<a class="lbl" href="{playbook}#{esc(ann["anchor"])}" target="_blank" rel="noopener">'
             f'<b>{ann["card"]} · {esc(ann["card_name"])}</b> → {esc(ann["label"])}</a>')
    parts = [f'<article class="q kk{ann["card"]}" id="q-{iid}">',
             f'<div class="qh"><span class="qn">Q{pos}</span>{label}<span class="mark"></span></div>',
             '<div class="qbody content">']
    if stimulus:
        parts.append(f'<div class="passage">\n{paragraphs(stimulus["text"], item, section, used)}\n</div>')
    parts.append(f'<div class="stem">\n{paragraphs(item["question"], item, section, used)}\n</div>')
    parts.append("</div>")
    if mc:
        opts = []
        for letter, text in item["options"].items():
            m = MEDIA.fullmatch(text)
            body = figure(item, int(m.group(1)), section, used, cls=None) if m else inline(text)
            opts.append(f'<button class="mc" data-c="{letter}"><span class="L">{letter}</span><span class="ot content">{body}</span></button>')
        parts.append('<div class="opts" role="group" aria-label="Choices for Q%d">%s</div>' % (pos, "".join(opts)))
        entry = ""
    else:
        entry = (f'<input type="text" id="in-{iid}" aria-label="Your answer for Q{pos}" placeholder="your answer" autocomplete="off" '
                 f'autocapitalize="off" spellcheck="false"><button class="chk">Check</button>')
    hint = ann.get("hint")
    hint_btn = '<button class="hintbtn" aria-expanded="false">Hint</button>' if hint else ""
    parts.append(f'<div class="ans">{entry}<span class="fb" aria-live="polite"></span><span class="acts">{hint_btn}'
                 f'<button class="revbtn" aria-expanded="false">Show answer</button></span></div>')
    if hint:
        anchor = hint.get("anchor") or ann["anchor"]
        parts.append(f'<div class="hint mj-wait" hidden><span class="t">{esc(hint["tag"])}</span><b>{esc(hint["title"])}</b>'
                     f'<p>{esc(hint["text"])}</p><a href="{playbook}#{esc(anchor)}" target="_blank" rel="noopener">See it on the cheat sheet →</a></div>')
    rationale = paragraphs("\n\n".join(item["rationale"]), item, section, used)
    parts.append(f'<div class="rat mj-wait" hidden><p class="ca">Correct answer: {inline(item["answer"])}</p>'
                 f'<div class="content">\n{rationale}\n</div></div>')
    parts.append("</article>")
    return "\n".join(parts)


def count_words(n):
    return f"{n} question" if n == 1 else f"{n} questions"


def render_drill(section, bank, used):
    data, notes = load(section, bank), load_annotations(section, bank)["items"]
    items = data["items"]
    missing = [it["id"] for it in items if it["id"] not in notes or "card" not in notes[it["id"]]]
    if missing:
        raise BuildError(f"{section}: no annotation (card) for {', '.join(missing)}")
    cards = {}
    for it in items:
        a = notes[it["id"]]
        cards.setdefault(a["card"], {"name": a["card_name"], "n": 0})["n"] += 1
    order = sorted(cards)
    blocks, js, math = [], [], False
    for pos, it in enumerate(items, 1):
        st = data["stimuli"].get(it["stimulus"]) if it["stimulus"] else None
        a = notes[it["id"]]
        blocks.append(render_item(it, st, a, pos, section, used))
        texts = [it["question"], *(it["options"] or {}).values(), *it["rationale"], (st or {}).get("text", ""), (a.get("hint") or {}).get("text", "")]
        math = math or any(has_math(t) for t in texts)
        row = {"id": it["id"], "card": a["card"], "answer": it["answer"], "mc": it["format"] == "mcq"}
        if it["format"] == "spr":
            row["acc"] = it["accepted"]
        js.append(row)
    n = len(items)
    chips = [f'<button class="chip" id="c-all" aria-pressed="true">All <small>{n}</small></button>']
    chips += [f'<button class="chip kk{k}" data-card="{k}" aria-pressed="false"><span class="d"></span>{k} · {esc(cards[k]["name"])} <small>{cards[k]["n"]}</small></button>' for k in order]
    bar = "\n".join([
        '<section class="bar" id="bar" aria-label="Score and filters">',
        '  <div class="scorerow">',
        '    <span class="score" id="score">0 / 0 <small id="scoresub"></small></span>',
        '    <span class="prog" aria-hidden="true"><i id="prog"></i></span>',
        "  </div>",
        f'  <div class="chips"><span class="lab">Subject</span>{"".join(chips)}</div>',
        '  <div class="chips"><span class="lab">Show</span>',
        '    <button class="chip" data-status="all" aria-pressed="true">All</button>',
        '    <button class="chip" data-status="todo" aria-pressed="false">Not done yet</button>',
        '    <button class="chip" data-status="missed" aria-pressed="false">Missed</button>',
        '    <button class="chip" data-status="right" aria-pressed="false">Got right</button>',
        '    <span class="shown" id="shown"></span>',
        "  </div>",
        '  <div class="chips">',
        '    <label class="switch"><input type="checkbox" id="labelsToggle"> Show which cheat-sheet card each question uses</label>',
        f'    <span class="btns"><button id="shuffleBtn">Shuffle</button><button id="orderBtn">Q1 → Q{max(n, 1)}</button><button id="resetBtn">Start over</button></span>',
        "  </div>",
        "</section>"])
    rows = "".join(f'<div class="srow kk{k}" id="s-{k}"><span class="nm"><i></i>{k} · {esc(cards[k]["name"])}</span><span class="st"></span>\n'
                   f'<span class="go"><button data-practice="{k}">Practice these</button></span><div class="minibar"><i></i></div></div>' for k in order)
    summary = f'<section class="sum" aria-label="Progress by subject">\n  <h2>Progress by subject</h2>\n  {rows}\n</section>'
    conf = {"key": STORAGE_KEY[section], "mathjax": math}
    data_js = (f"var DATA = {json.dumps(js, ensure_ascii=False)};\nvar CONF = {json.dumps(conf)};").replace("</", "<\\/")
    hard = f"{n} hard question" if n == 1 else f"{n} hard questions"
    return {"count": count_words(n), "count_hard": hard, "bar": bar, "questions": "\n".join(blocks), "summary": summary, "data": data_js,
            "mathjax": MATHJAX if math else ""}, n


def fill(text, values, where):
    def sub(m):
        if m.group(1) not in values:
            raise BuildError(f"{where}: unknown placeholder {{{{{m.group(1)}}}}}")
        return values[m.group(1)]
    return re.sub(r"\{\{([\w:]+)\}\}", sub, text)


MENU = (("cheat-sheet", "cheat sheet"), ("drill", "drill"))


def header(rel):
    """The website's header for the page at rel (a path under site/): the mark (the root), one link per segment of the
    address, the current one marked; inside a section, its menu: the cheat sheet and the drill."""
    segs = rel.parent.parts
    current = ' aria-current="page"'

    def up(n):
        return "../" * n or "./"
    crumbs = "".join('/<a href="%s"%s>%s</a>' % (up(len(segs) - 1 - i), current if i == len(segs) - 1 else "", seg)
                     for i, seg in enumerate(segs))
    nav = ""
    if segs:
        here = segs[1] if len(segs) > 1 else None
        base = "../" if len(segs) > 1 else ""
        links = "".join('<a href="%s"%s>%s</a>' % ("./" if key == here else base + key + "/", current if key == here else "", name)
                        for key, name in MENU)
        nav = '\n  <nav class="nav" aria-label="%s pages">%s</nav>' % (segs[0], links)
    return ('<header class="top frame">\n  <a class="mark" href="%s"%s>sat</a><span class="address">%s</span>%s\n</header>'
            % (up(len(segs)), "" if segs else current, crumbs, nav))


def build(bank=BANK, out=OUT, quiet=False):
    bank, out = Path(bank), Path(out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE, out, ignore=shutil.ignore_patterns(".DS_Store"))
    used, counts, drills = set(), {}, {}
    for section in SECTIONS:
        drills[section], counts[section] = render_drill(section, bank, used)
    globals_ = {f"count:{s}": count_words(n) for s, n in counts.items()}
    for s in SECTIONS:  # the cards on each cheat sheet, as the list pages show them
        n = len(re.findall(r'<section class="card k\d', (SITE / s / "cheat-sheet" / "index.html").read_text(encoding="utf-8")))
        globals_[f"cards:{s}"] = f"{n} card" if n == 1 else f"{n} cards"
    for page in sorted(out.rglob("*.html")):
        rel = page.relative_to(out)
        section = rel.parts[0] if len(rel.parts) == 3 and rel.parts[1] == "drill" and rel.parts[0] in SECTIONS else None
        values = dict(globals_, root="../" * (len(rel.parts) - 1), header=header(rel), **(drills[section] if section else {}))
        page.write_text(fill(page.read_text(encoding="utf-8"), values, page.name), encoding="utf-8")
    for rel in sorted(used):
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bank / rel if (bank / rel).is_file() else BANK / rel, dest)
    if not quiet:
        print(f"Built {out}: writing {counts['writing']} questions, math {counts['math']} questions, {len(used)} figures.")
    return counts


def serve(out, port=8000):
    handler = partial(SimpleHTTPRequestHandler, directory=str(out))
    with ThreadingHTTPServer(("localhost", port), handler) as server:
        print(f"Previewing at http://localhost:{port} (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bank", type=Path, default=BANK)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    try:
        build(args.bank, args.out)
    except BuildError as e:
        sys.exit(f"build: {e}")
    if args.serve:
        serve(args.out)


if __name__ == "__main__":
    main()
