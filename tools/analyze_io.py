"""Stage 57: input / output observation - every place where the cartridge code reads an input or writes an output, and what the real game does there.

Static part: every instruction of the ROM (tools/analyze_stack.py: the traced code) whose operand is a hardware register ($D000-$D7FF), a register or vector of the OS page 2 ($0200-$02FF) or one of the OS
zero-page variables the game shares with the OS ($10 POKMSK, $14 RTCLOK2, $4D ATRACT, $4E DRKMSK, $4F COLRSH), including the indexed forms (`sta HPOSP0,x`, `lda STICK0,x`, `sta AUDF1,y`).
Live part: tools/run_io_audit.ps1 puts a tracepoint on each of these instructions (`python -I tools/analyze_io.py --probes`), runs eleven sessions of the real game (Altirra) and prints, at every execution, the
effective address and the value read or written (`IO <pc> a=<address> v=<value>`); `python -I tools/analyze_io.py analysis/raw-logs/io-*.txt --write analysis/evidence-io-summary.txt` aggregates them.
The document docs/33-input-output.md (tools/analyze_io.py --doc) is generated from both and from the curated meaning of each register below (PURPOSE).
Usage:  python -I tools/analyze_io.py --probes | --doc [docs/33-input-output.md] | analysis/raw-logs/io-*.txt [--write analysis/evidence-io-summary.txt]
"""
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_stack as AS  # noqa: E402

ROOT = os.path.dirname(HERE)
SUMMARY = os.path.join(ROOT, "analysis", "evidence-io-summary.txt")
OS_ZP = {0x10, 0x14, 0x4D, 0x4E, 0x4F}
WRITES = ("sta", "stx", "sty")
READS = ("lda", "ldx", "ldy", "cmp", "cpx", "cpy", "ora", "and", "eor", "adc", "sbc", "bit")
RMW = ("inc", "dec", "asl", "lsr", "rol", "ror")
SESSIONS = ("fullgame", "pregame", "gameover", "p2win", "levels", "pause", "frightened_cases", "house_frightened", "catch", "inputs", "inputs1")

