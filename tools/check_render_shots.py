"""Stage 80b: the C renderer (src/c/render) against the REAL pictures of Altirra.
Input: the directory written by  tools/run_item_shots.ps1 -Cmd altirra_rendershots.cmd  (per target <name>.log = the frozen machine's RAM $0000-$CFFF and every write to the player-missile positions,
the player colours, PRIOR, the colour registers and CHBASE with their scan line; <name>_N.png = a capture of Altirra's own window).
For every target: the 64 KB image is built from the log, HPOSP0-3 / HPOSM0-3 are the last values written, the C program tests/render_check draws the frame (the World, the character sets and the
tables of the asset blob that install_assets made from the ROM), the measured NTSC palette (tools/measure_palette.py) turns the colour bytes into RGB, and every pixel of the 384 x 240 picture is compared
with the capture at the window pixel the calibration of analysis/evidence-ghost-screenshots-summary.txt gives (x_px = 5.4680 * colour clock + 12.05, y_px = 3.1711 * scan line - 46.68), after the best
whole-pixel shift of +-3 window pixels (the calibration's own residual is 1.3 pixels).  A pixel is
  exact      the capture shows exactly the expected colour,
  neighbour  it shows the expected colour of one of the 8 neighbouring pixels of the picture (the scaling of the window reads the edge of a pixel),
  blend      it shows no colour of the palette (a blend of two),
  wrong      it shows a colour of the palette that is neither (the renderer drew another colour, or a pixel where the machine has none).
The check holds when no pixel is wrong.  Usage: python -I tools/check_render_shots.py DIR [--summary-file out.txt] [--only name,name]"""
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AX, BX, AY, BY = 5.4680, 12.05, 3.1711, -46.68
W, H, FIRST_LINE, FIRST_CLOCK = 384, 240, 8, 32
HW = re.compile(r"HW r=([0-9A-F]{4}) v=([0-9A-F]{2}) vp=(\d+) hp=(\d+)")
DUMP = re.compile(r"\s*([0-9A-F]{4}): ((?:[0-9A-F]{2} )+)")


def parse(path):
    """-> (the 64 KB image, the last value written to each of $D000-$D01B, the list of HW writes)"""
    img = bytearray(65536)
    last, writes = {}, []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = DUMP.match(line)
            if m:
                a = int(m.group(1), 16)
                for i, b in enumerate(m.group(2).split()):
                    if a + i < 0xD000 or 0xE000 <= a + i < 0xE400:
                        img[a + i] = int(b, 16)
                continue
            m = HW.match(line)
            if m:
                r, v = int(m.group(1), 16), int(m.group(2), 16)
                last[r] = v
                writes.append((r, v, int(m.group(3)), int(m.group(4))))
    return bytes(img), last, writes


def palette():
    pal = {}
    with open(os.path.join(ROOT, "analysis", "palette-ntsc-measured.txt"), encoding="utf-8") as fh:
        for line in fh:
            if line[0] != "#" and line.strip():
                k, r, g, b = line.split()
                pal[int(k, 16)] = (int(r), int(g), int(b))
    return pal


def code(a):
    a = a.astype(np.uint32)
    return (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]


def render(exe, image, hpos, workdir, prev=None):
    """run tests/render_check on the image: -> the colour bytes (H x W); `prev`: the image of the frame before (its shadows give the colours of this frame; default: the same image)"""
    os.makedirs(workdir, exist_ok=True)
    rel = os.path.relpath(workdir, ROOT)
    with open(os.path.join(workdir, "shot.bin"), "wb") as fh:
        fh.write(image)
    args = [exe, os.path.join(rel, "shot.bin"), ",".join(str(h) for h in hpos), os.path.join(rel, "shot.col")]
    if prev is not None:
        with open(os.path.join(workdir, "prev.bin"), "wb") as fh:
            fh.write(prev)
        args.append(os.path.join(rel, "prev.bin"))
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("render_check: " + r.stdout + r.stderr)
    with open(os.path.join(workdir, "shot.col"), "rb") as fh:
        return np.frombuffer(fh.read(), dtype=np.uint8).reshape(H, W)


def expected_rgb(col, pal):
    lut = np.zeros((256, 3), dtype=np.uint8)
    for k in range(256):
        lut[k] = pal[k & 0xFE]
    return lut[col]


PELLET_CELLS = ((3, 3), (3, 36), (16, 3), (16, 36))      # rows / columns of the maze band: the four power pellets blink, the frozen RAM and the picture can differ (as in C-50)


def pellet_mask(image):
    """the pixels of the four power-pellet cells when the screen is the game screen (display list $BFA3), else nothing"""
    m = np.zeros((H, W), dtype=bool)
    if image[0x230] == 0xA3 and image[0x231] == 0xBF:
        for row, c in PELLET_CELLS:
            y0 = 40 + 8 * row - FIRST_LINE
            x0 = (48 - FIRST_CLOCK) * 2 + 8 * c
            m[y0:y0 + 8, x0:x0 + 8] = True
    return m


def sprite_region(exe, image, hpos, workdir, col):
    """the region of the players and missiles: where the picture `col` differs from the same frame drawn without the player-missile memory, widened by 16 pixels and 2 lines"""
    bare = bytearray(image)
    bare[0x2300:0x2800] = bytes(0x500)
    base = render(exe, bytes(bare), hpos, workdir + "-bare")
    return dilate(col != base)


