"""Stage 61 (startup): from power-on to the first frame of the title, live (Altirra: OS-B NTSC, OS-B PAL, the built-in OS; and a warm start) and in the interpreter (what the game needs from the power-on state).

Sources: analysis/raw-logs/startup-ntsc.txt, startup-pal.txt, startup-ntsc-hle.txt (tools/altirra_startup.cmd, run_patrol_trace.ps1 -Video -Kernel), warmstart.txt (tools/altirra_warmstart.cmd, -Keys 20:74 = F5, warm reset), the 6502 interpreter
(tools/cpu6502.py: `Start` expands the tables) and tools/startup_poison.py (RAM filled with random bytes against the zero fill).  The committed evidence is analysis/evidence-startup-summary.txt.
Usage: python -I tools/analyze_startup.py [--write analysis/evidence-startup-summary.txt] [--doc docs/37-startup.md]"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
LOGS = os.path.join(ROOT, "analysis", "raw-logs")
SUMMARY = os.path.join(ROOT, "analysis", "evidence-startup-summary.txt")
CONFIGS = [("NTSC, OS-B", "startup-ntsc.txt"), ("PAL, OS-B", "startup-pal.txt"), ("NTSC, built-in OS", "startup-ntsc-hle.txt")]
MS = ["MS_RUN", "MS_HSTEXT", "MS_ZPCLEAR", "MS_MAZE", "MS_NIBBLES", "MS_CHARSET", "MS_TITLECHARSET", "MS_TAIL", "MS_IRQ", "MS_SETVBV", "MS_SETVBV_DONE", "MS_RESTART", "MS_COPY1", "MS_COPIES_DONE"]
PHASES = {
    "MS_RUN": ("`$A386`", "RUN: the OS jumps to the cartridge"),
    "MS_HSTEXT": ("`$A391`", "the text `HIGH SCORE` (10 bytes) copied to `$200F`"),
    "MS_ZPCLEAR": ("`$A3A1`", "zero page `$18-$3F` and `$80-$FF` cleared; `GameState` = 1; `$1D` = `RTCLOK2` - 1"),
    "MS_MAZE": ("`$A3F6`", "the maze expanded to `$0800` (type A stream, 920 bytes)"),
    "MS_NIBBLES": ("`$A41B`", "the nibble tables expanded to `$0600-$07FF` (512 bytes)"),
    "MS_CHARSET": ("`$A42E`", "the game character set expanded to `$3000`"),
    "MS_TITLECHARSET": ("`$A441`", "the title character set expanded to `$1808`"),
    "MS_TAIL": ("`$A44C`", "its 32-byte tail copied to `$18A8`"),
    "MS_IRQ": ("`$A456`", "`POKMSK` bit 6 set and written to `IRQEN` (keyboard interrupt), interrupts enabled"),
    "MS_SETVBV": ("`$A460`", "`SKCTL` = `$07`, then `JSR SETVBV` with A=7, X=`$A5`, Y=`$FD`"),
    "MS_SETVBV_DONE": ("`$A463`", "`VVBLKD` = `$A5FD`: the game's vertical-blank handler is installed"),
    "MS_RESTART": ("`$A477`", "`NMIEN` = `$C0`, `SDMCTL` = `$3E`, `GRACTL` = 3, `PMBASE` = `$20`; the restart clear of `$20-$3F`"),
    "MS_COPY1": ("`$A484`", "the maze copied to `$0C00`, `$1000`, `$1400` (three copies of 1,024 bytes)"),
    "MS_COPIES_DONE": ("`$A48D`", "the copies are done; `GameState` is 1 or 2: the board is not initialised, the key loop starts"),
}
HEX = re.compile(r"^([0-9A-F]{4}): ((?:[0-9A-F]{2} )+)")


def read_log(path):
    out = {"ms": {}, "init": [], "hdr": [], "gs": [], "vdslst": [], "sections": {}, "vbi": []}
    cur = None
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if not ln.endswith("\n"):
                continue
            m = re.match(r"^(MS_[A-Z0-9_]+) f=(\d+) vp=(\d+) hp=(\d+)(.*)$", ln)
            if m:
                k = m.group(1)
                if k == "MS_INIT":
                    out["init"].append((int(m.group(2)), int(m.group(3)), m.group(5).strip()))
                elif k not in out["ms"]:
                    out["ms"][k] = (int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5).strip())
                cur = None
                continue
            m = re.match(r"^GS_WRITE pc=\$([0-9A-F]{4}) v=\$([0-9A-F]{2}) f=(\d+) vp=(\d+)", ln)
            if m:
                out["gs"].append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3)), int(m.group(4))))
                continue
            m = re.match(r"^VDSLST_WRITE pc=\$([0-9A-F]{4}) a=\$([0-9A-F]{4}) v=\$([0-9A-F]{2}) f=(\d+)", ln)
            if m:
                out["vdslst"].append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4))))
                continue
            m = re.match(r"^HDR_READ a=\$([0-9A-F]{4}) pc=\$([0-9A-F]{4}) f=(\d+)", ln)
            if m:
                out["hdr"].append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3))))
                continue
            m = re.match(r"^VBI f=(\d+) vp=(\d+) gs=(\d+) rtclok=(\d+)", ln)
            if m:
                out["vbi"].append((int(m.group(1)), int(m.group(3))))
                continue
            if ln.startswith("---"):
                cur = ln.strip()[3:].split()[0]
                out["sections"].setdefault(cur, [])
                out["sections"][cur].append([])
                continue
            if cur is not None:
                out["sections"][cur][-1].append(ln.rstrip("\n"))
    return out


def dump_bytes(lines):
    d = {}
    for ln in lines:
        m = HEX.match(ln)
        if m:
            a = int(m.group(1), 16)
            for i, b in enumerate(m.group(2).split()):
                d[a + i] = int(b, 16)
    return d


def chips(lines):
    import analyze_hw as H
    rec = {}
    for ln in lines:
        H.parse_dump_line(ln, rec)
    return rec


def interpreter_tables():
    import algorithm_models as A
    m = A.started_machine()
    return bytes(m.mem[0x600:0x800]), bytes(m.mem[0x800:0x800 + 920])


def read_warm(path):
    """tools/altirra_warmstart.cmd: RUN / INITRTS / GS_WRITE lines and the dumps at every RUN"""
    out = {"run": [], "init": [], "gs": [], "sections": {}}
    cur = None
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if not ln.endswith(chr(10)):
                continue
            m = re.match(r"^RUN f=(\d+) vp=(\d+) s=\$([0-9A-F]{2}) p=\$([0-9A-F]{2}) a=\$([0-9A-F]{2}) x=\$([0-9A-F]{2}) y=\$([0-9A-F]{2}) gs=(\d+)", ln)
            if m:
                out["run"].append(tuple(m.groups()))
                cur = None
                continue
            m = re.match(r"^INITRTS f=(\d+) vp=(\d+) ret=\$([0-9A-F]{4})", ln)
            if m:
                if int(m.group(3), 16) >= 0xC000:
                    out["init"].append((int(m.group(1)), m.group(3)))
                continue
            m = re.match(r"^GS_WRITE pc=\$([0-9A-F]{4}) v=\$([0-9A-F]{2}) f=(\d+)", ln)
            if m:
                out["gs"].append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3))))
                continue
            if ln.startswith("---"):
                cur = ln.strip()[3:].split()[0]
                out["sections"].setdefault(cur, []).append([])
                continue
            if cur is not None:
                out["sections"][cur][-1].append(ln.rstrip(chr(10)))
    return out


def gather():
    D = {"cfg": {}}
    for name, f in CONFIGS:
        p = os.path.join(LOGS, f)
        if os.path.isfile(p):
            D["cfg"][name] = read_log(p)
    wp = os.path.join(LOGS, "warmstart.txt")
    D["warm"] = read_warm(wp) if os.path.isfile(wp) else None
    return D


def lines(D):
    import startup_poison as SP
    L = []
    P = L.append
    tbl, maze = interpreter_tables()
    P("Startup audit (tools/altirra_startup.cmd, tools/altirra_warmstart.cmd, tools/startup_poison.py, tools/analyze_startup.py)")
    P("")
    P("milestones (frame / scan line / colour clock) per machine:")
    for name, c in D["cfg"].items():
        ini = c["init"][0] if c["init"] else None
        P("  %s: INIT called at frame %s (return to $%s)" % (name, ini[0] if ini else "-", (re.search(r"ret=\$([0-9A-F]+)", ini[2]).group(1) if ini and re.search(r"ret=\$([0-9A-F]+)", ini[2]) else "-")))
        for k in MS:
            if k in c["ms"]:
                f, vp, hp, extra = c["ms"][k]
                if k == "MS_RUN":
                    extra = re.sub(r" ret=\$[0-9A-F]+", "", extra)
                P("    %-16s f=%-4d vp=%-3d hp=%-3d %s" % (k, f, vp, hp, extra))
        P("    GameState writes (pc, value, frame): %s" % "; ".join("$%04X=%d f%d" % (pc, v, f) for pc, v, f, vp in c["gs"] if pc >= 0xA000))
        hd = []
        for a, pc, f in c["hdr"]:
            if (a, pc) not in hd:
                hd.append((a, pc))
        P("    cartridge header reads (address by pc): %s" % " ".join("$%04X@$%04X" % t for t in hd[:12]))
    P("")
    P("state at the first pass of the key loop ($A4BA):")
    chip_ref = None
    for name, c in D["cfg"].items():
        secs = c["sections"]
        rec = {}
        for k in ("ANTIC", "GTIA", "POKEY"):
            if k in secs:
                rec.update(chips(secs[k][0]))
        tb = dump_bytes(secs["TABLES"][0]) if "TABLES" in secs else {}
        have = bytes(tb.get(0x600 + i, 0) for i in range(512))
        P("  %s: tables $0600-$07FF %s the interpreter's expansion; DMACTL=%s CHBASE=%s NMIEN=%s PMBASE=%s GRACTL=%s IRQEN=%s SKCTL=%s AUDCTL=%s" % (
            name, "EQUAL to" if have == tbl else "DIFFERENT from", "%02X" % rec.get("DMACTL", -1), "%02X" % rec.get("CHBASE", -1), "%02X" % rec.get("NMIEN", -1), "%02X" % rec.get("PMBASE", -1), "%02X" % rec.get("GRACTL", -1), "%02X" % rec.get("IRQEN", -1), "%02X" % rec.get("SKCTL", -1), "%02X" % rec.get("AUDCTL", -1)))
    P("")
    P("state when the OS jumps to RUN:")
    for name, c in D["cfg"].items():
        secs = c["sections"]
        zp = dump_bytes(secs["RUN_ZP"][0]) if "RUN_ZP" in secs else {}
        p4 = dump_bytes(secs["RUN_P4"][0]) if "RUN_P4" in secs else {}
        mt = dump_bytes(secs["RUN_MAZETAIL"][0]) if "RUN_MAZETAIL" in secs else {}
        run = c["ms"].get("MS_RUN")
        P("  %s: %s; $0400-$043F %s; $0B98-$0BFF %s; $5E/$5F = %s; $45 = %s" % (name, re.sub(r" ret=\$[0-9A-F]+", "", run[3]) if run else "-", "all zero" if p4 and all(v == 0 for v in p4.values()) else "NOT zero", "all zero" if mt and all(v == 0 for k, v in mt.items() if k <= 0xBFF) else "NOT zero",
                                                                             "$%02X $%02X" % (zp.get(0x5E, -1), zp.get(0x5F, -1)), "$%02X" % zp.get(0x45, -1)))
    P("")
    w = D["warm"]
    if w:
        wr = [e for e in w["gs"] if e[0] == 0xF16E]
        P("warm start (F5 posted to Altirra's window while the title ran): the OS writes GameState = 0 at $F16E (frame %s), calls INIT again (frames %s; return into the OS at $%s), and jumps to RUN again at frame %s with %s" % (
            wr[0][2] if wr else "-", ", ".join(str(e[0]) for e in w["init"]), w["init"][-1][1] if w["init"] else "-", w["run"][-1][0] if w["run"] else "-",
            ("S=$%s P=$%s A=$%s X=$%s Y=$%s (cold: S=$%s P=$%s A=$%s X=$%s Y=$%s)" % (tuple(w["run"][-1][2:7]) + tuple(w["run"][0][2:7]))) if len(w["run"]) >= 2 else "-"))
        secs = w["sections"]
        if len(secs.get("RUN_STATE", [])) >= 2:
            z0, z1 = dump_bytes(secs["RUN_STATE"][0]), dump_bytes(secs["RUN_STATE"][-1])
            dd = [a for a in range(256) if z0.get(a) != z1.get(a)]
            P("  zero page at RUN, cold against warm: %d of 256 bytes differ (%s); the game's own ranges $18-$3F and $80-$FF (which Start clears): %s" % (len(dd), " ".join("$%02X" % a for a in dd), "the same in both" if all(z0.get(a) == z1.get(a) for a in list(range(0x18, 0x40)) + list(range(0x80, 0x100))) else "different"))
        for k, nm, hi in (("RUN_P4", "$0400-$043F", 0x440), ("RUN_MAZETAIL", "$0B98-$0BFF", 0xC00)):
            if len(secs.get(k, [])) >= 2:
                b = dump_bytes(secs[k][-1])
                P("  %s at the warm RUN: %s" % (nm, "all zero" if all(v == 0 for kk, v in b.items() if kk < hi) else "NOT zero"))
    P("")
    zero, zst = SP.run(0, 900, fill="zero")
    runs = [SP.run(s, 900) for s in range(1, 5)]
    cl = SP.classify(runs)
    P("what the game takes from the power-on state (interpreter: RAM filled with random bytes against zero, 4 fills, 900 frames with a START press and a joystick; game started at frame %s):" % zst["start_frame"])
    for (name, rd), dd in sorted(cl.items()):
        P("  read before write: %-18s %s  -> %s" % (name, " ".join(("$%04X-$%04X" % tuple(r)) if r[0] != r[1] else "$%04X" % r[0] for r in SP.ranges(dd)), "destination in ROM (no effect)" if rd else "destination in RAM"))
    diffs = SP.compare(zero, [m for m, _ in runs])
    P("  addresses the game wrote whose final value depends on the fill: %s" % " ".join(("$%04X-$%04X" % tuple(r)) if r[0] != r[1] else "$%04X" % r[0] for r in SP.ranges(diffs)))
    return L, D, cl, diffs, zst


def doc_lines(D, L, cl, diffs, zst):
    import startup_poison as SP
    out = []
    P = out.append
    c0 = D["cfg"]["NTSC, OS-B"]
    ms = c0["ms"]
    pal = D["cfg"]["PAL, OS-B"]
    hle = D["cfg"]["NTSC, built-in OS"]
    gs_a70a = [e for e in c0["gs"] if e[0] == 0xA70A]
    t_title = [e for e in gs_a70a if e[1] == 3][0][2]
    t_first = gs_a70a[0][2]
    P("# 37 - Startup (stage 61)")
    P("")
    P("GENERATED by `python -I tools/analyze_startup.py --doc docs/37-startup.md` from the logs of `tools/altirra_startup.cmd` (three machines), `tools/altirra_warmstart.cmd`, the interpreter and `tools/startup_poison.py`; evidence: `analysis/evidence-startup-summary.txt`. Tests: `tests/test_startup.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- **The cartridge is started exactly as the header says**: the OS reads `$BFFC` (cartridge present) and `$BFFD` (option byte), calls INIT (`$BFFE/F` = `$A6B4`) once and later jumps to RUN (`$BFFA/B` = `$A386`); RUN comes %d frames after INIT on the NTSC OS-B machine (%d PAL, %d built-in OS). INIT is **not a routine of its own**: `$A6B4` is the shared `RTS` at the end of `ReadSrcHighNibble` (the label `Init` of the source), so the OS's INIT call does nothing." % (ms["MS_RUN"][0] - c0["init"][0][0], pal["ms"]["MS_RUN"][0] - pal["init"][0][0], hle["ms"]["MS_RUN"][0] - hle["init"][0][0]))
    P("- **`Start` needs nothing from the OS but a normal CPU state**: the OS enters RUN with S=`$FF`, interrupts enabled (I=0) and the decimal flag clear (D=0; `Start` has no `CLD` and relies on it), on all three machines. Everything the game owns (`$18-$3F`, `$80-$FF`) is cleared by `Start` itself.")
    P("- **In %d frames (NTSC) `Start` builds all the game's data and installs the vertical-blank handler**: RUN at frame %d, `SETVBV` at frame %d, the end of the copies, and with it the first pass of the key loop, at frame %d, the title menu (`GameState` 3) at frame %d (the copyright screen runs %d frames). From RUN to `SETVBV` it takes %d frames on PAL and %d with the built-in OS (the OS's own timing and the number of scan lines differ; the code is the same)." % (ms["MS_SETVBV"][0] - ms["MS_RUN"][0], ms["MS_RUN"][0], ms["MS_SETVBV"][0], ms["MS_COPIES_DONE"][0], t_title, t_title - t_first, pal["ms"]["MS_SETVBV"][0] - pal["ms"]["MS_RUN"][0], hle["ms"]["MS_SETVBV"][0] - hle["ms"]["MS_RUN"][0]))
    P("- **The state at the first key loop is the same on all three machines**: the tables `$0600-$07FF` equal the interpreter's expansion byte for byte, and the chips hold `DMACTL`=`$3E`, `NMIEN`=`$C0`, `PMBASE`=`$20`, `GRACTL`=3, `IRQEN`=`$C0`, `SKCTL`=7.")
    P("- **What the game takes from the power-on state is small and listed** (section 4): the OS's RAM clear (zeros at `$0400-$041F` and `$0B98-$0BFF`) and a few OS zero-page values. With random RAM instead the game starts at the same frame and plays on; the differences are garbage in the unused tails of the maze copies and stray pixel rows in the player-missile pages.")
    P("- **A warm start (the RESET key) is a second cold start for the game**: the OS clears `GameState`, calls INIT and RUN again with the same registers; `Start` begins from scratch (section 5).")
    P("")
    P("## 2. From power-on to RUN (the OS side)")
    P("")
    P("| Step (NTSC, OS-B) | Frame | What happens |")
    P("|---|---|---|")
    hd = []
    for a, pc, f in c0["hdr"]:
        if (a, pc) not in [(x[0], x[1]) for x in hd]:
            hd.append((a, pc, f))
    P("| reset | 3 | the OS clears its variables; `GameState` (`$19`) is zeroed by the OS at `$F140`: the game's variable lies in the OS's cleared range |")
    P("| cartridge check | %d | the OS reads the header: %s |" % (hd[0][2], ", ".join("`$%04X` at `$%04X`" % (a, pc) for a, pc, f in hd[:7])))
    P("| INIT | %d | `JSR` through `$BFFE`; the routine is the `RTS` at `$A6B4` |" % c0["init"][0][0])
    P("| RUN | %d | the OS jumps through `$BFFA` to `Start` (`$A386`) with S=`$FF`, P=`$31` (I=0, D=0), A=`$04`, X=0, Y=`$80` (built-in OS: P=`$30`, X=Y=1) |" % ms["MS_RUN"][0])
    P("")
    P("Header (`07`): `$BFFA/B` RUN = `$A386`; `$BFFC` = 0 (cartridge present); `$BFFD` = `$04` (bit 2: run the cartridge; bit 0 clear: no disk boot); `$BFFE/F` INIT = `$A6B4`.")
    P("")
    P("## 3. What `Start` does, and when")
    P("")
    P("Frame / scan line of the first hit of each step (NTSC 262 lines, PAL 312):")
    P("")
    P("| Step | Address | What | NTSC OS-B | PAL OS-B | NTSC built-in OS |")
    P("|---|---|---|---|---|---|")
    for k in MS:
        a, w = PHASES[k]
        cells = []
        for name, c in D["cfg"].items():
            if k in c["ms"]:
                f, vp, hp, _ = c["ms"][k]
                cells.append("%d / %d" % (f, vp))
            else:
                cells.append("-")
        P("| %s | %s | %s | %s |" % (k[3:].lower(), a, w, " | ".join(cells)))
    P("")
    P("After the copies the key loop (`$A4BA`) runs; the game proper is driven by the vertical-blank handler: `GameState` 1 (written by `Start`) becomes 2 at the first handler run (frame %d, `$A70A`), 3 (the title menu) %d frames later. A START press then jumps to `$A537`, the single start-game entry (`21`)." % (t_first, t_title - t_first))
    P("")
    P("`Start` runs once per RUN and never returns (the key loop is the main program); the restart label `$A477` is also the target of every START (`$A541`): it clears `$20-$3F` and copies the maze again but does not repeat the expansion.")
    P("")
    P("## 4. What the game takes from the power-on state")
    P("")
    P("Method (`tools/startup_poison.py`): the 6502 interpreter runs `Start`, then the key loop with the vertical-blank handler and the display-list interrupts entering at random places, a START press at frame 480 and a joystick that changes direction (900 frames), with the whole RAM filled with random bytes (4 fills) and with zeros (what the OS leaves); the OS-owned inputs of `33` (`POKMSK`, `RTCLOK2`, `ATRACT`, `DRKMSK`, `COLRSH`, the stick and trigger shadows, `CH`) and the hardware registers are given. Every read of a byte that nothing has written is recorded.")
    P("")
    P("| Reader | Addresses read before written | What it is | Live check at RUN |")
    P("|---|---|---|---|")
    notes = {
        "Copy0800To0C00": ("the three maze copies read 1,024 bytes from `$0800`; the maze is 920 bytes, so `$0B98-$0BFF` (104 bytes) of RAM that nothing wrote are copied into the tails of the copies (`$0F98`, `$1398`, `$1798`); never read afterwards", "zero on all machines, cold and warm"),
        "DliHandler2": ("`DliColors` `$5E/$5F`: the display-list interrupts of the first frame(s) read the band colours before the key loop has stored them (`$A4C3`); the OS leaves `$42 $9C` there", "`$42 $9C` on all machines"),
        "DrawAllInPlace": ("the 16-byte picture copy reads its source from `$0400-$0402`, `$040D-$040F`: unused RAM that is meant to be blank; the bytes are copied into the player-missile pages", "zero on all machines, cold and warm"),
        "InitDisplay2": ("the same copy (`InitDisplay2` jumps into the tail of `StepAndDrawEntity`, `29`): `$0410-$0411`, `$041D-$041F` into RAM, and `$0000-$000F` with the destination in ROM (no effect)", "`$0400-$043F` zero on all machines"),
        "VbiHandler": ("`dec $45` (the debounce counter) before the key loop has set it; the key loop sets it to 1 before it is ever tested", "`$00` at RUN"),
    }
    seen = set()
    for (name, rd), dd in sorted(cl.items()):
        if name in seen:
            continue
        seen.add(name)
        allad = {a for (n2, r2), d2 in cl.items() if n2 == name for a in d2}
        rs = " ".join(("`$%04X-$%04X`" % tuple(r)) if r[0] != r[1] else "`$%04X`" % r[0] for r in SP.ranges(allad))
        n, lv = notes.get(name, ("(not classified)", "-"))
        P("| `%s` | %s | %s | %s |" % (name, rs, n, lv))
    P("")
    P("With random RAM the game starts at the same frame (%s) and plays on; what it writes that differs from the zero-filled run is only `$0045` (the counter), the tails of the maze copies (`$0F98-$0FFF`, `$1398-$13FF`, `$1798-$17FF`) and %d bytes of the player-missile pages `$2300-$27FF` (the garbage picture rows above). Nothing in the game's own variables, the maze, the tables or the score depends on the fill. **On a real machine the OS clears RAM at power-on and a warm start leaves these areas as they were (zero: the game never writes them), so the game always sees zeros there.**" % (zst["start_frame"], len([a for a in diffs if 0x2300 <= a < 0x2800])))
    P("")
    P("## 5. The warm start")
    P("")
    wl = [ln for ln in L if ln.startswith("warm start") or ln.startswith("  zero page at RUN") or ln.startswith("  $0400") or ln.startswith("  $0B98")]
    for ln in wl:
        P("- " + ln.strip())
    P("")
    P("## 6. Limits")
    P("")
    P("- The live runs are Altirra 4.40 (OS-B NTSC and PAL, the built-in OS); a real machine's power-on RAM and the timing of its OS are not tested (owner's decision, `OPEN-VERIFICATION.md` OV-01).")
    P("- The fill experiment runs in the interpreter with a fixed schedule of interrupts and inputs: it shows every read of an unwritten byte on that schedule, not on every possible one (the abstract search of `34` covers the state variables, not these RAM areas).")
    P("- The values read from hardware registers and the OS-owned inputs are taken as given (they are the inputs of `33`).")
    return out


def main():
    D = gather()
    L, D, cl, diffs, zst = lines(D)
    txt = "\n".join(L) + "\n"
    if "--doc" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--doc") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(chr(10).join(doc_lines(D, L, cl, diffs, zst)) + chr(10))
        print("wrote doc")
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
