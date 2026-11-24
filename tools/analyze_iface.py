"""Stage 67 (external interface): the chapter docs/45-external-interface.md, generated from the static classification of tools/iface_map.py (the instructions of the ROM that touch the outside), the evidence of its concrete
run (analysis/evidence-iface-summary.txt) and the curated text of this file.
Usage: python -I tools/analyze_iface.py [--doc docs/45-external-interface.md]   (the evidence is written by tools/iface_map.py --write analysis/evidence-iface-summary.txt)"""
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import analyze_io as IO  # noqa: E402
import iface_map as I  # noqa: E402
import output_map as O  # noqa: E402

EVIDENCE = os.path.join(ROOT, "analysis", "evidence-iface-summary.txt")

OS_TASKS = [
    ("the vertical blank (60 / s NTSC, 50 / s PAL)", "calls the deferred vector `VVBLKD` = `$A5FD`: the whole game frame; `RTCLOK2` (`$14`) counts the frames before it", "a timer that calls `play_frame` once per frame and counts a byte clock"),
    ("shadow to chip copy", "the OS copies the colour, display-list, DMA, priority and character-set shadows to the chips in its vertical blank; the game writes only the shadows (and some chip registers directly: `33`)", "the renderer reads `w.shadow` / the chip writes of the frame"),
    ("joystick and triggers", "the OS reads `PORTA`, `TRIG0`, `TRIG1` every frame into `STICK0-1`, `STRIG0-1`", "`Platform.stick(port)`, `Platform.trigger(port)`"),
    ("keyboard", "the keyboard interrupt of the OS stores the key code in `CH` and sets `KEYDEL`; the OS counts `KEYDEL` down", "`Platform.key()`, `Platform.key_delay()` (only the key loop reads them)"),
    ("console keys", "`CONSOL` is read by the game directly", "`Platform.console()`"),
    ("attract mode", "the OS counts `ATRACT` up; when it passes its limit the OS sets `DRKMSK` / `COLRSH`, which darken and cycle every colour the display-list handlers write; any key or stick input resets the count (the game also writes `ATRACT` itself)", "`Platform.attract()`; the game's writes to `ATRACT` (`$4D`) are outputs"),
    ("display-list interrupts", "the OS non-maskable interrupt routine jumps through `VDSLST` = `$A573` (game) or `$A5CE` (title) at each interrupt line of the display list", "five colour / character-set changes at fixed scan lines (`35`, section 4): the renderer's band table"),
    ("power-on", "the OS reads the cartridge header, calls INIT (a bare `RTS`), jumps to RUN with the interrupts as `37` shows; the OS's zeros at `$0400-$041F` and `$0B98-$0BFF` are used", "the port starts `Start`'s expansion from its own clean state (`37`, section 5)"),
]

ABSENT = [
    ("files and devices (CIO)", "no call of `CIOV` (`$E456` / `$E4C4`), no reference to page 3 (the IOCBs `$0340-$03BF`)", "static: absolute references to page 3 = 0"),
    ("the serial bus, disk and network (SIO)", "no call of `SIOV`, no reference to the device control block `$0300-$030B`, to `SEROUT` / `SERIN` (`$D20D`), no serial interrupt enabled", "static: absolute references to the serial data registers = 0; dynamic: 0 accesses"),
    ("the PIA", "the joystick is read through the OS shadow, never from `PORTA` / `PORTB`", "static: absolute references to `$D300-$D3FF` = 0; dynamic: 0 accesses"),
    ("OS ROM data and OS routines", "the only OS entries are `SETVBV` (`jsr $E45C`, `$A460`) and `XITVBV` (`jmp $E462`, `$A60D`)", "static: 2 control transfers outside the cartridge; no indirect jump, no BRK"),
    ("a printer, a cassette, a paddle, a light pen", "none: the paddle registers (`POT0-7`, the read side of `$D200-$D207`) and the pen registers (`PENH`, `PENV`, `$D40C-$D40D`) are read only by the OS (`35`, section 5)", "static: the game reads no address of those registers"),
]


