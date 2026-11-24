"""Stages 69-70 (resources, and the font): THE ASSET PACK OF THE PORT - every byte of the ROM that is not code, decoded into one defined format (schema 1), a reference loader, and the checks that the pack is complete and equals what the
original builds in RAM.

The pack is DERIVED FROM THE COPYRIGHTED ROM: it is written to `resources/pack/` (git-ignored) by `python -I tools/asset_pack.py --write`; only this tool, the format (docs/47-resources.md) and the tests are committed.
`resources/pack/assets.json` holds, in schema 1:
  regions     every labelled data region of the ROM (tools/labels.py DATA, 76 regions, 2,171 bytes) with its ROM address and bytes, plus the 69 bytes of the two display lists and the 6 header bytes: all 2,246 bytes that are not code
  charsets    the game set (101 glyphs, 8 rows of 8 bits; ANTIC mode 4: 4 pixels of 2 bits a row), the title set (24 glyphs, codes 1-24)
  maze        23 x 40 character codes, the legend (0 blank, 1 dot, 2 power pellet, the rest wall and decoration glyphs), the counts and the four pellet cells
  sprites     the ghost, eyes, Pac-Man, death-star and pop-up pictures as rows of 8 bits (player-missile graphics, one byte a scan line)
  text        every text of the game as screen codes and as ASCII
  tunes       the two 64-entry AUDF tables of the start tune, the two pitch sweeps
  colours, tables, display_lists: the colour tables, the level / lattice / route tables, the two display lists decoded
  font        (schema 2) the 64 glyphs of the OS font the title and status text is drawn with, rendered from the OFL font third-party/EightBit-Atari-Fonts (credit and licence: third-party/README.md); needs Pillow
Usage: python -I tools/asset_pack.py [--write [dir]] [--png]    (default dir resources/pack)"""
import hashlib
import json
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import decode_streams as S  # noqa: E402
import labels  # noqa: E402

SCHEMA = 2
FONT_PATH = os.path.join(ROOT, "third-party", "EightBit-Atari-Fonts", "EightBit Atari-Regular.ttf")
FONT_ROW_OFFSET = 2          # the glyph box of the font starts 2 rows below the top of the 8-pixel em as Pillow draws it (checked: all 64 glyphs equal the OS ROM font with this offset)
ROM_PATH = os.path.join(ROOT, "original", "Pac-Man.rom")
DISPLAY_LISTS = {"DisplayList2": (0xBF81, 0xBFA2), "DisplayList1": (0xBFA3, 0xBFC5)}
HEADER = (0xBFFA, 0xBFFF)


def rom_bytes(lo, hi):
    return bytes(S.rd(a) for a in range(lo, hi + 1))


def hexs(b):
    return bytes(b).hex()


def rows8(b, n=8):
    return [hexs(b[i:i + n]) for i in range(0, len(b), n)]


def region(name):
    for lo, hi, kind, nm, note in labels.DATA:
        if nm == name:
            return lo, hi, rom_bytes(lo, hi)
    raise KeyError(name)


def screen_ascii(codes):
    """ANTIC mode 2 / 6 screen code: the low 6 bits are the glyph, code + $20 = ASCII (the top two bits of mode 6 select the colour register)"""
    return "".join(chr((c & 0x3F) + 0x20) for c in codes)


def decode_dl(lo, hi):
    """a display list: [(mode or 'blank', scan lines, lms address or None, interrupt)]"""
    scan = {2: 8, 4: 8, 6: 8, 7: 16}
    out, a = [], lo
    while a <= hi:
        b = S.rd(a)
        m = b & 15
        if m == 0:
            out.append({"blank": ((b >> 4) & 7) + 1, "dli": bool(b & 0x80)})
            a += 1
        elif m == 1:
            out.append({"jvb": S.rd(a + 1) | S.rd(a + 2) << 8})
            a += 3
        else:
            lms = (S.rd(a + 1) | S.rd(a + 2) << 8) if b & 0x40 else None
            out.append({"mode": m, "lines": scan[m], "lms": lms, "dli": bool(b & 0x80)})
            a += 3 if b & 0x40 else 1
    return out


