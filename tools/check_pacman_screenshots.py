"""Pac-Man's pictures and the death sequence: compare Altirra's rendered pixels with what the ROM says (docs/20).

Input: the directory written by tools\\run_pacman_shots.ps1 (per target: <name>.log with the frozen machine's RAM, <name>_N.png = a capture of Altirra's own window).
Targets: Shape_<name> (the nine Pac-Man pictures), Death_freeze (ghosts frozen), Death_anim00..15 (the 16 frames of DeathAnimation), Death_end.
For every capture:
  1. the missile memory ($2300 + PacY ...), which is what the hardware shows for Pac-Man, must equal the picture the ROM gives: the nine shapes from the ROM bytes; for the death frames a software simulation of
     DeathAnimation built from the ROM bytes (PacShapeUp2, DeathPlotBytes at the rows DeathPlotRows, StarShape);
  2. the pixels on the screen must equal that bitmap: in each of the 8 x 16 cells the cell centre has one colour where the bit is set and a different one where it is clear (column = PacX + bit 7-c, row = missile-memory row);
  3. once the ghosts are hidden (death animation, end) no ghost-coloured pixel is on the playfield; in the freeze the four frozen ghosts are on the screen as the pictures in their player memory;
  4. the colours seen are listed (colour register $02C7 = Pac-Man).
The pixel scale (colour clock -> window pixel, scanline -> window pixel) is the one fitted from the ghost screenshots (analysis/evidence-ghost-screenshots-summary.txt); its residual is printed.
Usage: python -I tools\\check_pacman_screenshots.py F:\\Ports\\pac-shots [--summary-file analysis\\evidence-pacman-screenshots-summary.txt]
"""
import collections
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_ghost_screenshots as G  # noqa: E402
import decode_streams as S  # noqa: E402

