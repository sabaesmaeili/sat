#!/usr/bin/env python3
"""Generate and check site/css/palette.css: the website's palette, extended with more hues.

The website (esaba.ca, docs/design-system.xml) has three accents: blue, green and pink. These
pages need seven category colours (the cheat-sheet cards, k1 to k7) and two section accents, in
dark and light mode. This script adds hues built exactly the way the website builds its own,
so they are as lively as blue, green and pink and follow the same convention:

- light mode: the website's rule. Each hue at the highest chroma the screen can show, darkened
  until it is exactly 4.5:1 on the light canvas (Porcelain), the most vivid it can be and still
  pass AA there. That puts every hue at OKLCH lightness 0.53 to 0.58, with the website's light
  blue, green and pink;
- dark mode: each hue at Blue Atoll's lightness (OKLCH 0.702), at the highest chroma in gamut
  (capped at 0.25, about the website's pink and green); indigo at 0.76, as the website's green
  also sits higher, so violet and indigo stay apart for deuteranopia.

One value per hue per mode, `--color-<hue>`, plus `--color-<hue>-rgb` for tints, as the website
names its own. The website's blue, green and pink come from tokens.css and are not redefined.
Roles map onto hues: `--color-k1` ... `--color-k7`, `--color-writing`, `--color-math`,
`--color-right` (green) and `--color-wrong` (pink), each with -rgb. Green and pink stay off the
categories, which sit next to right and wrong in the drills.

Usage:
  python3 tools/palette.py            write site/css/palette.css and print the report
  python3 tools/palette.py --check    exit 1 if palette.css is stale or a contrast or distance check fails
  python3 tools/palette.py --report   print the values, contrasts and distances (markdown)
"""
import argparse
import itertools
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "site" / "css" / "tokens.css"
OUT = ROOT / "site" / "css" / "palette.css"

CHROMA_CAP = 0.25
DARK_L = 0.702  # Blue Atoll's OKLCH lightness
# name: (OKLCH hue, dark lightness). The light value keeps the hue, as the website's do. Indigo sits a little lighter
# in dark mode (as the website's green does) so it stays apart from violet for deuteranopia.
HUES = {"violet": (300, DARK_L), "teal": (175, DARK_L), "orange": (50, DARK_L), "magenta": (322, DARK_L),
        "indigo": (265, 0.76), "red": (20, DARK_L)}
WEBSITE = ("blue", "green", "pink")  # from tokens.css, never redefined here
ROLES = {
    "k1": "violet", "k2": "blue", "k3": "teal", "k4": "orange", "k5": "magenta", "k6": "indigo", "k7": "red",
    "writing": "violet", "math": "blue",
    "right": "green", "wrong": "pink",
}
CATEGORIES = [f"k{i}" for i in range(1, 8)]
WRITING_CATEGORIES = CATEGORIES[:6]
# Thresholds the check enforces (README, "Palette").
MIN_TEXT = 4.5            # every hue on the canvas (bg): it may colour text there
MIN_MARK = 3.0            # every hue on bg, surface and surface-2: marks, borders, headings
MIN_DE_NORMAL = 0.07      # OKLab distance between any two categories, normal vision
MIN_DE_CVD = 0.015        # ... simulated deuteranopia and protanopia: about a just-noticeable difference; seven equally
                          # vivid hues allow little more, so the card number and name always carry the category too
MIN_DE_STATE = 0.06       # between any category and right or wrong, normal vision


# ---- colour maths (sRGB, OKLab/OKLCH, WCAG, Machado 2009 CVD simulation) ----
def hex2rgb(h):
    h = h.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb2hex(c):
    return "#" + "".join(f"{round(max(0, min(1, x)) * 255):02x}" for x in c)


def lin(x):
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def delin(x):
    return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055


