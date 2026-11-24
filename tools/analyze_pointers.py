"""Stage 46: the pointers of the Pac-Man ROM.

A pointer on the 6502 is a pair of zero-page bytes (low, high) used with `(zp),Y`, or a table of 16-bit addresses in ROM / RAM.  This tool derives from the code (the trace of src/asm/pacman.s and the routines
of tools/analyze_functions.py):
  - every indirect instruction (`(zp),Y` / `(zp,X)` / `JMP (abs)`): there is no `(zp,X)` and no indirect jump, only `lda (zp),y` and `sta (zp),y`;
  - for each of the six pointer variables, who reads through it, who writes it and from what (a constant, a table entry, a computed value);
  - the tables of 16-bit addresses (pointer tables) and the 16-bit addresses inside the display lists, with the target of every entry;
  - the pointers the code hands to the OS and the hardware (SDLSTL/H, DLISTL/H, VDSLST);
  - the zero-page bulk clears that also clear the pointer bytes.
The measured part (the values the pointers really take, in Altirra, over five session harnesses) is read from analysis/evidence-pointers-summary.txt (tools/run_pointer_audit.ps1, tools/analyze_pointer_log.py).
Usage: python -I tools/analyze_pointers.py [--write docs/29-pointers.md]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402
import analyze_stack as AS  # noqa: E402

ROOT = AF.ROOT
LB = AF.LB
EVIDENCE = os.path.join(ROOT, "analysis", "evidence-pointers-summary.txt")
BASE = AF.BASE

# (low byte, name, short role, what it points into)
PTRS = [
    (0x3C, "SrcPtr", "source of the data copiers and the picture drawers", "ROM data (streams, shapes, text, tables) and the RAM picture buffers $0400 / $0410"),
    (0x3E, "DstPtr", "destination of the same", "RAM: the expand targets, the screen / bonus rows, the player-missile pages $23xx / $24xx+"),
    (0x38, "PopupMissilePtr", "GhostEaten: where in the missile page the score picture goes", "the missile page $23xx"),
    (0x3A, "PopupPlayerPtr", "GhostEaten: where in the eaten ghost's player page the '00' goes", "the player page $24xx + ghost"),
    (0x47, "ClipPtr", "ClipEntityAtTunnel: the 16 picture rows to mask", "the player page of the entity (Pac-Man: the missile page $23xx), at row $74"),
    (0x80, "MazePtr", "Pac-Man's cell in the maze screen RAM", "$0C00-$0F97 (the maze, 23 rows of 40 bytes)"),
]
SCREEN = {0x2000: "screen RAM $2000", 0x1C00: "screen RAM $1C00", 0x0F70: "screen RAM $0F70", 0x0C00: "the maze (screen RAM $0C00)"}
NAME = {lo: n for lo, n, *_ in PTRS}
BYTES = {}
for _lo, _n, *_ in PTRS:
    BYTES[_lo], BYTES[_lo + 1] = (_lo, "L"), (_lo, "H")

# probes of the Altirra measurement: the instruction before each loop (once per call) and the single accesses
PROBES = [0xA3B8, 0xA668, 0xA8DE, 0xABBD, 0xACC6, 0xACF9, 0xAF29, 0xAF33, 0xAF41, 0xAF4C, 0xB301, 0xB330, 0xB358, 0xB363, 0xB384, 0xB4D0, 0xB840, 0xB96A, 0xB98F]

READ_M = {"lda", "ldx", "ldy", "cmp", "cpx", "cpy", "adc", "sbc", "and", "ora", "eor", "bit"}
WRITE_M = {"sta", "stx", "sty", "inc", "dec", "asl", "lsr", "rol", "ror"}

NOTE = {      # the pointer set-up groups, by the address of the first store: what the value is
    0xA3AA: "Start: DstPtr = $0800, SrcPtr = $A1E1 (MazeMapStream, type A, inline RLE)",
    0xA3F8: "Start: SrcPtr = $BE95 (the nibble tables), DstPtr = $0600 (the RAM tables)",
    0xA41D: "Start: SrcPtr = $A003 (CharsetStream), DstPtr = $3000, then ExpandData",
    0xA430: "Start: SrcPtr = $BE13 (TitleCharsetStream), DstPtr = $1808, then ExpandData",
    0xA69E: "AdvanceSrcPtr: SrcPtr += 1 (16-bit)",
    0xA6A7: "WriteDstByte: DstPtr += 1 after each byte stored",
    0xA8BF: "GhostEaten: low byte = PacY, moved 2 towards the ghost's Y (the pop-up sits next to Pac-Man); high bytes $23 and $24 + ghost",
    0xA8D6: "GhostEaten: SrcPtr = GhostScorePtrs[2 * GhostsEaten]",
    0xAB57: "ClipEntityAtTunnel: low byte = A (the row $74), high = $24 + entity (entity 4 = Pac-Man: $24 + $FF = $23, the missile page)",
    0xABBB: "ClipEntityAtTunnel: MazePtr low byte = $B7 or $8F (Pac-Man wraps through the tunnel: the end of the maze row)",
    0xACC0: "DrawLevelIndicator: DstPtr = $0F92 (the right end of the indicator row), moved -2 / +1 per icon",
    0xACF1: "DrawLevelIndicator: SrcPtr = $BD3E - n (a window of BonusItemCodes)",
    0xAEFD: "DeathAnimation: DstPtr = PacY | $2300 (the missile page, one row of the plotted star)",
    0xB204: "MovePacMan: MazePtr -= $28 (up one maze row), before the cell test",
    0xB22E: "MovePacMan: MazePtr += $28 (down one maze row)",
    0xB24F: "MovePacMan: MazePtr low = $8F at the right tunnel exit (PacX wraps to $2A)",
    0xB263: "MovePacMan: MazePtr += 1 every fourth step to the right",
    0xB281: "MovePacMan: MazePtr low = $B7 at the left tunnel exit (PacX wraps to $CA)",
    0xB29E: "MovePacMan: MazePtr -= 1 every fourth step to the left",
    0xB2ED: "DrawAllInPlace: SrcPtr = PacShapePtrs[direction] + A (the mouth frame offset)",
    0xB30D: "DrawAllInPlace: SrcPtr = $0400 (the picture buffer), DstPtr = PacY | $2300",
    0xB4C8: "JunctionLookup: SrcPtr = JunctionRowPtrs[2 * row] (a row of JunctionExits in RAM)",
    0xB835: "GhostStartRoute: SrcPtr = StartRoutePtrs[2 * ghost] (the ghost's start route in RAM)",
    0xB962: "StepAndDrawEntity: SrcPtr = $BAC0 + A (a ghost shape: the direction block and the foot frame)",
    0xB976: "StepAndDrawEntity: SrcPtr = $0410 (the picture buffer), DstPtr = EntityY | $2400 + ghost (the ghost's player page)",
}

TABLES = [      # (address, label, number of 16-bit entries, what it indexes)
    (0xBB65, "PacShapePtrs", 5, "the first frame of each Pac-Man direction (full, right, left, up, down); DrawAllInPlace adds the mouth-frame offset"),
    (0xBB97, "JunctionRowPtrs", 10, "the 10 rows of the junction-exit table in RAM ($060E + 10 * row); JunctionLookup, indexed by 2 * row"),
    (0xBCD0, "GhostScorePtrs", 4, "the four pop-up shapes (200, 400, 800, 1600); GhostEaten, indexed by 2 * GhostsEaten"),
    (0xBCE6, "StartRoutePtrs", 4, "the four ghost start routes in RAM ($0686, $0693, $069B, $06A3); GhostStartRoute, indexed by 2 * ghost"),
]
DLIST = [       # (address of the 16-bit operand, what it is)
    (0xBF84, "DisplayList2, LMS of the first mode-2 line"),
    (0xBF88, "DisplayList2, LMS of the first mode-6 line"),
    (0xBF9E, "DisplayList2, LMS of the last mode-4 line"),
    (0xBFA1, "DisplayList2, JVB: the display list loops to its own start"),
    (0xBFA6, "DisplayList1, LMS of the first mode-2 line (the same $2000 as DisplayList2)"),
    (0xBFAA, "DisplayList1, LMS of the maze: $0C00, the first maze row"),
    (0xBFC4, "DisplayList1, JVB: the display list loops to its own start"),
]
VECTORS = [(0xBFFA, "RUN vector (cartridge header): Start"), (0xBFFE, "INIT vector (cartridge header): Init")]
BULK = {0xA395: "Start: `sta BandCounter,x` with X = $27..0 clears $18-$3F (the whole 40 bytes, including SrcPtr, DstPtr and the pop-up pointers)",
        0xA39C: "Start: `sta MazePtr,x` with X = $7F..0 clears $80-$FF (including MazePtr)",
        0xADB4: "InitBoard: `sta MazePtr,x` with X = $7F..0 clears $80-$FF (MazePtr is reloaded by the next loop)",
        0xADE3: "InitBoard: `ZeroPageInit80` copied to $80-$93 (X = $13..0): MazePtr = $0E93 (the first cell)"}


def w16(rom, a):
    o = a - BASE
    return rom.data[o] | (rom.data[o + 1] << 8)


class Ctx:
    def __init__(self):
        self.rom, self.F, self.owner = AS.load()

    def name_of(self, addr):
        """label (and +offset) of a ROM or RAM address"""
        if addr in self.rom.names:
            return self.rom.names[addr]
        if addr in LB.ROM_NAMES:
            return LB.ROM_NAMES[addr]
        if addr in SCREEN:
            return SCREEN[addr]
        best = None
        for first, last, kind, name, comment in LB.DATA:
            if first <= addr <= last:
                best = (name, addr - first)
        if best:
            return best[0] if best[1] == 0 else "%s+%d" % best
        below = [a for a in LB.RAM_TABLES if a <= addr < 0x0700]
        if below:
            a = max(below)
            n = LB.RAM_TABLES[a]
            return n if addr == a else "%s+%d" % (n, addr - a)
        return "$%04X" % addr

    def region(self, addr):
        if addr >= 0xA000:
            return "ROM"
        if 0x0600 <= addr <= 0x06FF:
            return "RAM tables"
        if 0x0400 <= addr <= 0x041F:
            return "picture buffer"
        if 0x2300 <= addr < 0x2800:
            return "player-missile area"
        if 0x0800 <= addr <= 0x17FF or addr in (0x2000, 0x1C00):
            return "screen RAM"
        return "RAM"


def prev_instr(rom, a):
    cand = [p for p in (a - 1, a - 2, a - 3) if p in rom.ins and p + rom.ins[p][0] == a]
    return cand[0] if cand else None


def source(ctx, a):
    rom = ctx.rom
    p = prev_instr(rom, a)
    if p is None:
        return "?"
    n, m, mode, op = rom.ins[p]
    if m == "lda" and mode == "imm":
        return "constant $%02X" % op
    if m == "lda" and mode in ("abx", "aby"):
        return "table %s,%s" % (ctx.name_of(op), "x" if mode == "abx" else "y")
    if m == "lda" and mode in ("zp", "zpx"):
        return "variable %s%s" % (LB.zp_name(op), ",x" if mode == "zpx" else "")
    if m == "lda" and mode == "abs":
        return "memory $%04X" % op
    if m in ("adc", "sbc"):
        return "computed (%s)" % m
    return "A (%s before)" % m


def analyse():
    ctx = Ctx()
    rom, F, owner = ctx.rom, ctx.F, ctx.owner
    ind = []
    for a, (n, m, mode, op) in sorted(rom.ins.items()):
        if mode in ("izy", "izx") or (m == "jmp" and mode == "ind"):
            ind.append((a, m, mode, op, F[owner[a]].name))
    access = collections.defaultdict(lambda: {"R": [], "W": []})     # pointer low byte -> sites
    setters = collections.defaultdict(list)                          # pointer low byte -> (addr, mnemonic, 'L'/'H', routine, source)
    bulk = []
    for a, (n, m, mode, op) in sorted(rom.ins.items()):
        if mode == "izy" and op in NAME:
            access[op]["R" if m == "lda" else "W"].append((a, F[owner[a]].name))
        elif mode == "zp" and op in BYTES and m in WRITE_M:
            lo, part = BYTES[op]
            setters[lo].append((a, m, part, F[owner[a]].name, source(ctx, a) if m == "sta" else "%s (16-bit step)" % m))
        elif mode == "zp" and op in BYTES and m in ("adc", "sbc") and False:
            pass
        elif mode == "zpx" and m in WRITE_M and a in BULK:
            bulk.append((a, m, op, F[owner[a]].name))
    tabs = []
    for addr, label, n, what in TABLES:
        ent = [w16(rom, addr + 2 * i) for i in range(n)]
        tabs.append((addr, label, n, what, ent))
    dl = [(a, what, w16(rom, a)) for a, what in DLIST]
    vec = [(a, what, w16(rom, a)) for a, what in VECTORS]
    hw = [(a, m, op, F[owner[a]].name) for a, (n, m, mode, op) in sorted(rom.ins.items())
          if mode in ("abs", "abx") and op in (0x0200, 0x0201, 0x0230, 0x0231, 0xD402, 0xD403) and m in ("sta", "stx", "sty")]
    return ctx, ind, access, setters, bulk, tabs, dl, vec, hw


def evidence():
    if os.path.exists(EVIDENCE):
        with open(EVIDENCE, encoding="utf-8", newline="") as fh:
            return fh.read().replace("\r\n", "\n").rstrip("\n").split("\n")
    return None


def report():
    ctx, ind, access, setters, bulk, tabs, dl, vec, hw = analyse()
    L = []
    P = L.append
    nread = sum(len(v["R"]) for v in access.values())
    nwrite = sum(len(v["W"]) for v in access.values())
    P("# 29 - The Pointers (stage 46)")
    P("")
    P("GENERATED by `python -I tools/analyze_pointers.py --write docs/29-pointers.md` from the trace of `src/asm/pacman.s`, the routines of `23-function-table.md`, the variables of `25-variable-catalogue.md` and `analysis/evidence-pointers-summary.txt` (the emulator measurement). Tests: `tests/test_pointers.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- The code has **%d indirect instructions**, all of the form `lda (zp),y` (%d) or `sta (zp),y` (%d). There is **no `(zp,X)` addressing and no `JMP (abs)`**, so no pointer is ever executed: **every pointer is a data pointer** and the control flow is fixed (`28-stack.md`, `23-function-table.md`)." % (len(ind), nread, nwrite))
    P("- There are **6 pointer variables** (12 zero-page bytes, low byte first): `SrcPtr`, `DstPtr`, `MazePtr` and, for one routine each, `PopupMissilePtr`, `PopupPlayerPtr` and `ClipPtr`. Nothing else in the zero page is used as a pointer.")
    P("- A pointer is always loaded **in two stores, low byte then high byte** (or by a 16-bit increment / decrement), and the index Y is a loop counter or a constant: the instruction before each loop is the measurement probe of section 6.")
    P("- Besides the zero-page pointers there are **%d tables of 16-bit addresses** in ROM (%d entries; each target is named in section 4), the **16-bit operands of the two display lists** (section 5), the two cartridge vectors, and the three pointers the code gives to the OS and ANTIC (section 5)." % (len(tabs), sum(t[2] for t in tabs)))
    P("- Every pointer value is computed at run time from a **constant, a table entry or the position of an entity**; none is kept in game state across frames except `MazePtr` (the cell of Pac-Man). The port needs one pointer type for the whole address space (section 7).")
    P("")
    P("## 2. The six pointer variables")
    P("")
    P("| Address | Name | Role | Points into | Reads (`lda (zp),y`) | Writes (`sta (zp),y`) |")
    P("|---|---|---|---|---|---|")
    for lo, name, role, into in PTRS:
        rd = access[lo]["R"]
        wr = access[lo]["W"]
        P("| `$%02X-$%02X` | %s | %s | %s | %s | %s |" % (lo, lo + 1, name, role, into,
          ("%d: %s" % (len(rd), ", ".join(sorted({r for a, r in rd})))) if rd else "-",
          ("%d: %s" % (len(wr), ", ".join(sorted({r for a, r in wr})))) if wr else "-"))
    P("")
    P("Every indirect instruction:")
    P("")
    P("| Address | Instruction | Pointer | Routine |")
    P("|---|---|---|---|")
    for a, m, mode, op, rn in ind:
        P("| `$%04X` | %s (%s),y | %s | %s |" % (a, m, LB.zp_name(op), NAME[op], rn))
    P("")
    P("`$B991` and `$B993` are the loop of the shared tail of `StepAndDrawEntity` (`$B985`); the name `InitDisplay2` is the routine with the smallest body that contains them, because `InitDisplay2` ends with `jmp $B985` (`$A62F`). See section 3, last paragraph.")
    P("")
    P("## 3. Where each pointer is loaded and from what")
    P("")
    P("The stores to the pointer bytes, found in the code; the source is the instruction before the store (a constant, a table, or a computation). Each set-up is explained below the table.")
    P("")
    P("| Pointer | Address | Store | Part | Routine | Source |")
    P("|---|---|---|---|---|---|")
    for lo, name, *_ in PTRS:
        for a, m, part, rn, src in sorted(setters[lo]):
            P("| %s | `$%04X` | %s | %s | %s | %s |" % (name, a, m, part, rn, src))
    P("")
    P("What the set-ups are (by the address of the first store):")
    P("")
    P("| First store | Meaning |")
    P("|---|---|")
    for a in sorted(NOTE):
        P("| `$%04X` | %s |" % (a, NOTE[a]))
    P("")
    P("Bulk writes that also clear or load the pointer bytes:")
    P("")
    for a, m, op, rn in bulk:
        P("- `$%04X`: %s." % (a, BULK[a]))
    P("")
    P("**A stray copy into the ROM.** `InitDisplay2` (the title and attract screen set-up) does not end with `rts`: its last instruction is `jmp $B985`, the middle of `StepAndDrawEntity`. That tail sets `DstPtr` high = `$24 + X` and copies 16 bytes `(SrcPtr),y -> (DstPtr),y`. X is still `$81` (the argument of `SetDisplayList`), so `DstPtr` is `$A5xx`: **a 16-byte copy into the cartridge ROM**, which the hardware ignores. Nothing is changed and no value is used, so it is harmless; the port must not reproduce the write (it has no effect) and must not call a ghost-drawing routine from the title set-up. The measurement (section 6) shows it at every entry of `InitDisplay2`.")
    P("")
    P("## 4. Tables of 16-bit addresses")
    P("")
    for addr, label, n, what, ent in tabs:
        P("### %s at `$%04X` (%d entries)" % (label, addr, n))
        P("")
        P("%s." % (what[0].upper() + what[1:]))
        P("")
        P("| Index | Value | Target | Region |")
        P("|---|---|---|---|")
        for i, v in enumerate(ent):
            P("| %d | `$%04X` | %s | %s |" % (i, v, ctx.name_of(v), ctx.region(v)))
        P("")
    P("## 5. Addresses given to the display hardware and the OS")
    P("")
    P("The two display lists contain 16-bit addresses that ANTIC reads itself (load-memory-scan `LMS` and jump-and-wait `JVB`), and the cartridge header has two vectors:")
    P("")
    P("| Operand at | Value | Target | What it is |")
    P("|---|---|---|---|")
    for a, what, v in dl + vec:
        P("| `$%04X` | `$%04X` | %s | %s |" % (a, v, ctx.name_of(v), what))
    P("")
    P("`SetDisplayList` hands a display list to the OS and the hardware: the `SDLSTL/H` shadow ($0230/$0231), `DLISTL/H` ($D402/$D403) and the display-list interrupt vector `VDSLST` ($0200/$0201):")
    P("")
    P("| Address | Instruction | Register | Routine |")
    P("|---|---|---|---|")
    for a, m, op, rn in hw:
        P("| `$%04X` | %s | %s | %s |" % (a, m, {0x200: "VDSLST low", 0x201: "VDSLST high", 0x230: "SDLSTL", 0x231: "SDLSTH", 0xD402: "DLISTL", 0xD403: "DLISTH"}[op], rn))
    P("")
    P("It is called with the display list and the handler as arguments (`23-function-table.md`): the game screen sets `DisplayList1` and `DliHandler1`, the title and attract screens `DisplayList2` and `DliHandler2`.")
    P("")
    P("## 6. Measured values (Altirra)")
    P("")
    ev = evidence()
    if ev:
        P("`tools/run_pointer_audit.ps1` runs five of the session harnesses of the project in Altirra (OS-B, NTSC; full games from the title, ghosts eaten, deaths, the extra life, the two-player win) with a trace at %d probe addresses (`PROBES` in `tools/analyze_pointers.py`: the instruction before each loop that reads or writes through a pointer, and the single accesses), logging all six pointers, X, Y and Pac-Man's position; `tools/analyze_pointer_log.py` checks each value against the rules of sections 2-4:" % len(PROBES))
        P("")
        P("```")
        for line in ev:
            P(line)
        P("```")
    else:
        P("NOT YET MEASURED: `analysis/evidence-pointers-summary.txt` does not exist (run `tools/run_pointer_audit.ps1`, then `python -I tools/analyze_pointer_log.py analysis/raw-logs/pointers-*.txt`).")
    P("")
    P("## 7. What the port does with this")
    P("")
    P("- One flat 64 KB `uint8_t mem[65536]` with the pointers as **`uint16_t` offsets** into it is the exact image of the original: `SrcPtr`, `DstPtr`, `MazePtr`, `ClipPtr`, `PopupMissilePtr`, `PopupPlayerPtr` become `uint16_t` variables, `(zp),y` becomes `mem[ptr + y]`, and the 16-bit increments are ordinary 16-bit adds (the stores come in pairs). The values should not be C pointers while the equivalence tests (stages 86-87) compare the RAM state.")
    P("- A pointer to ROM data (`SrcPtr` from `PacShapePtrs`, `GhostScorePtrs`, the streams) can become a typed C pointer or an index into the data array of the port **only** if the asset format of stages 69-70 keeps the offsets; the pointer tables of section 4 are then arrays of indices.")
    P("- `JunctionRowPtrs` and `StartRoutePtrs` point into **RAM** tables ($0600-$06FF, filled from the nibble tables at start): in C they are two-dimensional arrays and the pointer tables disappear.")
    P("- `PopupMissilePtr`, `PopupPlayerPtr` and `ClipPtr` are **locals** of one routine (`27-local-variables.md`): an index into the missile / player page.")
    P("- `MazePtr` is **state** (kept between frames): in C it is the offset into the maze array, or the pair (column, row) of Pac-Man's cell, updated by +-1 per 4 pixels sideways and +-40 per row (section 3); the two tunnel assignments (`$8F`, `$B7`) are the wrap of the column.")
    P("- The display-list operands are the screen addresses ($2000, $1C00, $0F70, $0C00): the graphics layer of the port (stages 79-80) needs them as the screen base addresses; the OS vector writes become the registration of the two display lists and the two interrupt handlers.")
    P("")
    return L


def main():
    txt = "\n".join(report()) + "\n"
    if "--write" in sys.argv:
        path = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", path, len(txt), "bytes")
    else:
        print(txt)


if __name__ == "__main__":
    main()
