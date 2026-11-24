"""Stage 42: the local variables of the Pac-Man ROM.

The 6502 has no stack frames: a routine's 'locals' are zero-page bytes, registers, and the few values it pushes.  This tool finds, by data-flow analysis of the same trace as src/asm/pacman.s, which zero-page
bytes behave as local variables of which routine, so that the C re-implementation can turn them into automatic variables (`int x;` inside the function) and keep the others as state (`static` or a field of the
game-state structure).

Method (zero-page bytes; an indexed access reaches the whole variable (array) it belongs to, an indexed write is only a 'may' write, a (zp),y access reads the pointer pair):
  UE(f)   upward-exposed reads of routine f = the bytes f (or a routine it calls) reads before it has written them on some path from its entry.  A byte in UE(f) carries a value INTO f.
  EL(f)   live after the return of f = the bytes some caller still reads after `JSR f` (liveness at every call site, iterated until stable).  The entry points, the interrupt handlers and a routine nobody
          calls by JSR have EL = every byte that some routine reads before it writes it (the code that runs next is not known); `Start` never returns.
  A byte that f writes and that is neither in UE(f) nor in EL(f) is a TEMPORARY of f: its value is born and dies inside one call.  If a routine that f calls reads it, it is an ARGUMENT slot (passed by
  the zero page); otherwise it is a plain local.  A byte of a variable that only one routine touches is STATIC when it is in UE (it keeps its value from one call to the next) and TEMPORARY otherwise.
  OS variables (the OS reads them) are never temporaries.
Usage: python -I tools/analyze_locals.py [--write docs/27-local-variables.md]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402
import analyze_relationships as AR  # noqa: E402
import analyze_variables as V  # noqa: E402
import labels as LB  # noqa: E402

ROOT = AF.ROOT
ALL = frozenset(range(256))
EMPTY = frozenset()

GROUP = {}
for _first, _n, _name, _kind, *_rest in V.ZP:
    for _b in range(_first, _first + _n):
        GROUP[_b] = (_first, _n)
VAR = {first: (n, name, kind, role) for first, n, name, kind, role, ev in V.ZP}


def group(b):
    first, n = GROUP.get(b, (b, 1))
    return set(range(first, first + n))


def access(m, mode, op):
    """(use, may, must) zero-page byte sets of one instruction that is not a JSR."""
    r, w, mr, mw = AF.effects(m, mode, op)
    use, may, must = set(), set(), set()
    for kind, addr, idx in mr:
        if kind == "ptr":
            use |= {addr, addr + 1}
        elif addr < 0x100:
            use |= group(addr) if idx else {addr}
    for kind, addr, idx in mw:
        if kind == "ptr":
            use |= {addr, addr + 1}
        elif addr < 0x100:
            if idx:
                may |= group(addr)
            else:
                may.add(addr)
                must.add(addr)
    return frozenset(use), frozenset(may), frozenset(must)


class Analysis:
    def __init__(self):
        self.rom, self.F, self.acc, self.areas = V.build()
        rom, F = self.rom, self.F
        self.node0 = {a: access(m, mode, op) for a, (n, m, mode, op) in rom.ins.items() if m != "jsr"}
        self.UE = {e: EMPTY for e in F}
        self.MAY = {e: EMPTY for e in F}
        self.MUST = {e: EMPTY for e in F}
        changed, rounds = True, 0
        while changed and rounds < 60:
            changed, rounds = False, rounds + 1
            for e, f in F.items():
                ue = self.live(f, EMPTY)[e]
                may = self.may_of(f)
                must = self.must_of(f)
                if (ue, may, must) != (self.UE[e], self.MAY[e], self.MUST[e]):
                    self.UE[e], self.MAY[e], self.MUST[e] = ue, may, must
                    changed = True
        # the code that runs after a routine nobody calls (the main loop, the interrupts) is not known: assume it may read every byte that some routine reads before it writes it
        self.READ_ANYWHERE = frozenset().union(*self.UE.values())
        callers = collections.defaultdict(list)
        for e, f in F.items():
            for site, c in f.calls.items():
                if c in F:
                    callers[c].append((e, site))
        self.EL = {}
        for e, f in F.items():
            noexit = not any(rom.ins[a][1] in ("rts", "rti") or (rom.ins[a][1] == "jmp" and rom.ins[a][3] not in f.body) for a in f.body)
            if noexit:
                self.EL[e] = EMPTY
            elif e in AF.ENTRIES or not callers[e]:
                self.EL[e] = self.READ_ANYWHERE
            else:
                self.EL[e] = EMPTY
        changed, rounds = True, 0
        while changed and rounds < 60:
            changed, rounds = False, rounds + 1
            for e, f in F.items():
                lv = self.live(f, self.EL[e])
                for site, c in f.calls.items():
                    if c in F and c in self.EL:
                        nxt = site + rom.ins[site][0]
                        new = self.EL[c] | lv.get(nxt, EMPTY)
                        if new != self.EL[c]:
                            self.EL[c] = new
                            changed = True

    def node(self, a):
        n, m, mode, op = self.rom.ins[a]
        if m == "jsr":
            c = self.F.get(op)
            if c is None:
                return EMPTY, EMPTY, EMPTY
            return self.UE[op], self.MAY[op], self.MUST[op]
        return self.node0[a]

    def is_exit(self, f, a):
        n, m, mode, op = self.rom.ins[a]
        return m in ("rts", "rti") or (m == "jmp" and op not in f.body)

    def live(self, f, exit_live):
        body = f.body
        li = {a: EMPTY for a in body}
        order = sorted(body, reverse=True)
        changed = True
        while changed:
            changed = False
            for a in order:
                use, may, must = self.node(a)
                out = set(exit_live) if self.is_exit(f, a) else set()
                for s in self.rom.succ(a):
                    if s in body:
                        out |= li[s]
                new = frozenset(use | (out - must))
                if new != li[a]:
                    li[a], changed = new, True
        return li

    def may_of(self, f):
        out = set()
        for a in f.body:
            out |= self.node(a)[1]
        return frozenset(out)

    def must_of(self, f):
        body = f.body
        mi = {a: ALL for a in body}
        mi[f.entry] = EMPTY
        changed = True
        while changed:
            changed = False
            for a in sorted(body):
                out = mi[a] | self.node(a)[2]
                for s in self.rom.succ(a):
                    if s in body and s != f.entry:
                        new = mi[s] & out
                        if new != mi[s]:
                            mi[s], changed = new, True
        res = ALL
        for a in body:
            if self.is_exit(f, a):
                res = res & (mi[a] | self.node(a)[2])
        return frozenset(res)

    # ---- classification
    def direct(self, f):
        """bytes the routine's own instructions (callees excluded) read / write."""
        use, may = set(), set()
        for a in f.body:
            if self.rom.ins[a][1] != "jsr":
                u, mw, mu = self.node0[a]
                use |= u
                may |= mw
        return use, may

    def callee_reads(self, f):
        out = set()
        for c in f.calls.values():
            if c in self.F:
                out |= self.UE[c]
        return out


