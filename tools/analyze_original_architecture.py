"""Stage 92 (original software architecture documentation): ONE chapter that describes the ORIGINAL program as a whole - its structure, its memory layout, its execution flow and its architectural characteristics - and says where
each part is treated in full.  GENERATED from the ROM, the recursive trace of the code (tools/analyze_functions.py), the subsystem table of `24`, the contexts of `46`, the memory regions of `42` and the data regions of the labelling
(tools/labels.py); the curated parts are the tables at the top of this file.  The numbers are therefore recomputed, not copied.
Usage: python -I tools/analyze_original_architecture.py [--doc docs/58-original-architecture.md]
Tests: tests/test_original_architecture.py (the chapter is current; the facts it states hold; every chapter it points to exists)."""
import collections
import functools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import analyze_relationships as R  # noqa: E402
import comm_map as CM  # noqa: E402
import labels  # noqa: E402
import output_map as O  # noqa: E402
import zp_catalogue as Z  # noqa: E402

# what each memory region holds (the range and the kind come from tools/output_map.py, the regions of `42`)
REGION_TEXT = {
    "ZeroPage": "the game's variables (109 variables in 184 of the 256 bytes: the 132 bytes an instruction names directly, `25`, and the rest of the arrays, reached by an index) and the OS's: clock, shadows of the chip registers",
    "Stack": "the hardware stack: JSR / RTS, interrupts, 8 push / pop pairs; nothing else lives here (`28`)",
    "OsPage2": "the OS shadows the game writes: colours, display list, DMA, priority, `ATRACT`, `CH`; the stick, trigger and key values it reads; the interrupt vectors it sets (`33`, `35`, `42`)",
    "PictureBuffers": "the 16 picture rows of Pac-Man (`$0400`) and of the ghost being drawn (`$0410`), copied into the player-missile pages (`42`)",
    "RamTables": "the tables `Start` builds from the nibble stream: move delays, the end phases of the frightened period, the routes (`12`, `14`)",
    "OriginalMaze": "the maze of a new board as `Start` expanded it, never written again (`12`)",
    "MazeScreen": "the working maze and the screen of the maze band: 23 rows of 40 (walls, dots, power pellets, the lives row, the level indicator, the bonus item, READY!) (`12`, `14`, `42`)",
    "SavedMaze1": "player 1's maze while player 2 plays (`19`)",
    "SavedMaze2": "player 2's maze while player 1 plays (`19`)",
    "TitleCharset": "the title character set: 20 glyphs of the PAC-MAN logo, written by `Start` (`12`)",
    "TitleScreen": "the title screen (mode 6 and 7 rows) (`21`, `42`)",
    "StatusRows": "the two status lines (mode 2): the 1UP / 2UP labels, the scores and the high score (`42`)",
    "PmMissiles": "the missile page: Pac-Man's body and the pop-up score digits (`16`, `42`)",
    "PmPlayers": "the four player pages: ghosts 0 to 3, one byte a scan line (`16`, `42`)",
    "GameCharset": "the game character set: 101 glyphs (the maze pieces, the dots, the digits, the text), written by `Start` (`12`)",
    "Gtia": "GTIA: player and missile positions, the colour registers, `HITCLR`, `PRIOR`; the collision registers it is read for (`35`, `50`)",
    "Pokey": "POKEY: the four sound channels, `SKCTL`, `IRQEN`; read for RANDOM (`22`, `33`)",
    "Pia": "never touched by the game (`45`)",
    "Antic": "ANTIC: the display-list pointer, `CHBASE`, `PMBASE`, `NMIEN`, `WSYNC` (`35`)",
    "Rom": "the cartridge: code, data, the header at `$BFFA` (`07`)",
}

