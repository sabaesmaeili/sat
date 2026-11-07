# SAT question bank

The drills' questions as data, one record per item, each pointing back to the screenshot it was typed from. The format follows the TCF question bank's (`~/Documents/GitHub/Projects/French/_Workspace/question-bank/README.md`), adapted to the SAT. The pages are built from these files by `tools/build.py`; `tools/check.py` enforces everything below.

## Originals and annotations

- `original/` holds only what the College Board printed, with `"origin": "original"`: the passage, question, choices, correct answer and rationale of each item, typed from the screenshots in `../img/`. The text is the source's, verbatim: nothing reworded, corrected or completed. A doubt (a smudged character, a possible typo in the source) goes in `notes`, never into a silent fix.
- `annotations/` holds our own additions, keyed by item id: the cheat-sheet card an item drills, its hint, and anything else we write. Never put our wording in `original/`, and never put the College Board's in `annotations/`.

## Layout

`original/<section>.json` (`writing.json`, `math.json`); cropped figures in `media/<section>/`; our additions in `annotations/<section>.json`; the screenshots the items were typed from in `../img/<section>/` (`<id>-q.png` question, `<id>-a.png` answer and rationale). Each item file holds:

| Key | Meaning |
| --- | --- |
| `source`, `section` | `cb-qbank` and the file's section (`writing` or `math`) |
| `stimuli` | Passages, by id: `{id: {id, text, ref}}`. An item points to one with `stimulus`. Each SAT passage belongs to one item, so its id is the item's id. |
| `items` | The items, in drill order |

## Item fields

Every item has all of these keys; a value that does not apply is `null` (or `[]` for lists).

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | The College Board question ID, e.g. `e41018de` (the screenshot's file name). Stable: the drills save progress under it. |
| `origin` | `original` | See above |
| `source` | `cb-qbank` | College Board SAT Suite Question Bank |
| `set` | string | The drill: `Writing drill` or `Math drill` |
| `number` | int | Position in the drill (Q1 to Q80) |
| `section` | `writing` / `math` | |
| `exam` | `SAT` | |
| `difficulty` | `Easy` / `Medium` / `Hard` / null | The College Board's rating, when the screenshot shows it (null otherwise) |
| `format` | `mcq` / `spr` | Multiple choice, or student-produced response (the student types the answer) |
| `stimulus` | string / null | Id of the passage in the file's `stimuli` (writing); null when there is none (math) |
| `question` | string | The question as printed under "Question", after any passage: for writing the prompt line ("Which choice completes the text…"), for math the whole question |
| `options` | object / null | `{"A": text, "B": …, "C": …, "D": …}` for `mcq`; null for `spr` |
| `answer` | string | As printed after "Correct Answer:": a letter for `mcq` (`"A"`), the printed value(s) for `spr` (`"17.5, 35/2"`) |
| `accepted` | list | `spr` only: each accepted answer as its own string, in printed order (`["17.5", "35/2"]`); `[]` for `mcq` |
| `rationale` | list | The paragraphs printed under "Rationale", in order, verbatim |
| `media` | list | Figures the item needs that aren't text (graphs, diagrams, scatterplots), each `{kind, file, where, note}`: `kind` `figure`; `file` the crop in `media/<section>/`, named `<id>-<n>.png` from 1; `where` `question`, `options` or `rationale`; `note` a short description of what it shows (also the image's alt text) |
| `refs` | object | `question` and `answer`: where to check the item (below) |
| `duplicate_of` | string / null | Id of an item this one repeats |
| `notes` | list | Doubts about a character, anything a checker should know; plain strings |

## Text

Every text value (a passage, `question`, an option, a rationale paragraph) is a string in this form:

