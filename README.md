# SAT prep

Two cheat sheets and two drills for the SAT, built from hard College Board question-bank items. Published at https://sabaesmaeili.github.io/sat/ and copied to https://tutoringwithsaba.ca/sat/.

## Layout

The site is one folder tree, the French tool's way: every prefix of an address is a page, and the header shows the address (`sat/writing/drill`), one link per segment.

| Address | Page | Source |
| --- | --- | --- |
| `/` | the list of everything (`$ tree`) | `site/index.html` |
| `/writing/`, `/math/` | a section: its cheat sheet and drill | `site/<section>/index.html` |
| `/<section>/cheat-sheet/` | the cheat sheet, cards with anchors (`#w-pairs`, `#m-disc`) | `site/<section>/cheat-sheet/index.html` |
| `/<section>/drill/` | the drill, built from the bank (not indexed by search engines) | `site/<section>/drill/index.html` (a template) |

- `site/`: the pages and their shared files: `css/tokens.css` (generated from the website), `css/tool-tokens.css` (copied from the French tool), `css/palette.css` (generated, below), `css/site.css` (header, prompt, type rule, tree rows), `css/drill.css`, `js/drill.js`. Every `{{…}}` in a page is filled by the build: `{{root}}` (the relative path to the site's root), `{{header}}`, the drills' questions, and the counts on the list pages. All links are relative, so the same build works under any path.
- `bank/`: the questions as data. `original/<section>.json` holds the College Board's text verbatim; `annotations/<section>.json` holds ours (each item's card, card link and optional hint); `media/<section>/` the figure crops. Format: `bank/README.md`.
- `img/<section>/`: the screenshots the items were typed from (`<id>-q.png`, `<id>-a.png`). They are not published.
- `tools/`: the scripts below (Python 3, standard library only).

The drills keep the original pages' behaviour: first-try scoring, retries, hints, Show answer with the rationale and "Correct answer: X", filters by card and status, shuffle, start over, and progress saved in the browser under `sat-drill80-writing` / `sat-drill80-math`, keyed by question id (the keys of the first version, so saved progress carries over). A drill shows exactly the items in its bank file, in `number` order, numbered Q1, Q2, … by position.

## Commands

```
python3 tools/check.py                              # check the bank, annotations, tokens, palette and the built site; run before every commit
python3 tools/build.py                              # build the site into _site/ (never committed)
python3 tools/build.py --serve                      # build, then preview at http://localhost:8000
python3 tools/import_staging.py <section> <dir>     # merge typed items (<dir>/<id>.json) into bank/original/<section>.json
python3 tools/sync_tokens.py                        # refresh css/tokens.css and css/tool-tokens.css from the website and the French tool
python3 tools/palette.py                            # regenerate css/palette.css; --report prints the tables below
python3 tools/bands.py img/math/<id>-q.png          # find a figure's rows in a screenshot (--crop to cut it)
```

## Add a question

1. Put the screenshots in `img/<section>/`: `<id>-q.png` (question) and `<id>-a.png` (answer and rationale), named by the College Board question id.
2. Type the record in the `bank/README.md` format, one file per item (`<id>.json` holding `{"stimulus", "item"}`), with `number` set to its place in the drill; crop any figure into `bank/media/<section>/<id>-<n>.png` (`tools/bands.py`). Then `python3 tools/import_staging.py <section> <folder>`: it validates each file, merges the good ones by id and lists the rest with their problems. Re-running it is safe.
3. Add its annotation to `bank/annotations/<section>.json`: `card`, `card_name`, `anchor`, `label`, and a hint if you have one (`bank/README.md`, "Annotations").
4. `python3 tools/check.py`, then `python3 tools/build.py` and look at the drill.
5. Commit and push: the Pages workflow checks, builds and deploys.

## Design

The pages follow the esaba.ca design system (`~/Documents/GitHub/Website/docs/design-system.xml`, tokens in its `src/styles/global.css`) and the French tool's conventions (`~/Documents/GitHub/Projects/French/_Workspace/tool/DESIGN.md`): its header and address (§4), prompt line and tree rows (§5), and type rule (§1).

