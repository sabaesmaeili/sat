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
bank/annotations/<section>.json (an item's extra tags count it under each tag's card too, the card that holds
that anchor on the cheat sheet); the list pages get the drills' question counts. Only the figures
the pages use are copied (into media/<section>/); the screenshots in img/ are not.
"""
import argparse
import html
import html.parser
import json
import re
import shutil
import struct
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bank import BANK, ROOT, SECTIONS, load, load_annotations, parse_text

SITE = ROOT / "site"
OUT = ROOT / "_site"
STORAGE_KEY = {"writing": "sat-drill80-writing", "math": "sat-drill80-math"}  # the original pages' keys: saved progress survives
# MathJax 3.2.2 from cdnjs, locked down: ui/safe with no URLs, classes, ids or styles; the html extension (\\href,
# \\class, \\style, \\cssId, \\data) removed and not autoloaded, nor \\unicode; bank.py rejects those macros too.
MATHJAX = ('<script>window.MathJax={loader:{load:["ui/safe"]},'
           'tex:{inlineMath:[["\\\\(","\\\\)"]],packages:{"[-]":["html"]},autoload:{html:[],unicode:[]}},'
           'svg:{fontCache:"global"},'
           'options:{ignoreHtmlClass:"mj-wait",safeOptions:{allow:{URLs:"none",classes:"none",cssIDs:"none",styles:"none"}}}};</script>\n'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.js" async></script>')
MATH = re.compile(r"(\\\(.*?\\\)|\\\[.*?\\\])", re.S)
MEDIA = re.compile(r"\[\[media:(\d+)\]\]")


class BuildError(Exception):
    pass


class Sheet(html.parser.HTMLParser):
    """A cheat sheet's anchors: for each id, the card (<section class="card kN">) that contains it and its title (the
    text of its first h2, h3 or b), read from the page itself, so moving a sub-test to another card needs no other edit."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.card, self.title, self.text, self.card_id = {}, {}, {}, {}  # card_id: card number → its section's id
        self.stack, self.into, self.depth = [], None, 0  # open elements as (tag, id, card); the id whose title is being read

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        a = dict(attrs)
        m = re.search(r"\bcard k(\d+)\b", a.get("class") or "") if tag == "section" else None
        card = int(m.group(1)) if m else next((c for _, _, c in reversed(self.stack) if c), None)
        iid = a.get("id")
        if iid:
            self.card[iid], self.text[iid] = card, ""
            if m:
                self.card_id.setdefault(card, iid)
        if tag in ("h2", "h3", "b") and self.into is None:
            owner = next((i for _, i, _ in reversed(self.stack) if i), None)
            if owner and owner not in self.title:
                self.into, self.depth = owner, len(self.stack)
                self.title[owner] = ""
        self.stack.append((tag, iid, card))

    def handle_endtag(self, tag):
        if tag in self.VOID or all(t != tag for t, _, _ in self.stack):
            return
        while self.stack and self.stack.pop()[0] != tag:
            pass
        if self.into and len(self.stack) <= self.depth:
            self.into = None

    def handle_data(self, data):
        if self.into:
            self.title[self.into] += data
        for _, iid, _ in self.stack:
            if iid:
                self.text[iid] += data


def read_sheet(section):
    """The section's cheat sheet (site/<section>/cheat-sheet/index.html), parsed: Sheet.card, .title, .text by id."""
    sheet = Sheet()
    sheet.feed((SITE / section / "cheat-sheet" / "index.html").read_text(encoding="utf-8"))
    return sheet


# Short tag labels where the cheat-sheet title doesn't shorten well (anchor → label); see tag_labels.
TAG_LABEL = {"w-form": "verb form", "m-pyth": "3-4-5 triples"}


def tag_labels(notes, sheet):
    """A short label for every anchor, for the extra card links (tags): the label an annotation already gives that
    anchor (the most used one), else TAG_LABEL, else the anchor's title on the cheat sheet, shortened (before a colon,
    without a trailing "test", lower case unless it is all capitals), else its text."""
    used = {}
    for a in notes.values():
        used.setdefault(a["anchor"], []).append(a["label"])
    out = {}
    for iid in sheet.card:
        if iid in used:
            out[iid] = max(used[iid], key=used[iid].count)
        elif iid in TAG_LABEL:
            out[iid] = TAG_LABEL[iid]
        else:
            plain = lambda s: " ".join(re.sub(r"\\[()\[\]]", "", s).split())  # no TeX delimiters in a label
            t = re.sub(r"\s+test$", "", plain(sheet.title.get(iid) or "").split(":")[0], flags=re.I).strip()
            out[iid] = (t if t.isupper() else t.lower()) if t else plain(sheet.text[iid])[:24].strip() or iid
    return out


def esc(s):
    return html.escape(s, quote=True)