- **Paragraphs** are separated by a blank line (`\n\n`). No other line breaks: the source wraps lines by width, so its line ends are not kept.
- **Characters** as printed: curly quotes (“ ” ‘ ’), em dashes (—), en dashes (–), ellipses as printed (`...` or `…`), degree signs. Straight quotes only where the source has them.
- **A blank** (the line a choice fills) is exactly six underscores: `______`.
- **Math** is TeX for MathJax, as the source sets it: `\(…\)` inline, `\[…\]` on its own line. The source typesets every variable and expression, even in prose: write `the \(xy\)-plane`, `\(k\) is a positive constant`, `\(\angle Q\)`, `\(t^\circ\)`. Choices that are expressions are fully inside `\(…\)`. Numbers that the source sets as math (inside the same font as the variables) go in `\(…\)` too; plain numbers in prose stay plain. Use standard macros only (`\frac`, `\sqrt`, `\angle`, `\circ`, `\pi`, `\le`, `\ge`, `\ne`, `\cdot`, `\times`, `\left( \right)`, `\text{}`); for a dollar amount write `\$`.
- **Markup**: only these HTML tags, with no attributes: `<i>` (italic words that aren't math, e.g. a title), `<b>`, `<u>` (an underlined portion), `<sup>`, `<sub>`, `<ul>` and `<li>` (bulleted notes: a paragraph that is only a `<ul>…</ul>`), and tables: `<table>`, `<caption>`, `<tr>`, `<th>`, `<td>` (a paragraph that is only the `<table>…</table>`; math inside cells is fine). Escape a literal `<`, `>` or `&` in prose as `&lt;`, `&gt;`, `&amp;` (inside `\(…\)` write `\lt`, `\gt`, or `<` / `>` with spaces around them).
- **A figure** is placed by a paragraph that is exactly `[[media:N]]` (N is its 1-based position in `media`), or by an option whose whole value is `[[media:N]]` (choices that are graphs). Every figure in `media` is placed exactly once.
- **Tables are text**, never crops: type them as `<table>`. Only graphs, diagrams and other drawings are cropped.

## References

| Key | Example |
| --- | --- |
| `file` | `img/writing/e41018de-q.png` (repo-relative) |
| `locator` | `College Board SAT Suite Question Bank › e41018de › Question` (or `› Rationale`) |

The passage's `ref` in `stimuli` is the same as the item's `refs.question`.

## Examples

```json
{
  "source": "cb-qbank",
  "section": "writing",
  "stimuli": {
    "e41018de": {
      "id": "e41018de",
      "text": "In 1977, legendary Puerto Rican performer Rita Moreno won an Emmy Award, making her one of the rare talents to earn the highest honors in television, music, film, and stage entertainment—the Emmy, Grammy, Oscar, and Tony ______ the achievement is known as “winning the EGOT.”",
      "ref": {"file": "img/writing/e41018de-q.png", "locator": "College Board SAT Suite Question Bank › e41018de › Question"}
    }
  },
  "items": [
    {
      "id": "e41018de", "origin": "original", "source": "cb-qbank", "set": "Writing drill", "number": 1,
      "section": "writing", "exam": "SAT", "difficulty": null, "format": "mcq",
      "stimulus": "e41018de",
      "question": "Which choice completes the text so that it conforms to the conventions of Standard English?",
      "options": {"A": "awards, respectively;", "B": "awards; respectively", "C": "awards, respectively—", "D": "awards, respectively,"},
      "answer": "A", "accepted": [],
      "rationale": ["Choice A is the best answer. The convention being tested is …", "Choice B is incorrect because …"],
      "media": [],
      "refs": {
        "question": {"file": "img/writing/e41018de-q.png", "locator": "College Board SAT Suite Question Bank › e41018de › Question"},
        "answer": {"file": "img/writing/e41018de-a.png", "locator": "College Board SAT Suite Question Bank › e41018de › Rationale"}
      },
      "duplicate_of": null, "notes": []
    }
  ]
}
```

A math item's `question` and options (no passage):

```json
"question": "Triangles \\(PQR\\) and \\(LMN\\) are graphed in the \\(xy\\)-plane. Triangle \\(PQR\\) has vertices \\(P\\), \\(Q\\), and \\(R\\) at \\((4, 5)\\), \\((4, 7)\\), and \\((6, 5)\\), respectively. Triangle \\(LMN\\) has vertices \\(L\\), \\(M\\), and \\(N\\) at \\((4, 5)\\), \\((4, 7 + k)\\), and \\((6 + k, 5)\\), respectively, where \\(k\\) is a positive constant. If the measure of \\(\\angle Q\\) is \\(t^\\circ\\), what is the measure of \\(\\angle N\\)?",
"options": {"A": "\\((90 - (t - k))^\\circ\\)", "B": "\\((90 - (t + k))^\\circ\\)", "C": "\\((90 - t)^\\circ\\)", "D": "\\((90 + k)^\\circ\\)"}
```

## Commands

```
python3 tools/bands.py img/math/<id>-q.png                 # list a screenshot's bands of content (to find a figure's rows)
python3 tools/bands.py img/math/<id>-q.png --crop Y0 Y1 bank/media/math/<id>-1.png   # crop rows Y0..Y1, trimmed to the ink
python3 tools/check.py                                     # validate the bank, annotations and pages
python3 tools/build.py                                     # build the site into _site/
```
