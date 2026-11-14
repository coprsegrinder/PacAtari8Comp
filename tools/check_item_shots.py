"""OV-32: the colours of the playfield, the bottom-row items, the bonus items and the ghost-eaten pop-up on the SCREEN, compared with what the ROM and the RAM say.

Input: the directory written by tools\\run_item_shots.ps1 (per target: <name>.log = the frozen machine's RAM, the last writes of the colour registers with their scanline, <name>_N.png = a capture of Altirra's own window).
For every capture of the playfield (targets Item_L<n>, Lives_<k>):
  1. every ANTIC mode-4 cell of the maze area (screen RAM $0C00-$0F97, 23 rows of 40 characters, charset $3000-$33FF) is rendered pixel by pixel: the glyph pixel value (0 = COLBK, 1 = COLPF0, 2 = COLPF1, 3 = COLPF2, or COLPF3
     when the character code has bit 7 set) selects the colour REGISTER, whose value at that scanline comes from the logged writes (the DLI bands); the capture must show, at every such pixel, one RGB colour per register value
     (the same value gives the same RGB everywhere in the capture, different values give different RGBs, and the same RGB table holds across all captures).  Pixels under a sprite (ghosts, Pac-Man, the pop-up) are left out.
  2. the registers: COLPF1 in the item rows must be ItemColor ($A0) ... (listed), and the bottom row (screen RAM row 22, $0F70-$0F97) is listed cell by cell: the lives icons and the level-indicator items, with the register values and the RGB that were on screen.
For the pop-up targets (Popup_<k>): the score picture in the missile memory (page $23) must be the ROM picture GhostScorePtrs[k]; every missile pixel on the screen has the colour of COLOR3 ($02C7 = $DC) and the pixels around it do not.
Usage: python -I tools\\check_item_shots.py analysis\\shots\\item-shots [--summary-file out.txt]
"""
import collections
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

rd = S.rd
AX, BX, AY, BY = 5.4680, 12.05, 3.1711, -46.68             # colour clock / scanline -> window pixel (analysis/evidence-ghost-screenshots-summary.txt; same window layout)
PELLET_CELLS = {(3, 3), (3, 36), (16, 3), (16, 36)}      # the four power pellets blink: the screen RAM of the frozen frame and the picture of the frame before can differ there
CW = re.compile(r"CW r=([0-9A-F]{4}) v=([0-9A-F]{2}) vp=(\d+) hp=(\d+)")
CB = re.compile(r"CB v=([0-9A-F]{2}) vp=(\d+) hp=(\d+)")
REG = {0xD016: "COLPF0", 0xD017: "COLPF1", 0xD018: "COLPF2", 0xD019: "COLPF3", 0xD01A: "COLBK"}


def parse(path):
    mem, cw = {}, []
    for line in open(path, errors="replace"):
        m = re.match(r"\s*([0-9A-F]{4}): ((?:[0-9A-F]{2} )+)", line)
        if m:
            a = int(m.group(1), 16)
            for i, b in enumerate(m.group(2).split()):
                mem[a + i] = int(b, 16)
            continue
        m = CW.match(line)
        if m:
            cw.append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3)), int(m.group(4))))
            continue
        m = CB.match(line)
        if m:
            cw.append((0xD409, int(m.group(1), 16), int(m.group(2)), int(m.group(3))))
    return mem, cw


def timeline(cw, regs=None):
    """Register values per scanline of the last complete frame: [reg][scan] -> value.  A frame ends where the scanline of the writes goes back down."""
    frames, cur, last = [], [], -1
    for r, v, vp, hp in cw:
        if vp < last - 5 and cur:
            frames.append(cur)
            cur = []
        cur.append((r, v, vp))
        last = vp
    frames.append(cur)
    # the frame whose writes reach the OS vertical-blank copy (scanline >= 240) and that is followed by another one
    done = [f for f in frames if any(vp >= 240 for r, v, vp in f)]
    base = {}
    for f in done[:-1]:
        for r, v, vp in f:
            base[r] = v
    use = done[-1] if done else frames[-1]
    # state at the start of the frame = the values at the end of the previous frame
    prev = done[-2] if len(done) > 1 else []
    state = {}
    for r, v, vp in prev:
        state[r] = v
    regs = list(regs or REG)
    tl = {r: [None] * 262 for r in regs}
    ev = sorted(((vp, r, v) for r, v, vp in use if vp < 240))
    cur = dict(state)
    k = 0
    for s in range(262):
        while k < len(ev) and ev[k][0] <= s:
            cur[ev[k][1]] = ev[k][2]
            k += 1
        for r in regs:
            tl[r][s] = cur.get(r)
    return tl, use