def build():
    A = Analysis()
    rom, F = A.rom, A.F
    sub = {F[e].name: AR.ROLE[e][0] for e in F}
    # per variable: scope as in the catalogue
    variables = []
    for first, n, name, kind, role, ev in V.ZP:
        r, w = V.group_access(A.acc, first, n)
        touch = set(r) | set(w)
        variables.append((first, n, name, kind, role, ev, touch))
    by_name = {F[e].name: e for e in F}
    # classification per (routine, variable)
    isr_entries = [e for e in F if F[e].irq or F[e].name == "VbiHandler"]
    isr_vis = set()
    for e in isr_entries:
        isr_vis |= A.UE[e]
    temp = collections.defaultdict(dict)       # routine entry -> {var first: 'TEMP' | 'ARG'}
    dead = collections.defaultdict(list)       # routine entry -> [var first]: written, never read by the routine, not needed afterwards
    carry = collections.defaultdict(dict)      # routine entry -> {var first: 'in' | 'out' | 'in/out' | 'shared'}
    for e, f in F.items():
        use, may = A.direct(f)
        crd = A.callee_reads(f)
        for first, n, name, kind, role, ev, touch in variables:
            if kind == "OS":
                continue
            bytes_ = set(range(first, first + n))
            mine = bytes_ & (use | may)
            if not mine:
                continue
            if not (bytes_ & may):
                carry[e][first] = "in"                 # only read here
                continue
            ue = bool(bytes_ & A.UE[e])
            el = bool(bytes_ & A.EL[e] & A.MAY[e])
            shared = bool(bytes_ & isr_vis) and e not in isr_entries
            if ue or el or shared:
                carry[e][first] = "in/out" if ue and el else "in" if ue else "out" if el else "shared with the interrupts"
            elif bytes_ & (use | crd):
                temp[e][first] = "ARG" if bytes_ & crd else "TEMP"
            else:
                dead[e].append(first)
    # single-routine variables
    singles = []
    for first, n, name, kind, role, ev, touch in variables:
        if len(touch) != 1:
            continue
        owner = by_name[next(iter(touch))]
        bytes_ = set(range(first, first + n))
        if kind == "OS":
            cls = "OS"
        elif bytes_ & A.UE[owner]:
            cls = "STATIC"
        elif first in temp[owner]:
            cls = "TEMP"
        elif first in dead[owner]:
            cls = "DEAD"
        else:
            cls = "STATIC"
        singles.append((first, n, name, kind, role, ev, owner, cls))
    return A, variables, temp, carry, singles, sub, dead


