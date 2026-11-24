"""Stages 33-40 and 43: the function table of the Pac-Man ROM - for every routine its body, callers and callees, loops, the registers and flags it needs (inputs), changes (clobbers) and hands back
(outputs, as the callers use them), and the zero-page variables, RAM and hardware registers it reads and writes.  Static analysis of the same trace that tools/make_asm.py uses, so it covers exactly the
bytes of src/asm/pacman.s.

Method.  Entries = the cartridge entry points, every JSR target and every named routine of tools/labels.py that is code.  The BODY of an entry is everything reachable from it by branches, JMP and fall-through
(JSR is a call: the callee is not part of the body; a JMP into another routine is a tail call and its code belongs to the body, so shared tails appear in several bodies).  The registers A, X, Y and the flags C, Z, N, V
are tracked per instruction (reads / writes); a JSR reads the callee's inputs and writes what the callee always writes (kill) or may write (clobber).
  inputs   = registers / flags live at the entry (read before every path has written them)               [stage 37]
  clobbers = registers / flags the routine (or a routine it calls) may change
  outputs  = clobbers that a caller still needs after the JSR (liveness at each call site, iterated until stable: a result passed on by 'JSR f / RTS' is an output of the caller as well)   [stage 38]
Memory: zero-page and absolute operands by name (tools/labels.py), (zp),y as 'via (zp)'; transitive sets include the callees.
Usage: python -I tools/analyze_functions.py [--write docs/23-function-table.md]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disasm6502 as D  # noqa: E402
import labels as LB  # noqa: E402

ROOT = os.path.dirname(HERE)
BASE, SIZE = 0xA000, 0x2000
ENTRIES = {0xA386: "RUN", 0xA6B4: "INIT", 0xA5FD: "VBI", 0xA573: "DLI1", 0xA5CE: "DLI2"}
REGS = ("A", "X", "Y", "C", "Z", "N", "V")
FLAGSET = {"C", "Z", "N", "V"}

LOADS = {"lda": "A", "ldx": "X", "ldy": "Y"}
STORES = {"sta": "A", "stx": "X", "sty": "Y"}
ALU = {"adc", "sbc", "and", "ora", "eor"}
CMPS = {"cmp": "A", "cpx": "X", "cpy": "Y"}
SHIFTS = {"asl", "lsr", "rol", "ror"}
INCDEC = {"inc", "dec"}
BR_FLAG = {"bcc": "C", "bcs": "C", "beq": "Z", "bne": "Z", "bmi": "N", "bpl": "N", "bvc": "V", "bvs": "V"}
INDEX = {"zpx": "X", "abx": "X", "izx": "X", "zpy": "Y", "aby": "Y", "izy": "Y"}


def load_rom():
    with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as fh:
        return fh.read()


def effects(mnem, mode, op):
    """(register reads, register writes, memory reads, memory writes) of one instruction, jsr/jmp/branches excluded.  Memory items: ('zp'|'abs'|'ptr', address, indexed)."""
    r, w, mr, mw = set(), set(), [], []
    idx = INDEX.get(mode)
    if idx:
        r.add(idx)
    mem = None
    if mode in ("zp", "zpx", "zpy"):
        mem = ("zp", op, bool(idx))
    elif mode in ("abs", "abx", "aby"):
        mem = ("abs", op, bool(idx))
    elif mode in ("izx", "izy"):
        mem = ("ptr", op, True)
    if mnem in LOADS:
        w |= {LOADS[mnem], "Z", "N"}
        mr.append(mem)
    elif mnem in STORES:
        r.add(STORES[mnem])
        mw.append(mem)
    elif mnem in ALU:
        r |= {"A"} | ({"C"} if mnem in ("adc", "sbc") else set())
        w |= {"A", "Z", "N"} | ({"C", "V"} if mnem in ("adc", "sbc") else set())
        if mode != "imm":
            mr.append(mem)
    elif mnem in CMPS:
        r.add(CMPS[mnem])
        w |= {"C", "Z", "N"}
        if mode != "imm":
            mr.append(mem)
    elif mnem == "bit":
        r.add("A")
        w |= {"Z", "N", "V"}
        mr.append(mem)
    elif mnem in SHIFTS:
        if mnem in ("rol", "ror"):
            r.add("C")
        w |= {"C", "Z", "N"}
        if mode == "acc":
            r.add("A")
            w.add("A")
        else:
            mr.append(mem)
            mw.append(mem)
    elif mnem in INCDEC:
        w |= {"Z", "N"}
        mr.append(mem)
        mw.append(mem)
    elif mnem in ("inx", "dex"):
        r.add("X"); w |= {"X", "Z", "N"}
    elif mnem in ("iny", "dey"):
        r.add("Y"); w |= {"Y", "Z", "N"}
    elif mnem in ("tax", "tay"):
        r.add("A"); w |= {"X" if mnem == "tax" else "Y", "Z", "N"}
    elif mnem in ("txa", "tya"):
        r.add("X" if mnem == "txa" else "Y"); w |= {"A", "Z", "N"}
    elif mnem == "tsx":
        w |= {"X", "Z", "N"}
    elif mnem == "txs":
        r.add("X")
    elif mnem == "pha":
        r.add("A")
    elif mnem == "pla":
        w |= {"A", "Z", "N"}
    elif mnem == "php":
        pass                                   # saves the flags: no register is needed for it
    elif mnem == "plp":
        w |= FLAGSET                           # restores flags saved earlier (counted as a write: the flags are not an input of the routine)
    elif mnem in ("clc", "sec"):
        w.add("C")
    elif mnem == "clv":
        w.add("V")
    mr = [m for m in mr if m]
    mw = [m for m in mw if m]
    return r, w, mr, mw


class Rom:
    def __init__(self):
        self.data = load_rom()
        self.code, self.targets = D.trace(self.data, BASE, list(ENTRIES))
        self.ins = {a: D.decode(self.data, BASE, a) for a in self.code}
        jsr = {i[3] for i in self.ins.values() if i[1] == "jsr"}
        self.jsr_targets = jsr
        named = {a for a in LB.ROM_NAMES if a in self.code}
        self.entries = sorted(set(ENTRIES) | {t for t in jsr if t in self.code} | named)
        self.names = {}
        for a in self.entries:
            self.names[a] = LB.ROM_NAMES.get(a) or ENTRIES.get(a) or "Sub_%04X" % a
        for a in LB.OS_ENTRY:
            self.names[a] = LB.OS_ENTRY[a]
        self.data_names = {}
        for first, last, kind, name, comment in LB.DATA:
            for a in range(first, last + 1):
                self.data_names[a] = (name, first)

    def decided(self, a):
        """True / False when the branch at `a` is always / never taken because the flags are known from a load of an immediate (or CLC / SEC) just before it - the idiom `lda #imm / bne label` used as an
        unconditional jump -; None when it depends on the data.  Stores in between do not change the flags; a join point between the load and the branch makes it undecided."""
        n, m, mode, op = self.ins[a]
        if m not in D.BRANCHES or a in self.targets:
            return None
        pos = a
        for _ in range(4):
            prev = [p for p in (pos - 1, pos - 2, pos - 3) if p in self.ins and p + self.ins[p][0] == pos]
            if not prev:
                return None
            p = prev[0]
            pm, pmode, pop = self.ins[p][1], self.ins[p][2], self.ins[p][3]
            if pm in ("sta", "stx", "sty"):
                if p in self.targets:
                    return None
                pos = p
                continue
            COMPLEMENT = {"bne": "beq", "beq": "bne", "bcc": "bcs", "bcs": "bcc", "bmi": "bpl", "bpl": "bmi", "bvc": "bvs", "bvs": "bvc"}
            if pm in COMPLEMENT and COMPLEMENT[pm] == m and pos == a:
                return True                         # `bne x / beq y`: reaching the second branch means the first was not taken, so the second always is
            if pm in ("lda", "ldx", "ldy") and pmode == "imm":
                z, ng = pop == 0, bool(pop & 0x80)
                return {"beq": z, "bne": not z, "bmi": ng, "bpl": not ng}.get(m)
            if pm in ("clc", "sec"):
                return {"bcc": pm == "clc", "bcs": pm == "sec"}.get(m)
            return None
        return None

    def succ(self, a):
        n, m, mode, op = self.ins[a]
        nxt = a + n
        if m in D.BRANCHES:
            d = self.decided(a)
            if d is True:
                return [op]
            if d is False:
                return [nxt]
            return [op, nxt]
        if m == "jmp":
            return [op]
        if m in ("rts", "rti", "brk"):
            return []
        return [nxt]

    def body(self, entry):
        seen, work = set(), [entry]
        while work:
            a = work.pop()
            if a in seen or a not in self.ins:
                continue
            seen.add(a)
            work.extend(self.succ(a))
        return seen

    def mem_name(self, kind, addr, mnem):
        if kind in ("zp", "ptr"):
            return LB.zp_name(addr)
        n = LB.hw_name(addr, mnem)
        if n:
            return n
        if addr in LB.RAM_TABLES:
            return LB.RAM_TABLES[addr]
        if addr in self.data_names:
            name, first = self.data_names[addr]
            return name if addr == first else "%s+%d" % (name, addr - first)
        return "$%04X" % addr


class Func:
    pass


def analyse(rom=None):
    rom = rom or Rom()
    F = {}
    for e in rom.entries:
        f = Func()
        f.entry, f.name = e, rom.names[e]
        f.body = rom.body(e)
        f.calls = {}                                           # call site -> callee entry
        f.loops = set()
        f.exits = collections.Counter()
        f.tail = set()
        f.mem_r, f.mem_w = set(), set()
        f.reg_r, f.reg_w = set(), set()
        for a in f.body:
            n, m, mode, op = rom.ins[a]
            if m == "jsr":
                f.calls[a] = op
            elif m in D.BRANCHES or m == "jmp":
                if op <= a:
                    f.loops.add((a, op))
                if m == "jmp" and op in rom.entries and op != e:
                    f.tail.add(op)
            if m in ("rts", "rti"):
                f.exits[m] += 1
            r, w, mr, mw = effects(m, mode, op)
            for x in mr:
                f.mem_r.add((x[0], x[1], x[2], m))
            for x in mw:
                f.mem_w.add((x[0], x[1], x[2], m))
        F[e] = f
    return rom, F


def solve(rom, F):
    """Fixpoint of the register summaries (inputs, may-write, must-write) and of the observed outputs."""
    for f in F.values():
        f.inputs, f.may, f.must = set(), set(), set()
        f.out = set()
        f.irq = any(rom.ins[a][1] == "rti" for a in f.body)
    changed = True
    rounds = 0
    while changed and rounds < 50:
        changed, rounds = False, rounds + 1
        for f in F.values():
            inp, may, must = summarise(rom, F, f, exit_live=set())
            if f.irq:
                inp = set()                                   # an interrupt handler is entered by the hardware: the registers it pushes are not inputs
            if (inp, may, must) != (f.inputs, f.may, f.must):
                f.inputs, f.may, f.must = inp, may, must
                changed = True
    for f in F.values():
        f.preserved = set()
    changed = True
    rounds = 0
    while changed and rounds < 50:
        changed, rounds = False, rounds + 1
        for f in F.values():
            p = preserved_regs(rom, F, f)
            if p != f.preserved:
                f.preserved = p
                changed = True
    changed = True
    rounds = 0
    while changed and rounds < 50:
        changed, rounds = False, rounds + 1
        obs = collections.defaultdict(set)
        for f in F.values():
            live_after = liveness(rom, F, f, exit_live=f.out)
            for site, callee in f.calls.items():
                if callee in F:
                    nxt = site + rom.ins[site][0]
                    obs[callee] |= live_after.get(nxt, set()) & (F[callee].may - F[callee].preserved)
        for e, f in F.items():
            new = obs.get(e, set())
            if new != f.out:
                f.out = new
                changed = True


def node_use_def(rom, F, a):
    n, m, mode, op = rom.ins[a]
    if m == "jsr":
        c = F.get(op)
        if c is None:                                           # an OS routine: nothing known
            return set(), set(), set()
        return set(c.inputs), set(c.may), set(c.must)
    r, w, mr, mw = effects(m, mode, op)
    if m in BR_FLAG:
        r = {BR_FLAG[m]}
    return r, w, set(w)


def liveness(rom, F, f, exit_live):
    """live-in sets per instruction of f's body (backward, until stable); exits have `exit_live`."""
    live_in = {a: set() for a in f.body}
    order = sorted(f.body, reverse=True)
    changed = True
    while changed:
        changed = False
        for a in order:
            use, may, must = node_use_def(rom, F, a)
            out = set()
            succ = [s for s in rom.succ(a) if s in f.body]
            m = rom.ins[a][1]
            if m in ("rts", "rti"):
                out |= exit_live
            for s in succ:
                out |= live_in[s]
            new = use | (out - must)
            if new != live_in[a]:
                live_in[a] = new
                changed = True
    return live_in