def sprites(mem):
    """Rectangles (x0, y0, x1, y1) in colour clocks / scanlines that sprites may cover: the four ghosts, Pac-Man and his missiles (the pop-up).  Generous."""
    rects = []
    for g in range(4):
        x, y = mem.get(0x8A + g, 0), mem.get(0x85 + g, 0)
        rects.append((x - 26, y - 26, x + 36, y + 44))
    x, y = mem.get(0x8E, 0), mem.get(0x89, 0)
    rects.append((x - 26, y - 26, x + 36, y + 44))
    return rects


def render_expect(mem, tl, s0):
    """For every pixel of the mode-4 area that is not under a sprite: (clock, scanline, register of the class, register value, character, row, col)."""
    out = []
    rects = sprites(mem)
    for r in range(23):
        for c in range(40):
            if (r, c) in PELLET_CELLS:
                continue
            code = mem.get(0xC00 + r * 40 + c, 0)
            for line in range(8):
                g = mem.get(0x3000 + (code & 0x7F) * 8 + line, 0)
                scan = s0 + 8 * r + line
                for k in range(4):
                    v = (g >> (6 - 2 * k)) & 3
                    reg = 0xD01A if v == 0 else 0xD016 if v == 1 else 0xD017 if v == 2 else (0xD019 if code & 0x80 else 0xD018)
                    clock = 48 + 4 * c + k
                    if any(x0 <= clock <= x1 and y0 <= scan <= y1 for x0, y0, x1, y1 in rects):
                        continue
                    val = tl_value(tl, reg, scan)
                    out.append((clock, scan, reg, val, code, r, c))
    return out


def tl_value(tl, reg, scan):
    return tl[reg][scan] if 0 <= scan < 262 else None


def near(im, clock, scan, rgb, r=1):
    """True if the colour appears within r pixels of the centre of the (clock, scanline) pixel (the picture is scaled: a thin feature can sit a pixel off)."""
    y = int(round(AY * (scan + 0.5) + BY))
    x = int(round(AX * (clock + 0.5) + BX))
    return any(0 <= y + b < im.shape[0] and 0 <= x + a < im.shape[1] and tuple(int(v) for v in im[y + b, x + a]) == rgb for a in range(-r, r + 1) for b in range(-r, r + 1))


def pix(im, clock, scan, dx=0.0, dy=0.0):
    y = int(round(AY * (scan + 0.5) + BY + dy))
    x = int(round(AX * (clock + 0.5) + BX + dx))
    if not (0 <= y < im.shape[0] and 0 <= x < im.shape[1]):
        return None
    return tuple(int(v) for v in im[y, x])


def refs_from(by):
    """RGB of each register value = the most common RGB at the pixel centres where the value is expected."""
    return {v: c.most_common(1)[0][0] for v, c in by.items() if v is not None}


def judge(exp, im, refs=None):
    """Per pixel: the RGB at the centre of the pixel must not be the clean colour of ANOTHER register value (the picture is scaled and the scanlines are dimmed, so edge and dim pixels are blends and are not judged).
    Returns (pixels, exact, wrong, by, refs): exact = the centre has exactly the colour of the expected value; wrong = it has the clean colour of a different value."""
    by = collections.defaultdict(collections.Counter)
    pts = []
    for clock, scan, reg, val, code, r, c in exp:
        rgb = pix(im, clock, scan)
        if rgb is not None and val is not None:
            by[val][rgb] += 1
            pts.append((val, rgb, r, c, clock, scan, reg))
    if refs is None:
        refs = refs_from(by)
    inv = collections.defaultdict(set)
    for v, rgb in refs.items():
        inv[rgb].add(v)
    grid = {(clock, scan): val for clock, scan, reg, val, code, r, c in exp if val is not None}
    exact = wrong = 0
    bad = []
    for val, rgb, r, c, clock, scan, reg in pts:
        if rgb == refs.get(val):
            exact += 1
        elif rgb in inv and val not in inv[rgb] and not any(grid.get((clock + dx, scan + dy)) in inv[rgb] for dx in (-1, 0, 1) for dy in (-1, 0, 1)):     # an edge pixel may be off by one pixel of registration
            wrong += 1
            if len(bad) < 5:
                bad.append((r, c, clock, scan, "$%02X" % val, rgb))
    return len(pts), exact, wrong, by, refs, bad


