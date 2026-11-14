r"""OV-53: the two-player title screen and the "1UP" / "2UP" labels as PIXELS on the screen.  Input: the captures of tools\run_item_shots.ps1 (Title_1P, Title_2P, Game2P_cp0_shown, Game2P_cp0_blank, Game2P_cp1_shown,
Game2P_cp1_blank: the frozen machine's RAM, the colour-register and CHBASE writes with their scanline, and a capture of Altirra's own window).
Every text row of the display list is rendered from the dumped screen RAM, the character set that CHBASE selected at that scanline ($E0 = the OS font, $18 and $30 = the game's own sets) and the colour registers at that
scanline, and compared with the capture exactly as in check_item_shots.py (a pixel is wrong when the screen shows the clean colour of a register value that is expected nowhere in its neighbourhood):
  ANTIC mode 2 (status line, hi-res, 40 characters): set pixel = hue of COLPF2 with luminance of COLPF1, clear pixel = COLPF2;  mode 6 / 7 (title text and logo, 20 characters of 8 colour clocks, mode 7 twice as tall):
  set pixel = COLPF0-3 chosen by the top two bits of the character code, clear = COLBK;  mode 4 (icons, bottom row): as in check_item_shots.py.
Usage: python -I tools\check_text_shots.py analysis\shots\item-shots [--summary-file out.txt]
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

REGS = list(C.REG) + [0xD409]
PF = [0xD016, 0xD017, 0xD018, 0xD019]
# display list of the title ($BF81): (first scanline, mode, scanlines, bytes per row, screen address or None = continue)
TITLE_ROWS = [(24, 2, 8, 40, 0x2000), (32, 2, 8, 40, None), (40, 6, 8, 20, 0x1C00), (48, 7, 16, 20, None), (64, 7, 16, 20, None)] + \
             [(s, 6, 8, 20, None) for s in (80, 88, 96, 104, 112, 120)] + [(128, 4, 8, 40, None)] + \
             [(s, 6, 8, 20, None) for s in (136, 144, 152, 160, 168, 176, 184, 192, 200, 208)] + [(216, 4, 8, 40, 0x0F70)]
GAME_STATUS_ROWS = [(24, 2, 8, 40, 0x2000), (32, 2, 8, 40, None)]


def rows_with_addresses(rows):
    out, addr = [], None
    for scan, mode, lines, nbytes, a in rows:
        if a is not None:
            addr = a
        out.append((scan, mode, lines, nbytes, addr))
        addr += nbytes
    return out


def val(tl, reg, scan):
    return tl[reg][scan] if 0 <= scan < 262 else None


def render(mem, tl, rows):
    exp, miss = [], collections.Counter()
    for scan0, mode, lines, nbytes, addr in rows_with_addresses(rows):
        for c in range(nbytes):
            code = mem.get(addr + c)
            if code is None:
                miss["screen RAM $%04X not in the dump" % (addr + c)] += 1
                continue
            for line in range(lines):
                scan = scan0 + line
                base = (tl[0xD409][scan] or 0) << 8
                gl = line if mode != 7 else line // 2
                if mode == 2:
                    g = mem.get(base + (code & 0x7F) * 8 + gl)
                    if g is None:
                        miss["character set $%04X not in the dump" % base] += 1
                        continue
                    if code & 0x80:
                        g ^= 0xFF
                    pf1, pf2 = val(tl, 0xD017, scan), val(tl, 0xD018, scan)
                    if pf1 is None or pf2 is None:
                        continue
                    on = (pf2 & 0xF0) | (pf1 & 0x0F)
                    for j in range(8):
                        v = on if (g >> (7 - j)) & 1 else pf2
                        exp.append((48 + 4 * c + 0.5 * j - 0.25, scan, 0, v, code, scan0, c))
                elif mode in (6, 7):
                    g = mem.get(base + (code & 0x3F) * 8 + gl)
                    if g is None:
                        miss["character set $%04X not in the dump" % base] += 1
                        continue
                    reg = PF[(code >> 6) & 3]
                    for j in range(8):
                        v = val(tl, reg, scan) if (g >> (7 - j)) & 1 else val(tl, 0xD01A, scan)
                        exp.append((48 + 8 * c + j, scan, 0, v, code, scan0, c))
                else:                                        # mode 4
                    g = mem.get(base + (code & 0x7F) * 8 + gl)
                    if g is None:
                        miss["character set $%04X not in the dump" % base] += 1
                        continue
                    for k in range(4):
                        p = (g >> (6 - 2 * k)) & 3
                        reg = 0xD01A if p == 0 else 0xD016 if p == 1 else 0xD017 if p == 2 else (0xD019 if code & 0x80 else 0xD018)
                        exp.append((48 + 4 * c + k, scan, 0, val(tl, reg, scan), code, scan0, c))
    return [e for e in exp if e[3] is not None], miss


def text_of(mem, addr, n):
    s = ""
    for i in range(n):
        ch = (mem.get(addr + i, 0)) & 0x3F
        s += " " if ch == 0 else chr(0x30 + ch - 0x10) if 0x10 <= ch <= 0x19 else chr(0x41 + ch - 0x21) if 0x21 <= ch <= 0x3A else "?"
    return s


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
    names = [n for n in ("Title_1P", "Title_2P", "Game2P_cp0_shown", "Game2P_cp0_blank", "Game2P_cp1_shown", "Game2P_cp1_blank") if os.path.exists(os.path.join(d, n + ".log"))]
    palette = collections.defaultdict(collections.Counter)
    for n in names:
        mem, cw = C.parse(os.path.join(d, n + ".log"))
        tl, use = C.timeline(cw, REGS)
        pngs = sorted(glob.glob(os.path.join(d, n + "_*.png")))
        if not pngs:
            continue
        im = np.array(Image.open(pngs[-1]).convert("RGB"))
        rows = TITLE_ROWS if n.startswith("Title") else GAME_STATUS_ROWS
        exp, miss = render(mem, tl, rows)
        total, exact, wrong, by, refs, bad = C.judge(exp, im)
        for v, c in by.items():
            for rgb, k in c.items():
                palette[v][rgb] += k
        P("%s: %d pixels rendered, %d exactly the colour of their register value, %d the clean colour of a value expected nowhere nearby%s" % (n, total, exact, wrong, "; MISSING: %s" % dict(miss) if miss else ""))
        if n.startswith("Title"):
            P("   screen RAM text: $1C54 %r  $1C56 %r | $1C90 %r  $1C92 %r | %r | %r | %r | %r" % (text_of(mem, 0x1C54, 1), text_of(mem, 0x1C56, 11), text_of(mem, 0x1C90, 1), text_of(mem, 0x1C92, 11),
              text_of(mem, 0x1C7A, 16), text_of(mem, 0x1CF2, 16), text_of(mem, 0x1D56, 16), text_of(mem, 0x1D05, 17)))
        P("   status line: %r / %r  (labels: $2004 %02X%02X%02X, $2021 %02X%02X%02X)" % (text_of(mem, 0x2000, 40), text_of(mem, 0x2028, 40), mem.get(0x2004, 0), mem.get(0x2005, 0), mem.get(0x2006, 0), mem.get(0x2021, 0), mem.get(0x2022, 0), mem.get(0x2023, 0)))
        ink_ref = refs.get(0x0C)                                   # the clean colour of the text value (COLPF1 $0C on COLPF2 $00)
        for lab, a in (("1UP", 0x2004), ("2UP", 0x2021)):
            cells = [(mem.get(a + i, 0)) for i in range(3)]
            region = [e for e in exp if e[5] == 24 and a - 0x2000 <= e[6] < a - 0x2000 + 3]
            n_exp = sum(1 for e in region if e[3] == 0x0C)
            n_obs = sum(1 for e in region if C.pix(im, e[0], e[1]) == ink_ref)
            shown = cells != [0, 0, 0]
            P("   label %s cells %s (%s): %d ink pixels expected, %d pixels with the ink colour (%s) on the screen in the three cells" % (lab, "".join("%02X" % x for x in cells), "shown" if shown else "blank", n_exp, n_obs, ink_ref))
            if shown and not (0.5 * n_exp <= n_obs <= 1.3 * n_exp):
                problems.append("%s %s ink count" % (n, lab))
            if not shown and n_obs != 0:
                problems.append("%s %s blank label shows ink" % (n, lab))
        if wrong or miss:
            problems.append("%s: %d wrong, missing %s" % (n, wrong, dict(miss)))
    P("")
    P("Register value -> clean RGB over all captures: " + ", ".join("$%02X %s" % (v, c.most_common(1)[0][0]) for v, c in sorted(palette.items())))
    P("")
    P("PROBLEMS: " + ("none" if not problems else "; ".join(problems)))
    if summ:
        open(summ, "w", encoding="utf-8").write("\n".join(out) + "\n")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