def summarise(rom, F, f, exit_live):
    live_in = liveness(rom, F, f, exit_live)
    may, must_in = set(), {}
    # must-write: forward intersection
    full = set(REGS)
    must_in = {a: set(full) for a in f.body}
    must_in[f.entry] = set()
    changed = True
    order = sorted(f.body)
    exits_must = None
    while changed:
        changed = False
        for a in order:
            use, mw, must = node_use_def(rom, F, a)
            out = must_in[a] | must
            for s in rom.succ(a):
                if s in f.body:
                    new = must_in[s] & out
                    if new != must_in[s]:
                        must_in[s] = new
                        changed = True
    for a in f.body:
        use, mw, must = node_use_def(rom, F, a)
        may |= mw
        if rom.ins[a][1] in ("rts", "rti"):
            out = must_in[a] | must
            exits_must = out if exits_must is None else exits_must & out
    return live_in[f.entry], may, exits_must or set()


def zp_written_closure(F, f):
    """Zero-page addresses a routine or anything it calls may write (indexed writes count as the whole base address and 'ALL')."""
    out, seen, work = set(), set(), [f]
    while work:
        g = work.pop()
        if g.entry in seen:
            continue
        seen.add(g.entry)
        for kind, addr, idx, m in g.mem_w:
            if kind == "zp":
                out.add("ALL" if idx else addr)
            elif kind == "ptr":
                out.add("ALL")
        for c in list(g.calls.values()) + list(g.tail):
            if c in F:
                work.append(F[c])
    return out