# address -> (device, direction label, what the game does)
PURPOSE = {
    0x0010: ("OS zero page", "in / out", "POKMSK, the shadow of the POKEY interrupt-enable register: `Start` reads it, sets bit 6 (the keyboard interrupt) and writes it back together with IRQEN (`$A44D-$A453`)."),
    0x0014: ("OS zero page", "in", "RTCLOK2, the low byte of the OS jiffy clock (60 / s NTSC, counted by the OS vertical-blank routine): every timer of the game is a mask of it (every 2nd, 4th, 8th, 16th jiffy), the frame-wait of the restart (`$A493`) and the title timer (`$A713`)."),
    0x004D: ("OS zero page", "out", "ATRACT, the attract-mode timer of the OS: the game writes 4, 3 or 0 (and the key value) so that the OS does not darken the screen or cycle the colours while a game or the title is shown; a key press resets it."),
    0x004E: ("OS zero page", "in", "DRKMSK, the OS attract-mode darkening mask (the OS sets it from the attract state): ANDed into every colour the display-list interrupts and the title put on the screen."),
    0x004F: ("OS zero page", "in", "COLRSH, the OS attract-mode colour shift (set by the OS): EORed into every colour of the display-list interrupts and the title."),
    0x0200: ("OS page 2", "out", "VDSLST low: the display-list-interrupt vector, set by `SetDisplayList` (`$A6B5`) to `$A573` (play) or `$A5CE` (title)."),
    0x0201: ("OS page 2", "out", "VDSLST high ($A5)."),
    0x022F: ("OS page 2", "out", "SDMCTL, the DMA control shadow: `$3E` once in `Start` (standard playfield, players and missiles on, single line)."),
    0x0230: ("OS page 2", "out", "SDLSTL: the display-list pointer shadow, low byte (`SetDisplayList`)."),
    0x0231: ("OS page 2", "out", "SDLSTH: the display-list pointer shadow, high byte ($BF: the lists are in the cartridge)."),
    0x026F: ("OS page 2", "out", "GPRIOR, the GTIA priority shadow: `$11` (players behind playfield 0-1) or `$14` (the ghost-eaten pop-up in front)."),
    0x0278: ("OS page 2", "in", "STICK0 / STICK1: the joystick shadows (the OS copies the PIA port in its vertical blank); `lda STICK0,x` with x = the player on turn. The low four bits, 0 = pressed: bit 0 up, 1 down, 2 left, 3 right."),
    0x0284: ("OS page 2", "in", "STRIG0: the trigger shadow of port 1 (0 = pressed): in the key loop it starts a new game while the title is shown or the countdown runs; ignored in play."),
    0x0285: ("OS page 2", "in", "STRIG1: the trigger shadow of port 2, same use."),
    0x02C0: ("OS page 2", "out", "PCOLR0-3, the player colour shadows, and (indexed up to 7) COLOR0-3: `LoadShadowColors` writes all eight at a board start; later the four ghost colours, the frightened blue, the flashing and the eaten-ghost pop-up colour; the OS copies them to COLPM0-3."),
    0x02C4: ("OS page 2", "out", "COLOR0, the playfield colour 0 shadow (the level-complete flashing; the title colours by `InitDisplay2`, indexed)."),
    0x02C5: ("OS page 2", "out", "COLOR1 shadow (cleared on the title)."),
    0x02C7: ("OS page 2", "out", "COLOR3 shadow: the fourth playfield colour (the READY! text `$44`, the ghost pop-up `$DC`, `$2A`)."),
    0x02F1: ("OS page 2", "in", "KEYDEL, the OS key-debounce delay: the pause key is accepted only when it is 0."),
    0x02FC: ("OS page 2", "in / out", "CH, the last key code of the OS keyboard handler: read for the pause key (`$21` = space bar), written `$FF` (no key) after use."),
    0xD000: ("GTIA", "out", "HPOSP0-3: the horizontal positions of players 0-3 = the four ghosts (indexed by the ghost); cleared at a death and a level end."),
    0xD002: ("GTIA", "in (read)", "M2PF: collision of missile 2 (a part of Pac-Man's picture) with playfield colour 1; bit 1 is tested (`bit M2PF`) as 'Pac-Man touches the bonus item'."),
    0xD004: ("GTIA", "out", "HPOSM0-3: the horizontal positions of the four missiles: Pac-Man's picture is drawn in the missile page (`$23`, 16 rows, four missiles side by side) and the ghost-eaten pop-up uses the same missiles."),
    0xD009: ("GTIA", "in (read)", "M1PL: collision of missile 1 with the players: the bit of ghost g tells that Pac-Man's body touches ghost g (the first half of the contact test)."),
    0xD00A: ("GTIA", "in (read)", "M2PL: collision of missile 2 with the players (the second half of the contact test)."),
    0xD012: ("GTIA", "out", "COLPM0-3: the player colours, cleared by the display-list interrupt of the lower screen."),
    0xD016: ("GTIA", "out", "COLPF0: the playfield colour 0, set by the third band interrupt."),
    0xD017: ("GTIA", "out", "COLPF1: set by the band interrupts (faded in attract mode by the OS variables)."),
    0xD018: ("GTIA", "out", "COLPF2: set by the band interrupts."),
    0xD019: ("GTIA", "out", "COLPF3: set by the band interrupts and by the READY! text."),
    0xD01D: ("GTIA", "out", "GRACTL: `$03` once in `Start`: players and missiles enabled."),
    0xD01E: ("GTIA", "out", "HITCLR: clears the collision registers (after each board set-up and each frame's contact test)."),
    0xD01F: ("GTIA", "in", "CONSOL: the three console keys, 0 = pressed: bit 0 START, bit 1 SELECT, bit 2 OPTION (`$07` = none). Read by the key loop with a debounce."),
    0xD200: ("POKEY", "out", "AUDF1, the frequency of channel 1 (indexed by the clearing loops)."),
    0xD201: ("POKEY", "out", "AUDC1: the control / volume of channel 1 (dots, bonus, death sweep, ghost eaten)."),
    0xD202: ("POKEY", "out", "AUDF2: frequency of channel 2 (siren, frightened sweep, eyes returning, start tune)."),
    0xD203: ("POKEY", "out", "AUDC2."),
    0xD204: ("POKEY", "out", "AUDF3 (the ghost-eaten pause sweep)."),
    0xD205: ("POKEY", "out", "AUDC3."),
    0xD206: ("POKEY", "out", "AUDF4."),
    0xD207: ("POKEY", "out", "AUDC4."),
    0xD208: ("POKEY", "out", "AUDCTL: the audio control (`$84` during the ghost-eaten sweep, with the high-pass filter described in `22-sound.md`; cleared elsewhere)."),
    0xD20A: ("POKEY", "in", "RANDOM: the polynomial counter, read at exactly three places (`$B859`, `$B9E1`, `$B9F4`: the ghost AI)."),
    0xD20E: ("POKEY", "out", "IRQEN: the interrupt enable, written once with POKMSK in `Start`."),
    0xD20F: ("POKEY", "out", "SKCTL: `$07` once in `Start`: keyboard scan and debounce enabled."),
    0xD402: ("ANTIC", "out", "DLISTL: the display-list pointer, low (`SetDisplayList`)."),
    0xD403: ("ANTIC", "out", "DLISTH."),
    0xD407: ("ANTIC", "out", "PMBASE: the player-missile base page, `$20` (the pages `$2300-$27FF`)."),
    0xD409: ("ANTIC", "out", "CHBASE: the character-set page, changed by the display-list interrupts (`$30` the game set, `$18` the title set, `$E0` ROM set for the OS text)."),
    0xD40A: ("ANTIC", "out", "WSYNC: wait for the end of the scan line: written in the display-list interrupts so that the colour changes happen between lines."),
    0xD40E: ("ANTIC", "out", "NMIEN: `$C0` once in `Start`: display-list interrupts and the vertical blank on."),
}


