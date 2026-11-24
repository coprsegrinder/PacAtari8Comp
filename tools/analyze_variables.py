"""Stage 41: the global variables of the Pac-Man ROM - every zero-page variable and every RAM area the code touches, with its role, its size, and who reads and writes it.

The roles and names are written down in this tool (ZP, AREAS; each with its evidence: a chapter, or 'code' = read from src/asm/pacman.s while writing the catalogue); the accesses are derived from the code: every
instruction is attributed to the routine with the smallest body that contains it (so a routine reached by a tail jump owns its own accesses), using tools/analyze_functions.py.
A variable touched by one routine only is LOCAL (scratch of that routine, stage 42); touched by two or more it is GLOBAL.
Usage: python -I tools/analyze_variables.py [--write docs/25-variable-catalogue.md]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402
import analyze_relationships as AR  # noqa: E402
import labels as LB  # noqa: E402

ROOT = os.path.dirname(HERE)

# the table of the zero-page variables lives in tools/zp_catalogue.py (it is also the source of the names in tools/labels.py)
from zp_catalogue import ZP  # noqa: E402,F401

# RAM outside the zero page the code touches: (first, last, name, role, evidence)
AREAS = [
    (0x0200, 0x0201, "VDSLST", "the display-list-interrupt vector (set by SetDisplayList)", "OS, 15"),
    (0x022F, 0x0231, "SDMCTL, SDLSTL, SDLSTH", "the DMA control and the display-list shadow", "OS"),
    (0x026F, 0x026F, "GPRIOR", "the priority shadow: $11 normally, $14 during the pop-up", "OS, C-51"),
    (0x0278, 0x0285, "STICK0, STRIG0, STRIG1", "the joystick and trigger shadows the game reads (STICK0 at $0278, STRIG0 at $0284, STRIG1 at $0285)", "OS, 13, 20"),
    (0x02C0, 0x02C7, "PCOLR0-3, COLOR0-3", "the colour shadows: four player colours, four playfield colours (COLOR3 = Pac-Man's / the pop-up's missiles)", "OS, 15, 16"),
    (0x02F1, 0x02F1, "(OS variable)", "tested once in the key loop ($A4CC) before the key code; its role was not identified", "code"),
    (0x02FC, 0x02FC, "CH", "the keyboard code of the last key", "OS"),
    (0x0403, 0x041C, "PictureBuffer", "the shape rows of the entity being drawn ($0412-$041B) with its feet row ($041C); Pac-Man's shape rows start at $0403", "16, 20"),
    (0x0600, 0x07D7, "RamTables", "tables built at start-up from the nibble map: DeathPlotRows $0600, JunctionExits $060E, FrightenEndPhase $0672, StartRoutes $0686, PatrolRoutes $06AE, BonusScore $0794, MoveDelay $07AE, NoReverseMask $07C6, ReverseDir $07CF", "12"),
    (0x0800, 0x0BFF, "OriginalMaze", "the stored original maze (four pages), copied to the working maze at every board", "12, 19"),
    (0x0C00, 0x0FFF, "WorkingMaze", "the working maze and the screen RAM of the maze display (23 rows of 40): the dots, the walls; $0C7B / $0C9C / $0E83 / $0EA4 the power pellets, $0DED the READY! row, $0DF3 the bonus item, $0F74-$0F87 the lives and level row", "12, 14, 15, C-50"),
    (0x1000, 0x13FF, "SavedMaze1", "player 1's saved maze while player 2 plays", "19, C-47"),
    (0x1400, 0x17FF, "SavedMaze2", "player 2's saved maze while player 1 plays", "19, C-47"),
    (0x18A8, 0x18A8, "(charset byte)", "one byte of the title logo character set written at start-up", "code"),
    (0x1C00, 0x1DFF, "TitleScreen", "the title screen RAM (mode 6 / 7 rows)", "21, C-52"),
    (0x1FFF, 0x204C, "StatusRow", "the status line (mode 2): '1UP' at $2004, the scores at $2020 / $202A / $2047, '2UP' at $2021, the high score", "19, 21"),
    (0x2300, 0x27FF, "PlayerMissileMemory", "player-missile graphics: $2300 the missiles (Pac-Man, the pop-up digits), $2400-$2700 the players of ghost 0-3", "16, 20"),
]


def build():
    rom, F = AF.analyse()
    AF.solve(rom, F)
    # accesses per instruction, attributed to the routine with the smallest body
    acc = collections.defaultdict(lambda: {"r": collections.Counter(), "w": collections.Counter()})
    areas = collections.defaultdict(lambda: {"r": collections.Counter(), "w": collections.Counter()})
    owner_of = {}
    for a in rom.ins:
        owner_of[a] = min((e for e in F if a in F[e].body), key=lambda e: (len(F[e].body), e))
    for a, (n, m, mode, op) in rom.ins.items():
        r, w, mr, mw = AF.effects(m, mode, op)
        o = F[owner_of[a]].name
        for kind, addr, idx in mr:
            if kind in ("zp", "ptr"):
                acc[addr]["r"][o] += 1
                if kind == "ptr":
                    acc[addr + 1]["r"][o] += 1
            elif kind == "abs" and addr < 0x100:                # the zero page addressed with a 16-bit operand ($0030,x / $0094,y)
                acc[addr]["r"][o] += 1
            elif kind == "abs" and addr < 0xA000:
                areas[addr]["r"][o] += 1
        for kind, addr, idx in mw:
            if kind in ("zp", "ptr"):
                acc[addr]["w"][o] += 1
                if kind == "ptr":
                    acc[addr + 1]["r"][o] += 1                 # a pointer pair is read when it is used
            elif kind == "abs" and addr < 0x100:
                acc[addr]["w"][o] += 1
            elif kind == "abs" and addr < 0xA000:
                areas[addr]["w"][o] += 1
    return rom, F, acc, areas


def group_access(acc, first, n):
    r, w = collections.Counter(), collections.Counter()
    for a in range(first, first + n):
        r.update(acc[a]["r"]) if a in acc else None
        w.update(acc[a]["w"]) if a in acc else None
    return r, w


def report(rom, F, acc, areas):
    sub = {F[e].name: AR.ROLE[e][0] for e in F}
    L = []
    P = L.append
    P("# 25 - The Variable Catalogue (stage 41)")
    P("")
    P("GENERATED by `python -I tools/analyze_variables.py --write docs/25-variable-catalogue.md`; the names, sizes and roles are written in `tools/zp_catalogue.py` (the **evidence** column: a chapter number = verified live there, `code` = read from `src/asm/pacman.s` for this catalogue and not tested separately, `OS` = a standard Atari OS variable); who reads and writes each variable is derived from the code. Tests: `tests/test_variables.py`.")
    P("")
    P("**All the names of this table are applied** (checklist stage 3): `tools/labels.py` derives the symbols of the generated source `src/asm/pacman.s` from `tools/zp_catalogue.py`, a byte that is not the first of its variable is written `Name+k`, and the source rebuilds byte for byte (section 5). The names marked with a trailing `*` in the **Name** column were already given explicitly in `tools/labels.py` before that (the others were `zp_XX`). A variable touched by **one routine only** is LOCAL (a scratch of that routine; stage 42), by two or more GLOBAL.")
    P("")
    accessed = {a for a in acc}
    covered = set()
    rows = []
    for first, n, name, kind, role, ev in ZP:
        covered.update(range(first, first + n))
        r, w = group_access(acc, first, n)
        touch = set(r) | set(w)
        scope = "GLOBAL" if len(touch) >= 2 else "LOCAL" if touch else "-"
        rows.append((first, n, name, kind, role, ev, r, w, touch, scope))
    glob = sum(1 for x in rows if x[9] == "GLOBAL")
    loc = sum(1 for x in rows if x[9] == "LOCAL")
    P("## 1. Summary")
    P("")
    P("- **Zero page:** %d of the 256 bytes are used by the code, in **%d variables** (scalars, arrays, pointers): %d GLOBAL, %d LOCAL. %d of the used bytes had an explicit name in `tools/labels.py` before stage 3 (marked `*`); the other %d were `zp_XX` and now have the names of this table (section 5)." %
      (len(accessed), len(rows), glob, loc, sum(1 for a in accessed if a in LB.OS_ZP or a in LB.GAME_ZP), sum(1 for a in accessed if not (a in LB.OS_ZP or a in LB.GAME_ZP))))
    P("- **Arrays** (indexed by X): per ghost (4), per entity (ghosts and Pac-Man, 5) or per player (2). The per-entity arrays are 'structure of arrays': `EntityX,x`, `GhostState,x`, ... (stage 48).")
    P("- **Other RAM:** the OS shadows, the picture buffer, the tables built at start-up, the mazes, the screens and the player-missile memory (section 3).")
    P("- The routines are named as in `23-function-table.md`; the subsystem codes (BOOT, FRAME, ...) are those of `24-function-relationships.md`.")
    P("")
    P("## 2. The zero-page variables")
    P("")
    P("| Address | Name | Size | Kind | Role | Evidence | Scope | Written by | Read by |")
    P("|---|---|---|---|---|---|---|---|---|")

    def names(c, limit=6):
        ks = sorted(c)
        return ", ".join(ks[:limit]) + (" +%d" % (len(ks) - limit) if len(ks) > limit else "") if ks else "-"
    for first, n, name, kind, role, ev, r, w, touch, scope in rows:
        star = "*" if (first in LB.OS_ZP or first in LB.GAME_ZP) and LB.zp_name(first) == name else ""
        addr = "$%02X" % first if n == 1 else "$%02X-$%02X" % (first, first + n - 1)
        P("| `%s` | %s%s | %d | %s | %s | %s | %s | %s | %s |" % (addr, name, star, n, kind, role, ev, scope + ("" if scope != "LOCAL" else " (%s)" % sorted(touch)[0]), names(w), names(r)))
    P("")
    unused = [a for a in range(0x100) if a not in covered]
    runs, start = [], None
    for a in unused + [0x1000]:
        if start is None:
            start = prev = a
        elif a == prev + 1:
            prev = a
        else:
            runs.append((start, prev))
            start = prev = a
    P("Zero-page bytes no instruction of the ROM touches: %s (the OS and the hardware use most of them)." % ", ".join(("$%02X" % a) if a == b else ("$%02X-$%02X" % (a, b)) for a, b in runs if a < 0x100))
    P("")
    P("`FrameDispatch` is the one big routine that is the whole game frame (`24`): a variable that only it touches is private state of the dispatcher, not a scratch byte.")
    P("")
    P("## 3. RAM outside the zero page")
    P("")
    P("| Addresses | Name | Role | Evidence | Written by | Read by |")
    P("|---|---|---|---|---|---|")
    for first, last, name, role, ev in AREAS:
        r, w = collections.Counter(), collections.Counter()
        for a in range(first, last + 1):
            if a in areas:
                r.update(areas[a]["r"])
                w.update(areas[a]["w"])
        P("| `$%04X-$%04X` | %s | %s | %s | %s | %s |" % (first, last, name, role, ev, names(w, 5), names(r, 5)))
    P("")
    P("## 4. Which subsystems share which global variables")
    P("")
    P("The global variables touched by three or more subsystems - the state that ties the game together:")
    P("")
    P("| Variable | Subsystems |")
    P("|---|---|")
    for first, n, name, kind, role, ev, r, w, touch, scope in rows:
        subs = sorted({sub[t] for t in touch})
        if len(subs) >= 3:
            P("| %s | %s |" % (name, ", ".join(subs)))
    P("")
    P("## 5. The names in the source (checklist stage 3)")
    P("")
    old = sorted(a for a in accessed if not (a in LB.OS_ZP or a in LB.GAME_ZP))
    P("`src/asm/pacman.s` is generated by `tools/make_asm.py` from the ROM and `tools/labels.py`; `labels.zp_name` returns, for a zero-page operand, the OS name, a name given in `GAME_ZP`, or the name of this catalogue (`Name` for the first byte of a variable, `Name+k` for the k-th). **%d zero-page bytes that were `zp_XX` now have these names**; no `zp_XX` is left in the source, and `tools/build_rom.py` rebuilds the ROM **byte for byte** (`tests/test_zp_names.py`). The older chapters keep the `zp_XX` they were written with; this table is the key:" % len(old))
    P("")
    P("| Old name | Now | Variable | Size |")
    P("|---|---|---|---|")
    for first, n, name, kind, role, ev in ZP:
        for a in range(first, first + n):
            if a in old:
                P("| `zp_%02X` | `%s` | %s | %d |" % (a, LB.zp_name(a), name, n))
    P("")
    return L


def main():
    rom, F, acc, areas = build()
    txt = "\n".join(report(rom, F, acc, areas)) + "\n"
    if "--write" in sys.argv:
        path = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", path, len(txt), "bytes")
    else:
        print(txt)


if __name__ == "__main__":
    main()
