"""Stage 58, proof of the transition rules: an ABSTRACT interpreter of the Pac-Man ROM (the traced code of tools/analyze_stack.py) that follows a chosen set of state variables exactly and treats every other byte of memory
and every hardware input as UNKNOWN, and a reachability search over it.  Because everything not followed is unknown, every branch on it is taken both ways, so the search covers all behaviours of the code for any
contents of the untracked memory (a sound over-approximation); a state variable value or a store that the search does not reach cannot happen in the game.

The model of the machine (the assumptions, each stated in docs/34-state-transitions.md):
  * two threads: the MAIN LOOP (the key loop of `Start` from $A477 on, with the restart and every routine it calls) and the VERTICAL-BLANK handler ($A5FD, atomic, enters at any instruction boundary of the main loop);
    the display-list interrupts and the OS's own vertical-blank code do not write any state variable (no write to one by an address outside the game's code was seen: analysis/evidence-states-summary.txt);
  * the only stores to followed variables are the instructions of the code with a zero-page / absolute operand (the indirect stores `(zp),y` point to RAM pages from $0200 on and to nothing in the zero page: docs/29);
  * RAM $0600-$07FF is a table that is never written after the expansion of `Start` (checked on the code: `tests/test_absint.py`) and is read as the constants the expansion makes.
A routine that neither reads nor writes a followed variable (checked on its code and its callees) is skipped as a whole (partial-order reduction: its effect on the followed state is nil), with every register unknown after it.
The abstract values are a byte or None (unknown); flags are 0, 1 or None.  After `cmp #imm / beq` on an unknown register the register is known to equal imm on the equal path.
Usage as a library (tools/prove_state_rules.py, tests/test_absint.py).
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_stack as AS  # noqa: E402

ROOT = os.path.dirname(HERE)
with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as _fh:
    ROM = _fh.read()
BASE = 0xA000
OS_EXIT = 0xC000
SPIN_LO, SPIN_HI = 0xA4BA, 0xA52F              # the polling loops of the key loop (the debounce reads of CONSOL included)
VBI_ENTRY = 0xA5FD
MAIN_ENTRY = 0xA477
BRANCH = {"bpl": ("n", 0), "bmi": ("n", 1), "bvc": ("v", 0), "bvs": ("v", 1), "bcc": ("c", 0), "bcs": ("c", 1), "bne": ("z", 0), "beq": ("z", 1)}
IDX = {"n": 4, "z": 5, "c": 6, "v": 7}
# state tuple: (pc, a, x, y, n, z, c, v, d, stack, T, cr)
PC, A, X, Y, N, Z, C, V, D, STK, T, CR = range(12)


# routines whose results (a known A / X after the call) reach followed variables: executed, not skipped (ClearPlayerMemory returns A = 0, which InitBoard stores over $80-$FF)
NO_SKIP = set()


class Program:
    def __init__(self):
        rom, F, owner = AS.load()
        self.rom, self.F, self.owner = rom, F, owner
        self.ins = rom.ins
        self.tables = {}                                        # $0600-$07FF as the expansion of Start builds it (a constant after Start)
        import decode_streams as DS
        nib, _ = DS.split_nibbles(0xBE95)
        for k in range(512):
            self.tables[0x0600 + k] = nib[k]
        self._touch = {}

    # ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def touches(self, entry, tracked):
        """does the routine or one of its callees read or write a followed variable (conservatively: any zero-page indexed access)?"""
        key = (entry, frozenset(tracked))
        if key in self._touch:
            return self._touch[key]
        self._touch[key] = True                                  # a cycle counts as touching (there is none: no recursion)
        f = self.F[entry]
        res = False
        for a in f.body:
            n, m, mode, op = self.ins[a]
            if not isinstance(op, int) or m in ("jsr", "jmp") or mode in ("imm", "imp", "acc", "rel"):
                continue
            if mode == "zp" or (mode == "abs" and op < 0x100):
                if op in tracked:
                    res = True
                    break
            elif mode == "zpx":
                res = True                                       # any zero-page byte may be addressed
                break
            elif mode in ("abx", "aby") and op < 0x100:
                res = True
                break
        if not res:
            for c in list(f.calls) + list(f.tail):
                if c in self.F and self.touches(c, tracked):
                    res = True
                    break
        self._touch[key] = res
        return res

    def skippable(self, tracked):
        return {e for e in self.F if not self.touches(e, tracked)}


class Machine:
    """the abstract machine for one set of followed variables"""

    def __init__(self, prog, tracked, skip=True):
        self.p = prog
        self.addrs = list(tracked)
        self.idx = {a: i for i, a in enumerate(self.addrs)}
        self.trackset = set(self.addrs)
        self.skip = (prog.skippable(self.trackset) - NO_SKIP) if skip else set()
        self.havoc_count = 0
        self.havoc_pcs = {}
        self.vbi_cache = {}
        self.summ = {}

    def window(self, base):
        """a table read with an unknown index: the set of the bytes of the window [base, base + 255] when it lies in the ROM or in the table area (one value: that value), else unknown"""
        if BASE <= base and base + 255 < 0xC000:
            vals = {ROM[a - BASE] for a in range(base, base + 256)}
        elif 0x0600 <= base and base + 255 <= 0x07FF:
            vals = {self.p.tables[a] for a in range(base, base + 256)}
        else:
            return None
        return next(iter(vals)) if len(vals) == 1 else frozenset(vals)

    # ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def read(self, T, mode, op, x, y):
        """-> value or None (a set of possible values counts as unknown)"""
        v = self.read_raw(T, mode, op, x, y)
        return None if isinstance(v, frozenset) else v

    def read_raw(self, T, mode, op, x, y):
        """-> value, None, or a frozenset of the possible values (a table read with an unknown index)"""
        if mode == "imm":
            return op
        if mode in ("zp",):
            addr = op
        elif mode == "abs":
            addr = op
        elif mode == "zpx":
            if x is None:
                return None
            addr = (op + x) & 0xFF
        elif mode == "abx":
            if x is None:
                return self.window(op)
            addr = op + x
        elif mode == "aby":
            if y is None:
                return self.window(op)
            addr = op + y
        else:                                                      # izy: a pointer into RAM pages or ROM tables: unknown
            return None
        if addr in self.idx:
            return T[self.idx[addr]]
        if BASE <= addr < 0xC000:
            return ROM[addr - BASE]
        if 0x0600 <= addr <= 0x07FF:
            return self.p.tables.get(addr)
        return None

    def write(self, T, mode, op, x, y, value, pc, events):
        """-> new T; records the stores to followed variables"""
        if mode in ("zp", "abs"):
            addrs = [op]
        elif mode == "zpx":
            addrs = None if x is None else [(op + x) & 0xFF]
        elif mode == "abx":
            addrs = None if x is None else [op + x]
        elif mode == "aby":
            addrs = None if y is None else [op + y]
        else:
            return T                                               # izy: RAM pages (docs/29), never a followed variable
        if addrs is None:
            if mode == "zpx" or op < 0x100:
                self.havoc_count += 1
                self.havoc_pcs[pc] = self.havoc_pcs.get(pc, 0) + 1
                lst = list(T)
                for i, a in enumerate(self.addrs):
                    if lst[i] is not None:
                        events.add((a, pc, lst[i], None))
                    lst[i] = None
                return tuple(lst)
            return T
        a = addrs[0]
        if a in self.idx:
            i = self.idx[a]
            old = T[i]
            lst = list(T)
            lst[i] = value
            events.add((a, pc, old, value))
            return tuple(lst)
        return T

    # ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def step(self, st, events, in_vbi):
        """one instruction: the list of successor states; the tuple 'EXIT' for the jump to the OS that ends the vertical-blank handler"""
        pc, a, x, y, n, z, c, v, d, stk, T, cr = st
        ln, m, mode, op = self.p.ins[pc]
        nxt = pc + ln
        if m not in ("cmp", "cpx", "cpy"):
            if isinstance(a, frozenset):
                a = None
            if isinstance(x, frozenset):
                x = None
            if isinstance(y, frozenset):
                y = None
        # ---- loads and stores -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        if m in ("lda", "ldx", "ldy"):
            val = self.read_raw(T, mode, op, x, y)
            n2 = None if val is None or isinstance(val, frozenset) else val >> 7
            z2 = None if val is None or isinstance(val, frozenset) else int(val == 0)
            zr = {"lda": "a", "ldx": "x", "ldy": "y"}[m]
            ncr = (zr, 0, "z") if val is None else None
            if isinstance(val, frozenset):
                ncr = (zr, 0, "z") if 0 in val else None                    # a set without 0: the Z flag is known to be 0 (no refinement needed)
                z2 = 0 if 0 not in val else None
            if m == "lda":
                return [(nxt, val, x, y, n2, z2, c, v, d, stk, T, ncr)]
            if m == "ldx":
                return [(nxt, a, val, y, n2, z2, c, v, d, stk, T, ncr)]
            return [(nxt, a, x, val, n2, z2, c, v, d, stk, T, ncr)]
        if m in ("sta", "stx", "sty"):
            val = {"sta": a, "stx": x, "sty": y}[m]
            T2 = self.write(T, mode, op, x, y, val, pc, events)
            return [(nxt, a, x, y, n, z, c, v, d, stk, T2, cr)]
        if m in ("tax", "tay", "txa", "tya"):
            src = {"tax": a, "tay": a, "txa": x, "tya": y}[m]
            n2 = None if src is None else src >> 7
            z2 = None if src is None else int(src == 0)
            ncr = None
            if src is None:
                ncr = ({"tax": "x", "tay": "y", "txa": "a", "tya": "a"}[m], 0, "z")
            if m == "tax":
                return [(nxt, a, src, y, n2, z2, c, v, d, stk, T, ncr)]
            if m == "tay":
                return [(nxt, a, x, src, n2, z2, c, v, d, stk, T, ncr)]
            return [(nxt, src, x, y, n2, z2, c, v, d, stk, T, ncr)]
        if m == "txs":
            return [(nxt, a, x, y, n, z, c, v, d, (), T, cr)]
        if m in ("inx", "iny", "dex", "dey"):
            if m in ("inx", "dex"):
                val = None if x is None else (x + (1 if m == "inx" else -1)) & 0xFF
                return [(nxt, a, val, y, None if val is None else val >> 7, None if val is None else int(val == 0), c, v, d, stk, T, ("x", 0, "z") if val is None else None)]
            val = None if y is None else (y + (1 if m == "iny" else -1)) & 0xFF
            return [(nxt, a, x, val, None if val is None else val >> 7, None if val is None else int(val == 0), c, v, d, stk, T, ("y", 0, "z") if val is None else None)]
        if m in ("inc", "dec"):
            cur = self.read(T, mode, op, x, y)
            val = None if cur is None else (cur + (1 if m == "inc" else -1)) & 0xFF
            T2 = self.write(T, mode, op, x, y, val, pc, events)
            return [(nxt, a, x, y, None if val is None else val >> 7, None if val is None else int(val == 0), c, v, d, stk, T2, None)]
        # ---- arithmetic and logic ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        if m in ("and", "ora", "eor"):
            mv = self.read(T, mode, op, x, y)
            if m == "and" and (mv == 0 or a == 0):
                val = 0
            elif m == "ora" and (mv == 0xFF or a == 0xFF):
                val = 0xFF
            elif a is None or mv is None:
                val = None
            else:
                val = {"and": a & mv, "ora": a | mv, "eor": a ^ mv}[m]
            return [(nxt, val, x, y, None if val is None else val >> 7, None if val is None else int(val == 0), c, v, d, stk, T, ("a", 0, "z") if val is None else None)]
        if m in ("adc", "sbc"):
            mv = self.read(T, mode, op, x, y)
            if a is None or mv is None or c is None or d != 0:
                return [(nxt, None, x, y, None, None, None, None, d, stk, T, None)]
            if m == "adc":
                r = a + mv + c
                cc = int(r > 0xFF)
                vv = int((~(a ^ mv) & (a ^ r) & 0x80) != 0)
            else:
                r = a - mv - (1 - c)
                cc = int(r >= 0)
                vv = int(((a ^ mv) & (a ^ r) & 0x80) != 0)
            r &= 0xFF
            return [(nxt, r, x, y, r >> 7, int(r == 0), cc, vv, d, stk, T, None)]
        if m in ("cmp", "cpx", "cpy"):
            reg = {"cmp": a, "cpx": x, "cpy": y}[m]
            mv = self.read(T, mode, op, x, y)
            if isinstance(reg, frozenset):
                if mv is None:
                    return [(nxt, None if m != "cmp" else a if not isinstance(a, frozenset) else None, None if isinstance(x, frozenset) else x, None if isinstance(y, frozenset) else y, None, None, None, v, d, stk, T, None)]
                if mv not in reg:
                    cc = int(all(r >= mv for r in reg)) if (all(r >= mv for r in reg) or all(r < mv for r in reg)) else None
                    return [(nxt, None if isinstance(a, frozenset) else a, None if isinstance(x, frozenset) else x, None if isinstance(y, frozenset) else y, None, 0, cc, v, d, stk, T, None)]
                ncr = ({"cmp": "a", "cpx": "x", "cpy": "y"}[m], mv, "c") if mode in ("imm", "zp", "abs") else None
                return [(nxt, None if isinstance(a, frozenset) else a, None if isinstance(x, frozenset) else x, None if isinstance(y, frozenset) else y, None, None, None, v, d, stk, T, ncr)]
            if reg is None or mv is None:
                ncr = None
                if reg is None and mode == "imm":
                    ncr = ({"cmp": "a", "cpx": "x", "cpy": "y"}[m], op, "c")
                return [(nxt, a, x, y, None, None, None, v, d, stk, T, ncr)]
            r = (reg - mv) & 0xFF
            return [(nxt, a, x, y, r >> 7, int(r == 0), int(reg >= mv), v, d, stk, T, None)]
        if m == "bit":
            mv = self.read(T, mode, op, x, y)
            if mv is None:
                return [(nxt, a, x, y, None, None if a is None else (None if a != 0 else 1), c, None, d, stk, T, None)]
            zz = None if a is None else int((a & mv) == 0)
            return [(nxt, a, x, y, mv >> 7, zz, c, (mv >> 6) & 1, d, stk, T, None)]
        if m in ("asl", "lsr", "rol", "ror"):
            if mode == "acc":
                cur = a
            else:
                cur = self.read(T, mode, op, x, y)
            if cur is None or (m in ("rol", "ror") and c is None):
                val, cc = None, None
            elif m == "asl":
                val, cc = (cur << 1) & 0xFF, cur >> 7
            elif m == "lsr":
                val, cc = cur >> 1, cur & 1
            elif m == "rol":
                val, cc = ((cur << 1) | c) & 0xFF, cur >> 7
            else:
                val, cc = (cur >> 1) | (c << 7), cur & 1
            nn = None if val is None else val >> 7
            zz = None if val is None else int(val == 0)
            if mode == "acc":
                return [(nxt, val, x, y, nn, zz, cc, v, d, stk, T, None)]
            T2 = self.write(T, mode, op, x, y, val, pc, events)
            return [(nxt, a, x, y, nn, zz, cc, v, d, stk, T2, None)]
        # ---- flags --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        if m == "clc":
            return [(nxt, a, x, y, n, z, 0, v, d, stk, T, cr)]
        if m == "sec":
            return [(nxt, a, x, y, n, z, 1, v, d, stk, T, cr)]
        if m == "cld":
            return [(nxt, a, x, y, n, z, c, v, 0, stk, T, cr)]
        if m == "sed":
            return [(nxt, a, x, y, n, z, c, v, 1, stk, T, cr)]
        if m in ("cli", "sei", "nop"):
            return [(nxt, a, x, y, n, z, c, v, d, stk, T, cr)]
        if m == "pha":
            return [(nxt, a, x, y, n, z, c, v, d, stk + (None,), T, cr)]
        if m == "php":
            return [(nxt, a, x, y, n, z, c, v, d, stk + (None,), T, cr)]
        if m == "pla":
            val = stk[-1] if stk else None
            return [(nxt, val, x, y, None if val is None else val >> 7, None if val is None else int(val == 0), c, v, d, stk[:-1], T, None)]
        if m == "plp":
            return [(nxt, a, x, y, None, None, None, None, None, stk[:-1], T, None)]
        # ---- control flow -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        if m in BRANCH:
            flag, want = BRANCH[m]
            fv = (n, z, c, v)[("n", "z", "c", "v").index(flag)]
            taken = (op, a, x, y, n, z, c, v, d, stk, T, None)
            fall = (nxt, a, x, y, n, z, c, v, d, stk, T, None)
            if fv is not None:
                return [taken] if fv == want else [fall]
            out = []
            t_st, f_st = list(taken), list(fall)
            if cr is not None and flag == "z":
                reg, imm, kind = cr
                eq_st, ne_st = (t_st, f_st) if m == "beq" else (f_st, t_st)
                eq_st[{"a": A, "x": X, "y": Y}[reg]] = imm
                eq_st[Z] = 1
                eq_st[N] = 0 if kind == "c" or imm < 0x80 else 1
                if kind == "c":
                    eq_st[C] = 1
                ne_st[Z] = 0
            else:
                t_st[IDX[flag]] = want
                f_st[IDX[flag]] = 1 - want
            return [tuple(t_st), tuple(f_st)]
        if m == "jmp":
            if op >= OS_EXIT:
                return "EXIT"
            return [(op, a, x, y, n, z, c, v, d, stk, T, cr)]
        if m == "jsr":
            if op >= OS_EXIT:
                return [(nxt, None, None, None, None, None, None, None, d, stk, T, None)]
            if op in self.skip:
                pres = self.p.F[op].preserved                       # the registers the routine gives back unchanged (static, tools/analyze_functions.py; checked live: 0 violations, 5.5 million calls, docs/32)
                sa, sx, sy, sn, sz, sc, sv = self.summary(op)
                return [(nxt, sa if sa is not None else (a if "A" in pres else None), sx if sx is not None else (x if "X" in pres else None), sy if sy is not None else (y if "Y" in pres else None), sn, sz, sc, sv, None, stk, T, None)]
            ret = nxt - 1
            pres = self.p.F[op].preserved if op in self.p.F else set()
            meta = ("M", x if "X" in pres else None, y if "Y" in pres else None, "X" in pres, "Y" in pres, a if "A" in pres else None, "A" in pres)
            return [(op, a, x, y, n, z, c, v, d, stk + (ret >> 8, ret & 0xFF, meta), T, cr)]
        if m == "rts":
            if len(stk) < 3 or not isinstance(stk[-1], tuple) or stk[-2] is None or stk[-3] is None:
                raise RuntimeError("rts without a return address at $%04X" % pc)
            meta = stk[-1]
            ret = ((stk[-3] << 8) | stk[-2]) + 1
            if meta[3]:
                x = meta[1]                                          # a register the routine preserves (docs/23, checked live) has the caller's value again
            if meta[4]:
                y = meta[2]
            if meta[6]:
                a = meta[5]
            return [(ret, a, x, y, n, z, c, v, d, stk[:-3], T, cr)]
        raise RuntimeError("instruction %s at $%04X not modelled" % (m, pc))

    # ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def summary(self, entry):
        """what a skipped routine gives back: (a, x, y, n, z, c, v) with None where the exits disagree or the value depends on the unknown input; found by running the routine once from unknown registers"""
        if entry in self.summ:
            return self.summ[entry]
        events = set()
        exits = []

        def on_exit(st):
            exits.append(st)
        start = (entry, None, None, None, None, None, None, None, 0, (), tuple(None for _ in self.addrs), None)
        self.explore([start], events, on_exit, False, summary=True)
        res = [None] * 7
        if exits:
            regs = [(st[A], st[X], st[Y], st[N], st[Z], st[C], st[V]) for st in exits]
            res = [regs[0][i] if all(r[i] == regs[0][i] for r in regs) else None for i in range(7)]
        res = tuple(res)
        self.summ[entry] = res
        return res

    # ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def key(st):
        """the part of a state that is kept exact: the place, the stack, the followed variables and the index register X (the ghost index and the loop counters); the accumulator, Y, the flags and the compare memory are joined"""
        return (st[PC], st[STK], st[T], st[X])

    @staticmethod
    def join(old, new):
        """the join of two (a, y, n, z, c, v, d, cr): a component that differs becomes unknown"""
        return tuple(o if o == w else None for o, w in zip(old, new))

    @staticmethod
    def regs(st):
        return (st[A], st[Y], st[N], st[Z], st[C], st[V], st[D], st[CR])

    @staticmethod
    def build(k, r):
        return (k[0], r[0], k[3], r[1], r[2], r[3], r[4], r[5], r[6], k[1], k[2], r[7])

    def explore(self, starts, events, on_exit, in_vbi, extra=None, limit=3_000_000, summary=False):
        """the worklist search with joins: `starts` are states; `extra(st)` gives further successors (the interrupt of the main loop); `on_exit(st)` is called at the jump to the OS; returns the number of keys"""
        table = {}
        work = []

        def add(st):
            k = self.key(st)
            r = self.regs(st)
            old = table.get(k)
            if old is None:
                table[k] = r
                work.append(k)
            else:
                j = self.join(old, r)
                if j != old:
                    table[k] = j
                    work.append(k)
        for st in starts:
            add(st)
        while work:
            k = work.pop()
            st = self.build(k, table[k])
            if summary and self.p.ins[st[PC]][1] == "rts" and not st[STK]:
                on_exit(st)
                continue
            out = self.step(st, events, in_vbi)
            if out == "EXIT":
                on_exit(st)
                continue
            for s2 in out:
                add(s2)
            if extra is not None:
                for s2 in extra(st):
                    add(s2)
            if len(table) > limit:
                raise RuntimeError("state limit")
        return len(table)

    def vbi(self, T):
        """the vertical-blank handler run atomically from the followed values T: (the set of followed values at its end, the set of stores (address, pc, old, new)) - cached"""
        if T in self.vbi_cache:
            return self.vbi_cache[T]
        events = set()
        finals = set()
        start = (VBI_ENTRY, None, None, None, None, None, None, None, 0, (), T, None)
        n = self.explore([start], events, lambda st: finals.add(st[T_IDX]), True)
        res = (frozenset(finals), frozenset(events), n)
        self.vbi_cache[T] = res
        return res

    def main_thread(self, T0, limit=6_000_000, spacing=100, deadline=None, progress=False):
        """every state the main loop can reach with the vertical-blank handler entering between instructions at least `spacing` main-loop instructions apart (the real handler comes every 16.7 ms: the main loop runs thousands of
        instructions between two of them; a routine that is skipped counts as one instruction, so the spacing is under-counted, which is on the safe side): (the set of followed values seen, the set of stores, the number of keys)"""
        events = set()
        reach = {T0}
        K = spacing
        start = (MAIN_ENTRY, None, None, None, None, None, None, None, 0, (), T0, None)
        table = {}
        work = []

        def add(st, cnt):
            if SPIN_LO <= st[PC] <= SPIN_HI:
                cnt = K                                             # the polling part of the key loop: the handler may enter at any pass (sound: more behaviours; no count kept)
            k = (self.key(st), cnt)
            r = self.regs(st)
            old = table.get(k)
            if old is None:
                table[k] = r
                work.append(k)
            else:
                j = self.join(old, r)
                if j != old:
                    table[k] = j
                    work.append(k)
        add(start, K)
        import time as _t
        t0 = _t.time()
        last = t0
        while work:
            if progress and _t.time() - last > 30:
                last = _t.time()
                print("  main thread: %ds, %d keys, %d to do, %d followed values, %d handler runs" % (last - t0, len(table), len(work), len(reach), len(self.vbi_cache)), file=sys.stderr, flush=True)
            if deadline and _t.time() - t0 > deadline:
                raise TimeoutError("deadline")
            k = work.pop()
            key, cnt = k
            st = self.build(key, table[k])
            out = self.step(st, events, False)
            for s2 in out:
                add(s2, min(cnt + 1, K))
            if cnt >= K:
                finals, vev, _ = self.vbi(st[T_IDX])
                events.update(vev)
                for T2 in finals:
                    reach.add(T2)
                    add(st[:T_IDX] + (T2,) + st[T_IDX + 1:], 0)
            if len(table) > limit:
                raise RuntimeError("state limit")
        return reach, events, len(table)


T_IDX = T
