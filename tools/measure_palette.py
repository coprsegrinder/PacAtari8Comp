"""Stage 80b: the NTSC palette AS MEASURED from Altirra (docs/51, decision D2).
Two modes:
  python -I tools/measure_palette.py --build DIR      writes DIR/palette_a.xex and palette_b.xex: a 6502 program (no OS use, no display list: the screen is all background) that sets COLBK once per two scan lines
                                                      to the value  2 * (VCOUNT - 4) + BASE  (BASE = 0 in a, 240 in b), so that the 128 colours of the GTIA (the low bit of a colour byte does not count) are shown as stripes
  python -I tools/measure_palette.py --read DIR OUT   reads DIR/palette_a_0.png and palette_b_0.png (captures of Altirra's own window made by tools/run_palette_shots.ps1), finds the stripes and writes OUT:
                                                      the 128 colour values and their RGB, and the checks (every stripe a clean flat colour, 128 different colours or the reason why not)
The program:  SEI; LDA #0; STA NMIEN; STA DMACTL;  loop: LDX VCOUNT; LDA table,X; STA WSYNC; STA COLBK; JMP loop   (table at $2100, 256 bytes)"""
import os
import struct
import sys

CODE = bytes([0x78, 0xA9, 0x00, 0x8D, 0x0E, 0xD4, 0x8D, 0x00, 0xD4,          # SEI; LDA #0; STA NMIEN; STA DMACTL
              0xAE, 0x0B, 0xD4, 0xBD, 0x00, 0x21, 0x8D, 0x0A, 0xD4, 0x8D, 0x1A, 0xD0, 0x4C, 0x09, 0x20])   # loop at $2009


PASSES = (("palette_a", 16), ("palette_b", 248), ("palette_c", 238))      # the first stripe of the window (VCOUNT 8, scan line 16) shows colour base + 8: a: 18..F4, b: 00..DE, c: F6..


def table(base):
    return bytes((2 * (v - 4) + base) & 0xFF if 4 <= v <= 130 else 0 for v in range(256))


def xex(base):
    out = bytearray(b"\xFF\xFF")
    out += struct.pack("<HH", 0x2000, 0x2000 + len(CODE) - 1) + CODE
    t = table(base)
    out += struct.pack("<HH", 0x2100, 0x21FF) + t
    out += struct.pack("<HH", 0x02E0, 0x02E1) + struct.pack("<H", 0x2000)     # RUNAD
    return bytes(out)


def build(d):
    os.makedirs(d, exist_ok=True)
    for name, base in PASSES:
        with open(os.path.join(d, name + ".xex"), "wb") as fh:
            fh.write(xex(base))
    print("wrote", d)


KNOWN = {0x0C: (205, 198, 210), 0x28: (170, 126, 0), 0x44: (144, 24, 41), 0x4A: (254, 135, 155), 0x84: (18, 62, 178), 0xD8: (49, 156, 13), 0xDC: (142, 227, 110)}   # colours seen on the game's own screens (C-50, C-52)


def stripes(path, x_px=900):
    """the colours of the stripes down the column x_px: the runs of 5 to 9 pixels (the scaling of the window leaves one-pixel blends between them)"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    runs = []
    for y in range(im.size[1]):
        p = im.getpixel((x_px, y))
        if runs and runs[-1][0] == p:
            runs[-1][1] += 1
        else:
            runs.append([p, 1])
    return [c for c, n in runs if 5 <= n <= 9]


def read(d, out):
    pal, notes = {}, []
    for name, base in PASSES:
        clean = stripes(os.path.join(d, name + "_0.png"))
        s0 = (base + 8) & 0xFF                      # by construction: the first stripe in the window is VCOUNT 8
        hits = sum(1 for k, v in KNOWN.items() if 0 <= (k - s0) // 2 < len(clean) and (k - s0) % 2 == 0 and clean[(k - s0) // 2] == v)
        inside = sum(1 for k in KNOWN if 0 <= (k - s0) // 2 < len(clean) and (k - s0) % 2 == 0)
        notes.append("%s: %d stripes from colour %02X, %d of %d known colours inside it are where the order puts them" % (name, len(clean), s0, hits, inside))
        for i, c in enumerate(clean):
            k = s0 + 2 * i
            if k <= 254 and k not in pal:
                pal[k] = c
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("# NTSC palette as rendered by Altirra 4.40 (tools/measure_palette.py): colour byte (even values; the low bit is not used), R G B"+"\n")
        for k in sorted(pal):
            fh.write("%02X %d %d %d" % ((k,) + tuple(pal[k])) + "\n")
        fh.write("# " + "; ".join(notes) + "\n" + "# colours found: %d of 128, distinct RGB: %d" % (len(pal), len(set(pal.values()))) + "\n")
    print(open(out).read()[-700:])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--build":
        build(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "--read":
        read(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