def main():
    args = list(sys.argv[1:])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    d = args[0]
    out, P = [], None
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    names = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(d, "*.log")))
    play = [n for n in names if n.startswith(("Item_", "Lives_"))]
    pops = [n for n in names if n.startswith("Popup_")]
    problems = []
    palette = collections.defaultdict(collections.Counter)         # register value -> RGB over all captures
    first = True
    s0 = None
    rows_report = []
    for n in play:
        mem, cw = parse(os.path.join(d, n + ".log"))
        tl, use = timeline(cw)
        pngs = sorted(glob.glob(os.path.join(d, n + "_*.png")))
        if not pngs:
            continue
        im = np.array(Image.open(pngs[-1]).convert("RGB"))
        if s0 is None:                                           # fit the scanline of the first mode-4 row on the first capture
            best = None
            for cand in range(0, 90):
                exp = render_expect(mem, tl, cand)
                n_, ex_, wr_, _, _, _ = judge(exp, im)
                if best is None or ex_ > best[0]:
                    best = (ex_, cand)
            s0 = best[1]
            P("Fit: the first mode-4 row starts at scanline %d (%d of %d pixels exactly the expected colour at the best fit)." % (s0, best[0], len(exp)))
        exp = render_expect(mem, tl, s0)
        total, exact, bad, by, refs, badex = judge(exp, im)
        for val, c in by.items():
            for rgb, k in c.items():
                palette[val][rgb] += k
        regs = {REG[r]: sorted(set(v for v in tl[r][s0:s0 + 8 * 23] if v is not None)) for r in REG}
        lv, item = mem.get(0x30), mem.get(0xA0)
        rows_report.append((n, total, bad, lv, item, regs, mem, exact, badex))
    P("Playfield captures: %d. Per capture: pixels of the mode-4 area (sprites left out), how many show exactly the colour of their register value, how many show the clean colour of a value that is expected nowhere in their 3x3 neighbourhood (blends of the scaling and dimmed scanlines are not clean colours; an edge pixel may be one pixel off):" % len(rows_report))
    for n, total, bad, lv, item, regs, mem, exact, badex in rows_report:
        P("  %-10s %7d pixels, %6d exactly the expected colour, %4d the clean colour of another register value, level %s, ItemColor $%02X, registers over the rows: %s" % (n, total, exact, bad, lv, item or 0,
          "; ".join("%s %s" % (k, ",".join("$%02X" % x for x in v)) for k, v in regs.items())))
        if bad:
            problems.append("%s: %d pixels in the colour of another register value, e.g. %s" % (n, bad, badex[:2]))
    P("")
    P("Register value -> RGB over all captures (the pixels of every cell of every capture):")
    rgbs = collections.defaultdict(set)
    for val, c in sorted(palette.items()):
        main_rgb, k = c.most_common(1)[0]
        P("  $%02X -> %s  (%d pixels, %d other)" % (val, main_rgb, k, sum(c.values()) - k))
        rgbs[main_rgb].add(val)
    for rgb, vals in rgbs.items():
        if len(vals) > 1:
            problems.append("the colour %s is the clean colour of several register values %s" % (rgb, sorted("$%02X" % v for v in vals)))
    P("  (the pixels counted as 'other' are the blends of the scaling and the dimmed scanlines; the clean colours of different values are all different: %s)" % ("yes" if all(len(v) == 1 for v in rgbs.values()) else "NO"))
    P("")
    P("Bottom row (screen RAM row 22, $0F70-$0F97): the characters on it and the colours on screen")
    for n, total, bad, lv, item, regs, mem, exact, badex in rows_report:
        cells_ = [(c, mem.get(0xC00 + 22 * 40 + c, 0)) for c in range(40) if mem.get(0xC00 + 22 * 40 + c, 0)]
        P("  %-10s level %s: %s" % (n, lv, " ".join("c%d=$%02X" % (c, v) for c, v in cells_) or "(empty)"))
    P("")
    P("Items cell by cell: per capture, the in-maze bonus item (screen RAM $0DF3/$0DF4, row 12, columns 19-20) and the bottom-row glyphs: the register value of each pixel class and the colour on the screen (most common RGB, share of the pixels that show it)")
    for n, total, bad, lv, item, regs, mem, exact, badex in rows_report:
        pngs = sorted(glob.glob(os.path.join(d, n + "_*.png")))
        im = np.array(Image.open(pngs[-1]).convert("RGB"))
        tl, _ = timeline(parse(os.path.join(d, n + ".log"))[1])
        lines = []
        for (r, c) in [(12, 19), (12, 20)] + [(22, c) for c in range(40)]:
            code = mem.get(0xC00 + r * 40 + c, 0)
            if code == 0:
                continue
            cls = collections.defaultdict(collections.Counter)
            for line in range(8):
                g = mem.get(0x3000 + (code & 0x7F) * 8 + line, 0)
                for k in range(4):
                    v = (g >> (6 - 2 * k)) & 3
                    if v == 0:
                        continue
                    reg = 0xD016 if v == 1 else 0xD017 if v == 2 else (0xD019 if code & 0x80 else 0xD018)
                    scan = s0 + 8 * r + line
                    val = tl[reg][scan]
                    cls[(REG[reg], val)][pix(im, 48 + 4 * c + k, scan)] += 1
            lines.append("    (%d,%d) code $%02X: %s" % (r, c, code, "; ".join("%s=$%02X -> %s (%d of %d)" % (k[0], k[1] or 0, cn.most_common(1)[0][0], cn.most_common(1)[0][1], sum(cn.values())) for k, cn in sorted(cls.items()))))
        P("  %s (level %s, ItemColor $%02X):" % (n, lv, item or 0))
        for l in lines:
            P(l)
    # ---- the pop-up ----
    P("")
    P("Ghost-eaten pop-up (targets Popup_<k>): the digits of the score are in the missile memory (page $23), the two zeros in the eaten ghost's player memory (page $24+g), both in colour $DC (COLOR3 and the ghost's PCOLR); x = PacX - 4 (missiles) and PacX + 4 (player)")
    for n in pops:
        mem, cw = parse(os.path.join(d, n + ".log"))
        pngs = sorted(glob.glob(os.path.join(d, n + "_*.png")))
        if not pngs:
            continue
        k = int(n.split("_")[1])
        im = np.array(Image.open(pngs[-1]).convert("RGB"))
        ptr = rd(0xBCD0 + 2 * k) | rd(0xBCD1 + 2 * k) << 8
        pic = [rd(ptr + i) for i in range(16)]
        zeros = [rd(0xBC13 + i) for i in range(16)]
        px_ = mem.get(0x8E, 0)
        g = next((i for i in range(4) if mem.get(0x2C0 + i, 0) == 0xDC), None)      # the ghost whose colour register holds the pop-up colour
        m0 = [m for m in range(0, 256 - 16) if all(mem.get(0x2300 + m + i, 0) == pic[i] for i in range(16))]
        mz = [m for m in range(0, 256 - 16) if g is not None and all(mem.get(((0x24 + g) << 8) + m + i, 0) == zeros[i] for i in range(16))]
        ok_mem = len(m0) >= 1 and set(m0) & set(mz)
        col3, pcol = mem.get(0x2C7), mem.get(0x2C0 + (g or 0))
        P("  %s: GhostsEaten %d; score picture (ROM $%04X) found in missile memory at row %s, zeros in player memory of ghost %s at row %s; COLOR3 $%02X, PCOLR $%02X" % (n, mem.get(0xE9, 0) + 0, ptr, m0[:2], g, mz[:2], col3 or 0, pcol or 0))
        if not ok_mem:
            problems.append("%s: the pop-up is not in the memory as the ROM says" % n)
            continue
        row0 = sorted(set(m0) & set(mz))[0]
        best = None
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                setrgb, clrrgb = collections.Counter(), collections.Counter()
                for i in range(16):
                    for half, byte, x0 in (("m", pic[i], px_ - 4), ("p", zeros[i], px_ + 4)):
                        for b in range(8):
                            clock = x0 + (7 - b) + dx
                            rgb = pix(im, clock, row0 + i + dy)
                            if rgb is None:
                                continue
                            (setrgb if (byte >> b) & 1 else clrrgb)[rgb] += 1
                nz = [(c, rgb) for rgb, c in setrgb.items() if rgb != (0, 0, 0)]
                if nz:
                    c, rgb = max(nz)
                    hits = sum(1 for i in range(16) for byte, x0 in ((pic[i], px_ - 4), (zeros[i], px_ + 4)) for b in range(8)
                               if (byte >> b) & 1 and near(im, x0 + (7 - b) + dx, row0 + i + dy, rgb))
                    sc = hits / max(1, sum(setrgb.values()))
                    if best is None or sc > best[0]:
                        best = (sc, dx, dy, rgb, sum(setrgb.values()), clrrgb)
        sc, dx, dy, rgb, nset, clr = best
        wrong = clr.get(rgb, 0)
        P("    set pixels (%d): %.1f%% have the clean colour %s within one pixel of their centre (registration offset %d,%d pixels); of %d clear pixels in the box %d show that colour (%.1f%%)" % (nset, 100 * sc, rgb, dx, dy, sum(clr.values()), wrong, 100 * wrong / max(1, sum(clr.values()))))
        palette[col3][rgb] += nset
        if sc < 0.5:
            problems.append("%s: pop-up pixels not one colour" % n)
    open_ = None
    if summ:
        open(summ, "w", encoding="utf-8").write("\n".join(out) + "\n")
    P("")
    P("PROBLEMS: " + ("none" if not problems else "; ".join(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