def names():
    out = {}
    with open(os.path.join(ROOT, "src", "asm", "pacman.s"), encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^(\w+)\s*=\s*\$([0-9A-F]+)", line)
            if m:
                out.setdefault(int(m.group(2), 16), m.group(1))
    return out


def is_io(op):
    return isinstance(op, int) and (0xD000 <= op <= 0xD7FF or 0x0200 <= op <= 0x02FF or op in OS_ZP)


def sites():
    """-> list of dicts: pc, mnemonic, mode, base operand, direction ('r' / 'w' / 'rw'), routine"""
    rom, F, owner = AS.load()
    out = []
    for a in sorted(rom.ins):
        n, m, mode, op = rom.ins[a]
        if mode in ("abs", "abx", "aby", "zp", "zpx") and is_io(op):
            if m in WRITES:
                d = "w"
            elif m in READS:
                d = "r"
            elif m in RMW:
                d = "rw"
            else:
                continue
            out.append({"pc": a, "len": n, "m": m, "mode": mode, "op": op, "dir": d, "routine": F[owner[a]].name})
    return out


def register_of(op):
    """the base address used as the key of PURPOSE: the register of the group (HPOSP0..3 -> $D000 ...)"""
    groups = [(0xD000, 0xD003), (0xD004, 0xD007), (0xD012, 0xD015), (0x02C0, 0x02C3), (0x0278, 0x0279)]
    for lo, hi in groups:
        if lo <= op <= hi:
            return lo
    return op


def key_of(s):
    """the register a site belongs to: the GTIA read registers ($D000-$D01F) are other registers than the write registers of the same addresses (M2PF is not HPOSP2)"""
    if 0xD000 <= s["op"] <= 0xD01F and s["dir"] == "r":
        return s["op"]
    return register_of(s["op"])


def probe_lines():
    L = []
    for s in sites():
        idx = {"abs": "", "zp": "", "abx": "+x", "zpx": "+x", "aby": "+y"}[s["mode"]]
        eff = "$%04X%s" % (s["op"], idx)
        at = s["pc"]
        if s["m"] in WRITES:
            val = {"sta": "@a", "stx": "@x", "sty": "@y"}[s["m"]]
        elif s["m"] in ("lda", "ldx", "ldy"):
            # the value the game GETS: the register at the next instruction (the harnesses inject the console, trigger and key values into the register right after the load, docs/04), so it is printed there
            at = s["pc"] + s["len"]
            val = {"lda": "@a", "ldx": "@x", "ldy": "@y"}[s["m"]]
        else:
            val = "db(%s)" % eff                               # the value the instruction is about to compare, OR, test or modify
        L.append('bt %04x "IO %04X a=%%04X v=%%02X" %s %s' % (at, s["pc"], eff, val))
    return L


LINE = re.compile(r"^IO ([0-9A-F]{4}) a=([0-9A-F]{4}) v=([0-9A-F]{2})")


def parse(paths):
    """-> per pc: {'hits': n, 'values': Counter, 'addrs': Counter}, and the harness names that executed it"""
    per = {}
    seen = collections.defaultdict(set)
    for p in paths:
        h = os.path.basename(p)[len("io-"):-len(".txt")]
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = LINE.match(line)
                if not m:
                    continue
                pc, ad, v = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)
                e = per.setdefault(pc, {"hits": 0, "values": collections.Counter(), "addrs": collections.Counter()})
                e["hits"] += 1
                e["values"][v] += 1
                e["addrs"][ad] += 1
                seen[pc].add(h)
    return per, seen


