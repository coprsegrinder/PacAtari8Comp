"""Stage 93 (binary analysis documentation): ONE chapter that records what is known about the BINARY itself - its file and format, how it was taken apart and what came out, where every routine begins and ends, every instruction the
program uses (an instruction reference of this program), the chip registers and OS entries it touches, the regions of data and their formats, and the things reverse engineering found.  GENERATED from the ROM, the recursive trace
(tools/analyze_functions.py), the opcode table of the disassembler (tools/disasm6502.py), the data regions of the labelling (tools/labels.py) and the manifest of the originals; the curated parts are the tables at the top.
Usage: python -I tools/analyze_binary_docs.py [--doc docs/59-binary-analysis.md]
Tests: tests/test_binary_docs.py (the chapter is current; the facts hold; the ROM is the one of the manifest; every opcode used is a documented one)."""
import collections
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import analyze_relationships as R  # noqa: E402
import asset_pack as AP  # noqa: E402
import disasm6502 as D  # noqa: E402
import labels  # noqa: E402

ROM_PATH = os.path.join(ROOT, "original", "Pac-Man.rom")
MANIFEST = os.path.join(ROOT, "docs", "original-manifest.txt")

# entry points of the recursive trace and the evidence for each (docs/09)
ENTRY_EVIDENCE = {
    0xA386: "the cartridge RUN vector (`$BFFA`)",
    0xA6B4: "the cartridge INIT vector (`$BFFE`); the routine is a bare `RTS`",
    0xA5FD: "`SETVBV` (A=7, X=`$A5`, Y=`$FD`) at `$A460`; ends with `JMP XITVBV` at `$A60D`",
    0xA573: "`VDSLST` set to `$A573` by the call at `$A49B`; saves A and X, ends `RTI`",
    0xA5CE: "the same prologue and `RTI` shape; the second display-list handler, between the first and the vertical-blank handler",
}

# what reverse engineering found, with where it is shown
DISCOVERIES = [
    ("An 8 KB image whose two 4 KB halves differ (consistent with the two-chip retail cartridge); RUN and INIT are in the header at `$BFFA`; INIT is a bare `RTS`", "`07`, `03`"),
    ("The vertical-blank handler is installed as a **deferred** VBI (`SETVBV` with A=7): the whole game frame is one routine, `FrameDispatch`, and the main program only runs between frames", "`07`, `24`, `38`"),
    ("Every `JSR` and `JMP` target is static: no indirect jump, no push-and-return trick, no `BRK`; the call tree is complete", "`23`, `28`"),
    ("6 routines are not reducible: a loop with a second entry through `lda #imm / bne`", "`26`"),
    ("39 routines had no name from the start (`Sub_XXXX`); they were named from their behaviour, evidence in the chapters", "`11`, `24`"),
    ("The data is packed: the maze, the character sets and the move-delay tables are nibble and run streams that `Start` expands into RAM", "`12`"),
    ("The level-dependent tables are indexed past their ends on boards above 15: the real game reads the bytes that follow", "`14`, `44`"),
    ("`PCOLR0-3` = `$DC` carries which ghost was eaten across the pause: a colour shadow used as a variable", "`45`"),
    ("Two stray writes: `InitDisplay2` writes 16 bytes into the ROM (ignored by the machine), a black band-1 colour writes `$D111`", "`42`"),
    ("A race at `$A800` (ghost 0 incremented twice) that is a path of the search no game can take", "`34`"),
    ("The extra life is decided by the screen cell of the ten-thousands digit, not by the number: it can be given at a score wrap", "`44`"),
    ("5 instructions are never executed in any run: dead paths of the original, shown from the code", "`32`"),
    ("The game's RANDOM is read at exactly 3 places", "`31`"),
    ("The time budget of the handler is not provable by static analysis (the play frame's bound is 2x the budget); the heaviest play frame found costs 89% of it", "`39`"),
]


def read_rom():
    with open(ROM_PATH, "rb") as fh:
        return fh.read()


def manifest():
    out = {}
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            p = line.split()
            if len(p) >= 3 and len(p[0]) == 64:
                out[p[2]] = (p[0], p[1])
    return out


