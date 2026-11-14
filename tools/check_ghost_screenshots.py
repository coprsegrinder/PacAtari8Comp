"""Step C11, ghost frames: compare Altirra's rendered pixels with the ghost bitmaps in the ROM.

Input: the directory written by tools\\run_ghost_shots.ps1 (per picture: <name>.log with the frozen machine's RAM, <name>_N.png = a capture of Altirra's own window).
For every ghost on every screenshot:
  1. its player memory (what the hardware shows) must be exactly one of the 11 pictures built from the ROM: 4 directions x 2 feet rows, frightened x 2 feet rows, eyes;
     and for the ghost the picture was waited for it must be the shape and feet row the game was drawing;
  2. the pixels on the screen must equal that bitmap: in each of the 8 x 11 cells the cell centre has one colour where the bit is set and a different one where it is clear.
     The row is the player-memory row where the picture was found; the column is found by trying HPOSP = EntityX +-8 (the game moves the ghost-house ghosts after drawing them).
  3. the colours seen on the screen are listed per picture kind (and compared with the status-text colour, colour register $0C).
Pixel scale (colour clock -> window pixel, scanline -> window pixel) is fitted from the normal ghosts' exact-colour bounding boxes; its residual is printed.
Usage: python -I tools\\check_ghost_screenshots.py analysis\\shots\\ghost-shots [--summary-file analysis\\evidence-ghost-screenshots-summary.txt]
"""
import collections
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

rd = S.rd
KNOWN = {0x44: (144, 24, 41), 0x4A: (254, 135, 155), 0xD8: (49, 156, 13), 0x28: (170, 126, 0)}   # normal ghost colours, seen in an earlier capture
DISP_W, DISP_H = 1420, 716                        # the display pane inside Altirra's window (the rest is the debugger)


def parse_log(path):
    mem, shot = {}, None
    for line in open(path, errors="replace"):
        m = re.match(r"\s*([0-9A-F]{4}): ((?:[0-9A-F]{2} )+)", line)
        if m:
            a = int(m.group(1), 16)
            for i, h in enumerate(m.group(2).split()):
                mem[a + i] = int(h, 16)
        m = re.match(r"\s*SHOT ghost=(\d+) src=\$([0-9A-F]+) feet=\$([0-9A-F]+) pcolr=\$([0-9A-F]+) af=(\d+) frame=(\d+)", line)
        if m:
            shot = dict(ghost=int(m.group(1)), src=int(m.group(2), 16), feet=int(m.group(3), 16), pcolr=int(m.group(4), 16),
                        af=int(m.group(5)), frame=int(m.group(6)))
    return mem, shot


def pictures():
    """All 11 pictures the game can put in a ghost's player: name -> 11 rows (10 shape rows + feet row)."""
    pic = {}
    for nm, off in (("Up", 0x00), ("Down", 0x0A), ("Left", 0x14), ("Right", 0x1E), ("Frightened", 0x28)):
        for feet in (0x54, 0xAA):
            pic["%s/feet%02X" % (nm, feet)] = [rd(0xBAC0 + off + r) for r in range(10)] + [feet]
    pic["Eyes"] = [rd(0xBAF2 + r) for r in range(10)] + [0]
    return pic


PICS = pictures()


CLIPS = [None] + [(0xFF << k) & 0xFF for k in range(1, 8)] + [0xFF >> k for k in range(1, 8)]     # none, right-edge clip, left-edge clip (found in the memory of ghosts at the tunnel)


def locate(mem, g):
    """Find the ghost's picture in its player page: (row, name, rows) nearest to EntityY + 2, or None.
    A picture whose rows are ANDed with one mask (the game cuts the ghost at the tunnel's screen edge) is accepted and named '<picture>&XX'."""
    page, y = 0x2400 + 0x100 * g, mem[0x85 + g]
    best = None
    for clip in CLIPS:
        for nm, rows in PICS.items():
            rr = rows if clip is None else [r & clip for r in rows]
            for i in range(0xF0):
                if [mem[page + i + r] for r in range(11)] == rr and any(rr):
                    d = abs(i - (y + 2))
                    if d <= 6 and (best is None or d < best[0]):
                        best = (d, i, nm if clip is None else "%s&%02X" % (nm, clip), rr)
        if best is not None:
            break
    return None if best is None else (best[1], best[2], best[3])


