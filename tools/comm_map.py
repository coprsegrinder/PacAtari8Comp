"""Stage 68 (communication): the game has no communication with anything outside the machine (docs/45: no file, serial, network or PIA access, two OS calls); the only communication there is lies INSIDE the program, between its four
contexts that run interleaved on the one CPU: the main program (the key loop `$A4BA-$A572`), the deferred vertical-blank handler (`$A5FD`, the whole game frame), and the two display-list interrupt handlers (`$A573` game screen,
`$A5CE` title).  Static: for each context the variables and memory regions read and written by it and by every routine it calls (tools/absint6502.py, the catalogue of docs/25 for the names), and from them the variables one context
writes and another reads.  Dynamic, on the concrete 6502: the same contexts run from random states (tools/iface_map.py's set-ups); every cell read or written must lie in the static set of its context.
Usage: python -I tools/comm_map.py [--trials 300] [--write analysis/evidence-comm-summary.txt] [--doc docs/46-communication.md]"""
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import algorithm_models as A  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402
import iface_map as I  # noqa: E402
import output_map as O  # noqa: E402

INS, F = O.INS, O.PROG.F
CONTEXTS = [("key", "main program: the key loop", None), ("newgame", "main program: the new-game sequence it starts", None), ("vbi", "vertical-blank handler (the frame)", 0xA5FD), ("dli1", "display-list interrupt, game screen", 0xA573), ("dli2", "display-list interrupt, title", 0xA5CE)]
KEY_LOOP = (0xA4BA, 0xA572)
NEW_GAME = (0xA477, 0xA4B9)                       # the key loop jumps to it ($A541: jmp $A477) and it returns to the key loop ($A4B6)
READ_OPS = {"lda", "ldx", "ldy", "cmp", "cpx", "cpy", "ora", "and", "eor", "adc", "sbc", "bit", "inc", "dec", "asl", "lsr", "rol", "ror"}
WRITE_OPS = {"sta", "stx", "sty", "inc", "dec", "asl", "lsr", "rol", "ror"}
FIELD_AT = {}
for _n, _a, _c in W.FIELDS:
    for _k in range(_c):
        FIELD_AT[_a + _k] = (_n, _a, _c)


def closure(entries):
    """the instruction addresses of the routines reached from the entries (their bodies and every callee)"""
    seen, work, pcs = set(), list(entries), set()
    while work:
        e = work.pop()
        if e in seen or e not in F:
            continue
        seen.add(e)
        pcs |= set(F[e].body)
        work.extend(F[e].calls.values())
    return pcs


def context_pcs():
    out = {}
    start = F[0xA386]
    key = {a for a in start.body if KEY_LOOP[0] <= a <= KEY_LOOP[1]}
    new = {a for a in start.body if NEW_GAME[0] <= a <= NEW_GAME[1]}
    out["key"] = key | closure([t for site, t in start.calls.items() if site in key])
    out["newgame"] = new | closure([t for site, t in start.calls.items() if site in new])
    for name, label, entry in CONTEXTS[2:]:
        out[name] = closure([entry])
    return out


INDEX_SPAN = {0xA47B: 32, 0xADB4: 128, 0xADE3: 20}          # `ldx #$1F ... sta $20,x ... bpl` (`$A479-$A47E`): the new game clears $20-$3F; InitBoard clears $80-$FF (`ldx #$7F`, `$ADB2`) and loads $80-$93 (`ldx #$13`, `$ADDE`); the other indexed zero-page accesses stay inside the variable of their base address (the concrete run checks it)


def cells_of(op, mode, span=1):
    """-> set of keys: a zero-page variable name or a region name for the cells an instruction can touch (indexed: the whole variable / region window)"""
    if mode in ("zp", "zpx", "zpy") or (mode == "abs" and op < 0x100):
        if mode == "abs" or mode == "zp":
            f = FIELD_AT.get(op)
            return {("zp", f[0] if f else "$%02X" % op)}
        if span > 1:
            return {("zp", FIELD_AT[op + k][0] if op + k in FIELD_AT else "$%02X" % (op + k)) for k in range(span)}
        f = FIELD_AT.get(op)
        if f:
            return {("zp", f[0])}
        return {("zp", "$%02X..." % op)}
    if mode in ("abs", "abx", "aby"):
        hi = op + (255 if mode != "abs" else 0)
        regs = O.regions_between(op, hi)
        regs.discard("Rom")
        return {("mem", r) for r in regs if r not in ("Other",)} or set()
    return set()


def static_sets():
    """-> {context: (reads, writes)} of keys, with the instruction count"""
    pcs = context_pcs()
    out = {}
    for name, _, _ in CONTEXTS:
        rd, wr = set(), set()
        for pc in pcs[name]:
            ln, m, mode, op = INS[pc]
            if not isinstance(op, int) or mode in ("imm", "imp", "acc", "rel") or m in ("jsr", "jmp"):
                continue
            if mode == "izy":
                continue                                # through a pointer: the regions of docs/29 / tools/output_map.py IZY
            ks = cells_of(op, mode, INDEX_SPAN.get(pc, 1))
            if m in READ_OPS:
                rd |= ks
            if m in WRITE_OPS:
                wr |= ks
        out[name] = (rd, wr, len(pcs[name]))
    return out