def facts():
    rom, F, miss, extra = R.build()
    ins = rom.ins
    f = {"rom": rom, "F": F, "ins": ins}
    f["code"] = sum(v[0] for v in ins.values())
    f["data"] = len(A.ROM) - f["code"]
    f["data_regions"] = [(int(r["addr"], 16), r["size"], r["kind"], r["name"], r["note"]) for r in AP.build()["regions"]]       # the 79 regions of the asset pack: every non-code byte once
    f["data_bytes"] = sum(r[1] for r in f["data_regions"])
    f["code_lo"] = min(ins)
    f["code_hi"] = max(ins) + ins[max(ins)][0]
    # contiguous runs of code
    runs = 0
    prev_end = None
    for a in sorted(ins):
        if prev_end is None or a != prev_end:
            runs += 1
        prev_end = a + ins[a][0]
    f["chunks"] = runs
    # opcode usage
    opc = collections.Counter()
    for a in ins:
        opc[A.ROM[a - 0xA000]] += 1
    f["opcodes"] = opc
    f["mnemonics"] = collections.Counter(v[1] for v in ins.values())
    f["modes"] = collections.Counter(v[2] for v in ins.values())
    # chip registers
    regs = collections.OrderedDict()
    for a, v in sorted(ins.items()):
        if v[2] in ("abs", "abx", "aby") and 0xD000 <= v[3] <= 0xD4FF:
            r = regs.setdefault(v[3], [0, 0])
            r[0] += 1
            if v[1] in ("sta", "stx", "sty"):
                r[1] += 1
    f["regs"] = regs
    shadows = set(v[3] for v in ins.values() if v[2] in ("abs", "abx", "aby") and 0x0200 <= v[3] <= 0x02FF)
    f["shadows"] = sorted(shadows)
    f["os_calls"] = sorted(set(v[3] for v in ins.values() if v[1] in ("jsr", "jmp") and v[2] == "abs" and v[3] >= 0xC000))
    f["header"] = [A.ROM[0x1FFA + i] for i in range(6)]
    # routines
    callers = collections.Counter()
    sites = collections.Counter()
    for e in F:
        for site, t in F[e].calls.items():
            if t in F:
                sites[t] += 1
    own = {}
    nins = collections.Counter()
    for a in ins:
        o = min((e for e in F if a in F[e].body), key=lambda e: (len(F[e].body), e))
        own[o] = own.get(o, 0) + ins[a][0]
        nins[o] += 1
    f["own_bytes"], f["own_ins"], f["sites"] = own, nins, sites
    return f