def preserved_regs(rom, F, f):
    """Registers (A, X, Y) whose value at every exit equals their value at the entry, also when they are saved in a zero-page byte or on the stack and loaded back."""
    unk = None
    start = {"A": "eA", "X": "eX", "Y": "eY"}
    init = (tuple(sorted(start.items())), (), ())
    state_in = {f.entry: init}
    work = [f.entry]
    exits = []

    def join(a, b):
        ra, sa, za = dict(a[0]), a[1], dict(a[2])
        rb, sb, zb = dict(b[0]), b[1], dict(b[2])
        regs = {k: (ra[k] if ra[k] == rb.get(k) else unk) for k in ra}
        stack = sa if sa == sb else tuple(x if x == y else unk for x, y in zip(sa, sb)) if len(sa) == len(sb) else ()
        zs = {k: v for k, v in za.items() if zb.get(k) == v}
        return (tuple(sorted(regs.items())), stack, tuple(sorted(zs.items(), key=lambda kv: str(kv[0]))))
    while work:
        a = work.pop()
        regs, stack, zs = dict(state_in[a][0]), list(state_in[a][1]), dict(state_in[a][2])
        n, m, mode, op = rom.ins[a]
        if m == "jsr":
            c = F.get(op)
            wz = zp_written_closure(F, c) if c else {"ALL"}
            for r in ("A", "X", "Y"):
                if not c or r not in c.preserved:
                    regs[r] = unk
            if "ALL" in wz:
                zs = {}
            else:
                zs = {k: v for k, v in zs.items() if k not in wz}
        elif m in LOADS:
            regs[LOADS[m]] = zs.get(op) if mode == "zp" else unk
        elif m in STORES:
            if mode == "zp":
                zs[op] = regs[STORES[m]]
            elif mode in ("zpx", "zpy", "izx", "izy"):
                zs = {}
        elif m in ALU or (m in SHIFTS and mode == "acc"):
            regs["A"] = unk
        elif m in SHIFTS or m in INCDEC:
            if mode == "zp":
                zs[op] = unk
            elif mode in ("zpx", "zpy"):
                zs = {}
        elif m in ("inx", "dex"):
            regs["X"] = unk
        elif m in ("iny", "dey"):
            regs["Y"] = unk
        elif m == "tax":
            regs["X"] = regs["A"]
        elif m == "tay":
            regs["Y"] = regs["A"]
        elif m == "txa":
            regs["A"] = regs["X"]
        elif m == "tya":
            regs["A"] = regs["Y"]
        elif m == "tsx":
            regs["X"] = unk
        elif m == "pha":
            stack.append(regs["A"])
        elif m == "pla":
            regs["A"] = stack.pop() if stack else unk
        elif m == "plp" or m == "php" or m == "txs":
            pass
        if m in ("rts", "rti"):
            exits.append(regs)
            continue
        cur = (tuple(sorted(regs.items())), tuple(stack), tuple(sorted(zs.items(), key=lambda kv: str(kv[0]))))
        for t in rom.succ(a):
            if t not in f.body:
                continue
            new = cur if t not in state_in else join(state_in[t], cur)
            if state_in.get(t) != new:
                state_in[t] = new
                work.append(t)
    if not exits:
        return set()
    return {r for r in ("A", "X", "Y") if all(e[r] == "e" + r for e in exits)}