def png_size(path):
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def inline(s):
    """A text value's inline HTML, serialized from its parse (bank.parse_text): only the allowed tags, without
    attributes; text escaped, with a blank drawn as a line and \\$ as a dollar sign; math kept as TeX for MathJax,
    with &, < and > escaped. Anything bank.py rejects raises, so nothing unchecked reaches a page."""
    tokens, errs = parse_text(s)
    if errs:
        raise BuildError(f"invalid text ({'; '.join(errs)}): {s[:60]!r}")
    out = []
    for kind, value in tokens:
        if kind == "start":
            out.append(f"<{value}>")
        elif kind == "end":
            out.append(f"</{value}>")
        elif kind == "math":
            out.append(value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        else:
            text = html.escape(value, quote=False).replace("\\$", "$")
            out.append(text.replace("______", '<span class="blank"><span class="vh">blank</span></span>'))
    return "".join(out)


def figure(item, n, section, used, bank, cls="fig"):
    media = item["media"]
    if not 1 <= n <= len(media):
        raise BuildError(f"{item['id']}: [[media:{n}]] has no media entry")
    md = media[n - 1]
    src = Path(bank) / md["file"]
    if not src.is_file():
        raise BuildError(f"{item['id']}: bank/{md['file']} doesn't exist")
    used.add(md["file"])
    size = png_size(src)
    dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
    img = f'<img src="../../{esc(md["file"])}" alt="{esc(md["note"])}"{dims} loading="lazy">'
    return f'<figure class="{cls} figure-panel">{img}</figure>' if cls else f'<span class="figure-panel">{img}</span>'


def paragraphs(s, item, section, used, bank):
    out = []
    for para in s.split("\n\n"):
        m = MEDIA.fullmatch(para)
        if m:
            out.append(figure(item, int(m.group(1)), section, used, bank))
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


def render_item(item, stimulus, ann, pos, section, used, bank, tags=()):
    """One question. tags: its extra card links, as (anchor, card, card name, label), each a small link after the main one."""
    iid, mc = item["id"], item["format"] == "mcq"
    playbook = "../cheat-sheet/"
    label = (f'<a class="lbl" href="{playbook}#{esc(ann["anchor"])}" target="_blank" rel="noopener">'
             f'<b>{ann["card"]} · {esc(ann["card_name"])}</b> → {esc(ann["label"])}</a>')
    label += "".join(f'<a class="lbl xtag kk{k}" href="{playbook}#{esc(anchor)}" target="_blank" rel="noopener" '
                     f'title="Also card {k} · {esc(name)} → {esc(words)}"><b>+ {k}</b> · {esc(words)}</a>'
                     for anchor, k, name, words in tags)
    parts = [f'<article class="q kk{ann["card"]}" id="q-{iid}">',
             f'<div class="qh"><span class="qn">Q{pos}</span>{label}<span class="mark"></span></div>',
             '<div class="qbody content">']
    if stimulus:
        parts.append(f'<div class="passage">\n{paragraphs(stimulus["text"], item, section, used, bank)}\n</div>')
    parts.append(f'<div class="stem">\n{paragraphs(item["question"], item, section, used, bank)}\n</div>')
    parts.append("</div>")
    if mc:
        opts = []
        for letter, text in item["options"].items():
            m = MEDIA.fullmatch(text)
            body = figure(item, int(m.group(1)), section, used, bank, cls=None) if m else inline(text)
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
    rationale = paragraphs("\n\n".join(item["rationale"]), item, section, used, bank)
    parts.append(f'<div class="rat mj-wait" hidden><p class="ca">Correct answer: {esc(item["answer"])}</p>'
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
    # An item counts under its main card and under each tag's card: the cheat-sheet card that holds the tag's anchor,
    # read from the page, so a sub-test moved to another card moves its tagged items with it.
    sheet, cards, sets = read_sheet(section), {}, {}
    words = tag_labels(notes, sheet)
    for it in items:
        a = notes[it["id"]]
        cards.setdefault(a["card"], {"name": a["card_name"], "n": 0})
    for it in items:
        a = notes[it["id"]]
        for anchor in a.get("tags") or []:
            if sheet.card.get(anchor) is None:
                raise BuildError(f"{section}: {it['id']}: tag #{anchor} isn't inside a card on the cheat sheet")
        sets[it["id"]] = sorted({a["card"], *(sheet.card[t] for t in a.get("tags") or [])})
        for k in sets[it["id"]]:  # a card that only tags reach is named by its title on the cheat sheet
            cards.setdefault(k, {"name": " ".join(sheet.title.get(sheet.card_id.get(k), "").split()) or f"Card {k}", "n": 0})["n"] += 1
    order = sorted(cards)
    blocks, js, math = [], [], False
    for pos, it in enumerate(items, 1):
        st = data["stimuli"].get(it["stimulus"]) if it["stimulus"] else None
        a = notes[it["id"]]
        tags = [(t, sheet.card[t], cards[sheet.card[t]]["name"], words[t]) for t in a.get("tags") or []]
        blocks.append(render_item(it, st, a, pos, section, used, bank, tags))
        texts = [it["question"], *(it["options"] or {}).values(), *it["rationale"], (st or {}).get("text", ""), (a.get("hint") or {}).get("text", "")]
        math = math or any(has_math(t) for t in texts)
        row = {"id": it["id"], "card": a["card"], "cards": sets[it["id"]], "answer": it["answer"], "mc": it["format"] == "mcq"}
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
SUBJECT = {"writing": "english", "math": "math"}  # the subject toggle's words (the owner's); the folders stay writing/, math/


def header(rel):
    """The website's header for the page at rel (a path under site/): the mark (the root), one link per segment of the
    address, the current one marked; inside a section, its menu (the cheat sheet and the drill) and the subject
    toggle, drawn like the French tool's language switch: the current subject, which switches to the same page of the
    other subject (writing/drill/ to math/drill/, writing/ to math/)."""
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
        other = next(x for x in SUBJECT if x != segs[0])
        toggle = '<a class="lang" href="%s" title="switch to %s" aria-label="subject: %s; switch to %s">%s</a>' % (
            up(len(segs)) + "/".join((other,) + segs[1:]) + "/", SUBJECT[other], SUBJECT[segs[0]], SUBJECT[other], SUBJECT[segs[0]])
        nav = '\n  <nav class="nav" aria-label="%s pages">%s%s</nav>' % (segs[0], links, toggle)
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
        shutil.copy2(bank / rel, dest)
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