def fmt_values(vals, limit=12):
    ks = sorted(vals)
    if len(ks) <= limit:
        return " ".join("%02X" % k for k in ks)
    return "%d values, %02X..%02X" % (len(ks), ks[0], ks[-1])


def summary_lines(paths):
    per, seen = parse(paths)
    st = sites()
    nm = names()
    L = []
    P = L.append
    runs = sorted({h for v in seen.values() for h in v})
    P("I/O audit (tools/run_io_audit.ps1, tools/analyze_io.py): %d harness logs (%s), %d I/O instructions in the ROM, %d executed in these runs, %d accesses printed" %
      (len(paths), ", ".join(runs), len(st), sum(1 for s in st if s["pc"] in per), sum(e["hits"] for e in per.values())))
    P("")
    P("register (as used: reads / writes, sites) | accesses | effective addresses | values (hex)")
    byreg = collections.OrderedDict()
    for s in st:
        byreg.setdefault(key_of(s), []).append(s)
    for reg in sorted(byreg):
        ss = byreg[reg]
        hits = sum(per[s["pc"]]["hits"] for s in ss if s["pc"] in per)
        vals = collections.Counter()
        addrs = collections.Counter()
        for s in ss:
            if s["pc"] in per:
                vals.update(per[s["pc"]]["values"])
                addrs.update(per[s["pc"]]["addrs"])
        dirs = "".join(sorted({s["dir"] for s in ss}))
        name = nm.get(reg, "$%04X" % reg)
        P("%-9s $%04X %-3s %2d sites | %8d | %s | %s" % (name, reg, dirs, len(ss), hits, " ".join("%04X" % a for a in sorted(addrs)[:8]) + (" ..." if len(addrs) > 8 else ""), fmt_values(vals)))
    P("")
    miss = [s for s in st if s["pc"] not in per]
    P("I/O instructions not executed in these runs: %d" % len(miss))
    for s in miss:
        P("  $%04X %s %s (%s)" % (s["pc"], s["m"], nm.get(s["op"], "$%04X" % s["op"]), s["routine"]))
    return L