def doc():
    f = facts()
    F, ins, rom = f["F"], f["ins"], f["rom"]
    data = read_rom()
    sha = hashlib.sha256(data).hexdigest()
    man = manifest()
    L = []
    P = L.append
    P("# 59 - Binary Analysis (checklist stage 93)")
    P("")
    P("GENERATED by `python -I tools/analyze_binary_docs.py --doc docs/59-binary-analysis.md` from the ROM, the recursive trace of its code, the opcode table of the disassembler, the data regions of the labelling and the manifest of the originals; the entry-point evidence and the list of discoveries are tables in the tool. Tests: `tests/test_binary_docs.py`.")
    P("")
    P("Checklist stage 93: \"Document file formats, disassembly findings, instruction references, function boundaries, and other reverse engineering discoveries.\" The binary is the Pac-Man cartridge image for the Atari 8-bit computers; this chapter records everything that is known about it **as a binary**. What the program *does* is in the chapters of `13`-`22` and `34`-`46`; how it is organised is `58`.")
    P("")
    P("## 1. The file")
    P("")
    P("| | |")
    P("|---|---|")
    P("| File | `original/Pac-Man.rom` (never modified; a read-only copy and the manifest are kept, `03`) |")
    P("| Format | a raw cartridge image, no header: %d bytes, mapped at `$A000-$BFFF` of the 6502's address space (the left cartridge slot) |" % len(data))
    P("| SHA-256 | `%s` (%s the manifest) |" % (sha, "equal to" if man.get("original/Pac-Man.rom", ("",))[0] == sha else "NOT equal to"))
    P("| Structure | two 4 KB halves that differ (a two-chip retail cartridge, not a doubled image); code and data share the space (no separation by address) |")
    P("| Identity | **not proved**: no published checksum of this ROM could be found to compare with (assumption A1, `01`, `03`); the file is the owner's |")
    P("| Needs | the Atari OS (Rev B, NTSC for the verification; the OS ROM is a separate file the emulator needs and is not part of this binary) |")
    P("")
    P("**The cartridge header** (`$BFFA-$BFFF`, `07`; the meaning of the option byte is the standard Atari layout, from memory and not cross-checked; the RUN and INIT vectors were checked by the live start-up on three machines, `37`):")
    P("")
    h = f["header"]
    P("| Address | Bytes | Meaning |")
    P("|---|---|---|")
    P("| `$BFFA-$BFFB` | `%02X %02X` | RUN address = `$%02X%02X` |" % (h[0], h[1], h[1], h[0]))
    P("| `$BFFC` | `%02X` | cartridge-present byte (0 = present) |" % h[2])
    P("| `$BFFD` | `%02X` | option byte: bit 2 set = the cartridge is run (not just a data cartridge), bit 0 clear = no disk boot |" % h[3])
    P("| `$BFFE-$BFFF` | `%02X %02X` | INIT address = `$%02X%02X` (a bare `RTS`) |" % (h[4], h[5], h[5], h[4]))
    P("")
    P("## 2. How the binary was taken apart")
    P("")
    P("**Method** (`08`, `09`, `10`): a recursive-descent disassembler for the documented 6502 instruction set (`tools/disasm6502.py`, validated against the instruction set, `tests/test_disasm6502.py`) follows every branch, `JSR` and `JMP` from five entry points whose evidence is recorded; whatever it cannot reach is data. The listing `src/asm/pacman.s` is generated (`tools/make_asm.py`) with labels and names from `tools/labels.py`, assembles with ca65 / ld65 and **rebuilds the ROM byte for byte** (`tools/build_rom.py`, `tests/test_rebuild.py`: same size and SHA-256).")
    P("")
    P("| Entry point | Address | Evidence |")
    P("|---|---|---|")
    for a in sorted(ENTRY_EVIDENCE):
        P("| %s | `$%04X` | %s |" % (F[a].name, a, ENTRY_EVIDENCE[a]))
    P("")
    P("**Result:**")
    P("")
    P("- **%s instructions, %s code bytes** (%.1f%% of the ROM), all in **one block, `$%04X-$%04X`**; the data is in the two blocks around it: `$A000-$%04X` (%s bytes: 3 bytes no code reads, then the character-set stream and the maze stream) and `$%04X-$BFFF` (%s bytes: the ghost and Pac-Man pictures, the junction and sight tables, the colours, the score digits, the tune, the texts, a stream, the two display lists and the cartridge header). **%s bytes of data in %d named regions**; the code and the regions **account for every byte of the ROM** (%s + %s = %s: no byte uncovered, none counted twice, `09`, `47`)." % ("{:,}".format(len(ins)), "{:,}".format(f["code"]), 100.0 * f["code"] / len(A.ROM), f["code_lo"], f["code_hi"] - 1, f["code_lo"] - 1, "{:,}".format(f["code_lo"] - 0xA000), f["code_hi"], "{:,}".format(0xC000 - f["code_hi"]), "{:,}".format(f["data_bytes"]), len(f["data_regions"]), "{:,}".format(f["code"]), "{:,}".format(f["data_bytes"]), "{:,}".format(len(A.ROM))))
    P("- Every one of the instructions was also **run** in the real machine or on the 6502 interpreter, except 5 that are dead paths of the original (`32`); every `JSR` site ran (`32`).")
    P("")
    P("## 3. Function boundaries")
    P("")
    entries = [e for e in F if e in ENTRY_EVIDENCE]
    jsr_all = [e for e in F if e in rom.jsr_targets]
    both = [e for e in entries if e in rom.jsr_targets]
    others = [e for e in F if e not in ENTRY_EVIDENCE and e not in rom.jsr_targets]
    P("A routine begins at an address that is the target of a `JSR` (%d of the routines; the %d distinct `JSR` targets of `23` are these and the OS's `SETVBV`), an entry point (%d; %d of them is also called by a `JSR`: `%s`), or the target of a `JMP` that is not inside another routine's straight-line code (the other %d); it ends at its `RTS` or `RTI` or at the `JMP` that hands over to another routine (%d tail jumps). Where two routines share code (the 6 loops with a second entry, `26`), each instruction is counted once, for the routine with the smallest body that contains it. **%d routines**; every code byte belongs to one." % (
        len(jsr_all), len(rom.jsr_targets), len(entries), len(both), "`, `".join(F[e].name for e in both), len(others), sum(1 for e in F if F[e].tail), len(F)))
    P("")
    P("| Address | Routine | Own bytes | Instructions | Call sites | Back edges | Subsystem |")
    P("|---|---|---|---|---|---|---|")
    for e in sorted(F):
        P("| `$%04X` | %s | %d | %d | %d | %d | %s |" % (e, F[e].name, f["own_bytes"].get(e, 0), f["own_ins"].get(e, 0), f["sites"].get(e, 0), len(F[e].loops), R.ROLE[e][0]))
    P("")
    P("The inputs, outputs and role of each routine are in `23`, its place in the call tree in `24`, its control-flow graph in `26`.")
    P("")
    P("## 4. Instruction reference of this program")
    P("")
    mn = f["mnemonics"]
    opc = f["opcodes"]
    P("The program uses **%d of the 56 documented 6502 mnemonics**, in **%d of the 151 documented opcodes**; no undocumented opcode is decoded anywhere in the code. Addressing modes: %s." % (len(mn), len(opc), ", ".join("%s %d" % kv for kv in sorted(f["modes"].items(), key=lambda kv: -kv[1]))))
    P("")
    P("| Opcode | Instruction | Mode | Bytes | Count |")
    P("|---|---|---|---|---|")
    for o in sorted(opc, key=lambda o: (D.OPCODES[o][0], D.OPCODES[o][1])):
        m, mode = D.OPCODES[o]
        P("| `$%02X` | %s | %s | %d | %d |" % (o, m.upper(), mode, 1 + D.SIZE[mode], opc[o]))
    P("")
    P("## 5. The machine the binary touches")
    P("")
    P("**%d chip registers** (ANTIC, GTIA, POKEY; none of the PIA), **%d OS shadow and vector addresses** in page 2, and **%d OS entry points**: %s (`35`, `45`)." % (len(f["regs"]), len(f["shadows"]), len(f["os_calls"]), ", ".join("`$%04X`" % t for t in f["os_calls"])))
    P("")
    P("| Register | Name | Instructions | Of them writes |")
    P("|---|---|---|---|")
    for a, (n, w) in f["regs"].items():
        name = labels.hw_name(a, "sta" if w else "lda")            # a register has a different name for a read and a write at some addresses (CONSOL / CONSPK)
        P("| `$%04X` | %s | %d | %d |" % (a, name if name else "", n, w))
    P("")
    P("## 6. The data")
    P("")
    P("%d regions, %s bytes: every byte of the ROM that is not code (`12` has the formats; `47` how a port installs them)." % (len(f["data_regions"]), "{:,}".format(f["data_bytes"])))
    P("")
    P("| Address | Bytes | Kind | Name | What it is |")
    P("|---|---|---|---|---|")
    for lo, size, kind, name, desc in f["data_regions"]:
        P("| `$%04X` | %d | %s | `%s` | %s |" % (lo, size, kind, name, (desc or "").replace("|", "/")))
    P("")
    unknown = [(lo, n, d) for lo, size, k, n, d in f["data_regions"] if d and "unknown" in d.lower()]
    if unknown:
        P("**Not understood:** %s." % "; ".join("`%s` (`$%04X`): %s" % (n, lo, d) for lo, n, d in unknown))
        P("")
    P("## 7. What reverse engineering found")
    P("")
    P("| Finding | Where it is shown |")
    P("|---|---|")
    for a, b in DISCOVERIES:
        P("| %s | %s |" % (a, b))
    P("")
    P("## 8. How this was checked")
    P("")
    P("- The disassembler decodes every opcode of the documented set and nothing else (`tests/test_disasm6502.py`); the listing assembles to the original, byte for byte (`tests/test_rebuild.py`); the named zero-page bytes rebuild the same ROM (`tests/test_zp_names.py`).")
    P("- The control flow was cross-checked: the recursive trace, the live sessions (36 sessions, 2,920 of 2,925 instructions, `32`) and the static / dynamic comparisons of `26`, `28`, `46`.")
    P("- This chapter is regenerated from the ROM and the tools: `tests/test_binary_docs.py` fails if the numbers or the tables change.")
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