- **Type**: the monospace (`--font-primary`) for everything the site says (headings, labels, buttons, navigation, scores, card titles); the serif reading face (`--font-serif`, from the French tool's tokens) only for material read at length: passages, questions, choices, rationales and cheat-sheet card prose. Website sizes (`--text-sm`, `--text-base`, `--text-lg`) and weights (400, 600).
- **Greys and panels**: only the website's and French tool's tokens. Cards and panels are the canvas (`--color-bg`) with a 1px `--color-line` border, as the French tool draws its panels; inner fills are `--color-surface-2`. Light and dark follow the system setting; `data-theme="light"` or `"dark"` on `<html>` forces a mode.
- **Recorded exceptions** (in `css/site.css` and the cheat sheets): the cards keep their original layout, borders, radii and size hierarchy, so they add `--text-xl` (1.5rem) and `--text-2xl` (2rem) for card and page titles, `.75rem` for the tags and pattern labels inside diagrams, and a wider frame (`--frame-wide`, 70rem; drills `--frame-drill`, 61.25rem). The drills keep their bordered buttons. On phones the card pages use a 1rem gutter. Figures are scans on white: multiplied onto the page in light mode and onto a `--color-text` panel in dark mode.
- **Hints** are neutral toggles (the French tool's convention for anything that opens in place); right is green, wrong pink (state words in the website's `--color-pink-text`).

## Palette

`tools/palette.py` writes `site/css/palette.css`: the website's blue, green and pink plus six hues built exactly as the website builds its own, so they are as lively and follow the same convention. Light mode uses the website's rule: each hue at the highest chroma the screen can show, darkened until it is exactly 4.5:1 on the light canvas (OKLCH lightness 0.53 to 0.58, with the website's light accents). Dark mode puts each hue at Blue Atoll's lightness (OKLCH 0.702) at the highest chroma in gamut (cap 0.25); indigo sits at 0.76, as the website's green also sits higher, to stay apart from violet for deuteranopia. One value per hue per mode, `--color-<hue>`, plus `--color-<hue>-rgb` for tints. Roles map onto hues: `--color-k1` violet, `k2` blue, `k3` teal, `k4` orange, `k5` magenta, `k6` indigo, `k7` red; `--color-writing` violet, `--color-math` blue; `--color-right` green, `--color-wrong` pink. Green and pink stay off the categories, which sit next to right and wrong in the drills. Coloured text is kept to headings, labels and state words; body text is `--color-text`.

The check (`tools/palette.py --check`, run by `tools/check.py`) requires every added hue at 4.5:1 on the canvas (it may colour text there) and 3:1 on bg, surface and surface-2 (marks, borders, headings); categories at least 0.07 apart in OKLab for normal vision and 0.015 for simulated deuteranopia and protanopia (Machado 2009), and 0.06 from right and wrong. Seven equally vivid hues allow little more under colour-vision deficiency, so every category also carries its number and name.

| Hue | Mode | Value | OKLCH L / C / h | Contrast on bg / surface / surface-2 |
| --- | --- | --- | --- | --- |
| blue (website) | dark | `#00b1d2` | 0.702 / 0.126 / 217 | 6.87 / 6.36 / 5.77 |
| green (website) | dark | `#69ff47` | 0.885 / 0.253 / 140 | 13.38 / 12.38 / 11.23 |
| pink (website) | dark | `#ff3ea5` | 0.682 / 0.241 / 353 | 5.42 / 5.02 / 4.55 |
| violet | dark | `#b27fff` | 0.702 / 0.185 / 300 | 6.17 / 5.71 / 5.18 |
| teal | dark | `#00b99a` | 0.701 / 0.132 / 175 | 7.03 / 6.51 / 5.90 |
| orange | dark | `#f67400` | 0.701 / 0.186 / 50 | 6.20 / 5.74 / 5.21 |
| magenta | dark | `#e358f8` | 0.702 / 0.250 / 322 | 5.87 / 5.43 / 4.93 |
| indigo | dark | `#8bafff` | 0.760 / 0.122 / 265 | 8.09 / 7.49 / 6.79 |
| red | dark | `#ff636c` | 0.702 / 0.190 / 20 | 6.07 / 5.62 / 5.09 |
| blue (website) | light | `#007a92` | 0.535 / 0.096 / 218 | 4.54 / 3.90 / 3.55 |
| green (website) | light | `#228100` | 0.528 / 0.171 / 140 | 4.53 / 3.89 / 3.54 |
| pink (website) | light | `#d70085` | 0.576 / 0.238 / 353 | 4.51 / 3.88 / 3.52 |
| violet | light | `#943ef2` | 0.575 / 0.250 / 300 | 4.51 / 3.87 / 3.52 |
| teal | light | `#007f69` | 0.532 / 0.100 / 175 | 4.50 / 3.86 / 3.51 |
| orange | light | `#b55400` | 0.558 / 0.147 / 50 | 4.51 / 3.87 / 3.52 |
| magenta | light | `#b926ce` | 0.578 / 0.251 / 322 | 4.51 / 3.87 / 3.52 |
| indigo | light | `#2c60ff` | 0.560 / 0.242 / 265 | 4.52 / 3.88 / 3.53 |
| red | light | `#e0003a` | 0.574 / 0.230 / 20 | 4.51 / 3.87 / 3.52 |

| Mode | Set | Vision | Closest pair (OKLab distance) |
| --- | --- | --- | --- |
| dark | all seven | normal | k2 / k3: 0.094 |
| dark | all seven | deuteranopia | k1 / k5: 0.019 |
| dark | all seven | protanopia | k1 / k5: 0.048 |
| dark | writing's six | normal | k2 / k3: 0.094 |
| dark | writing's six | deuteranopia | k1 / k5: 0.019 |
| dark | writing's six | protanopia | k1 / k5: 0.048 |
| dark | vs states | normal | k7 / wrong: 0.114 |
| light | all seven | normal | k2 / k3: 0.072 |
| light | all seven | deuteranopia | k1 / k6: 0.029 |
| light | all seven | protanopia | k1 / k6: 0.028 |
| light | writing's six | normal | k2 / k3: 0.072 |
| light | writing's six | deuteranopia | k1 / k6: 0.029 |
| light | writing's six | protanopia | k1 / k6: 0.028 |
| light | vs states | normal | k3 / right: 0.105 |

To adopt the palette on the website or in the French tool: copy the hue blocks of `palette.css` into the website's `global.css` token blocks (they are named like its own), then re-sync.

## Publishing

`.github/workflows/pages.yml` runs on every push to `main` (and by hand): `tools/check.py`, `tools/build.py`, then deploys `_site/` to GitHub Pages (repository Settings → Pages → Source: GitHub Actions). It then copies the same build into `sat/` of `sabaesmaeili/tutoringwithsaba`, which serves tutoringwithsaba.ca, touching nothing else there. That step needs the repository secret `MIRROR_DEPLOY_KEY` (the private half of a deploy key with write access on tutoringwithsaba); without it the copy is skipped and Pages still deploys. In CI the Website and French repos are absent, so the token-copy checks are skipped; the committed copies are used.

## Source

Questions and rationales: College Board SAT Suite Question Bank. They are typed verbatim into `bank/original/`, and every drill page credits the source. The cheat sheets, card links and hints are ours. The drill pages carry `<meta name="robots" content="noindex">`; the cheat sheets and list pages are indexable.