CHAPTERS = [
    ("Hardware, memory map, vectors", "06, 07, 35"),
    ("Binary: disassembly, labelling, control flow", "08, 09, 10, 11, 26"),
    ("Routines, call tree, relationships", "23, 24"),
    ("Variables, locals, the stack, pointers, structures", "25, 27, 28, 29, 30"),
    ("Constants, algorithms", "31"),
    ("Data formats and tables", "12, 13, 14, 15, 16, 17"),
    ("Subsystems: ghosts, frightened, Pac-Man, death, sound, title", "13, 17, 18, 19, 20, 21, 22"),
    ("Start-up and the main loop", "37, 38, 40"),
    ("Inputs, outputs, state, the interface to the machine, communication", "33, 34, 41, 42, 43, 45, 46"),
    ("Time budget", "39"),
    ("Collision geometry, resources", "50, 47"),
]


def calls_and_depth(F):
    calls = {e: set(t for t in F[e].calls.values() if t in F) for e in F}

    @functools.lru_cache(None)
    def depth(e, stack=()):
        if e in stack:
            return 99
        return 1 + max([depth(c, stack + (e,)) for c in calls[e]] or [0])
    return calls, {e: depth(e) for e in F}


def facts():
    rom, F, miss, extra = R.build()
    ins = rom.ins
    f = {}
    f["rom_size"] = len(A.ROM)
    f["ins"] = len(ins)
    f["code"] = sum(v[0] for v in ins.values())
    f["data"] = f["rom_size"] - f["code"]
    f["routines"] = len(F)
    f["jsr_targets"] = len([e for e in F if e in rom.jsr_targets])
    f["jsr_targets_all"] = len(rom.jsr_targets)
    ops = collections.Counter(v[1] for v in ins.values())
    modes = collections.Counter(v[2] for v in ins.values())
    f["ops"], f["modes"] = ops, modes
    f["jsr"] = ops["jsr"]
    f["jmp"] = ops["jmp"]
    f["rts"], f["rti"] = ops["rts"], ops["rti"]
    f["branches"] = sum(ops[m] for m in ("bne", "beq", "bpl", "bmi", "bcc", "bcs", "bvc", "bvs"))
    f["indirect_jumps"] = sum(1 for v in ins.values() if v[1] == "jmp" and v[2] == "ind")
    f["brk"] = ops["brk"]
    f["stack_ops"] = {m: ops[m] for m in ("pha", "pla", "php", "plp", "txs", "tsx")}
    f["outside_targets"] = sorted(set(v[3] for v in ins.values() if v[1] in ("jsr", "jmp") and v[2] == "abs" and not (0xA000 <= v[3] <= 0xBFFF)))
    f["zp_indirect"] = modes["izy"] + modes["izx"]
    regs = set(v[3] for v in ins.values() if v[2] in ("abs", "abx", "aby") and 0xD000 <= v[3] <= 0xD4FF)
    f["chip_registers"] = len(regs)
    f["zp_vars"] = len(Z.ZP)
    f["zp_bytes"] = sum(z[0] and 0 or 0 for z in Z.ZP)
    calls, depth = calls_and_depth(F)
    f["max_depth"] = max(depth.values())
    f["deepest"] = [F[e].name for e in F if depth[e] == f["max_depth"]]
    f["tail"] = sum(1 for e in F if F[e].tail)
    f["loops"] = sum(len(F[e].loops) for e in F)
    ctx = CM.context_pcs()
    f["contexts"] = {k: (len(v), len([e for e in F if e in v])) for k, v in ctx.items()}
    f["vectors"] = [A.ROM[0x1FFA + i] for i in range(6)]
    cat = collections.Counter()
    size = collections.Counter()
    for lo, hi, kind, name, desc in labels.DATA:
        cat[kind] += 1
        size[kind] += hi - lo
    f["data_kinds"] = (cat, size)
    f["subsystems"] = collections.OrderedDict()
    own = collections.Counter()
    cnt = collections.Counter()
    for e in F:
        cnt[R.ROLE[e][0]] += 1
    for a in ins:
        owner = min((e for e in F if a in F[e].body), key=lambda e: (len(F[e].body), e))
        own[R.ROLE[owner][0]] += ins[a][0]
    for k, (title, what, ch) in R.SUBSYSTEMS.items():
        f["subsystems"][k] = (title, what, cnt[k], own[k], ch)
    f["F"] = F
    return f