def vname(first):
    return VAR[first][1]


def report(A, variables, temp, carry, singles, sub, dead):
    rom, F = A.rom, A.F
    L = []
    P = L.append
    P("# 27 - The Local Variables (stage 42)")
    P("")
    P("GENERATED by `python -I tools/analyze_locals.py --write docs/27-local-variables.md` from the trace of `src/asm/pacman.s`, the routines of `23-function-table.md` and the variables of `25-variable-catalogue.md`. Tests: `tests/test_locals.py`.")
    P("")
    P("## 1. What a local variable is on this machine")
    P("")
    P("The 6502 has no frames and no locals. A routine keeps what it needs in **registers** (A, X, Y; their roles are in `23`, stage 43), in **zero-page bytes** used as scratch, and, rarely, on the **hardware stack** (`PHA` / `PHP` / `TXS`, see section 5). Zero-page scratch is shared: the same byte is a temporary in one routine and a stored value in another. For the C port the question is therefore not 'which names are local' but **which bytes carry a value only inside one call** (an automatic variable) and which **carry it from one call to the next** (a `static` or a field of the game-state structure).")
    P("")
    P("Per routine f, from the data flow of the code (details in `tools/analyze_locals.py`):")
    P("")
    P("- **in**: f reads the byte before writing it on some path (its value comes from before the call: a parameter or kept state);")
    P("- **out**: f writes it and a caller still reads it after the call (a result or kept state);")
    P("- **TEMPORARY**: f writes it, it is not *in* and not *out*: born and dead inside one call, an automatic variable of f. **ARGUMENT** is a temporary that a routine called by f reads (the zero page used to pass a value, like `SrcPtr`).")
    P("")
    P("The entry points, the interrupt handlers and a routine that nobody calls with `JSR` are treated as if every byte that some routine reads before writing it is read after them; `Start` never returns. The bytes the interrupt handlers read are also never temporaries of the main program, because an interrupt can come at any instruction.")
    P("")
    nt = sum(1 for x in singles if x[7] == "TEMP")
    ns = sum(1 for x in singles if x[7] == "STATIC")
    no = sum(1 for x in singles if x[7] == "OS")
    nd = sum(1 for x in singles if x[7] == "DEAD")
    P("## 2. Variables touched by one routine only (the LOCAL variables of `25`)")
    P("")
    P("%d variables: **%d TEMPORARY** (an automatic variable of the owner), **%d STATIC** (read before it is written: it keeps its value from one call to the next, so it is state of the owner and, in C, a `static` or a field of the state structure), %d OS (the OS also reads it), %d DEAD (written and never read)." % (len(singles), nt, ns, no, nd))
    P("")
    P("| Address | Name | Size | Kind | Owner | Class | Role |")
    P("|---|---|---|---|---|---|---|")
    for first, n, name, kind, role, ev, owner, cls in singles:
        addr = "$%02X" % first if n == 1 else "$%02X-$%02X" % (first, first + n - 1)
        P("| `%s` | %s | %d | %s | %s | **%s** | %s |" % (addr, name, n, kind, F[owner].name, cls, role))
    P("")
    P("## 3. Shared bytes that are temporaries in some routines")
    P("")
    P("Variables touched by two or more routines (GLOBAL in `25`) that are, in at least one routine, born and dead inside one call. In the C port each such use can be a local of that routine; the variable itself stays global for the routines in the last column, which keep a value in it across calls or pass it on.")
    P("")
    P("| Variable | Kind | Temporary (or argument slot, `ARG`) in | Carries a value in / out of |")
    P("|---|---|---|---|")
    singles_set = {x[0] for x in singles}
    tmp_by_var = collections.defaultdict(dict)
    car_by_var = collections.defaultdict(dict)
    for e, d in temp.items():
        for first, c in d.items():
            tmp_by_var[first][e] = c
    for e, d in carry.items():
        for first, c in d.items():
            car_by_var[first][e] = c
    rows3 = 0
    for first, n, name, kind, role, ev, touch in variables:
        if first in singles_set or not tmp_by_var.get(first):
            continue
        rows3 += 1
        tl = ", ".join("%s%s" % (F[e].name, " (ARG)" if c == "ARG" else "") for e, c in sorted(tmp_by_var[first].items(), key=lambda kv: F[kv[0]].name))
        cl = ", ".join("%s (%s)" % (F[e].name, c) for e, c in sorted(car_by_var.get(first, {}).items(), key=lambda kv: F[kv[0]].name))
        P("| %s | %s | %s | %s |" % (name, kind, tl, cl or "-"))
    P("")
    P("### Writes that nothing reads")
    P("")
    P("A routine that writes a byte which neither it nor a routine it calls reads, and which no caller reads before rewriting it, is an initialisation or a store whose value is not used there. It is **not** a local variable; it is listed so that the port does not mistake it for one (if it is dead in the port it can be dropped, but the equivalence tests compare the RAM, so keep it until they say otherwise).")
    P("")
    dl = [(F[e].name, ", ".join(vname(k) for k in sorted(v))) for e, v in sorted(dead.items(), key=lambda kv: F[kv[0]].name) if v]
    for nm, vs in dl:
        P("- %s: %s" % (nm, vs))
    if not dl:
        P("- none")
    P("")
    P("## 4. The locals of every routine")
    P("")
    P("For each routine: the zero-page variables that are **temporaries** of it (own use, section 3 and 2), the variables it **owns as state** (STATIC, section 2) and the stack and register spills (section 5). A routine without an entry has no zero-page local: it works in registers and on global state.")
    P("")
    P("| Routine | Temporaries | Argument slots | Owned state (STATIC) | Stack |")
    P("|---|---|---|---|---|")
    own = collections.defaultdict(list)
    for first, n, name, kind, role, ev, owner, cls in singles:
        own[owner].append((name, cls))
    stack_use = {}
    for e, f in F.items():
        c = collections.Counter(rom.ins[a][1] for a in f.body if rom.ins[a][1] in ("pha", "pla", "php", "plp", "txs", "tsx"))
        stack_use[e] = c
    n_with = 0
    for e in sorted(F, key=lambda e: F[e].name):
        f = F[e]
        t = sorted(vname(k) for k, c in temp[e].items() if c == "TEMP")
        ar = sorted(vname(k) for k, c in temp[e].items() if c == "ARG")
        st = sorted(name for name, cls in own.get(e, []) if cls == "STATIC")
        sk = stack_use[e]
        stk = ", ".join("%d %s" % (v, k.upper()) for k, v in sorted(sk.items())) if sk else "-"
        if t or ar or st or sk:
            n_with += 1
        P("| %s | %s | %s | %s | %s |" % (f.name, ", ".join(t) or "-", ", ".join(ar) or "-", ", ".join(st) or "-", stk))
    P("")
    P("%d of the %d routines have a zero-page temporary, an argument slot, owned state or a stack use." % (n_with, len(F)))
    P("")
    P("## 5. Locals on the stack and in saved registers")
    P("")
    users = [(F[e].name, stack_use[e]) for e in sorted(F, key=lambda e: F[e].name) if stack_use[e]]
    P("The hardware stack holds the return addresses of `JSR` and the interrupt frames; routines push their own values in only these places (`PHA` / `PHP` pairs; `TXS` / `TSX` change the stack pointer): %s." %
      "; ".join("%s (%s)" % (n, ", ".join("%d %s" % (v, k.upper()) for k, v in sorted(c.items()))) for n, c in users))
    P("")
    P("The registers a routine changes but gives back (the 'saves and restores' of `23`, in a zero-page byte or on the stack) are locals in the C sense: `%s`." % "`, `".join("%s: %s" % (F[e].name, "".join(sorted(F[e].may & F[e].preserved))) for e in sorted(F, key=lambda e: F[e].name) if F[e].may & F[e].preserved))
    P("")
    P("## 6. What the port does with this")
    P("")
    P("- **TEMPORARY** (sections 2 and 3): an automatic variable declared in the C function that corresponds to the routine; the zero-page byte is not needed.")
    P("- **ARGUMENT**: a parameter of the C function, or a local that is passed down; the zero page was only the transport.")
    P("- **STATIC**: a field of the game-state structure (or a `static`), initialised to the value the zero page has at power-on and reset by the same code that resets it on the 6502.")
    P("- **Everything else** (the GLOBAL variables of `25`) stays a field of the game state; the byte-exact equivalence tests of stages 86-87 compare those.")
    P("- Interrupt handlers (`VbiHandler`, `DliHandler1`, `DliHandler2`) share no temporaries with the main program in this analysis; where a shared scratch byte is used in both, section 3 lists the routines separately and the port must keep them apart.")
    P("")
    return L


def main():
    txt = "\n".join(report(*build())) + "\n"
    if "--write" in sys.argv:
        path = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", path, len(txt), "bytes")
    else:
        print(txt)


if __name__ == "__main__":
    main()