def dilate(mask, dx=16, dy=2):
    out = mask.copy()
    for sy in range(-dy, dy + 1):
        for sx in range(-dx, dx + 1):
            out |= np.roll(np.roll(mask, sy, axis=0), sx, axis=1)
    return out


def compare(col, cap_path, pal, exclude=None, sprites=None):
    """-> dict of counts, the best shift.  `exclude` (a boolean H x W): pixels counted apart, not as wrong (the blinking power pellets); `sprites`: the region of the players and missiles - a wrong pixel inside it is
    counted as `wrong_sprite` (the window can show the frame before the logged one, and sprites move), a wrong pixel outside it as `wrong`"""
    cap = np.asarray(Image.open(cap_path).convert("RGB"))
    E = expected_rgb(col, pal)
    Ec = code(E)
    pcodes = np.array(sorted({(r << 16) | (g << 8) | b for r, g, b in pal.values()}), dtype=np.uint32)
    ys, xs = np.mgrid[0:H, 0:W]
    clock = FIRST_CLOCK + (xs + 0.5) / 2.0
    line = FIRST_LINE + ys + 0.5
    xw = AX * clock + BX
    yw = AY * line + BY
    best = None
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            xi = np.rint(xw + dx).astype(int)
            yi = np.rint(yw + dy).astype(int)
            vis = (yi >= 2) & (yi < cap.shape[0] - 2) & (xi >= 0) & (xi < cap.shape[1])
            O = np.zeros((H, W), dtype=np.uint32)
            O[vis] = code(cap[yi[vis], xi[vis]])
            exact = int(((O == Ec) & vis).sum())
            if best is None or exact > best[0]:
                best = (exact, dx, dy, O.copy(), vis.copy())
    exact, dx, dy, O, vis = best
    is_exact = (O == Ec) & vis
    near = np.zeros((H, W), dtype=bool)
    for sy in (-1, 0, 1):
        for sx in (-1, 0, 1):
            if sy or sx:
                near |= (O == np.roll(np.roll(Ec, sy, axis=0), sx, axis=1))
    is_near = near & ~is_exact & vis
    clean = np.isin(O, pcodes)
    is_blend = ~clean & vis & ~is_exact
    is_wrong = clean & vis & ~is_exact & ~is_near
    excluded = 0
    if exclude is not None:
        excluded = int((is_wrong & exclude).sum())
        is_wrong &= ~exclude
    in_sprites = np.zeros((H, W), dtype=bool) if sprites is None else sprites
    wrong_sprite = int((is_wrong & in_sprites).sum())
    is_wrong &= ~in_sprites
    return {"pixels": int(vis.sum()), "exact": int(is_exact.sum()), "neighbour": int(is_near.sum()), "blend": int(is_blend.sum()), "wrong": int(is_wrong.sum()), "excluded": excluded, "wrong_sprite": wrong_sprite, "shift": (dx, dy),
            "wrong_at": [(int(x), int(y)) for y, x in zip(*np.nonzero(is_wrong))][:8], "wrong_map": is_wrong}


def targets(d, only=None):
    names = sorted({f[:-4] for f in os.listdir(d) if f.endswith(".log")})
    return [n for n in names if os.path.exists(os.path.join(d, n + "_0.png")) and (not only or n in only)]


def hpos_of(last):
    return [last.get(0xD000 + i, 0) for i in range(8)]


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    d = args[0]
    summary = args[args.index("--summary-file") + 1] if "--summary-file" in args else None
    only = args[args.index("--only") + 1].split(",") if "--only" in args else None
    exe = os.path.join(ROOT, "build", "c-clang", "tests", "render_check" + (".exe" if os.name == "nt" else ""))
    pal = palette()
    out, bad = [], 0
    tot = {"pixels": 0, "exact": 0, "neighbour": 0, "blend": 0, "wrong": 0, "wrong_sprite": 0}
    for n in targets(d, only):
        img, last, _ = parse(os.path.join(d, n + ".log"))
        col = render(exe, img, hpos_of(last), os.path.join(ROOT, "build", "t80b", n))
        r = compare(col, os.path.join(d, n + "_0.png"), pal, pellet_mask(img), sprite_region(exe, img, hpos_of(last), os.path.join(ROOT, "build", "t80b", n), col))
        for k in tot:
            tot[k] += r[k]
        bad += r["wrong"]
        out.append("%-18s pixels %6d  exact %6d (%5.1f %%)  neighbour %5d  blend %5d  wrong %4d  at sprites %4d  (pellet cells %3d)  shift %s  hpos %s%s" % (
            n, r["pixels"], r["exact"], 100.0 * r["exact"] / max(1, r["pixels"]), r["neighbour"], r["blend"], r["wrong"], r["wrong_sprite"], r["excluded"], r["shift"], hpos_of(last), ("  at " + str(r["wrong_at"])) if r["wrong"] else ""))
    out.append("total              pixels %6d  exact %6d (%5.1f %%)  neighbour %5d  blend %5d  wrong %4d  at sprites %4d" % (tot["pixels"], tot["exact"], 100.0 * tot["exact"] / max(1, tot["pixels"]), tot["neighbour"], tot["blend"], tot["wrong"], tot["wrong_sprite"]))
    text = "\n".join(out)
    print(text)
    if summary:
        with open(summary, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