def cells(rows):
    return [[(b >> (7 - c)) & 1 for c in range(8)] for b in rows]


def sample(im, ax, bx, ay, by, clock, line, rows, ox=0.0, oy=0.0):
    px = lambda r, c: tuple(int(v) for v in im[int(round(ay * (line + r + 0.5) + by + oy)), int(round(ax * (clock + c + 0.5) + bx + ox))])
    cl = cells(rows)
    setc = [px(r, c) for r in range(11) for c in range(8) if cl[r][c]]
    clr = [px(r, c) for r in range(11) for c in range(8) if not cl[r][c]]
    main = collections.Counter(setc).most_common(1)[0][0]
    return all(c == main for c in setc) and all(c != main for c in clr), main


def main():
    d = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    shots = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".log"):
            name = f[:-4]
            mem, shot = parse_log(os.path.join(d, f))
            pngs = [os.path.join(d, "%s_%d.png" % (name, i)) for i in range(3) if os.path.exists(os.path.join(d, "%s_%d.png" % (name, i)))]
            if shot and pngs and 0x85 in mem:
                shots.append((name, mem, shot, pngs))
    P("pictures with a log and a capture:", len(shots), "  captures:", sum(len(s[3]) for s in shots))
    # ---- calibration: left/top/right/bottom edge of each normal ghost's exact-colour pixels ----
    pts = []
    for name, mem, shot, pngs in shots:
        im = np.array(Image.open(pngs[0]).convert("RGB"))[:560, :DISP_W]
        for g in range(4):
            loc = locate(mem, g)
            col = mem[0x2C0 + g]
            if loc is None or col not in KNOWN or loc[1].startswith(("Frightened", "Eyes")) or "&" in loc[1]:
                continue
            rows = loc[2]
            m = np.all(im == KNOWN[col], axis=2)
            if m.sum() < 400:
                continue
            ys, xs = np.nonzero(m)
            if ys.max() - ys.min() > 40 or xs.max() - xs.min() > 50:
                continue
            cs = [c for r in cells(rows) for c in range(8) if r[c]]
            x = mem[0x8A + g]
            pts.append((x + min(cs), xs.min(), x + max(cs) + 1, xs.max() + 1, loc[0], ys.min(), loc[0] + 11, ys.max() + 1))
    A = np.array(pts, float)
    keep = np.ones(len(A), bool)
    for _ in range(6):                      # least squares with outlier rejection (a cluster merged with another sprite, or EntityX moved after the draw)
        B = A[keep]
        ax, bx = np.polyfit(np.concatenate([B[:, 0], B[:, 2]]), np.concatenate([B[:, 1], B[:, 3]]), 1)
        ay, by = np.polyfit(np.concatenate([B[:, 4], B[:, 6]]), np.concatenate([B[:, 5], B[:, 7]]), 1)
        res = np.maximum(np.maximum(np.abs(A[:, 0] * ax + bx - A[:, 1]), np.abs(A[:, 2] * ax + bx - A[:, 3])),
                         np.maximum(np.abs(A[:, 4] * ay + by - A[:, 5]), np.abs(A[:, 6] * ay + by - A[:, 7])))
        keep = res < 2.0
    P("calibration points used: %d of %d" % (keep.sum(), len(A)))
    P("calibration: x_px = %.4f * colour clock + %.2f;  y_px = %.4f * scanline + %.2f (max residual of the points used: %.2f px)" % (
        ax, bx, ay, by, res[keep].max()))
    # ---- every ghost on every capture ----
    tot, seen, rgb_of, dxs, bad = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter), collections.Counter(), []
    dys, subs = collections.Counter(), collections.Counter()
    text_rgb = None
    for name, mem, shot, pngs in shots:
        for png in pngs:
            im = np.array(Image.open(png).convert("RGB"))
            if text_rgb is None:        # colour register $0C = the status text ("HIGH SCORE")
                reg = im[28:52, 600:830].reshape(-1, 3)
                text_rgb = collections.Counter(tuple(int(v) for v in p) for p in reg if p.any()).most_common(1)[0][0]
            for g in range(4):
                tot["ghost views"] += 1
                loc = locate(mem, g)
                if loc is None:
                    tot["player memory is none of the 11 pictures (not counted)"] += 1
                    continue
                row, pic, rows = loc
                base = pic.split("&")[0]
                if g == shot["ghost"]:        # the ghost the picture was waited for: exactly the ROM shape and feet row that were being drawn
                    want = [rd(shot["src"] + r) for r in range(10)] + [shot["feet"]]
                    if "&" not in pic and rows != want:
                        bad.append((name, png, g, "target ghost's picture differs from the shape being drawn", pic))
                        continue
                    tot["target ghost: player memory == the ROM shape + feet being drawn"] += 1
                x = mem[0x8A + g]
                others = [h for h in range(4) if h != g and locate(mem, h)]
                if any(abs(mem[0x8A + h] - x) < 8 and abs(locate(mem, h)[0] - row) < 11 for h in others):
                    tot["not compared: overlaps another ghost (their colours merge)"] += 1
                    continue
                hit = None      # the nominal position first, then whole-cell shifts; sub-cell pixel offsets absorb the error of the fitted scale
                order = sorted(((dy, dx) for dy in range(-4, 5) for dx in range(-8, 9)), key=lambda t: (abs(t[0]) + abs(t[1]), t))
                for sub in sorted(((ox, oy) for ox in range(-3, 4) for oy in range(-5, 6)), key=lambda t: (abs(t[0]) + abs(t[1]), t)):
                    for dy, dx in order:
                        ok, rgb = sample(im, ax, bx, ay, by, x + dx, row + dy, rows, sub[0], sub[1])
                        if ok:
                            hit = (dx, dy, sub, rgb)
                            break
                    if hit:
                        break
                if hit:
                    dx, dy, sub, rgb = hit
                    dxs[dx] += 1
                    dys[dy] += 1
                    subs[sub] += 1
                    tot["on screen == bitmap: " + pic.split("/")[0].split("&")[0] + (" (clipped at the tunnel edge)" if "&" in pic else "")] += 1
                    seen[base if "&" not in pic else pic] += 1
                    rgb_of[pic.split("/")[0].split("&")[0]][(mem[0x2C0 + g], rgb)] += 1
                else:
                    bad.append((name, png, g, pic, "no position matches the bitmap"))
    for k in sorted(tot):
        P("%-62s %d" % (k, tot[k]))
    P("pictures confirmed on the screen (of 11):", len([n for n in seen if n in PICS]), "  (plus tunnel-clipped variants: %s)" % [n for n in seen if n not in PICS])
    for nm in PICS:
        P("  %-18s %d" % (nm, seen[nm]))
    P("column found on the screen minus EntityX (0 = the ghost is where the game says):", dict(sorted(dxs.items())))
    P("row found on the screen minus the player-memory row (0 = drawn where the memory says):", dict(sorted(dys.items())))
    P("sub-cell pixel offset needed (scale-fit error), (x, y) in window pixels:", dict(sorted(subs.items())))
    P("status-text colour (colour register $0C):", text_rgb)
    P("(colour register $02C0+g at the freeze, screen RGB) per kind:")
    for k, cnt in rgb_of.items():
        P("  %-11s" % k, dict(("$%02X %s" % (c, rgb), n) for (c, rgb), n in cnt.items()))
    P("deviations:", len(bad))
    for b in bad[:12]:
        P("  ", b)
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
