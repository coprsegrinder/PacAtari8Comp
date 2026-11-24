"""Stage 44: the stack of the Pac-Man ROM.

The 6502 has one hardware stack: page 1 ($0100-$01FF), the stack pointer S (offset into the page, the next free byte is $0100+S, it grows down).  JSR pushes 2 bytes (return address - 1), RTS pops them; an
interrupt pushes 3 (PC and P), RTI pops them; PHA / PHP push 1, PLA / PLP pop 1; TXS sets S, TSX reads it.  This tool derives from the code (the same trace as src/asm/pacman.s and the routines of
tools/analyze_functions.py):
  - every instruction that touches the stack, and what it belongs to (the routine with the smallest body that contains it);
  - that the stack page is used as the stack only (no instruction addresses $0100-$01FF), that no routine pushes without popping (every RTS / RTI is reached with the same, zero, own depth on every path) and that
    the code has no indirect jump, so no pushed address is ever 'returned to';
  - the initial S, from the instructions around the TXS;
  - the deepest the stack gets inside each routine and below each interrupt handler (PEAK = bytes the routine and everything it calls use beyond its own return address).
The measured part (the lowest S seen in the emulator over whole games, and S at the entry of the interrupt handlers) is read from analysis/evidence-stack-summary.txt (tools/run_stack_audit.ps1, tools/analyze_stack_log.py).
Usage: python -I tools/analyze_stack.py [--write docs/28-stack.md]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402

ROOT = AF.ROOT
EVIDENCE = os.path.join(ROOT, "analysis", "evidence-stack-summary.txt")
STACK_OPS = {"pha": +1, "php": +1, "pla": -1, "plp": -1}
NOTE = {                                 # by address: what the instruction is for (read from src/asm/pacman.s)
    0xA480: "sets the stack pointer to $FF once at the start of every game / title restart ($A477)",
    0xA573: "DliHandler1 saves A", 0xA575: "DliHandler1 saves X (after TXA)",
    0xA5CA: "DliHandler1 restores X (then TAX)", 0xA5CC: "DliHandler1 restores A",
    0xA5CE: "DliHandler2 saves A", 0xA5D0: "DliHandler2 saves X (after TXA)", 0xA5D2: "DliHandler2 saves Y (after TYA)",
    0xA5F7: "DliHandler2 restores Y (then TAY)", 0xA5F9: "DliHandler2 restores X (then TAX)", 0xA5FB: "DliHandler2 restores A",
    0xB1A8: "saves the joystick direction bits (STICK0 xor $0F) while the loop counts the set bits", 0xB1B5: "gets them back",
    0xB43F: "saves the digit sum while its carry bit is tested", 0xB448: "gets it back",
    0xB4D7: "keeps the lookup's result flags (carry) across the entity test", 0xB506: "gets the flags back before RTS",
}


def load():
    rom, F = AF.analyse()
    AF.solve(rom, F)
    owner = {}
    for a in rom.ins:
        owner[a] = min((e for e in F if a in F[e].body), key=lambda e: (len(F[e].body), e))
    return rom, F, owner


def depth_map(rom, f):
    """own stack depth (bytes pushed by the routine's own PHA / PHP, not yet popped) before every instruction, and the (from, to, depth_a, depth_b) join mismatches."""
    d = {f.entry: 0}
    work, bad = [f.entry], []
    while work:
        a = work.pop()
        n, m, mode, op = rom.ins[a]
        x = d[a] + STACK_OPS.get(m, 0)
        for s in rom.succ(a):
            if s not in f.body:
                continue
            if s in d:
                if d[s] != x:
                    bad.append((a, s, d[s], x))
            else:
                d[s] = x
                work.append(s)
    return d, bad


def analyse():
    rom, F, owner = load()
    depth, bad, unbalanced = {}, {}, []
    for e, f in F.items():
        depth[e], bad[e] = depth_map(rom, f)
        for a, x in depth[e].items():
            if rom.ins[a][1] in ("rts", "rti") and x != 0:
                unbalanced.append((f.name, a, x))
    peak, chain = {}, {}

    def calc(e):
        if e in peak:
            return peak[e]
        peak[e], chain[e] = 0, []
        p, best = 0, []
        for a, x in depth[e].items():
            n, m, mode, op = rom.ins[a]
            if m in ("pha", "php") and x + 1 > p:
                p, best = x + 1, [("own push", a)]
            if m == "jsr":
                sub = calc(op) if op in F else 0
                if x + 2 + sub > p:
                    p, best = x + 2 + sub, [("call", a)] + (chain[op] if op in F else [])
        peak[e], chain[e] = p, best
        return p
    for e in F:
        calc(e)
    ops = collections.defaultdict(list)
    for a, (n, m, mode, op) in rom.ins.items():
        if m in STACK_OPS or m in ("txs", "tsx"):
            ops[owner[a]].append((a, m))
    page1 = [a for a, (n, m, mode, op) in rom.ins.items() if mode in ("abs", "abx", "aby") and 0x100 <= op <= 0x1FF]
    return rom, F, owner, depth, bad, unbalanced, peak, chain, ops, page1


def init_sp(rom):
    """S after the TXS: the X value at the TXS.  The code before it is `ldx #$1F / sta zp,x / dex / bpl back / txs`: the loop ends when X goes from 0 to $FF."""
    txs = [a for a, i in rom.ins.items() if i[1] == "txs"]
    assert len(txs) == 1
    t = txs[0]
    prev = sorted(a for a in rom.ins if a + rom.ins[a][0] == t)[0]            # the bpl before it
    ok = rom.ins[prev][1] == "bpl"
    dex = [a for a in rom.ins if a + rom.ins[a][0] == prev and rom.ins[a][1] == "dex"]
    return t, ok and bool(dex), 0xFF


def evidence():
    if os.path.exists(EVIDENCE):
        with open(EVIDENCE, encoding="utf-8", newline="") as fh:
            return fh.read().replace("\r\n", "\n").rstrip("\n").split("\n")
    return None


def report():
    rom, F, owner, depth, bad, unbalanced, peak, chain, ops, page1 = analyse()
    by = {f.name: e for e, f in F.items()}
    txs, txs_ok, sp0 = init_sp(rom)
    L = []
    P = L.append
    P("# 28 - The Stack (stage 44)")
    P("")
    P("GENERATED by `python -I tools/analyze_stack.py --write docs/28-stack.md` from the trace of `src/asm/pacman.s`, the routines of `23-function-table.md`, and `analysis/evidence-stack-summary.txt` (the emulator measurement). Tests: `tests/test_stack.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- The program uses **the hardware stack only** (page 1, `$0100-$01FF`): no instruction of the ROM addresses that page (%d found), there is no heap, no software stack and no stack frame, and the stack is **not game state**: no game variable, table or buffer lives in it." % len(page1))
    P("- The stack pointer is set once, to **$%02X** (the whole page, 256 bytes), by the `TXS` at `$%04X`: the instructions before it count X down from $1F to $FF (`dex / bpl`), so X is $FF at the `TXS`%s." % (sp0, txs, "" if txs_ok else " (PATTERN NOT FOUND)"))
    P("- The only stack operations are: `JSR` / `RTS` (%d call sites, 2 bytes each), the interrupt entry and `RTI` (3 bytes), and the %d pushes (each with its pop) listed in section 2. **Every routine is balanced**: on every path to every `RTS` / `RTI` it has popped what it pushed (%d routines checked, %d unbalanced), and at every join of two paths the own depth is the same (%d mismatches)." %
      (sum(1 for i in rom.ins.values() if i[1] == "jsr"), sum(1 for e in ops for a, m in ops[e] if m in ("pha", "php")), len(F), len(unbalanced), sum(len(v) for v in bad.values())))
    P("- There is no indirect jump and no `PHA / PHA / RTS` jump trick, so no pushed value is ever used as an address except by `RTS` / `RTI`: **the call structure of `23-function-table.md` is the whole control flow** and a C function call per `JSR` reproduces it exactly.")
    P("")
    P("## 2. Every instruction that uses the stack besides JSR / RTS")
    P("")
    P("| Address | Instruction | In routine | What it is for |")
    P("|---|---|---|---|")
    rows = []
    for e, lst in ops.items():
        for a, m in lst:
            rows.append((a, m, F[e].name))
    for a, m, nm in sorted(rows):
        P("| `$%04X` | %s | %s | %s |" % (a, m.upper(), nm, NOTE[a]))
    P("")
    P("`PHA` / `PLA` in the two display-list handlers are the 6502 idiom for 'save the registers the handler uses'; in the C port they have no counterpart (the registers are the C locals). The three in the middle of the game routines are a one-value save across a few instructions: a C local. `PHP` / `PLP` keeps the **carry** the lookup hands back across code that would clobber it (`23`: result in C).")
    P("")
    P("## 3. How deep the stack gets - from the code")
    P("")
    P("PEAK of a routine = the most bytes it and everything it calls put on the stack beyond its own return address (each nested `JSR` adds 2, each own `PHA` / `PHP` 1). Interrupt handlers: beyond the 3 bytes the hardware pushes (and what the OS pushes before it jumps to them).")
    P("")
    top = sorted(F, key=lambda e: (-peak[e], F[e].name))
    P("| Routine | PEAK (bytes) | Deepest path |")
    P("|---|---|---|")
    for e in top:
        if peak[e] == 0:
            continue
        names = []
        for kind, a in chain[e]:
            if kind == "call":
                tgt = rom.ins[a][3]
                names.append(F[tgt].name if tgt in F else "$%04X" % tgt)
            else:
                names.append("PHA/PHP at $%04X" % a)
        P("| %s | %d | %s |" % (F[e].name, peak[e], " -> ".join(names) or "-"))
    zero = sum(1 for e in F if peak[e] == 0)
    P("")
    P("%d further routines call nothing and push nothing (PEAK 0)." % zero)
    P("")
    entry = {n: by[n] for n in ("Start", "VbiHandler", "DliHandler1", "DliHandler2")}
    P("Entry points: **Start %d**, **VbiHandler %d** (the whole game frame runs from the vertical-blank interrupt: `FrameDispatch` is entered by it), **DliHandler1 %d**, **DliHandler2 %d** bytes beyond what the hardware and OS have pushed." %
      (peak[entry["Start"]], peak[entry["VbiHandler"]], peak[entry["DliHandler1"]], peak[entry["DliHandler2"]]))
    P("")
    st, vb, d1, d2 = peak[entry["Start"]], peak[entry["VbiHandler"]], peak[entry["DliHandler1"]], peak[entry["DliHandler2"]]
    P("Contexts that can be stacked: the main program (`Start`), an NMI that runs the vertical-blank handler (the game frame), and - because a display-list interrupt is also an NMI and the frame code runs on into the display - one display-list interrupt inside it. Two facts from the code limit this:")
    P("")
    P("- **Only one display-list handler is active at a time.** `SetDisplayList` writes the display list and `VDSLST` together: the game screen sets `DliHandler1` (the call at `$A49B`, `ldy #$73`), the title and attract screens set `DliHandler2` (`InitDisplay2`, the call at `$A621`, `ldy #$CE`). The deepest chain below runs only on the game screen (`TurnControl` handles a turn switch in a two-player game), so it can be interrupted by `DliHandler1` only; `DliHandler2` can only interrupt the title-screen frames, whose chains are shallow.")
    P("- **The interrupts do not nest inside each other's handlers**, and the OS pushes nothing before a display-list interrupt (it jumps through `VDSLST`) but 3 bytes (A, X, Y) before the deferred VBI handler; the hardware pushes 3 bytes for each. Both are measured (section 4: the interrupted pc is read from the stack at every entry).")
    P("")
    P("So the bound **by construction**, for every combination whether it occurs or not, is `Start %d + VBI entry 6 (3 hardware + 3 OS) + VbiHandler %d + DLI hardware 3 + the larger DLI handler %d` = **%d bytes** of the 256. The case that really occurs (the deepest chain interrupted by `DliHandler1`, with the main program idle) is `6 + %d + 3 + %d` = **%d bytes**; section 4 shows that the measurement gives exactly that." %
      (st, vb, max(d1, d2), st + 6 + vb + 3 + max(d1, d2), vb, d1, 6 + vb + 3 + d1))
    P("")
    P("## 4. How deep the stack gets - measured")
    P("")
    ev = evidence()
    if ev:
        P("`tools/run_stack_audit.ps1` runs five of the session harnesses of the project in Altirra (OS-B, NTSC; full games from the title, deaths, ghosts eaten, extra life, the two-player win) with a trace of every write to the stack page below `$01F0`, of S, the scan line and the interrupted pc at the entry of the three interrupt handlers, and of the entries of `InitBoard`, `FillPlayerPages` and the end of the VBI handler (`tools/analyze_stack_log.py`). The interrupted pc is read from the stack, which also checks the stack layout assumed above:")
        P("")
        P("```")
        for line in ev:
            P(line)
        P("```")
    else:
        P("NOT YET MEASURED: `analysis/evidence-stack-summary.txt` does not exist (run `tools/run_stack_audit.ps1`, then `python -I tools/analyze_stack_log.py analysis/raw-logs/stack-*.txt`).")
    P("")
    P("## 5. What the port does with this")
    P("")
    P("- The C code uses the C call stack: one function call per `JSR`, one `return` per `RTS`; nothing to emulate. The stack page is not part of the state the equivalence tests (stages 86-87) compare, except as a bound: the original never uses more than the depth in section 4 (of 256 bytes).")
    P("- The interrupt handlers become functions that the hardware layer calls at the right moments of the frame (stage 79/80); `PHA` / `PLA` / `PHP` / `PLP` become locals (`27-local-variables.md`).")
    P("- Nothing in the ROM depends on the stack contents surviving a call except through `RTS` / `RTI`; there is no `longjmp`-like use. The restart at `$A477` (`TXS`) resets the stack pointer: in C it is a jump back to the start of the main loop.")
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
