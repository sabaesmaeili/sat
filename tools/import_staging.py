#!/usr/bin/env python3
"""Merge typed items into bank/original/<section>.json.

Each item is typed into its own file, <staging dir>/<id>.json, holding {"stimulus", "item"}:
the item (bank/README.md, "Item fields") and its passage, or null when it has none. This
validates every file, then merges the ones that pass into the bank by id: new items are
added, changed ones replaced, the rest kept; items stay in `number` order. Files that fail
are skipped and listed with their problems; re-running after fixing them, or after more
items arrive, is safe.

    python3 tools/import_staging.py writing staging/writing
    python3 tools/import_staging.py math staging/math --bank /tmp/bank-copy   # into a copy of bank/
    python3 tools/import_staging.py math staging/math --dry-run               # report only

The bank is written only when every merged item passes and no two items share a number.
Exit status: 0 when every staged file was imported (or already current), 1 when any was skipped.
Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

from bank import BANK, SECTIONS, bank_errors, bank_path, dump, item_errors, load


def read_staged(path, section, bank):
    """(item, stimulus) from a staging file, or raise ValueError with the problems."""
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError([f"not valid JSON: {e}"])
    if not isinstance(rec, dict) or set(rec) != {"stimulus", "item"}:
        raise ValueError(["the file must be {stimulus, item}"])
    it, st = rec["item"], rec["stimulus"]
    errs = item_errors(it, st, section, bank=bank)
    if isinstance(it, dict) and path.stem != it.get("id"):
        errs.append(f"file name doesn't match the id {it.get('id')!r}")
    if errs:
        raise ValueError(errs)
    return it, st


def merge(data, staged):
    """The bank with the staged (item, stimulus) pairs merged in by id; returns (data, added, replaced)."""
    items = {it["id"]: it for it in data["items"]}
    stimuli = dict(data["stimuli"])
    added, replaced = [], []
    for it, st in staged:
        old = items.get(it["id"])
        old_st = stimuli.get(old["stimulus"]) if old and old.get("stimulus") else None
        if old == it and old_st == st:
            continue
        (replaced if old else added).append(it["id"])
        if old and old.get("stimulus") and old["stimulus"] != it.get("stimulus"):
            stimuli.pop(old["stimulus"], None)
        items[it["id"]] = it
        if st is not None:
            stimuli[st["id"]] = st
    ordered = sorted(items.values(), key=lambda it: (it["number"], it["id"]))
    used = [it["stimulus"] for it in ordered if it.get("stimulus")]
    merged = {"source": "cb-qbank", "section": data["section"], "stimuli": {sid: stimuli[sid] for sid in used}, "items": ordered}
    return merged, added, replaced


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("section", choices=SECTIONS)
    parser.add_argument("staging", type=Path, help="the folder of <id>.json files")
    parser.add_argument("--bank", type=Path, default=BANK, help="the bank folder to merge into (default: bank/)")
    parser.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    args = parser.parse_args()
    files = sorted(args.staging.glob("*.json"))
    if not files:
        sys.exit(f"import_staging: no .json files in {args.staging}")
    staged, skipped = [], {}
    for path in files:
        try:
            staged.append(read_staged(path, args.section, args.bank))
        except ValueError as e:
            skipped[path.name] = e.args[0]
        except Exception as e:  # noqa: BLE001  one bad file is skipped and listed, never the whole import
            skipped[path.name] = [f"could not be checked: {type(e).__name__}: {e}"]
    data = load(args.section, args.bank)
    merged, added, replaced = merge(data, staged)
    errs = bank_errors(merged, args.section, args.bank)
    numbers = {}
    for it in merged["items"]:
        numbers.setdefault(it["number"], []).append(it["id"])
    errs += [f"number {n} is used by {', '.join(ids)}" for n, ids in numbers.items() if len(ids) > 1]
    for name, problems in skipped.items():
        print(f"skipped {name}:")
        for p in problems:
            print(f"   - {p}")
    if errs:
        print("import_staging: the merged bank would be invalid; nothing written:", file=sys.stderr)
        for e in errs:
            print(f"   - {e}", file=sys.stderr)
        sys.exit(2)
    path = bank_path(args.section, args.bank)
    print(f"import_staging: {args.section}: {len(staged)} valid of {len(files)} staged; "
          f"{len(added)} added, {len(replaced)} replaced, {len(skipped)} skipped; bank now {len(merged['items'])} items.")
    if args.dry_run:
        print("import_staging: dry run, nothing written.")
    elif added or replaced or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump(merged), encoding="utf-8")
        print(f"import_staging: wrote {path}")
    else:
        print("import_staging: the bank is already current.")
    sys.exit(1 if skipped else 0)


if __name__ == "__main__":
    main()