def outputs_table():
    """-> rows (device, register address list, purpose, sites, routines) of the written registers"""
    sites = IO.sites()
    groups = defaultdict(list)
    for s in sites:
        if "w" in s["dir"]:
            groups[IO.key_of(s)].append(s)
    rows = []
    for key in sorted(groups):
        ss = groups[key]
        dev, dirn, text = IO.PURPOSE.get(key, ("?", "out", ""))
        label = text.split(". ")[0].split(": ")[0] if text else ""
        routines = sorted({s["routine"] for s in ss})
        rows.append((dev, key, label, len(ss), routines))
    return rows


def read_evidence():
    with open(EVIDENCE, encoding="utf-8") as fh:
        return fh.read()


def build():
    st = I.static_report()
    ev = read_evidence()
    return st, ev


def chapter():
    st, ev = build()
    lines = ev.splitlines()
    sens = [ln for ln in lines if ln.startswith("input ") or any(ln.startswith(n.ljust(10)) for n, lo, hi in I.DECLARED)]
    m_clos = re.search(r"closure: (\d+) random game states", ev)
    m_reads = re.search(r"reads: (\d+) distinct \(instruction, address\) pairs read (\d+) times", ev)
    m_acc = re.search(r"page 3, the PIA, the serial data registers, the OS ROM data and the other hardware: (\d+)", ev)
    P = []
    w = P.append
    reads = sorted(st["reads"], key=lambda s: (s["op"], s["pc"]))
    w("# 45 - External interface (stage 67)")
    w("")
    w("GENERATED by `python -I tools/iface_map.py --write analysis/evidence-iface-summary.txt` and `python -I tools/analyze_iface.py --doc docs/45-external-interface.md` from the static classification of the 2,925 instructions of the ROM (`tools/iface_map.py`), its run on the concrete 6502, `tools/platform_iface.py` and the curated text of `tools/analyze_iface.py`; tests: `tests/test_iface.py`. The chips and registers one by one are `33` (stage 57), `35` (stage 59: every chip write traced live), `41` (the inputs), `42` (the output regions); this chapter is the **boundary as a whole**: the closed list of what crosses it, a check that nothing else does, and the interface the port implements.")
    w("")
    w("## 1. The result")
    w("")
    w("- **The game takes 14 things from the outside** (section 2), read by **%d instructions** of the ROM: the joystick, the two triggers, the keyboard code and its delay, the console keys, three GTIA collision registers, `RANDOM`, the jiffy clock and three OS variables (`POKMSK`, the two attract-mode values); and one thing it reads back of its own: the player colour shadows (section 4). **Nothing else reaches it.**" % len(st["reads"]))
    w("- **The list is closed, and this was run, not only read** (section 3): %s random game states (the frame in every mode, the two display-list handlers, a pass of the key loop, the running-game frame body) were each run twice, the second time with **every external cell that is not a declared input** (page 2 and page 3, the hardware registers, the OS ROM: up to 11,000 cells) holding other random values: **0 differences** in the RAM, in the ordered writes to the outside, in the RANDOM reads and in the OS calls." % (m_clos.group(1) if m_clos else "?"))
    w("- **Every declared input is live** (section 3): changing one alone changed the result in some runs, for each of them (the table of section 3; `POKMSK` is read only by `Start`, which these entries do not run).")
    w("- **There is nothing else**: the game makes **%d** control transfers outside the cartridge (`SETVBV`, `XITVBV`), has no indirect jump, no BRK, and **no file, device, serial, network or PIA access** of any kind (section 5). \"No files, no network\" is a measured fact of the code, not an assumption." % len(st["control_out"]))
    w("- **One finding for the port's state** (section 4): the game keeps one piece of state in the OS page, **the ghost colour shadow `PCOLR0-3`**: `GhostEaten` writes `$DC` into the eaten ghost's shadow and the end of the pause finds the ghost by looking for it (`$B09D`). It is state of the eaten-ghost pause; the port's save state must carry it if it saves in the pause (`43`, section 8).")
    w("- **What the port implements** (section 7): `tools/platform_iface.py`, a `Platform` class with one method per declared input, a scripted implementation, and `run_frame(w, platform)`, which runs one frame of the port-form game (`44`) on a platform. The **collision registers** are an input the port must compute from the sprite pictures: that model is built and equals the GTIA's (OV-68, closed in `50`); the scene it needs is the sprite drawing's, in port form (OV-69, closed in `44`).")
    w("")
    w("## 2. What the game takes from the outside")
    w("")
    w("| Input | Address | Device | Read by | What it is |")
    w("|---|---|---|---|---|")
    for name, lo, hi, dev, who, what in I.INPUTS:
        a = "`$%04X`" % lo if lo == hi else "`$%04X-$%04X`" % (lo, hi)
        w("| `%s` | %s | %s | %s | %s |" % (name, a, dev, who, what))
    w("")
    w("The static read list, instruction by instruction (every instruction of the ROM that reads an address outside the game's own memory; `tools/analyze_io.py` finds the sites, `tools/iface_map.py` classifies them):")
    w("")
    w("| Address | Instruction | Routine |")
    w("|---|---|---|")
    for s in reads:
        mode = {"abs": "", "abx": ",x", "aby": ",y", "zp": "", "zpx": ",x"}[s["mode"]]
        w("| `$%04X%s` | `$%04X %s` | %s |" % (s["op"], mode, s["pc"], s["m"], s["routine"]))
    w("")
    w("Reading it: the `RTCLOK2` reads are every timer of the game (every 2nd, 4th, 8th, 16th jiffy are masks of it); `$02C0,x` is the read-back of section 4; the three `$D00x` reads are the collision registers (the same addresses are the `HPOSP` / `HPOSM` write registers, so a flat-memory port must keep the reads and the writes apart: the harness of `check_play` does); the key loop's reads are `38`, the stick path `41`.")
    w("")
    w("## 3. The list is closed")
    w("")
    w("`tools/iface_map.py` runs the real ROM on the concrete 6502 (`tools/cpu6502.py`) with a probe on every read and write outside the game's memory. Entries: the vertical-blank handler in the six frame kinds of `42` (title, game, play, level end, death, eaten pause), both display-list interrupt handlers, one pass of the key loop, and the running-game frame body from random lattice states (`tools/check_play.py`'s set-up).")
    w("")
    w("1. **Reads**: %s distinct (instruction, address) pairs, read %s times in all; **every one is made by an instruction of the static read list, from an address of its range, and the address is a declared input**: 0 exceptions." % ((m_reads.group(1), "{:,}".format(int(m_reads.group(2)))) if m_reads else ("?", "?")))
    w("2. **Closure**: the same random state is run twice; the second time every undeclared external cell holds another random value. The RAM (`$0000-$3FFF`, with the OS-page cells that are inputs masked), the ordered list of writes to the outside, the RANDOM values read and the OS calls are compared: **0 differences in %s runs**. A game that depended on an undeclared cell (an OS vector, a page-3 byte, a chip register read back) would differ here." % (m_clos.group(1) if m_clos else "?"))
    w("3. **Areas never used**: page 3, the PIA, the serial data registers, the OS ROM data and the other hardware were touched **%s** times." % (m_acc.group(1) if m_acc else "?"))
    w("4. **Sensitivity**: one declared input changed alone, the rest identical: the number of runs, of those of the column, in which the result changed:")
    w("")
    w("```")
    for ln in lines:
        if ln.startswith("input ") or any(ln.startswith(n.ljust(10)) for n, lo, hi in I.DECLARED):
            w(ln)
    w("```")
    w("")
    w("Every row has a non-zero entry. The inputs of the key loop show only in its column (`STRIG`, `KEYDEL`, `CH`, `CONSOL`), the stick, the collision registers and `RANDOM` only in the frame columns (the collision registers and `RANDOM` matter only in states of play: the columns `v:play` and `frame-play`), the attract-mode values in the first display-list handler and the key loop (the colours), the clock in the frames. The columns that show 0 for an input are entries that never read it, as the static list says.")
    w("")
    w("The key-loop runs are one pass of the loop; where it waits (`$A511` for the console key to be released, `$A493` for the clock to change) the run is stopped at 40,000 steps and the state there is compared. The start-up (`Start` up to the key loop) reads `POKMSK` and the clock in wait loops; it is the subject of `37` (measured on three machines), not run here.")
    w("")
    w("## 4. What the game gives to the outside, and the one read-back")
    w("")
    w("The outputs are the registers of `33` and the regions of `42`. By register (the written registers of the ROM, from the static list; `tools/analyze_io.py`):")
    w("")
    w("| Device | Register | What | Write sites | Routines |")
    w("|---|---|---|---|---|")
    for dev, key, label, n, routines in outputs_table():
        w("| %s | `$%04X` | %s | %d | %s |" % (dev, key, label.replace("|", "/"), n, ", ".join(routines[:5]) + (" ..." if len(routines) > 5 else "")))
    w("")
    w("**The colour shadow read-back.** `GhostEaten` (`$A886`) writes `$DC` into `PCOLR0+x` of the eaten ghost, and the end of `GhostEatenPause` (`$B09D-$B0AA`) scans `PCOLR0-3` for the value `$DC`, restores `$0C` into it and goes on. The shadow therefore carries which ghost was eaten across the pause, in the OS page. The port-form code (`core_frame.ghost_eaten`, `core_sound.ghost_eaten_pause`) keeps it in `w.shadow[0xC0 + x]`, and the 500 frame runs of `44` compare it. A port with its own colour tables must keep this one byte of state in a place the pause can read.")
    w("")
    w("## 5. What is not there")
    w("")
    w("| Service | The code | How it is shown |")
    w("|---|---|---|")
    for a, b, c in ABSENT:
        w("| %s | %s | %s |" % (a, b, c))
    w("")
    w("Control transfers outside the cartridge, all %d: %s. Interrupt returns (`RTI`): %s, the ends of the two display-list handlers (the vertical-blank handler ends with the OS's `XITVBV`). CPU flag instructions: %s (`sei` / `cli` bracket the write of the keyboard-interrupt enable in `Start`, `sed` / `cld` the BCD addition of the score)." % (
        len(st["control_out"]), ", ".join("`%s $%04X -> $%04X`" % (m, pc, op) for pc, m, op in st["control_out"]), ", ".join("`$%04X`" % p for p in st["rti"]), ", ".join("`%s $%04X` (%s)" % (m, pc, O.routine_name(pc)) for pc, m in st["cpu_flags"])))
    refs = st["refs"]
    w("")
    w("Absolute-address references: page 3 %d, the PIA %d, the serial data registers %d, OS ROM data %d. The indexed instructions whose 256-byte window reaches those areas (%d, %d, %d, %d) are page-2 and chip-register loops with small indexes (`sta PCOLR0,x`, `sta AUDF1,y`, `sta COLOR0,y`) and four reads of the cartridge's last page with small indexes (`lda $BFC6,x` and three more: tables of the title); the concrete run touched no address in those areas." % (
        refs["page3"][0], refs["pia"][0], refs["serial"][0], refs["osrom"][0], refs["page3"][1], refs["pia"][1], refs["serial"][1], refs["osrom"][1]))
    w("")
    w("## 6. What the OS does for the game, and what the port does instead")
    w("")
    w("| The OS does | What it does for the game | The port instead |")
    w("|---|---|---|")
    for a, b, c in OS_TASKS:
        w("| %s | %s | %s |" % (a, b, c))
    w("")
    w("**The timing contract**: one call of `play_frame` per frame, 60 per second on NTSC (on PAL 50 per second: the frame body takes 122 of 312 scan lines there, `38`, OV-62); in the original the frame body takes at most 234 of 262 scan lines (`38`: 28 lines of margin), so a port has no timing to hit but the frame. The five colour interrupts of the game screen and of the title are at fixed lines (`35`, section 4): a renderer applies them per band.")
    w("")
    w("## 7. The interface of the port")
    w("")
    w("`tools/platform_iface.py`:")
    w("")
    w("| Declared input | `Platform` method | Reaches the port-form World as |")
    w("|---|---|---|")
    w("| `STICK0-1` | `stick(port)` | `w.stick[0..1]` (`core_pacman.read_joystick`) |")
    w("| `STRIG0-1` | `trigger(port)` | the key loop (not in the port form) |")
    w("| `CONSOL` | `console()` | the key loop |")
    w("| `CH`, `KEYDEL` | `key()`, `key_delay()` | the key loop |")
    w("| `M2PF`, `M1PL`, `M2PL` | `collisions(w)` | `w.collide[2, 9, 10]` (`core_play._contact_and_bonus`) |")
    w("| `RANDOM` | `random()` | the iterator `rnd` of the port functions (`RandomFeed`) |")
    w("| `RTCLOK2` | `clock()` | `w.RTCLOK2` |")
    w("| `DRKMSK`, `COLRSH` | `attract()` | `w.DRKMSK`, `w.COLRSH` |")
    w("| `POKMSK` | -- | `Start` only: the port sets its own interrupt state |")
    w("")
    w("`run_frame(w, platform)` copies the inputs into the World, runs `play_frame` and returns a `Frame`: the ordered sound-chip writes, the maze and status cells, the colour shadows and the number of RANDOM values used. `ScriptedPlatform` is deterministic and counts its calls: `tests/test_iface.py` runs frames on it and checks that the same script gives the same frames, that a different stick script gives different ones, and that every RANDOM value used came through the platform. The part of the game outside `play_frame` (the key loop, the title and level-end states, the drawing) is the port's to build on this interface; its inputs are in the table above.")
    w("")
    w("## 8. Limits")
    w("")
    w("- **The closure experiment is a sample**, not a proof: random states of the stage-50 to stage-66 kinds, 1,000 to 1,300 a kind, with the maze pointer, positions and states kept to the game's own (as `42`). The static facts (the 15 read instructions, the 2 control transfers) are proved by the scan of the ROM; the dynamic run adds that the **indirect** reads (`lda (zp),y`, indexed forms) never reach the outside. The pointers the code reads through are in `29`; the run is the check of their reads.")
    w("- **`Start` is not in the closure run**: its reads of `POKMSK` and the clock are in wait loops that need a real clock. The start-up is `37` (three machines measured, what the game takes from the power-on state).")
    w("- **The key loop's one pass** is compared where it waits for an input; its branches are `40` (every one run in the real game).")
    w("- **OV-68: the collision registers** are an input the hardware computes from the pictures of the sprites. The game tests them only as bits (`M1PL`, `M2PL`: Pac-Man's missiles on a ghost's player; `M2PF`: the bonus item). The port needs a geometry for them: **built since this chapter was written** (`50`, `tools/gtia_collisions.py`, checked on 73,111 random scenes and 27,193 frames of real play, 0 differences), and available as `GtiaCollisions` in `tools/platform_iface.py`. The vertical half of the contact test is in the game (`|dy| < 5`, `41`). What the model takes is the scene (positions and pictures of the pages) the original's drawing leaves, which the port produces in `tools/core_draw.py` (OV-69, closed: `44`).")
    w("- **The PAL machine** has not been run through this interface test (PAL timing is OV-02's concern, `38`).")
    w("")
    return "\n".join(P) + "\n"


def main():
    if "--doc" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--doc") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(chapter())
    else:
        print(chapter())


if __name__ == "__main__":
    main()