def closure(F, f, attr):
    out, work, seen = set(getattr(f, attr)), [f], {f.entry}
    while work:
        g = work.pop()
        for callee in list(g.calls.values()) + list(g.tail):
            if callee in F and callee not in seen:
                seen.add(callee)
                out |= set(getattr(F[callee], attr))
                work.append(F[callee])
    return out


def fmt_regs(s):
    order = "AXYCZNV"
    return " ".join(x for x in order if x in s) or "-"


def mem_names(rom, items, indexed_mark=True):
    names = set()
    for kind, addr, idx, m in items:
        nm = rom.mem_name(kind, addr, m)
        if kind == "ptr":
            nm = "(%s),y" % nm if m else nm
        elif idx:
            nm += ",idx"
        names.add(nm)
    return sorted(names)


def report(rom, F):
    callers = collections.defaultdict(set)
    for e, f in F.items():
        for site, c in f.calls.items():
            callers[c].add(e)
    L = []
    P = L.append
    P("# 23 - The Function Table (stages 33-40, 43)")
    P("")
    P("GENERATED by `python -I tools/analyze_functions.py --write docs/23-function-table.md` from the same trace as `src/asm/pacman.s`; do not edit by hand. Tests: `tests/test_functions.py`.")
    P("")
    P("**%d routines** (%d JSR targets, the cartridge and interrupt entry points and every named routine that is code), %d instructions, %d bytes of code. No indirect jump exists in the ROM and the stack is used only by JSR/RTS, the interrupt handlers and one `TXS` at start." %
      (len(F), len(rom.jsr_targets), len(rom.ins), sum(v[0] for v in rom.ins.values())))
    P("")
    P("## How to read the table")
    P("")
    P("- **in**: registers and flags the routine reads before it has written them (its inputs); **clobbers**: what it may change, including through its callees, and does not give back; **saves and restores**: A, X or Y that it changes but restores (in a zero-page byte or on the stack) before every return; **out**: what at least one caller still needs after the call (the return value). A flag in `out` is a result in the flags (for example `C` after a lookup, or `Z` after a compare). Registers and flags that are neither in `in` nor in `clobbers` are preserved.")
    P("- **reads / writes**: the zero-page variables, tables, RAM and hardware registers the routine itself touches (callees not included; `,idx` = indexed, `(name),y` = through the pointer pair at `name`). **calls**: callees; **tail**: routines it jumps into (their code is part of this routine).")
    P("- **loops**: backward branches (a loop each). **exits**: RTS / RTI instructions.")
    P("")
    # statistics for the convention
    st = collections.Counter()
    for f in F.values():
        for r in f.inputs & {"A", "X", "Y"}:
            st["in " + r] += 1
        for r in f.out & {"A", "X", "Y"}:
            st["out " + r] += 1
        if f.out & FLAGSET:
            st["out flags"] += 1
        if f.inputs & FLAGSET:
            st["in flags"] += 1
        if not f.inputs:
            st["no register input"] += 1
    P("## The calling convention (stage 39)")
    P("")
    P("There is one convention and it is not written anywhere in the ROM; it follows from the %d routines below:" % len(F))
    P("")
    P("- **No parameters on the stack.** Arguments go in **A, X, Y** and in **zero-page variables** (the pointers `SrcPtr` / `DstPtr`, `CurrentPlayer`, the shared tables indexed by X); results come back in **A, X, Y, the flags (C, Z, N)** and in memory. Routines are not re-entrant in general (shared scratch zero page).")
    P("- **X is the entity index** (ghost 0-3, Pac-Man 4) in the per-entity routines (`StepAndDrawEntity`, `GhostBehaviour`, `SteerToTarget`, `GhostSeesPacMan`, ...) and the player index in the per-player ones; the per-entity variables are arrays indexed by it (`EntityX,x`, `GhostState,x`, ...).")
    keepX = sum(1 for f in F.values() if "X" in (f.may & f.preserved))
    keepY = sum(1 for f in F.values() if "Y" in (f.may & f.preserved))
    keepA = sum(1 for f in F.values() if "A" in (f.may & f.preserved))
    P("- **No register is preserved by convention.** A routine that changes a register and gives it back is marked 'saves and restores' (%d routines for X - mostly the per-entity routines that loop over ghosts -, %d for Y, %d for A: in a zero-page byte, or on the stack by `PHA ... PLA` in the interrupt handlers); every other routine may change A, X, Y and the flags, and a caller that needs a register after a call saves it itself." % (keepX, keepY, keepA))
    P("- Counts over the %d routines: input A %d, X %d, Y %d, flags %d; result in A %d, X %d, Y %d, flags %d; %d routines read no register at entry." %
      (len(F), st["in A"], st["in X"], st["in Y"], st["in flags"], st["out A"], st["out X"], st["out Y"], st["out flags"], st["no register input"]))
    P("")
    P("## The call tree (stage 36, 40)")
    P("")
    P("From the entry points (`Start` is the cartridge RUN entry and the main loop and never returns; `VBI` is the deferred vertical-blank handler; `DLI1`, `DLI2` the display-list interrupts). A routine already shown is marked `...`.")
    P("")
    P("```")
    shown = set()

    def tree(e, depth, prefix):
        f = F[e]
        callee_list = []
        for site in sorted(f.calls):
            c = f.calls[site]
            if c in F and c not in callee_list:
                callee_list.append(c)
        for t in sorted(f.tail):
            if t not in callee_list:
                callee_list.append(t)
        P("%s%s%s" % ("  " * depth, f.name, "" if e not in shown or not callee_list else "  ..."))
        if e in shown:
            return
        shown.add(e)
        for c in callee_list:
            tree(c, depth + 1, prefix)
    for e in ENTRIES:
        tree(e, 0, "")
    P("```")
    P("")
    unreached = [e for e in F if e not in shown]
    if unreached:
        P("Routines not reached from those five entry points by calls or tail jumps (reached by fall-through or a branch only): %s." % ", ".join(F[e].name for e in unreached))
        P("")
    P("## The routines")
    P("")
    for e in sorted(F):
        f = F[e]
        size = sum(rom.ins[a][0] for a in f.body)
        P("### %s  `$%04X`  (%d bytes in the body)" % (f.name, e, size))
        P("")
        P("- in: %s  |  clobbers: %s  |  out: %s%s" % (fmt_regs(f.inputs), fmt_regs(f.may - f.preserved), fmt_regs(f.out), ("  |  saves and restores: " + fmt_regs(f.may & f.preserved)) if f.may & f.preserved else ""))
        cs = sorted({F[c].name for c in f.calls.values() if c in F} | {rom.names.get(c, "$%04X" % c) for c in f.calls.values() if c not in F})
        P("- calls: %s%s  |  called by: %s" % (", ".join(cs) or "-", ("  |  tail: " + ", ".join(sorted(F[t].name for t in f.tail))) if f.tail else "", ", ".join(sorted(F[c].name for c in callers.get(e, []))) or "(entry point)"))
        P("- loops: %d  |  exits: %s" % (len(f.loops), ", ".join("%d %s" % (v, k.upper()) for k, v in sorted(f.exits.items())) or "none (does not return)"))
        rn = mem_names(rom, f.mem_r)
        wn = mem_names(rom, f.mem_w)
        P("- reads: %s" % (", ".join(rn) or "-"))
        P("- writes: %s" % (", ".join(wn) or "-"))
        P("")
    return L


def main():
    rom, F = analyse()
    solve(rom, F)
    L = report(rom, F)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        path = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", path, len(F), "routines,", len(txt), "bytes")
    else:
        print(txt)


if __name__ == "__main__":
    main()
