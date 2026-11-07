#!/usr/bin/env python3
"""Find the horizontal bands of content in a question screenshot, and crop them.

    python3 tools/bands.py img/math/<id>-q.png            # list bands: y range, height, ink width
    python3 tools/bands.py img/math/<id>-q.png --crop Y0 Y1 OUT.png   # crop rows Y0..Y1 (inclusive), full width, trimmed
    python3 tools/bands.py --scan img/math/*-q.png        # list images with a band taller than a text line (figure candidates)

Text lines are about 18-30 px tall; a band much taller than that is usually a figure, graph or table.
Standard library plus macOS `sips` (to read and crop PNGs); nothing to install.
"""
import os, struct, subprocess, sys, tempfile

WHITE = 235      # a pixel counts as ink when any channel is below this
GAP = 6          # blank rows that separate two bands
LINE_MAX = 34    # bands taller than this are figure candidates


def rows(path):
    """Return (width, height, ink_rows) where ink_rows[y] = (first_x, last_x, count) or None."""
    with tempfile.TemporaryDirectory() as d:
        bmp = os.path.join(d, "x.bmp")
        subprocess.run(["sips", "-s", "format", "bmp", path, "--out", bmp], check=True, capture_output=True)
        data = open(bmp, "rb").read()
    off = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    if bpp not in (24, 32):
        sys.exit(f"{path}: unsupported BMP depth {bpp}")
    step = bpp // 8
    stride = (w * step + 3) & ~3
    top_down = h < 0
    h = abs(h)
    out = []
    for y in range(h):
        r = y if top_down else h - 1 - y
        base = off + r * stride
        first = last = None
        n = 0
        for x in range(w):
            p = base + x * step
            b, g, rr = data[p], data[p + 1], data[p + 2]
            if b < WHITE or g < WHITE or rr < WHITE:
                n += 1
                if first is None:
                    first = x
                last = x
        out.append((first, last, n) if n else None)
    return w, h, out


def bands(path):
    w, h, ink = rows(path)
    res, start, blank = [], None, 0
    for y, r in enumerate(ink + [None] * (GAP + 1)):
        if r:
            if start is None:
                start = y
            blank = 0
            end = y
        elif start is not None:
            blank += 1
            if blank > GAP:
                xs = [ink[i] for i in range(start, end + 1) if i < h and ink[i]]
                res.append((start, end, min(a for a, _, _ in xs), max(b for _, b, _ in xs)))
                start, blank = None, 0
    return w, h, res


def crop(path, y0, y1, out):
    w, h, ink = rows(path)
    xs = [ink[y] for y in range(y0, y1 + 1) if ink[y]]
    # sips ignores an offset of 0 (it centres the crop instead), so offsets start at 1
    x0 = max(1, min(a for a, _, _ in xs) - 8)
    x1 = min(w - 1, max(b for _, b, _ in xs) + 8)
    y0, y1 = max(1, y0 - 8), min(h - 1, y1 + 8)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    subprocess.run(["sips", "-c", str(y1 - y0 + 1), str(x1 - x0 + 1), "--cropOffset", str(y0), str(x0),
                    path, "--out", out], check=True, capture_output=True)
    print(f"{out}: rows {y0}-{y1}, cols {x0}-{x1}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--scan":
        for p in a[1:]:
            _, _, bs = bands(p)
            tall = [(s, e) for s, e, _, _ in bs if e - s + 1 > LINE_MAX]
            if tall:
                print(p, " ".join(f"{s}-{e}" for s, e in tall))
    elif len(a) == 5 and a[1] == "--crop":
        crop(a[0], int(a[2]), int(a[3]), a[4])
    else:
        w, h, bs = bands(a[0])
        print(f"{a[0]}: {w}x{h}")
        for s, e, x0, x1 in bs:
            tag = "  <- taller than a text line" if e - s + 1 > LINE_MAX else ""
            print(f"  y {s:4d}-{e:4d}  h {e - s + 1:4d}  x {x0:4d}-{x1:4d}{tag}")