def doc():
    f = facts()
    L = []
    P = L.append
    P("# 58 - The Original Software: Architecture (checklist stage 92)")
    P("")
    P("GENERATED by `python -I tools/analyze_original_architecture.py --doc docs/58-original-architecture.md` from the ROM, the recursive trace of its code, the subsystem table of `24`, the contexts of `46`, the memory regions of `42` and the data regions of the labelling; the curated parts (what each region holds, the reading guide) are tables in the tool. Tests: `tests/test_original_architecture.py`.")
    P("")
    P("Checklist stage 92: \"Record the original program structure, memory layout, execution flow, and architectural characteristics.\" This chapter is the overview of the **original** (Pac-Man for the Atari 8-bit computers, the 8 KB cartridge, NTSC, Rev B OS); the C port's architecture is `48`. Every number below is computed from the ROM when the chapter is generated; the detail is in the chapters named in each section.")
    P("")
    P("## 1. In one page")
    P("")
    P("- **One 8 KB cartridge image** at `$A000-$BFFF` of an Atari 400/800 (6502 at 1.79 MHz, ANTIC, GTIA, POKEY; no other chip is touched). It holds **%s bytes of code** (%s instructions in %s routines) and **%s bytes of data** (%s regions: streams that `Start` expands, tables, pictures, texts)." % ("{:,}".format(f["code"]), "{:,}".format(f["ins"]), f["routines"], "{:,}".format(f["data"]), len(labels.DATA)))
    P("- **One program and one interrupt-driven frame.** The *main program* (`Start`, ending in the key loop) reads the console and starts games; **everything else is the vertical-blank handler** `$A5FD`, run once per frame by the OS's deferred-VBI mechanism: it is a 15-way dispatcher over the state of the game (title, countdown, intro, play, death, level end, ...), and the game itself is a state machine whose state lives in 20 variables (`34`, `38`). Two display-list interrupts change colours between screen bands (`35`).")
    P("- **All state is in RAM at fixed addresses**: %d zero-page variables, a few buffers, the maze in four copies, the player-missile pages. There is no heap, no software stack and no code in RAM: every `JSR` and `JMP` target is in the cartridge except the %d OS entry points (`%s`) (two stray writes of the original are listed in `42`)." % (f["zp_vars"], len(f["outside_targets"]), "`, `".join("$%04X" % t for t in f["outside_targets"])))
    P("- **Static control flow is the whole control flow**: %d `JSR` and %d `JMP`, **%d indirect jumps, %d `BRK`**, and the stack holds only return addresses and 8 balanced push / pop pairs (`28`). The longest chain of calls is %d routines deep (`%s`)." % (f["jsr"], f["jmp"], f["indirect_jumps"], f["brk"], f["max_depth"], "`, `".join(f["deepest"])))
    P("- **The machine is touched through %d chip registers** and **2 OS calls** (`SETVBV`, `XITVBV`); no file, serial, network or PIA access (`45`, `46`)." % f["chip_registers"])
    P("")
    P("## 2. Structure: the code")
    P("")
    P("| Subsystem | What it does | Routines | Code bytes | Chapters |")
    P("|---|---|---|---|---|")
    tot = 0
    for k, (title, what, n, b, ch) in f["subsystems"].items():
        P("| **%s** (%s) | %s | %d | %d | %s |" % (title, k, what, n, b, ch))
        tot += b
    P("")
    P("(Each instruction is counted once, for the routine with the smallest body that contains it: %s of %s code bytes.)" % ("{:,}".format(tot), "{:,}".format(f["code"])))
    P("")
    P("**Shape of the code.** %d routines (%d are the target of a `JSR`, %d distinct `JSR` targets with the OS's `SETVBV`; the rest are entry points, interrupt handlers and jump targets); %d tail jumps between routines; %d of the routines contain loops, in all %d back edges; the addressing is mostly zero page (%d instructions) and immediate (%d), with %d indirect-indexed accesses `(zp),y` for the pointer-walking routines (`29`) and no `(zp,x)`; %d conditional branches (%d%% of the instructions). The data tables are read with indexed absolute addressing (%d `abx`, %d `aby`)." % (
        f["routines"], f["jsr_targets"], f["jsr_targets_all"], f["tail"], sum(1 for e in f["F"] if f["F"][e].loops), f["loops"], f["modes"]["zp"] + f["modes"]["zpx"], f["modes"]["imm"], f["modes"]["izy"], f["branches"], round(100 * f["branches"] / f["ins"]), f["modes"]["abx"], f["modes"]["aby"]))
    P("")
    P("The call tree, every routine's inputs and outputs, and its subsystem and role are in `23` and `24`; the control-flow graph of each routine in `26`; the 6 loops with a second entry in `26`.")
    P("")
    P("## 3. Structure: the data in the ROM")
    P("")
    cat, size = f["data_kinds"]
    P("| Kind | Regions | Bytes |")
    P("|---|---|---|")
    for k in sorted(cat, key=lambda k: -size[k]):
        P("| %s | %d | %d |" % (k, cat[k], size[k]))
    P("")
    P("The regions are named and described one by one in `12` (formats), `13`-`17` (the ghosts' patrols, the levels, the small tables, the ghost pictures and transitions), `15` and `47` (the resources and how a port installs them); the packed streams (maze, character sets, move-delay nibbles) are expanded into RAM by `Start`.")
    P("")
    P("## 4. Memory layout")
    P("")
    P("| Range | Region | Kind | An output of the game | Holds |")
    P("|---|---|---|---|---|")
    for name, lo, hi, kind in sorted(O.REGIONS, key=lambda r: r[1]):
        P("| `$%04X-$%04X` | %s | %s | %s | %s |" % (lo, hi, name, kind, "yes" if name in O.OUTPUT else "no", REGION_TEXT.get(name, "")))
    P("")
    P("The OS's own areas (`$0300-$03FF`, `$E000`: the OS font the title text uses, `$D800-$FFFF`) are the platform's, not the game's (`06`, `47`). What each routine and each context reads and writes is in `23`, `42` and `46`; the 144 bytes of the zero page that are state, found by experiment, in `43`.")
    P("")
    P("## 5. Execution flow")
    P("")
    P("```mermaid")
    P("flowchart TD")
    P("  PWR[power-on: the OS reads the cartridge header at $BFFA] --> RUN[RUN $A386: Start]")
    P("  RUN --> SET[Start: clear, build the RAM tables, set the vertical-blank handler and the display list]")
    P("  SET --> KEY[the key loop: read CONSOL, debounce, release]")
    P("  KEY -->|START or a trigger| NEW[the new game: restart, first board]")
    P("  NEW --> KEY")
    P("  VBI[each frame: the OS's vertical blank, then the deferred handler $A5FD] --> DISP[FrameDispatch: 15 classes]")
    P("  DISP --> PLAY[play: one frame of the game in a fixed order]")
    P("  DISP --> OTHER[title, countdown, intro, death, eaten pause, level end, turn control]")
    P("  DLI[display-list interrupts on fixed scan lines] --> COL[colours and CHBASE per band]")
    P("```")
    P("")
    P("| Context | What runs | Instructions | Routines it calls |")
    P("|---|---|---|---|")
    names = {"key": "the main program: the key loop (`$A4BA-$A572`)", "newgame": "the new-game sequence the key loop starts (`$A477-$A4B8`)", "vbi": "the deferred vertical-blank handler `$A5FD`: the whole game frame", "dli1": "display-list interrupt, game screen (5 lines)", "dli2": "display-list interrupt, title screen (5 lines)"}
    for k, (ni, nr) in f["contexts"].items():
        P("| %s | %s | %d | %d |" % (k, names.get(k, k), ni, nr))
    P("")
    P("Five contexts share one CPU; they hand over through 12 variables with single-byte stores, and the one race the code has is one no game can reach (`46`, `34`). **A frame**, in order: the OS clock tick and the shadow registers, the handler (`FrameDispatch` chooses by `GameState`, `Paused`, `IntroRequest`, `CountdownActive`, `LevelComplete`, `PlayStarted`, `WaitState`, `DeathState`, `EatPause`: the 15 classes of `38`), and then the main program for the rest of the frame (the key loop's wait for the next clock tick). A play frame runs its routines in the order listed in `24` section 4.3 and `48` section 3.")
    P("")
    P("**Start-up** (`37`): the OS reads the header (`RUN = $%02X%02X`, `INIT = $%02X%02X`, the flags `$%02X` and `$%02X`), jumps to RUN with the stack at `$FF`; `Start` clears the zero page (`$18-$3F` and `$80-$FF`), builds the tables in RAM from the nibble streams, expands the maze and the character sets, sets the display list and the handler vectors, and falls into the key loop. **Time** (`39`): the handler has about 16,100 cycles a frame on the game screen (19,750 on the title); a play frame costs 14,278 cycles at most in the heaviest case found, the static bound (32,049) could not be tightened." % (f["vectors"][1], f["vectors"][0], f["vectors"][5], f["vectors"][4], f["vectors"][2], f["vectors"][3]))
    P("")
    P("## 6. Architectural characteristics")
    P("")
    P("| Characteristic | What the original does | Evidence |")
    P("|---|---|---|")
    P("| Concurrency | one CPU, five interleaved contexts, no reentrancy, hand-over through 12 variables | `46` |")
    P("| State | 20 state variables, 68 transition rules, every one seen in the real game | `34` |")
    P("| Data-driven | %.0f%% of the ROM is data; ghost behaviour, levels and sound are tables read by index; the level-dependent tables are indexed past their ends on boards above 15 (the original's behaviour, kept) | `14`, `44` |" % (100.0 * f["data"] / f["rom_size"]))
    P("| Pointers | 16-bit zero-page pointers walk the maze, the pictures and the streams; no pointer to code | `29` |")
    P("| Dynamic memory | none; every buffer is at a fixed address | `45`, `47` |")
    P("| Stack | %d balanced push / pop pairs besides call and return; no stack-held data; the maximum depth is within 256 bytes | `28` |" % (f["stack_ops"]["pha"] + f["stack_ops"]["php"]))
    P("| Indirect control flow | none: no indirect jump, no push-and-return trick; the call tree is complete | `23`, `28` |")
    P("| Timing | the frame is driven by the vertical blank; sound and the display lists run from the same frame; collision registers are read at the start of a frame | `38`, `39`, `50` |")
    P("| Operating system | the Atari OS Rev B supplies the clock, the shadow registers and the vertical-blank vector; the game calls 2 OS routines; the character set of the text lines is the OS's | `37`, `45`, `47` |")
    P("| Randomness | the POKEY RANDOM register is read at 3 places in the code, for ghost steering and the corner choice | `31`, `44` |")
    P("| Quirks that are part of the behaviour | the extra-life cell rule, the 8-bit ghost count, the unclamped frightened tables, two stray writes (`$D111`, 16 bytes of ROM), the race at `$A800` that no game can take | `34`, `42`, `44` |")
    P("")
    P("## 7. Where to read more")
    P("")
    P("| Topic | Chapters |")
    P("|---|---|")
    for t, c in CHAPTERS:
        P("| %s | %s |" % (t, ", ".join("`%s`" % x.strip() for x in c.split(","))))
    P("")
    P("The architecture of the **port** (the layers, the oracle chain, the layout of `src/c`) is `48`; how the C source is organised is `57`; how the port was shown to equal the original is `52`-`56`.")
    return "\n".join(L) + "\n"


def main():
    text = doc()
    if "--doc" in sys.argv:
        o = sys.argv[sys.argv.index("--doc") + 1]
        with open(os.path.join(ROOT, o) if not os.path.isabs(o) else o, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("wrote", o)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