def render_font(size=8):
    """-> 64 glyphs (screen codes $00-$3F = ASCII $20-$5F) of 8 bytes each, rendered from the OFL font at one pixel per design unit; the outlines lie on the 8 x 8 grid, so there is no anti-aliasing to decide"""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(FONT_PATH, size)
    out = []
    for code in range(64):
        im = Image.new("1", (8, 24), 0)
        ImageDraw.Draw(im).text((0, 0), chr(0xE000 + 0x20 + code), font=f, fill=1)      # the standard set is at ASCII + $E000 (upstream README)
        out.append(bytes(sum((1 if im.getpixel((x, y)) else 0) << (7 - x) for x in range(8)) for y in range(FONT_ROW_OFFSET, FONT_ROW_OFFSET + 8)))
    return out


def build():
    """-> the pack as a JSON-able dict"""
    with open(ROM_PATH, "rb") as fh:
        rom = fh.read()
    P = {"schema": SCHEMA, "rom": {"sha256": hashlib.sha256(rom).hexdigest(), "size": len(rom), "base": "A000"}}
    # 1. every region of the ROM that is not code
    regs = []
    for lo, hi, kind, nm, note in labels.DATA:
        regs.append({"name": nm, "kind": kind, "addr": "%04X" % lo, "size": hi - lo + 1, "bytes": hexs(rom_bytes(lo, hi)), "note": note})
    for nm, (lo, hi) in DISPLAY_LISTS.items():
        regs.append({"name": nm, "kind": "display list", "addr": "%04X" % lo, "size": hi - lo + 1, "bytes": hexs(rom_bytes(lo, hi)), "note": "ANTIC display list"})
    regs.append({"name": "CartridgeHeader", "kind": "header", "addr": "%04X" % HEADER[0], "size": HEADER[1] - HEADER[0] + 1, "bytes": hexs(rom_bytes(*HEADER)), "note": "RUN, flags, INIT"})
    P["regions"] = regs
    # 2. the character sets: what Start builds in RAM
    game, _ = S.decode_b(0xA003)
    title_a, _ = S.decode_b(0xBE13)
    tail = rom_bytes(*region("TitleCharsetTail")[:2])
    title = bytes(title_a) + tail
    P["charsets"] = {
        "game": {"ram": "3000", "glyphs": len(game) // 8, "rows": rows8(bytes(game)), "format": "ANTIC mode 4: each row is 4 pixels of 2 bits (00 COLBK, 01 COLPF0, 10 COLPF1, 11 COLPF2; COLPF3 when bit 7 of the screen code is set)"},
        "title": {"ram": "1808", "first_code": 1, "glyphs": len(title) // 8, "rows": rows8(title), "format": "the title character set (CHBASE $18): codes 1-24; glyph 0 ($1800-$1807) is not part of the ROM"},
    }
    # 3. the maze
    maze, _ = S.decode_a(0xA1E1)
    maze = bytes(maze)
    cells = [maze[r * 40:(r + 1) * 40] for r in range(23)]
    P["maze"] = {"ram": "0800", "cols": 40, "rows": 23, "codes": [list(r) for r in cells],
                 "legend": {"0": "blank", "1": "dot (10 points)", "2": "power pellet (50 points)", "other": "wall and decoration glyphs of the game character set"},
                 "dots": sum(1 for b in maze if b == 1), "power_pellets": [[i // 40, i % 40] for i, b in enumerate(maze) if b == 2],
                 "cell_to_coordinates": "an entity at cell (row, col) of a junction row / column has y = 8 * row + 36 and x = 4 * col + 46 (JunctionYList, JunctionXList)"}
    # 4. sprites: rows of 8 bits, one byte a scan line
    spr = {}
    for nm in ("GhostShapeUp", "GhostShapeDown", "GhostShapeLeft", "GhostShapeRight", "GhostShapeFrightened", "GhostEyesShape", "PacShapeFull", "PacShapeRight1", "PacShapeRight2", "PacShapeLeft1", "PacShapeLeft2",
               "PacShapeUp1", "PacShapeUp2", "PacShapeDown1", "PacShapeDown2", "StarShape", "GhostScoreZeros", "GhostScore200Digits", "GhostScore400Digits", "GhostScore800Digits", "GhostScore1600Digits"):
        lo, hi, b = region(nm)
        spr[nm] = {"addr": "%04X" % lo, "rows": list(b)}
    P["sprites"] = {"format": "player-missile graphics: one byte a scan line, bit 7 the leftmost pixel; the ghost is a player (8 pixels), Pac-Man and the pop-up score are drawn with the four missiles and a player (docs 16, 20)", "shapes": spr,
                    "pac_shape_pointers": [int.from_bytes(region("PacShapePtrs")[2][i:i + 2], "little") for i in range(0, 10, 2)],
                    "ghost_score_pointers": [int.from_bytes(region("GhostScorePtrs")[2][i:i + 2], "little") for i in range(0, 8, 2)]}
    # 5. text
    txt = {}
    for nm in ("TextHighScore", "TextChangeDifficulty", "TextPressStartTo", "TextCopyright", "TextPlayerGame", "TextPressSelectFor", "TextPressOptionTo", "TextPlayGame"):
        lo, hi, b = region(nm)
        kind = [k for l_, h_, k, n_, _ in labels.DATA if n_ == nm][0]
        txt[nm] = {"addr": "%04X" % lo, "mode": 6 if kind == "text6" else 2, "codes": list(b), "ascii": screen_ascii(b), "colour_bits": [c >> 6 for c in b] if kind == "text6" else None}
    P["text"] = {"note": "screen codes, not zero-terminated: every line has a fixed length given by its copy loop; code 0 is the space; ANTIC mode 6 lines take their glyphs from the OS font (CHBASE $E0)", "strings": txt}
    # 6. tunes and sweeps
    P["tunes"] = {"start_tune": {"audf1": list(region("TuneAudf1")[2]), "audf2": list(region("TuneAudf2")[2]), "step_jiffies": 4,
                                 "note": "stored to AUDF1 / AUDF2 one entry per 4th jiffy (docs 22; analysis/start-tune.wav is the rendered tune)"},
                  "audf_sweep_down": list(region("AudfSweepDown")[2]), "audf_sweep_up": list(region("AudfSweepUp")[2]),
                  "other_sounds": "the dot, bonus, frightened, eyes, siren, ghost-eaten and death sounds are computed by code, not stored: tools/core_sound.py writes their sound-chip registers in the ROM's order (docs 22, 44)"}
    # 7. colours
    P["colours"] = {"game": list(region("ColorsGame")[2]), "game_names": ["PCOLR0", "PCOLR1", "PCOLR2", "PCOLR3", "COLOR0", "COLOR1", "COLOR2", "COLOR3"], "title": list(region("ColorsTitle")[2]), "dli": list(region("ColorsDli")[2]),
                    "note": "Atari colour bytes (hue in the high nibble, luminance in the low); the display-list interrupts change them by band (docs 35)"}
    # 8. the tables of the expansion and of the levels (the RAM image $0600-$07D7 and the ROM tables)
    nib, _ = S.split_nibbles(0xBE95)
    ram0600 = bytes(nib[:0x1D8])
    P["tables"] = {"ram_0600": hexs(ram0600), "slices": {n: {"addr": "%04X" % a, "size": c} for n, a, c in RAM_SLICES}}
    for n, a, c in RAM_SLICES:
        P["tables"][n] = list(ram0600[a - 0x600:a - 0x600 + c])
    for nm in ("JunctionYList", "JunctionXList", "SightOffsetsX", "SightOffsetsY", "HouseReleaseTimers", "FrightenFrames", "PatrolStartPositions", "CornerPositions", "PatrolRouteOffsets", "BonusItemCodes", "BonusScoreGlyphs",
               "BonusScoreGlyphOffsets", "PacMoveDelayBase", "GhostMoveDelayBase", "LevelIconCodes", "DeathPlotBytes", "DliChbaseTable"):
        P["tables"][nm] = list(region(nm)[2])
    P["display_lists"] = {nm: decode_dl(lo, hi) for nm, (lo, hi) in DISPLAY_LISTS.items()}
    with open(FONT_PATH, "rb") as fh:
        ttf = fh.read()
    P["font"] = {"codes": 64, "first_ascii": 32, "rows": [hexs(g) for g in render_font()], "ram": "E000",
                 "format": "8 x 8, one byte a row, bit 7 leftmost; screen code c (the low six bits of an ANTIC mode 2 / 6 code) is glyph c, ASCII c + $20; the OS ROM keeps this set at $E000 (CHBASE $E0) and the game's text and status lines are drawn from it",
                 "source": {"file": "third-party/EightBit-Atari-Fonts/EightBit Atari-Regular.ttf", "sha256": hashlib.sha256(ttf).hexdigest(), "url": "https://github.com/a8bit/EightBit-Atari-Fonts", "commit": "8b5a19f41f46fc93fe58455355b5bc0c31c31bda",
                            "author": "Steve Boswell (c) 2018", "license": "SIL Open Font License 1.1 (third-party/EightBit-Atari-Fonts/OFL.txt)", "credit": "Atari 8-bit bitmaps; layout after Mark Simonson's Atari font; see third-party/README.md"}}
    return P


# the tables the nibble split puts at $0600 (docs/12): name, RAM address, nibbles
RAM_SLICES = [("DeathPlotRows", 0x0600, 14), ("JunctionExits", 0x060E, 100), ("FrightenEndPhase", 0x0672, 20), ("StartRoutes", 0x0686, 40), ("PatrolRoutes", 0x06AE, 230), ("BonusScore", 0x0794, 26),
              ("MoveDelay", 0x07AE, 24), ("NoReverseMask", 0x07C6, 9), ("ReverseDir", 0x07CF, 9)]


def dumps(P):
    return json.dumps(P, indent=1, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# the reference loader: the pack to the RAM image the original builds
def load(path):
    with open(path, encoding="utf-8") as fh:
        P = json.load(fh)
    if P.get("schema") != SCHEMA:
        raise ValueError("asset pack schema %r, expected %d" % (P.get("schema"), SCHEMA))
    return P


def ram_image(P):
    """-> a 64 KB image with the game character set at $3000, the title set at $1808, the maze at $0800 and the tables at $0600, as `Start` builds them"""
    m = bytearray(0x10000)
    g = bytes.fromhex("".join(P["charsets"]["game"]["rows"]))
    m[0x3000:0x3000 + len(g)] = g
    t = bytes.fromhex("".join(P["charsets"]["title"]["rows"]))
    m[0x1808:0x1808 + len(t)] = t
    mz = bytes(c for row in P["maze"]["codes"] for c in row)
    m[0x0800:0x0800 + len(mz)] = mz
    r = bytes.fromhex(P["tables"]["ram_0600"])
    m[0x0600:0x0600 + len(r)] = r
    f = bytes.fromhex("".join(P["font"]["rows"]))
    m[0xE000:0xE000 + len(f)] = f                       # the OS font page the text lines read (CHBASE $E0); not part of the cartridge
    return m


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# previews: indexed PNGs written with the standard library only (not colour-accurate: the exact colours are in assets.json)
def png(path, w, h, pix, palette):
    raw = b"".join(b"\x00" + bytes(pix[y * w:(y + 1) * w]) for y in range(h))

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)) + chunk(b"PLTE", bytes(c for rgb in palette for c in rgb)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(out)


PAL4 = [(0, 0, 0), (40, 80, 200), (240, 240, 240), (230, 190, 40)]
PAL1 = [(0, 0, 0), (255, 255, 255)]


def glyph_pixels2(rows):
    """8 bytes of a mode-4 glyph -> 8 rows of 4 pixels of 2 bits, doubled to 8 columns"""
    out = []
    for b in rows:
        px = [(b >> s) & 3 for s in (6, 4, 2, 0)]
        out.append([v for v in px for _ in (0, 1)])
    return out


def write_previews(P, outdir):
    # game charset atlas: 16 glyphs a row, 2 bits a pixel
    g = bytes.fromhex("".join(P["charsets"]["game"]["rows"]))
    n = len(g) // 8
    cols = 16
    rws = (n + cols - 1) // cols
    W, H = cols * 8, rws * 8
    pix = [0] * (W * H)
    for i in range(n):
        for y, row in enumerate(glyph_pixels2(g[i * 8:i * 8 + 8])):
            for x, v in enumerate(row):
                pix[(i // cols * 8 + y) * W + (i % cols) * 8 + x] = v
    png(os.path.join(outdir, "charset_game.png"), W, H, pix, PAL4)
    # maze preview: the 23 x 40 cells drawn with the game set
    mz = P["maze"]["codes"]
    W, H = 40 * 8, 23 * 8
    pix = [0] * (W * H)
    for r in range(23):
        for c in range(40):
            code = mz[r][c] & 0x7F
            for y, row in enumerate(glyph_pixels2(g[code * 8:code * 8 + 8])):
                for x, v in enumerate(row):
                    pix[(r * 8 + y) * W + c * 8 + x] = v
    png(os.path.join(outdir, "maze.png"), W, H, pix, PAL4)
    # sprites: 1 bit a pixel, one column of 16 px per shape
    shapes = P["sprites"]["shapes"]
    names = list(shapes)
    W, H = len(names) * 10, 16
    pix = [0] * (W * H)
    for i, nm in enumerate(names):
        for y, b in enumerate(shapes[nm]["rows"][:16]):
            for x in range(8):
                pix[y * W + i * 10 + x] = (b >> (7 - x)) & 1
    png(os.path.join(outdir, "sprites.png"), W, H, pix, PAL1)
    # the text of the game drawn with the font, mode 6 style (each glyph doubled in width)
    lines = [v["ascii"] for v in P["text"]["strings"].values()]
    fr = [bytes.fromhex(r) for r in P["font"]["rows"]]
    W, H = 17 * 16, len(lines) * 8
    pix = [0] * (W * H)
    for li, line in enumerate(lines):
        for ci, ch in enumerate(line[:17]):
            g = fr[(ord(ch) - 0x20) & 0x3F]
            for y in range(8):
                for x in range(8):
                    if (g[y] >> (7 - x)) & 1:
                        pix[(li * 8 + y) * W + ci * 16 + x * 2] = pix[(li * 8 + y) * W + ci * 16 + x * 2 + 1] = 1
    png(os.path.join(outdir, "text.png"), W, H, pix, PAL1)


def write(outdir, previews=True):
    os.makedirs(outdir, exist_ok=True)
    P = build()
    files = {"assets.json": dumps(P).encode("utf-8")}
    for name, data in files.items():
        with open(os.path.join(outdir, name), "wb") as fh:
            fh.write(data)
    if previews:
        write_previews(P, outdir)
    man = {"schema": SCHEMA, "rom_sha256": P["rom"]["sha256"], "files": {}}
    for name in sorted(os.listdir(outdir)):
        if name != "manifest.json":
            with open(os.path.join(outdir, name), "rb") as fh:
                man["files"][name] = hashlib.sha256(fh.read()).hexdigest()
    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(man, indent=1, sort_keys=True) + "\n")
    return P


def main():
    if "--write" in sys.argv:
        i = sys.argv.index("--write")
        out = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else os.path.join(ROOT, "resources", "pack")
        P = write(out)
        print("wrote", out, "-", len(dumps(P)), "bytes of assets.json,", len(P["regions"]), "regions")
        return
    P = build()
    print("regions:", len(P["regions"]), "bytes:", sum(r["size"] for r in P["regions"]), "dots:", P["maze"]["dots"], "pellets:", P["maze"]["power_pellets"])


if __name__ == "__main__":
    main()
