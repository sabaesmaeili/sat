"""The question bank: paths, loading and validation against bank/README.md. Standard library only.

Used by tools/import_staging.py, tools/check.py and tools/build.py.
"""
import html.parser
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "bank"
SECTIONS = ("writing", "math")
SET_NAME = {"writing": "Writing drill", "math": "Math drill"}
PLAYBOOK = {"writing": "writing-playbook.html", "math": "math-playbook.html"}
KEYS = ["id", "origin", "source", "set", "number", "section", "exam", "difficulty", "format", "stimulus", "question",
        "options", "answer", "accepted", "rationale", "media", "refs", "duplicate_of", "notes"]
TAGS = {"i", "b", "u", "sup", "sub", "ul", "li", "table", "caption", "tr", "th", "td"}
LOCATOR = "College Board SAT Suite Question Bank › {id} › {part}"
MEDIA_TOKEN = re.compile(r"\[\[media:(\d+)\]\]")
MATH = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.S)


class _Tags(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.errs, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in TAGS:
            self.errs.append(f"tag <{tag}> not allowed")
        if attrs:
            self.errs.append(f"<{tag}> has attributes")
        self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.errs.append(f"<{tag}/> not allowed")

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errs.append(f"</{tag}> doesn't close {self.stack[-1:] or 'anything'}")
        else:
            self.stack.pop()


def text_errors(s, where):
    """Problems with one text value (README, "Text")."""
    if not isinstance(s, str) or not s.strip():
        return [f"{where}: empty or not a string"]
    errs = []
    if s != s.strip():
        errs.append(f"{where}: leading/trailing whitespace")
    if re.search(r"(?<!\n)\n(?!\n)", s) or "\n\n\n" in s:
        errs.append(f"{where}: single line break or 3+ newlines (paragraphs are separated by exactly one blank line)")
    if s.count("\\(") != s.count("\\)"):
        errs.append(f"{where}: {s.count(chr(92) + '(')} '\\(' vs {s.count(chr(92) + ')')} '\\)'")
    if s.count("\\[") != s.count("\\]"):
        errs.append(f"{where}: unbalanced \\[ \\]")
    prose = MATH.sub(" ", s)
    if re.search(r"(?<!\\)\$", prose):
        errs.append(f"{where}: bare $ (write \\$)")
    for m in re.finditer(r"_+", prose):
        if len(m.group()) != 6:
            errs.append(f"{where}: underscore run of {len(m.group())} (a blank is exactly ______)")
    p = _Tags()
    try:
        p.feed(prose)
        p.close()
    except Exception as e:  # noqa: BLE001
        errs.append(f"{where}: HTML parse error {e}")
    errs += [f"{where}: {e}" for e in p.errs]
    if p.stack:
        errs.append(f"{where}: unclosed {p.stack}")
    if re.search(r"&(?![a-zA-Z]+;|#\d+;|#x[0-9a-fA-F]+;)", prose):
        errs.append(f"{where}: bare & (write &amp;)")
    for para in s.split("\n\n"):
        if para.startswith("<table>") != para.endswith("</table>") or ("<table>" in para and not para.startswith("<table>")):
            errs.append(f"{where}: a table must be a whole paragraph")
        if ("<ul>" in para) and not (para.startswith("<ul>") and para.endswith("</ul>")):
            errs.append(f"{where}: a bulleted list must be a whole paragraph")
        if "[[media:" in para and not re.fullmatch(r"\[\[media:\d+\]\]", para):
            errs.append(f"{where}: [[media:N]] must be a whole paragraph or a whole option")
    return errs


def item_errors(it, stimulus, section, stimuli_ids=None):
    """Problems with one item (and the passage it points to, when given). README, "Item fields"."""
    errs = []
    if not isinstance(it, dict):
        return ["item is not an object"]
    if list(it) != KEYS:
        missing = [k for k in KEYS if k not in it]
        extra = [k for k in it if k not in KEYS]
        errs.append(f"item keys: missing {missing}, extra {extra}" if missing or extra else "item keys out of README order")
    iid = it.get("id")
    if not isinstance(iid, str) or not re.fullmatch(r"[0-9a-z]{6,12}", iid or ""):
        return errs + [f"id {iid!r} is not a question id"]
    fixed = {"origin": "original", "source": "cb-qbank", "section": section, "exam": "SAT", "set": SET_NAME[section]}
    for k, v in fixed.items():
        if it.get(k) != v:
            errs.append(f"{k} = {it.get(k)!r}, want {v!r}")
    if not isinstance(it.get("number"), int) or isinstance(it.get("number"), bool) or it["number"] < 1:
        errs.append("number must be a positive integer")
    if it.get("difficulty") not in (None, "Easy", "Medium", "Hard"):
        errs.append("difficulty must be Easy, Medium, Hard or null")
    fmt = it.get("format")
    if fmt == "mcq":
        o = it.get("options")
        if not isinstance(o, dict) or list(o) != ["A", "B", "C", "D"]:
            errs.append("options must be {A, B, C, D}")
        else:
            for k, v in o.items():
                errs += text_errors(v, f"option {k}")
        if it.get("answer") not in ("A", "B", "C", "D"):
            errs.append("answer must be a letter A-D for mcq")
        if it.get("accepted") != []:
            errs.append("accepted must be [] for mcq")
    elif fmt == "spr":
        if it.get("options") is not None:
            errs.append("options must be null for spr")
        acc = it.get("accepted")
        if not isinstance(acc, list) or not acc or not all(isinstance(a, str) and a.strip() == a and a for a in acc):
            errs.append("accepted must list each accepted answer as its own string")
        if not isinstance(it.get("answer"), str) or not it["answer"].strip():
            errs.append("answer must be the printed value(s)")
    else:
        errs.append("format must be mcq or spr")
    sid = it.get("stimulus")
    if sid is not None:
        if stimulus is None or not isinstance(stimulus, dict):
            errs.append(f"stimulus {sid!r} has no passage")
        else:
            if list(stimulus) != ["id", "text", "ref"] or stimulus.get("id") != sid:
                errs.append("a passage must be {id, text, ref} with its own id")
            errs += text_errors(stimulus.get("text"), "passage")
            if stimulus.get("ref") != (it.get("refs") or {}).get("question"):
                errs.append("the passage's ref must equal refs.question")
        if stimuli_ids is not None and sid not in stimuli_ids:
            errs.append(f"stimulus {sid!r} is not in the file's stimuli")
    elif stimulus is not None:
        errs.append("a passage is given but the item's stimulus is null")
    errs += text_errors(it.get("question"), "question")
    rat = it.get("rationale")
    if not isinstance(rat, list) or not rat:
        errs.append("rationale must be a non-empty list of paragraphs")
        rat = []
    for i, p in enumerate(rat):
        errs += text_errors(p, f"rationale[{i}]")
        if isinstance(p, str) and "\n" in p:
            errs.append(f"rationale[{i}]: one paragraph per list entry")
    base = f"img/{section}/{iid}"
    want = {"question": {"file": f"{base}-q.png", "locator": LOCATOR.format(id=iid, part="Question")},
            "answer": {"file": f"{base}-a.png", "locator": LOCATOR.format(id=iid, part="Rationale")}}
    if it.get("refs") != want:
        errs.append(f"refs must be exactly {json.dumps(want, ensure_ascii=False)}")
    media = it.get("media")
    if not isinstance(media, list):
        errs.append("media must be a list")
        media = []
    options = it.get("options") if isinstance(it.get("options"), dict) else {}
    places = {"question": [it.get("question") or ""] + ([(stimulus or {}).get("text") or ""] if stimulus else []),
              "options": [v for v in options.values() if isinstance(v, str)],
              "rationale": [p for p in rat if isinstance(p, str)]}
    for n, md in enumerate(media, 1):
        if not isinstance(md, dict) or list(md) != ["kind", "file", "where", "note"]:
            errs.append(f"media[{n}] must be {{kind, file, where, note}}")
            continue
        if md["kind"] != "figure":
            errs.append(f"media[{n}].kind must be figure")
        if md["where"] not in places:
            errs.append(f"media[{n}].where must be question, options or rationale")
            continue
        if md["file"] != f"media/{section}/{iid}-{n}.png":
            errs.append(f"media[{n}].file must be media/{section}/{iid}-{n}.png")
        elif not (BANK / md["file"]).is_file():
            errs.append(f"media[{n}]: bank/{md['file']} doesn't exist")
        if not isinstance(md.get("note"), str) or not md["note"].strip():
            errs.append(f"media[{n}]: note (the alt text) is empty")
        tok = f"[[media:{n}]]"
        uses = sum(t.count(tok) for t in places[md["where"]])
        others = sum(t.count(tok) for w, ts in places.items() if w != md["where"] for t in ts)
        if uses != 1 or others:
            errs.append(f"{tok} must be placed exactly once, in {md['where']}")
    for ts in places.values():
        for t in ts:
            for tok in MEDIA_TOKEN.findall(t):
                if not 1 <= int(tok) <= len(media):
                    errs.append(f"[[media:{tok}]] has no media entry")
    if it.get("duplicate_of") is not None and not isinstance(it.get("duplicate_of"), str):
        errs.append("duplicate_of must be an id or null")
    if not isinstance(it.get("notes"), list) or not all(isinstance(x, str) for x in it.get("notes") or []):
        errs.append("notes must be a list of strings")
    return errs


def bank_path(section, bank=BANK):
    return Path(bank) / "original" / f"{section}.json"


def load(section, bank=BANK):
    """The section's bank file, or an empty bank when it doesn't exist yet."""
    path = bank_path(section, bank)
    if not path.exists():
        return {"source": "cb-qbank", "section": section, "stimuli": {}, "items": []}
    return json.loads(path.read_text(encoding="utf-8"))


def bank_errors(data, section):
    """Problems with a whole section file (README, "Layout")."""
    errs = []
    if not isinstance(data, dict) or list(data) != ["source", "section", "stimuli", "items"]:
        return ["the file must be {source, section, stimuli, items}"]
    if data["source"] != "cb-qbank" or data["section"] != section:
        errs.append(f"source/section must be cb-qbank/{section}")
    stimuli, items = data["stimuli"], data["items"]
    if not isinstance(stimuli, dict) or not isinstance(items, list):
        return errs + ["stimuli must be an object and items a list"]
    ids, numbers, used = set(), [], set()
    for it in items:
        iid = it.get("id") if isinstance(it, dict) else None
        sid = it.get("stimulus") if isinstance(it, dict) else None
        for e in item_errors(it, stimuli.get(sid) if sid else None, section, set(stimuli)):
            errs.append(f"{iid}: {e}")
        if iid in ids:
            errs.append(f"{iid}: listed twice")
        ids.add(iid)
        if isinstance(it, dict):
            numbers.append(it.get("number"))
            if sid:
                used.add(sid)
    if numbers != sorted(numbers, key=lambda n: (n if isinstance(n, int) else 0)) or len(set(numbers)) != len(numbers):
        errs.append("items must be in drill order with distinct numbers")
    for sid in stimuli:
        if sid not in used:
            errs.append(f"passage {sid} is used by no item")
        if not isinstance(stimuli[sid], dict) or stimuli[sid].get("id") != sid:
            errs.append(f"passage {sid}: its id must be its key")
    return errs


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def annotations_path(section, bank=BANK):
    return Path(bank) / "annotations" / f"{section}.json"


def load_annotations(section, bank=BANK):
    path = annotations_path(section, bank)
    if not path.exists():
        return {"section": section, "origin": "annotation", "items": {}}
    return json.loads(path.read_text(encoding="utf-8"))