def shared(st):
    """-> {key: (writer contexts, reader contexts)} for the keys one context writes and another reads or writes"""
    keys = set()
    for name in st:
        keys |= st[name][0] | st[name][1]
    res = {}
    for k in keys:
        wr = {n for n in st if k in st[n][1]}
        rd = {n for n in st if k in st[n][0]}
        if wr and len(wr | rd) > 1:
            res[k] = (wr, rd)
    return res


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def dynamic(trials=300, seed=68, st=None):
    base = A.started_machine()
    ys, xs = O.load_junction_lists()
    st = st or static_sets()
    orig = (C.Machine.rd, C.Machine.wr, C.Machine.step)
    seen = {"r": set(), "w": set()}
    cur = {"pc": 0}
    rec_rd, rec_wr, rec_step = orig

    def via_pointer(m):
        return INS.get(m.cur, (0, "", "", 0))[2] == "izy"          # a pointer's target: classified by tools/output_map.py (stage 64), and random pointers of random states may point anywhere

    def rd(m, a):
        a &= 0xFFFF
        if a < 0x4000 and a != 0xD20A and not via_pointer(m):
            seen["r"].add(a)
        return rec_rd(m, a)

    def wr(m, a, v):
        a &= 0xFFFF
        if a < 0x4000 and not via_pointer(m):
            seen["w"].add(a)
        rec_wr(m, a, v)

    def step(m):
        m.cur = m.pc
        return rec_step(m)

    C.Machine.rd, C.Machine.wr, C.Machine.step = rd, wr, step
    bad = []
    ctxkind = {"key": ("keyloop",), "vbi": ("vbi-game", "vbi-play", "vbi-title", "vbi-levelend", "vbi-death", "vbi-eaten", "frame-play"), "dli1": ("dli-game",), "dli2": ("dli-title",)}
    ran = Counter()
    try:
        for ctx, kinds in ctxkind.items():
            rng = random.Random(seed + len(ctx))
            for kind in kinds:
                for _ in range(trials):
                    m = I.make_trial(kind, base, random.Random(rng.randrange(1 << 30)), ys, xs)
                    m.mem[0x2B] &= 1                                   # CurrentPlayer is 0 or 1 (a random byte indexes the per-player tables out of their variables)
                    seen["r"].clear()
                    seen["w"].clear()
                    I.go(m, kind)
                    ran[ctx] += 1
                    rd_keys, wr_keys = st[ctx][0], st[ctx][1]
                    if ctx == "key":                                   # a pass of the key loop may start a new game: the two sets of the main program
                        rd_keys, wr_keys = rd_keys | st["newgame"][0], wr_keys | st["newgame"][1]
                    for a in seen["w"]:
                        ks = cells_of(a, "abs")
                        if not (ks & wr_keys) and not _stack_or_hw(a):
                            bad.append((ctx, kind, "write", a))
                    for a in seen["r"]:
                        ks = cells_of(a, "abs")
                        if not (ks & (rd_keys | wr_keys)) and not _stack_or_hw(a):
                            bad.append((ctx, kind, "read", a))
    finally:
        C.Machine.rd, C.Machine.wr, C.Machine.step = orig
    return bad, ran


def _stack_or_hw(a):
    return 0x100 <= a <= 0x1FF or a >= 0xA000


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def pair_matrix(sh):
    """number of keys written by the row context and read by the column context"""
    names = [c[0] for c in CONTEXTS]
    mat = {(a, b): 0 for a in names for b in names}
    for k, (wr, rd) in sh.items():
        for a in wr:
            for b in rd:
                if a != b:
                    mat[(a, b)] += 1
    return names, mat


def summary_lines(bad, ran, trials):
    st = static_sets()
    sh = shared(st)
    L = ["Communication inside the program (tools/comm_map.py, stage 68): the contexts of the game and the variables and regions they share, from the static read / write sets of each context and every routine it calls, checked on the concrete 6502", ""]
    for name, label, entry in CONTEXTS:
        rd, wr, n = st[name]
        L.append("%s: %d instructions; reads %d variables / regions, writes %d" % (label, n, len(rd), len(wr)))
    zp = {k: v for k, v in sh.items() if k[0] == "zp"}
    mem = {k: v for k, v in sh.items() if k[0] == "mem"}
    L.append("")
    L.append("shared (written by one context and read or written by another): %d zero-page variables, %d memory regions" % (len(zp), len(mem)))
    names, mat = pair_matrix(sh)
    L.append("variables / regions written by the row and read by the column:")
    L.append("row\\col".ljust(8) + "".join(n.rjust(7) for n in names))
    for a in names:
        L.append(a.ljust(8) + "".join(("%d" % mat[(a, b)] if a != b else "-").rjust(7) for b in names))
    L.append("")
    L.append("run: %s contexts runs (%s); every cell read or written outside the stack and the ROM lies in the static set of its context: %d outside" % (sum(ran.values()), ", ".join("%s %d" % kv for kv in sorted(ran.items())), len(bad)))
    for b in bad[:5]:
        L.append("  %s" % (b,))
    return L


def main():
    n = int(sys.argv[sys.argv.index("--trials") + 1]) if "--trials" in sys.argv else 300
    bad, ran = dynamic(n)
    L = summary_lines(bad, ran, n)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