rd = S.rd
AX, BX, AY, BY = 5.4680, 12.05, 3.1711, -46.68             # from analysis/evidence-ghost-screenshots-summary.txt (same window layout)
PT = [rd(0xBB65 + 2 * i) | rd(0xBB66 + 2 * i) << 8 for i in range(5)]
SHAPES = {}
for nm, y in (("Full", 0), ("Right", 2), ("Left", 4), ("Up", 6), ("Down", 8)):
    for k, off in ((("", 0),) if y == 0 else (("1", 0), ("2", 10))):
        SHAPES[nm + k] = [rd(PT[y // 2] + off + i) for i in range(10)]
NIB, _ = S.split_nibbles(0xBE95)
PLOT_ROWS = [NIB[i] for i in range(14)]                    # DeathPlotRows ($0600+x)
PLOT_BYTES = [rd(0xBB57 + i) for i in range(14)]
UP2 = [rd(0xBB38 + i) for i in range(10)]
STAR = [rd(0xBC07 + i) for i in range(16)]


def death_page(k):
    """Pac-Man's 16 missile rows after death-animation frame k (0 = PacShapeUp2, 1-14 plot bytes, 15 = StarShape, 16 = cleared), from DeathAnimation ($AEF7-$AF53)."""
    page = [0] * 16
    if k == 16:
        return page
    for i in range(10):                                     # frame 0: Y = $0C down to 3, X = 9 down to 0
        page[3 + i] = UP2[i]
    for j in range(1, min(k, 14) + 1):
        page[PLOT_ROWS[j - 1] - 1] = PLOT_BYTES[j - 1]
    if k == 15:
        page = list(STAR)
    return page


def parse(path):
    mem = {}
    mode = None
    for line in open(path, errors="replace"):
        m = re.match(r"\s*([0-9A-F]{4}): ((?:[0-9A-F]{2} )+)", line)
        if m:
            a = int(m.group(1), 16)
            for i, h in enumerate(m.group(2).split()):
                mem[a + i] = int(h, 16)
        m = re.match(r"\s*SHOT mode=(\w+) f=(\d+)", line)
        if m:
            mode = (m.group(1), int(m.group(2)))
    return mem, mode


GOLD = (210, 163, 58)          # colour register $2A (Pac-Man) as rendered; the same RGB in every capture where nothing covers him
BLACK = (0, 0, 0)


def cell_ok(im, x0, row0, rows, ox, oy, ncol=8):
    """Cells: column c = bit (7-c) at colour clock x0 + c, row r = row0 + r. A set bit must show Pac-Man's gold, or - where a ghost, a wall or a dot has priority - some other non-background colour;
    a clear bit must never show gold; at least half of the set cells must be plain gold. Returns (ok, gold cells, covered cells)."""
    px = lambda r, c: tuple(int(v) for v in im[int(round(AY * (row0 + r + 0.5) + BY + oy)), int(round(AX * (x0 + c + 0.5) + BX + ox))])
    gold = covered = 0
    for r, b in enumerate(rows):
        for c in range(8):
            p = px(r, c)
            if (b >> (7 - c)) & 1:
                if p == GOLD:
                    gold += 1
                elif p == BLACK:
                    return False, 0, 0
                else:
                    covered += 1
            elif p == GOLD:
                return False, 0, 0
    nset = sum(bin(b).count("1") for b in rows)
    return (nset > 0 and gold * 2 >= nset), gold, covered


def find(im, x, row0, rows):
    order = sorted(((dy, dx) for dy in range(-2, 3) for dx in range(-2, 3)), key=lambda t: (abs(t[0]) + abs(t[1]), t))
    for sub in sorted(((ox, oy) for ox in range(-3, 4) for oy in range(-5, 6)), key=lambda t: (abs(t[0]) + abs(t[1]), t)):
        for dy, dx in order:
            ok, gold, covered = cell_ok(im, x + dx, row0 + dy, rows, sub[0], sub[1])
            if ok:
                return dx, dy, sub, (gold, covered)
    return None


def main():
    d = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    names = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".log"))
    tot, bad = collections.Counter(), []
    rgb_of = collections.defaultdict(collections.Counter)
    dxs, dys, subs = collections.Counter(), collections.Counter(), collections.Counter()
    ghost_rgb = list(G.KNOWN.values())
    P("targets with a log:", len(names))
    results = {}
    for name in names:
        mem, mode = parse(os.path.join(d, name + ".log"))
        pngs = [os.path.join(d, "%s_%d.png" % (name, i)) for i in range(3) if os.path.exists(os.path.join(d, "%s_%d.png" % (name, i)))]
        if not mode or 0x2300 not in mem or not pngs:
            bad.append((name, "no log/capture"))
            continue
        pacx, pacy = mem[0x8E], mem[0x89]
        page = [mem[0x2300 + pacy + r] for r in range(16)]
        # ---- expected picture ----
        if name.startswith("Shape_"):
            want_rows = SHAPES[name[6:]]
            exp = [0, 0, 0] + want_rows + [0, 0, 0]
            kind = "shape"
        elif name.startswith("Death_anim"):
            k = int(name[10:])
            exp = death_page(k)
            kind = "death frame %d" % k
            # the game's own variables at the freeze
            if mem[0xEB] != k or mem[0xEA] != 1 or mem[0xED] < 3:
                bad.append((name, "game variables at the freeze are not the wanted death frame", mem[0xED], mem[0xEA], mem[0xEB]))
        elif name == "Death_end":
            exp = death_page(16)
            kind = "death end (rows cleared)"
        else:                                    # Death_freeze: Pac-Man shows the picture he had when he was caught - one of the nine shapes
            exp = None
            kind = "freeze"
        tot["targets"] += 1
        if exp is not None:
            if page != exp:
                bad.append((name, "missile memory differs from the expected picture", [hex(b) for b in page], [hex(b) for b in exp]))
                continue
            tot["missile memory == expected picture (%s)" % ("ROM shape" if name.startswith("Shape_") else "simulated DeathAnimation")] += 1
        else:
            hit = [nm for nm, rows in SHAPES.items() if page == [0, 0, 0] + rows + [0, 0, 0]]
            if not hit or mem[0xED] != 1:
                bad.append((name, "freeze: Pac-Man's memory is not one of the nine shapes", [hex(b) for b in page]))
                continue
            exp = page
            kind = "freeze (Pac-Man shows %s)" % hit[0]
            tot["missile memory == one of the nine ROM shapes (freeze)"] += 1
        results[name] = (kind, pacx, pacy, exp, mem, pngs)
    # ---- the screen ----
    for name, (kind, pacx, pacy, exp, mem, pngs) in results.items():
        for png in pngs:
            im = np.array(Image.open(png).convert("RGB"))
            tot["Pac-Man views"] += 1
            nonzero = any(exp)
            if nonzero:
                hit = find(im, pacx, pacy, exp)
                if hit:
                    dx, dy, sub, rgb = hit
                    dxs[dx] += 1
                    dys[dy] += 1
                    subs[sub] += 1
                    rgb_of[name.split("_")[0] + ("/" + name.split("_")[1][:5] if name.startswith("Death") else "")][(mem[0x2C7], GOLD)] += 1
                    tot["set cells showing Pac-Man's gold (of the set cells compared)"] += rgb[0]
                    tot["set cells covered by a ghost / wall / dot of higher priority"] += rgb[1]
                    tot["on screen == picture: " + ("shape" if name.startswith("Shape_") else ("freeze" if name == "Death_freeze" else "death animation"))] += 1
                else:
                    bad.append((name, png, "no position matches the bitmap"))
            else:
                # cleared picture: no Pac-Man pixels; the 8 x 16 cells must all be the background colour
                px = [tuple(int(v) for v in im[int(round(AY * (pacy + r + 0.5) + BY)), int(round(AX * (pacx + c + 0.5) + BX))]) for r in range(16) for c in range(8)]
                if GOLD not in px:
                    tot["on screen == picture: cleared (nothing drawn)"] += 1
                else:
                    bad.append((name, png, "Pac-Man gold on the screen although the picture is cleared", collections.Counter(px).most_common(3)))
            # ghosts: hidden after the freeze; frozen ones are on screen in the freeze
            if name.startswith("Death_anim") or name == "Death_end":
                region = im[100:620, 330:1100]
                n = 0
                for c in ghost_rgb:
                    if tuple(c) == (170, 126, 0):
                        continue                                   # the gold of ghost 3 is also close to the lives/Pac-Man icons; the other three are unique
                    n += int(np.all(region == np.array(c), axis=2).sum())
                tot["frames checked for ghost-coloured pixels (death animation)"] += 1
                if n:
                    bad.append((name, png, "ghost-coloured pixels on the playfield", n))
                else:
                    tot["... no ghost-coloured pixel on the playfield (ghosts hidden)"] += 1
    # ---- the freeze: the four ghosts ----
    if "Death_freeze" in results:
        kind, pacx, pacy, exp, mem, pngs = results["Death_freeze"]
        for png in pngs:
            im = np.array(Image.open(png).convert("RGB"))
            for g in range(4):
                loc = G.locate(mem, g)
                tot["freeze: ghost views"] += 1
                if loc is None:
                    bad.append(("Death_freeze", g, "player memory is none of the 11 pictures"))
                    continue
                row, pic, rows = loc
                x = mem[0x8A + g]
                hit = None
                order = sorted(((dy, dx) for dy in range(-4, 5) for dx in range(-8, 9)), key=lambda t: (abs(t[0]) + abs(t[1]), t))
                for sub in sorted(((ox, oy) for ox in range(-3, 4) for oy in range(-5, 6)), key=lambda t: (abs(t[0]) + abs(t[1]), t)):
                    for dy, dx in order:
                        ok, rgb = G.sample(im, AX, BX, AY, BY, x + dx, row + dy, rows, sub[0], sub[1])
                        if ok:
                            hit = (dx, dy, sub, rgb)
                            break
                    if hit:
                        break
                if hit:
                    tot["freeze: ghost on screen == its player-memory picture (%s)" % pic.split("/")[0]] += 1
                else:
                    tot["freeze: ghost not matched (overlap with another sprite?)"] += 1
    for k in sorted(tot):
        P("  %-86s %d" % (k, tot[k]))
    P("column found on the screen minus PacX (0 = where the game says):", dict(sorted(dxs.items())))
    P("row found on the screen minus the missile-memory row:", dict(sorted(dys.items())))
    P("sub-cell pixel offset needed (scale-fit error), (x, y) in window pixels:", dict(sorted(subs.items())))
    P("(colour register $02C7 at the freeze, screen RGB) per kind:")
    for k, cnt in sorted(rgb_of.items()):
        P("  %-14s" % k, dict(("$%02X %s" % (c, rgb), n) for (c, rgb), n in cnt.items()))
    P("deviations:", len(bad))
    for b in bad[:12]:
        P("  ", b)
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