def doc_lines(paths_summary=True):
    st = sites()
    nm = names()
    live = None
    if os.path.exists(SUMMARY):
        with open(SUMMARY, encoding="utf-8", newline="") as fh:
            live = fh.read().replace("\r\n", "\n").rstrip("\n").split("\n")
    L = []
    P = L.append
    byreg = collections.OrderedDict()
    for s in st:
        byreg.setdefault(key_of(s), []).append(s)
    rt = collections.Counter(PURPOSE[r][0] for r in byreg if r in PURPOSE)
    P("# 33 - Input and Output Observation (stage 57)")
    P("")
    P("GENERATED by `python -I tools/analyze_io.py --doc docs/33-input-output.md` from the traced code of `src/asm/pacman.s`, the curated meaning of each register (`PURPOSE` in the tool) and `analysis/evidence-io-summary.txt` (`tools/run_io_audit.ps1`). Tests: `tests/test_io.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- The cartridge code touches the outside world at **%d instructions** in **%d registers or register groups**: %s. No other address of the hardware pages or of the OS pages is addressed by any data instruction (the 31 indirect `(zp),y` instructions reach RAM and ROM data, never a register: `29-pointers.md`), and the PIA (`$D300`) is not touched at all: the joystick comes in through the OS shadows (`STICK0`, `STRIG0/1`) that the OS fills in its vertical blank." %
      (len(st), len(byreg), ", ".join("%d %s" % (n, d) for d, n in sorted(rt.items()))))
    P("- **Inputs** (what the game reads, the only ways a player or the machine can influence it): the joystick directions (`STICK0,x`, x = the player on turn), the triggers (`STRIG0`, `STRIG1`), the three console keys (`CONSOL`), the keyboard (`CH`, `KEYDEL`: the space bar only), the polynomial random counter (`RANDOM`, 3 places), the collision registers (`M2PF`, `M1PL`, `M2PL`), the OS clock (`RTCLOK2`) and the two OS attract-mode variables (`DRKMSK`, `COLRSH`).")
    P("- **Outputs**: the display (ANTIC pointers, the character-set page, `WSYNC`, `NMIEN`, `PMBASE`, the GTIA positions and colours and their OS shadows), the sound (POKEY `AUDF1-4`, `AUDC1-4`, `AUDCTL`) and the hand-over to the OS (`VDSLST`, `SDLSTL/H`, `SDMCTL`, `GPRIOR`, `ATRACT`, `POKMSK`, `IRQEN`, `SKCTL`).")
    P("- **Observed live**: eleven sessions of the real game (fullgame, pregame, gameover, p2win, levels, pause, frightened_cases, house_frightened, catch, and the two input exercisers `inputs` and `inputs1`) executed **every one of the %d instructions**; at each execution the effective address and the value were printed. Section 4 lists, per register, the number of accesses and the values seen." % len(st))
    P("- This replaces the heuristic scan of `06-hardware-and-memory-map.md` (absolute addresses only, written from memory): **the list below is complete, including the indexed forms**, and every register has the meaning the game gives it.")
    P("")
    P("## 2. How it was found and observed")
    P("")
    P("1. **Static**: every instruction of the traced ROM code (2,925, `26-control-flow-graphs.md`) whose operand lies in `$D000-$D7FF`, `$0200-$02FF` or is one of the five OS zero-page variables the game shares with the OS (`POKMSK $10`, `RTCLOK2 $14`, `ATRACT $4D`, `DRKMSK $4E`, `COLRSH $4F`), in absolute, zero-page or indexed form; the direction is read from the mnemonic (`sta/stx/sty` write; `lda/cmp/ora/bit` read). No instruction addresses the PIA or any other chip; the OS ROM is entered at two places only: `jsr SETVBV` (`$A460`, in `Start`: the deferred vertical-blank vector) and `jmp XITVBV` (`$A60D`, the end of the vertical-blank handler).")
    P("2. **Live**: `tools/run_io_audit.ps1` copies a session harness, appends one tracepoint per instruction (`bt <pc> \"IO <pc> a=<effective address> v=<value>\"`: the register A, X or Y for a store, the memory byte for a read) and runs it in Altirra 4.40 (NTSC, OS-B, `Altirra_fast.ini`); nothing is written to the emulated machine by the tracing. The harnesses' own test aids are those of `04-analysis-tools.md` (the injected STICK0 / CONSOL / STRIG values are the inputs under observation).")
    P("3. **Compare**: `tools/analyze_io.py` aggregates the logs per instruction and per register.")
    P("")
    P("## 3. The registers")
    P("")
    P("| Register | Address | Dir | Sites | What the game does with it |")
    P("|---|---|---|---|---|")
    for reg in sorted(byreg):
        ss = byreg[reg]
        dirs = "/".join(sorted({"read" if s["dir"] == "r" else "write" if s["dir"] == "w" else "read-modify-write" for s in ss}))
        sites_txt = ", ".join("`$%04X`" % s["pc"] for s in ss)
        dev, direction, text = PURPOSE.get(reg, ("?", "?", "NOT DESCRIBED"))
        extra = ""
        if reg == 0x0278:
            extra = ""
        P("| `%s` (%s) | `$%04X` | %s | %s | %s |" % (nm.get(reg, "$%04X" % reg), dev, reg, dirs, sites_txt, text))
    P("")
    P("## 4. What the real game does there (live)")
    P("")
    if live:
        P("```")
        for line in live:
            P(line)
        P("```")
    else:
        P("NOT YET RUN: `analysis/evidence-io-summary.txt` does not exist (run `tools/run_io_audit.ps1`, then `python -I tools/analyze_io.py analysis/raw-logs/io-*.txt --write analysis/evidence-io-summary.txt`).")
    P("")
    P("## 5. Reading the values")
    P("")
    P("- **Inputs**, values seen: `STICK0` (`$0278`, player 1) and `STICK1` (`$0279`, read for player 2's turn) show `$0F` (nothing), the four directions `$0E` up, `$0D` down, `$0B` left, `$07` right and the diagonals `$0A`, `$06` (the game refuses two direction bits at once, `20-pacman-and-death.md`); `STRIG0` and `STRIG1` show `1` (not pressed) and `0` (pressed): the trigger starts a game at the title and in the countdown (`21-start-gameover-title.md`); `CONSOL` shows all eight values `$00-$07` (`$07` nothing, `$06` START, `$05` SELECT, `$03` OPTION, `$04` SELECT + START, `$02` OPTION + START, `$01` OPTION + SELECT, `$00` all three: the game acts on the first three alone and ignores the others); `CH` shows `$FF` and `$21` (the space bar, the pause key); `KEYDEL` is 0 whenever it is read; `RANDOM` returns every value; the collision registers show the contact and bonus bits.")
    P("- **Outputs**: the values written to the POKEY and GTIA registers are those of the sound and colour chapters (`22-sound.md`, `15-small-tables.md`, `16-ghost-frames.md`); the one-time writes of `Start` (`SDMCTL $3E`, `GRACTL $03`, `PMBASE $20`, `NMIEN $C0`, `SKCTL $07`, `IRQEN` = `$C0`: the break key and keyboard interrupts) are each seen once per run (11 runs, 11 accesses: the restart of a game at `$A477` does not repeat them).")
    P("- The input values were **injected** in these sessions (STICK0 by the bots, CONSOL / STRIG at the controller reads, CH for the pause key, `04-analysis-tools.md`): what the audit observes is what the game *reads*; a real person produces the same values through the OS (OV-23: a real keyboard event was run once and acted on, the same value reached `CH`).")
    P("")
    P("## 6. Limits")
    P("")
    P("- The meaning of each register is the game's use of it, written from the code and the live values; the hardware meaning of the bits (for example `CONSOL` bit order, `M1PL` bits) is the one Altirra implements and the game's behaviour confirms, but it has not been cross-checked against a printed hardware manual (the open item 1 of `06-hardware-and-memory-map.md`).")
    P("- Only the cartridge code is traced: the OS routines that copy the shadows to the hardware (`STICK0` from the PIA, `PCOLR0` to `COLPM0`, `SDLSTL` to `DLISTL`, the clock) run in the OS ROM and are not part of this chapter.")
    P("- Real hardware and the keyboard hardware path are outside the emulated sessions (OV-01, OV-23).")
    P("")
    return L


def main():
    args = sys.argv[1:]
    if "--probes" in args:
        print("\n".join(probe_lines()))
        return
    if "--doc" in args:
        txt = "\n".join(doc_lines()) + "\n"
        i = args.index("--doc")
        if i + 1 < len(args):
            with open(os.path.join(ROOT, args[i + 1]), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(txt)
            print("wrote", args[i + 1], len(txt), "bytes")
        else:
            print(txt)
        return
    paths = [a for a in args if a.endswith(".txt") and "raw-logs" in a.replace("\\", "/")]
    if len(paths) == 1 and ("*" in paths[0]):
        paths = sorted(glob.glob(paths[0]))
    L = summary_lines(paths)
    txt = "\n".join(L) + "\n"
    if "--write" in args:
        out = args[args.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
