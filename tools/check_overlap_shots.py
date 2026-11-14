r"""OV-52: overlapping ghosts on the screen.  The game writes GPRIOR = $11 ($A4A0, $B098): bit 5 (overlapping players ORed into a third colour) is clear, so where two ghosts overlap the lower-numbered
player must win (GTIA: player 0 in front of player 1 ... of player 3) and no pixel may show a mixed colour.  Input: the captures of tools\run_item_shots.ps1 (Overlap_A / Overlap_B: the four ghosts put side by side, 4 pixels
apart, in the ghost house).  For each capture the player memory ($2400-$27FF, 16 rows from EntityY, bit 7 = leftmost, one colour clock per bit, x = EntityX) gives for every pixel the set of ghosts that cover it; the clean
colour of each ghost is taken from the pixels only that ghost covers; at every overlap pixel the colour on the screen must be the clean colour of the lowest-numbered ghost of the set.
Usage: python -I tools\check_overlap_shots.py analysis\shots\item-shots [--summary-file out.txt]
"""
import collections
import glob
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_item_shots as C  # noqa: E402


def analyse(d, name):
    mem, cw = C.parse(os.path.join(d, name + ".log"))
    hp = {}
    for line in open(os.path.join(d, name + ".log"), errors="replace"):          # the position each ghost was last DRAWN at (HPOSP written at $B97E, the picture copied at EntityY): what the screen shows
        if line.startswith("HP "):
            g = dict(kv.split("=") for kv in line.split()[1:])
            hp[int(g["g"])] = (int(g["x"]), int(g["y"]))
    pngs = sorted(glob.glob(os.path.join(d, name + "_*.png")))
    im = np.array(Image.open(pngs[-1]).convert("RGB"))
    cover = collections.defaultdict(set)                      # (clock, memory row) -> ghosts
    for g in range(4):
        x, y = hp.get(g, (mem[0x8A + g], mem[0x85 + g]))
        for i in range(16):
            byte = mem.get(((0x24 + g) << 8) + y + i, 0)
            for b in range(8):
                if (byte >> b) & 1:
                    cover[(x + 7 - b, y + i)].add(g)
    best = None
    for dy in range(-3, 4):
        single = collections.defaultdict(collections.Counter)
        for (clock, row), gs in cover.items():
            if len(gs) == 1:
                rgb = C.pix(im, clock, row + dy)
                if rgb:
                    single[next(iter(gs))][rgb] += 1
        score = sum(c.most_common(1)[0][1] for c in single.values() if c)
        if best is None or score > best[0]:
            best = (score, dy, single)
    score, dy, single = best
    clean = {g: single[g].most_common(1)[0][0] for g in single if single[g]}
    res = collections.Counter()
    detail = collections.Counter()
    for (clock, row), gs in sorted(cover.items()):
        if len(gs) < 2:
            continue
        win = min(gs)
        rgb = C.pix(im, clock, row + dy)
        loserc = {clean[g] for g in gs if g != win and g in clean}
        if win not in clean:
            res["winner colour unknown"] += 1
        elif rgb == clean[win]:
            res["shows the winner's colour"] += 1
            detail[("ghosts %s" % sorted(gs))] += 1
        elif C.near(im, clock, row + dy, clean[win]) and rgb not in loserc:
            res["blend with the winner's colour (edge)"] += 1
        elif rgb in loserc:
            res["SHOWS A LOSER'S COLOUR"] += 1
        else:
            res["other"] += 1
    return mem, clean, dy, res, detail, cover


def main():
    args = list(sys.argv[1:])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    d = args[0]
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    problems = []
    names = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(d, "Overlap_*.log")))
    for n in names:
        mem, clean, dy, res, detail, cover = analyse(d, n)
        P("%s: ghosts at x %s, y %s; PCOLR %s; GPRIOR bit 5 clear = lowest player wins" % (n, [mem[0x8A + g] for g in range(4)], [mem[0x85 + g] for g in range(4)], ["$%02X" % mem[0x2C0 + g] for g in range(4)]))
        P("  clean colours on the screen (from the pixels that only one ghost covers): " + ", ".join("ghost %d %s" % (g, c) for g, c in sorted(clean.items())) + "; registration offset %d scanline" % dy)
        tot = sum(res.values())
        P("  overlap pixels (two or more ghosts cover them): %d; " % tot + "; ".join("%s: %d" % kv for kv in sorted(res.items())))
        P("  by the set of ghosts: " + ", ".join("%s: %d" % kv for kv in sorted(detail.items())))
        if res["SHOWS A LOSER'S COLOUR"] or res["other"] > 0.05 * max(tot, 1) or tot == 0 or len(clean) < 4:
            problems.append("%s: overlap rule" % n)
    P("")
    P("PROBLEMS: " + ("none" if not problems else "; ".join(problems)))
    if summ:
        open(summ, "w", encoding="utf-8").write("\n".join(out) + "\n")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