def rgb2oklab(c):
    r, g, b = (lin(x) for x in c)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklch2linrgb(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def lch(c):
    L, a, b = rgb2oklab(c)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def in_gamut(L, C, h):
    return all(-1e-6 <= x <= 1 + 1e-6 for x in oklch2linrgb(L, C, h))


def max_chroma(L, h):
    lo, hi = 0.0, 0.4
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if in_gamut(L, mid, h) else (lo, mid)
    return lo


def colour(L, h):
    """The hue at lightness L and the highest chroma in gamut (capped), quantised to 8-bit sRGB."""
    C = min(CHROMA_CAP, max_chroma(L, h))
    return hex2rgb(rgb2hex(tuple(delin(max(0, min(1, x))) for x in oklch2linrgb(L, C, h))))


def luminance(c):
    r, g, b = (lin(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1, c2):
    a, b = sorted((luminance(c1), luminance(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


CVD = {
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
}


def simulate(c, kind):
    if kind == "normal":
        return c
    l = [lin(x) for x in c]
    m = CVD[kind]
    return tuple(delin(max(0, min(1, sum(m[i][j] * l[j] for j in range(3))))) for i in range(3))


def distance(c1, c2, kind="normal"):
    return math.dist(rgb2oklab(simulate(c1, kind)), rgb2oklab(simulate(c2, kind)))


# ---- the website's values, read from tokens.css ----
def website_values():
    css = TOKENS.read_text(encoding="utf-8")
    dark_block = re.search(r"^:root \{(.*?)^\}", css, re.S | re.M).group(1)
    light_block = re.search(r'^:root\[data-theme="light"\] \{(.*?)^\}', css, re.S | re.M).group(1)

    def read(block):
        return {m.group(1): m.group(2) for m in re.finditer(r"--color-([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", block)}
    return {"dark": read(dark_block), "light": read(light_block)}


def surfaces(site, mode):
    return [hex2rgb(site[mode][k]) for k in ("bg", "surface", "surface-2")]


def light_rule(h, bg):
    """The website's rule: highest chroma, darkened until exactly 4.5:1 on the light canvas."""
    lo, hi = 0.2, 0.9
    for _ in range(50):
        L = (lo + hi) / 2
        lo, hi = (L, hi) if contrast(colour(L, h), bg) >= MIN_TEXT else (lo, L)
    return colour(lo, h)


def derive():
    site = website_values()
    values = {"dark": {}, "light": {}}
    for mode in ("dark", "light"):
        grounds = surfaces(site, mode)
        for name in WEBSITE:
            values[mode][name] = {"mark": hex2rgb(site[mode][name]), "website": True}
        for name, (h, dark_l) in HUES.items():
            mark = colour(dark_l, h) if mode == "dark" else light_rule(h, grounds[0])
            values[mode][name] = {"mark": mark, "website": False}
    return site, values


# ---- CSS ----
def rgb_channels(c):
    return ", ".join(str(round(x * 255)) for x in c)


def block(values, mode, indent):
    pad = " " * indent
    out = []
    for name, v in values[mode].items():
        if not v["website"]:
            out.append(f"{pad}--color-{name}: {rgb2hex(v['mark'])};")
            out.append(f"{pad}--color-{name}-rgb: {rgb_channels(v['mark'])};")
    return "\n".join(out)


def css(values):
    roles = []
    for role, hue in ROLES.items():
        roles.append(f"  --color-{role}: var(--color-{hue});")
        roles.append(f"  --color-{role}-rgb: var(--color-{hue}-rgb);")
    hues = ", ".join(f"{n} {h}" for n, (h, _) in HUES.items())
    return "\n".join([
        "/*",
        "  GENERATED FILE. Never edit it by hand: edit tools/palette.py, then run it.",
        "  The website's palette (tokens.css) extended with more hues, built as the website builds its own: light, each",
        "  OKLCH hue at the highest chroma, darkened to exactly 4.5:1 on the canvas; dark, at Blue Atoll's lightness",
        "  (0.702) and the highest chroma in gamut (cap 0.25). Hues: " + hues + ".",
        "  One value per hue per mode, --color-<hue>, and --color-<hue>-rgb for tints. Roles map onto hues at the end.",
        "  Values and checks: README.md, Palette.",
        "  Load after tokens.css. The light block appears twice, so data-theme on <html> can force either mode.",
        "*/",
        "",
        ":root {",
        block(values, "dark", 2),
        "",
        "  /* Roles */",
        *roles,
        "}",
        "",
        "@media (prefers-color-scheme: light) {",
        '  :root:not([data-theme="dark"]) {',
        block(values, "light", 4),
        "  }",
        "}",
        "",
        ':root[data-theme="light"] {',
        block(values, "light", 2),
        "}",
        "",
    ])


# ---- checks and report ----
def resolve(values, mode, role):
    return values[mode][ROLES[role]]


def checks(site, values):
    problems, report = [], []
    for mode in ("dark", "light"):
        grounds = surfaces(site, mode)
        for name, v in values[mode].items():
            c = [contrast(v["mark"], g) for g in grounds]
            if c[0] < MIN_TEXT and not v["website"]:
                problems.append(f"{mode} {name} is {c[0]:.2f}:1 on bg (needs {MIN_TEXT})")
            if min(c) < MIN_MARK:
                problems.append(f"{mode} {name} is {min(c):.2f}:1 on a surface (needs {MIN_MARK})")
            report.append((mode, name, v, c))
    dist = {}
    for mode in ("dark", "light"):
        for label, cats in (("all seven", CATEGORIES), ("writing's six", WRITING_CATEGORIES)):
            for kind in ("normal", "deuteranopia", "protanopia"):
                worst = min((distance(resolve(values, mode, a)["mark"], resolve(values, mode, b)["mark"], kind), a, b)
                            for a, b in itertools.combinations(cats, 2))
                dist[(mode, label, kind)] = worst
                need = MIN_DE_NORMAL if kind == "normal" else MIN_DE_CVD
                if worst[0] < need:
                    problems.append(f"{mode} categories ({label}) {worst[1]}/{worst[2]} are {worst[0]:.3f} apart under {kind} (needs {need})")
        worst = min((distance(resolve(values, mode, k)["mark"], resolve(values, mode, s)["mark"]), k, s)
                    for k in CATEGORIES for s in ("right", "wrong"))
        dist[(mode, "vs states", "normal")] = worst
        if worst[0] < MIN_DE_STATE:
            problems.append(f"{mode} {worst[1]} is {worst[0]:.3f} from {worst[2]} (needs {MIN_DE_STATE})")
    return problems, report, dist


def markdown(report, dist):
    lines = ["| Hue | Mode | Value | OKLCH L / C / h | Contrast on bg / surface / surface-2 |", "| --- | --- | --- | --- | --- |"]
    for mode, name, v, c in report:
        tag = " (website)" if v["website"] else ""
        L, C, h = lch(v["mark"])
        lines.append(f"| {name}{tag} | {mode} | `{rgb2hex(v['mark'])}` | {L:.3f} / {C:.3f} / {h:.0f} | {' / '.join(f'{t:.2f}' for t in c)} |")
    lines += ["", "| Mode | Set | Vision | Closest pair (OKLab distance) |", "| --- | --- | --- | --- |"]
    for (mode, label, kind), (d, a, b) in dist.items():
        lines.append(f"| {mode} | {label} | {kind} | {a} / {b}: {d:.3f} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    site, values = derive()
    text = css(values)
    problems, report, dist = checks(site, values)
    if args.report:
        print(markdown(report, dist))
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            problems.append(f"{OUT.relative_to(ROOT)} is stale; run tools/palette.py")
        for p in problems:
            print("palette:", p, file=sys.stderr)
        if problems:
            sys.exit(1)
        print("palette: palette.css is current; contrast and distance checks pass.")
        return
    if args.report:
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"palette: wrote {OUT.relative_to(ROOT)}")
    for p in problems:
        print("palette: PROBLEM", p)
    print(markdown(report, dist))


if __name__ == "__main__":
    main()
