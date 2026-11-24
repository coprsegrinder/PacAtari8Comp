"""Stages 69-70: the checks of the asset pack (tools/asset_pack.py): completeness against the code, equality with what the original builds in RAM, the meaning of the maze, the texts, the pointers, the display lists, and that
the written pack is deterministic.  Each check is (name, ok, detail).
Usage: python -I tools/check_assets.py [--write analysis/evidence-assets-summary.txt]"""
import hashlib
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import algorithm_models as A  # noqa: E402
import asset_pack as AP  # noqa: E402
import core_ref as R  # noqa: E402
import decode_streams as S  # noqa: E402
import output_map as O  # noqa: E402

EXPECTED_TEXT = {"TextHighScore": "HIGH SCORE", "TextChangeDifficulty": "CHANGE DIFFICULTY", "TextPressStartTo": "PRESS START TO  ", "TextCopyright": "(C) ATARI 1982", "TextPlayerGame": "PLAYER GAME",
                 "TextPressSelectFor": "PRESS SELECT FOR", "TextPressOptionTo": "PRESS OPTION TO ", "TextPlayGame": "PLAY GAME"}


def checks():
    P = AP.build()
    out = []

    def add(name, ok, detail):
        out.append((name, bool(ok), detail))

    # 1. completeness: every byte of the ROM is code or in exactly one region
    code = set()
    for pc, (ln, m, mode, op) in O.INS.items():
        code.update(range(pc, pc + ln))
    seen = {}
    overlap = 0
    for r in P["regions"]:
        lo = int(r["addr"], 16)
        for a in range(lo, lo + r["size"]):
            overlap += a in seen
            seen[a] = r["name"]
    rom_range = set(range(0xA000, 0xC000))
    uncovered = sorted(rom_range - code - set(seen))
    both = sorted(code & set(seen))
    add("completeness", not uncovered and not overlap and not both,
        "the ROM's 8192 bytes: %d code (%d instructions traced), %d in %d regions; uncovered %d, in two regions %d, in a region and in code %d" % (len(code & rom_range), len(O.INS), len(seen), len(P["regions"]), len(uncovered), overlap, len(both)))
    add("non-code total", sum(r["size"] for r in P["regions"]) == 2246, "the regions hold %d bytes (docs/12: 2,246 bytes are not code)" % sum(r["size"] for r in P["regions"]))
    # 2. the regions equal the ROM
    with open(AP.ROM_PATH, "rb") as fh:
        rom = fh.read()
    bad = [r["name"] for r in P["regions"] if bytes.fromhex(r["bytes"]) != rom[int(r["addr"], 16) - 0xA000:int(r["addr"], 16) - 0xA000 + r["size"]]]
    add("regions equal the ROM", not bad, "%d regions, %d differ" % (len(P["regions"]), len(bad)))
    # 3. the loader's image equals what Start builds in RAM (the 6502 runs Start's own expansion code)
    img = AP.ram_image(P)
    mem = A.started_machine().mem
    diffs = []
    for lo, hi, nm in ((0x3000, 0x3000 + 808, "game charset"), (0x1808, 0x1808 + 192, "title charset"), (0x0800, 0x0800 + 920, "maze"), (0x0600, 0x07D8, "tables")):
        if bytes(img[lo:hi]) != bytes(mem[lo:hi]):
            diffs.append(nm)
    add("loader image equals the RAM Start builds", not diffs, "game charset 808, title charset 192, maze 920 and tables 472 bytes, compared with the concrete 6502 after Start's expansion: %s" % ("equal" if not diffs else "differ: " + ", ".join(diffs)))
    # 4. the maze
    mz = P["maze"]
    dots, pel = mz["dots"], len(mz["power_pellets"])
    lo = hi = 0
    n = 0
    while True:
        lo, hi, done = R.count_dot(lo, hi)
        n += 1
        if done:
            break
    add("maze counts equal the board-complete count of the code", dots + pel == n, "%d dots + %d power pellets = %d; the code counts one more at each of them and ends the board at %d (core_ref.count_dot, checked against the ROM in `44`)" % (dots, pel, dots + pel, n))
    squares = [(8 * r + 36, 4 * c + 46) for r, c in mz["power_pellets"]]
    add("pellet cells are the pellet squares", sorted(squares) == sorted(R.PELLET_SQUARES), "cells %s -> (y, x) %s; the code's squares %s" % (mz["power_pellets"], ["$%02X,$%02X" % s for s in squares], ["$%02X,$%02X" % s for s in R.PELLET_SQUARES]))
    jy, jx = P["tables"]["JunctionYList"], P["tables"]["JunctionXList"]
    add("junction lists follow the cell formula", jy == [8 * r + 36 for r in (1, 4, 6, 8, 10, 12, 14, 16, 18, 20)] and jx == [4 * c + 46 for c in (3, 6, 9, 13, 18, 21, 26, 30, 33, 36)], "y = 8 * row + 36 for rows 1,4,6,8,10,12,14,16,18,20; x = 4 * col + 46 for columns 3,6,9,13,18,21,26,30,33,36")
    sym = all((mz["codes"][r][c] in (1, 2)) == (mz["codes"][r][39 - c] in (1, 2)) and (mz["codes"][r][c] == 2) == (mz["codes"][r][39 - c] == 2) for r in range(23) for c in range(20))
    add("dots and pellets are left-right symmetric", sym, "the dot and pellet cells of the 23 x 40 maze mirror about the middle (the wall glyphs do not: a left wall and a right wall are different glyphs): %s" % ("yes" if sym else "no"))
    # 5. texts
    got = {k: v["ascii"] for k, v in P["text"]["strings"].items()}
    badt = [k for k, v in EXPECTED_TEXT.items() if got.get(k) != v]
    add("texts decode", not badt, "%d strings decoded with code + $20 = ASCII; those confirmed on screen in docs/12 and docs/21 match: %s" % (len(got), "all" if not badt else badt))
    # 6. the pointers of the code point at the regions of the pack
    ad = {r["name"]: int(r["addr"], 16) for r in P["regions"]}
    pac = [ad[n] for n in ("PacShapeFull", "PacShapeRight1", "PacShapeLeft1", "PacShapeUp1", "PacShapeDown1")]
    gs = [ad[n] for n in ("GhostScore200Digits", "GhostScore400Digits", "GhostScore800Digits", "GhostScore1600Digits")]
    add("shape pointers", P["sprites"]["pac_shape_pointers"] == pac and P["sprites"]["ghost_score_pointers"] == gs,
        "PacShapePtrs %s = the first frames of full, right, left, up, down; GhostScorePtrs %s = the four pop-up pictures" % (["$%04X" % p for p in P["sprites"]["pac_shape_pointers"]], ["$%04X" % p for p in P["sprites"]["ghost_score_pointers"]]))
    sh = P["sprites"]["shapes"]
    add("shape sizes", all(len(sh[n]["rows"]) == 10 for n in sh if n.startswith(("Ghost", "Pac")) and "Score" not in n) and all(len(sh[n]["rows"]) == 12 for n in sh if "Score" in n or n == "StarShape"),
        "ghost and Pac-Man pictures 10 rows, the star and the pop-up pictures 12 rows (the draw routines copy 16)")
    # 7. display lists
    dl1 = P["display_lists"]["DisplayList1"]
    m4 = [e for e in dl1 if e.get("mode") == 4]
    lms = [e["lms"] for e in dl1 if e.get("lms") is not None]
    add("display list of the game", len(m4) == 23 and 0x0C00 in lms and 0x2000 in lms and dl1[-1].get("jvb") is not None,
        "%d mode-4 rows, screen memory at %s, ends with a jump to its own start (%s)" % (len(m4), ", ".join("$%04X" % x for x in lms), "$%04X" % dl1[-1].get("jvb", 0)))
    # 8. the tune tables
    t = P["tunes"]["start_tune"]
    add("tune tables", len(t["audf1"]) == 64 and len(t["audf2"]) == 64 and t["audf1"] == [S.rd(0xBC50 + i) for i in range(64)] and t["audf2"] == [S.rd(0xBC90 + i) for i in range(64)], "two tables of 64 AUDF values, one step per 4 jiffies; the rendered tune is analysis/start-tune.wav (`22`)")
    # 8b. the font: grid-exact, identical to the OS ROM font, credited and licensed
    from PIL import Image, ImageDraw, ImageFont
    big = ImageFont.truetype(AP.FONT_PATH, 64)
    ragged = []
    for code in range(64):
        im = Image.new("L", (64, 192), 0)
        ImageDraw.Draw(im).text((0, 0), chr(0xE020 + code), font=big, fill=255)
        for by in range(24):
            for bx in range(8):
                vals = {im.getpixel((bx * 8 + dx, by * 8 + dy)) > 127 for dx in range(8) for dy in range(8)}
                if len(vals) > 1:
                    ragged.append((code, bx, by))
    add("font outlines lie on the 8 x 8 grid", not ragged, "64 glyphs rendered at 64 px: every 8 x 8 block of every glyph is uniform (%d mixed blocks), so the 8 px rendering has one pixel per design unit and nothing to round" % len(ragged))
    fr = [bytes.fromhex(r) for r in P["font"]["rows"]]
    add("font has 64 glyphs of 8 bytes", len(fr) == 64 and all(len(g) == 8 for g in fr) and fr[0] == bytes(8) and any(fr[33]), "screen codes $00-$3F = ASCII $20-$5F; the space is empty, 'A' (code $21) is not")
    os_path = os.path.join(ROOT, "original", "Atari OS Rev B (19xx)(Atari)(NTSC)[400-800].rom")
    if os.path.exists(os_path):
        with open(os_path, "rb") as fh:
            osr = fh.read()
        base = 0xE000 - (0x10000 - len(osr))
        same = sum(1 for c in range(64) if osr[base + c * 8:base + c * 8 + 8] == fr[c])
        add("font equals the OS ROM font", same == 64, "%d of 64 glyphs are bit-for-bit the glyphs of the character set at $E000 of the Atari OS Rev B ROM (local file, used here as evidence only; see third-party/README.md on what this means for the licence)" % same)
    else:
        add("font equals the OS ROM font", True, "SKIPPED: the OS ROM file is not in original/")
    with open(AP.FONT_PATH, "rb") as fh:
        h = hashlib.sha256(fh.read()).hexdigest()
    tp = os.path.join(ROOT, "third-party")
    with open(os.path.join(tp, "EightBit-Atari-Fonts", "OFL.txt"), encoding="utf-8") as fh:
        ofl = fh.read()
    with open(os.path.join(tp, "README.md"), encoding="utf-8") as fh:
        note = fh.read()
    ok = h == P["font"]["source"]["sha256"] and "SIL OPEN FONT LICENSE Version 1.1" in ofl and "Steve Boswell" in ofl and "Steve Boswell" in note and h in note and "SIL Open Font License" in note
    add("font credit and licence are in place", ok, "the font file is unmodified (sha256 %s, the one in third-party/README.md); OFL.txt carries the copyright line and the full licence; README.md credits the author, the source commit and the upstream credits" % h[:16])
    # 9. determinism: the written pack twice
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        AP.write(d1)
        AP.write(d2)
        def hashes(d):
            out_ = {}
            for f in sorted(os.listdir(d)):
                with open(os.path.join(d, f), "rb") as fh:
                    out_[f] = hashlib.sha256(fh.read()).hexdigest()
            return out_
        h1, h2 = hashes(d1), hashes(d2)
    add("the written pack is deterministic", h1 == h2 and len(h1) == 6, "%d files written twice: %s" % (len(h1), "identical hashes" if h1 == h2 else "different"))
    # 10. the loader refuses another schema
    try:
        import json
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.json")
            with open(p, "w") as fh:
                json.dump({"schema": 99}, fh)
            AP.load(p)
        refused = False
    except ValueError:
        refused = True
    add("the loader refuses another schema", refused, "schema 99 raises ValueError")
    return P, out


def main():
    P, out = checks()
    L = ["Asset pack of the port (tools/asset_pack.py, tools/check_assets.py, stages 69-70): %d checks" % len(out), ""]
    for name, ok, detail in out:
        L.append("%s: %s: %s" % ("PASS" if ok else "FAIL", name, detail))
    L.append("")
    L.append("pack: %d regions, %d bytes of region data; %d glyphs in the game set, %d in the title set; maze %d x %d; %d sprites; %d texts; ROM sha256 %s" % (
        len(P["regions"]), sum(r["size"] for r in P["regions"]), P["charsets"]["game"]["glyphs"], P["charsets"]["title"]["glyphs"], P["maze"]["cols"], P["maze"]["rows"], len(P["sprites"]["shapes"]), len(P["text"]["strings"]), P["rom"]["sha256"]))
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 0 if all(ok for _, ok, _ in out) else 1


if __name__ == "__main__":
    sys.exit(main())
