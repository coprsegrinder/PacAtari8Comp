"""Stage 58, exactness check of the transition rules (tools/analyze_states.py RULES): the ROM code is run in the 6502 interpreter (tools/cpu6502.py, the setups of the OV-58 models) with every state variable forced to each
value of its domain before the call, in many random contexts, and every store to a state variable is logged with the writing instruction, the old and the new value.  The result per writing instruction is the relation
old -> new that the code implements for arbitrary memory contents (a superset of what a game reaches), to be compared with the rules:
  - a pair made by a call of the FRAME level (the frame, the vertical-blank handler, the key loop, InitBoard, Start: the guards of the callers are inside) that no rule allows  -> the rule table is wrong,
  - a pair made only when a routine is CALLED DIRECTLY (its callers' guards left out) that no rule allows  -> the routine accepts it, the caller never lets it happen (listed and explained, tests/test_states.py),
  - a pair a rule allows that no call produced -> the rule is too wide, or no context was found (listed).
The domain of a variable is the closure of its rules (analyze_states.DOMAIN); an old value outside it is not tried (a store through an index that is not 0 / 1, for example, is outside the model).
Usage: python -I tools/check_state_rules.py [--write analysis/evidence-state-rules-summary.txt] [--cache FILE]   (about 20 minutes; --cache keeps the log of the stores)
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpu6502 as C  # noqa: E402
import algorithm_models as A  # noqa: E402
import algorithm_models6 as M6  # noqa: E402
import algorithm_models7 as M7  # noqa: E402
import analyze_states as S  # noqa: E402

ROOT = os.path.dirname(HERE)
SUMMARY = os.path.join(ROOT, "analysis", "evidence-state-rules-summary.txt")
LOG = collections.defaultdict(collections.Counter)            # (address, writing pc) -> Counter((old, new, level)), level 'f' = frame level, 'd' = a routine called directly
CUR = {"level": "f"}
STATE_ADDRS = {a for a, n, s, d in S.STATES for a in range(a, a + s)}
_orig_step = C.Machine.step
_orig_wr = C.Machine.wr


def instrument():
    def step(self):
        self._ipc = self.pc
        _orig_step(self)

    def wr(self, a, v):
        a &= 0xFFFF
        if a in STATE_ADDRS and not (C.BASE <= a < self.rom_end):
            LOG[(a, getattr(self, "_ipc", 0))][(self.mem[a], v & 0xFF, CUR["level"])] += 1
        _orig_wr(self, a, v)
    C.Machine.step = step
    C.Machine.wr = wr


def in_domain(m, rng):
    """every state variable gets a random value of its own domain (the other bytes of the zero page stay random, as in the OV-58 models)"""
    for a, name, size, d in S.STATES:
        for k in range(size):
            m.mem[a + k] = rng.choice(S.DOMAIN[name])


SMALL = [0, 0, 0, 1, 1, 2, 3, 4, 5, 6, 7, 8, 0x10, 0x18, 0x20, 0x40, 0x60, 0x80, 0xFF]


def bias(m, rng):
    """small values for the flags, counters and timers of the zero page (a random byte is almost never 0 or 1, which the paths of the frame need)"""
    for a in range(0x100):
        if a not in STATE_ADDRS and rng.random() < 0.55:
            m.mem[a] = rng.choice(SMALL)
    m.mem[0x81] = 0x0C + rng.randrange(3)                      # MazePtr high: inside the working maze copy
    m.mem[0x83], m.mem[0x84] = rng.randrange(256), rng.randrange(256)


_orig_setup_game = M7.M5.setup_game


def _biased_setup_game(m, rng, entities=True):
    """the OV-58 setup of a game state, with small values in a part of the zero page (set BEFORE the specific choices of the frame setup, which win)"""
    _orig_setup_game(m, rng, entities)
    bias(m, rng)


M7.M5.setup_game = _biased_setup_game


def perturb(m, rng, addr, v):
    """contexts that the random setup rarely makes: ghosts at the door and house squares, at their targets, the death glide at its end, the frightened period at its end phase"""
    if rng.random() < 0.35:
        g = rng.randrange(4)
        m.mem[0x8A + g], m.mem[0x85 + g] = rng.choice([(0x7C, 0x64), (0x7C, 0x74), (0x70, 0x74), (0x88, 0x74), (0x7C, 0x70), (0x82, 0x64), (0x76, 0x64)])
    if rng.random() < 0.35:
        g = rng.randrange(4)
        m.mem[0xC2 + g], m.mem[0xC6 + g] = m.mem[0x8A + g], m.mem[0x85 + g]
        if rng.random() < 0.5:
            m.mem[0x8A + g], m.mem[0x85 + g] = M7.M2.lattice_position(rng)
            m.mem[0xC2 + g], m.mem[0xC6 + g] = m.mem[0x8A + g], m.mem[0x85 + g]
    if rng.random() < 0.3:
        m.mem[0xF1] = rng.choice([1, 3, 4, 0x80])
        m.mem[0xEF] = rng.choice([0x6D, 0x69, 0x35, 0x2D])
    if rng.random() < 0.35:
        # the conditions of a plain play frame (the title and the intro are over, nobody is dying or eating, no turn handling), except for the variable under test
        for a2, v2 in ((0x19, 0), (0x9B, 0), (0x1C, 0), (0x20, 0), (0x26, 0), (0x21, 1), (0x22, 1), (0x24, 0), (0x23, 0), (0xAA, 0), (0xED, 0), (0xE5, 0), (0xA8, 0)):
            if a2 != addr:
                m.mem[a2] = v2
        if rng.random() < 0.5:
            m.mem[0x89], m.mem[0x8E] = rng.choice(M7.M2.PELLET_SQUARES)
            m.mem[0x32 + m.mem[0x2B]] = 0x0F
        m.mem[0xD009] = m.mem[0xD00A] = 0x0F
        if rng.random() < 0.5:
            g = rng.randrange(4)
            m.mem[0x8A + g], m.mem[0x85 + g] = m.mem[0x8E], (m.mem[0x89] + rng.randrange(-4, 5)) & 0xFF
    if S.ADDR[addr][0] == "FrightenPhase" and rng.random() < 0.7:
        # the level whose end phase is v: the period ends when FrightenPhase equals FrightenEndPhase[Level]
        cands = [lv for lv in range(256) if m.mem[0x0672 + lv] == v]
        if cands:
            m.mem[0x30 + m.mem[0x2B]] = rng.choice(cands)
        m.mem[0xFD] = 0
        m.mem[0xFB] = rng.choice([0, 0, 1, 0x18])
        m.mem[0xF2] = rng.choice([0, 1])


# the routines of the frame that write state variables, called directly in a frame-setup context
DIRECT = [(0xB7F5, "x"), (0xB5C7, None), (0xB7A5, None), (0xB69E, None), (0xAF54, None), (0xB39F, None), (0xA886, "x"), (0xAA2D, None), (0xAC18, None), (0xAC75, None), (0xB33A, None),
          (0xAE3D, None), (0xB049, None), (0xB62E, None), (0xB616, "x"), (0xAEF7, None), (0xB0BC, None)]
KINDS = 5 + len(DIRECT)


def force(m, addr, v):
    m.mem[addr] = v


def domain_of(addr):
    return S.DOMAIN[S.ADDR[addr][0]]


def context(base, rng, addr, v, kind):
    """one call of the ROM with the state variables in their domains and `addr` forced to v; kind 0-3 = the frame (game, play, title) and the VBI handler, 4 = the key loop, 5.. = a routine called directly"""
    m = M6.prepare(base, rng)
    CUR["level"] = "d" if kind >= 5 else "f"
    if kind >= 5:
        entry, reg = DIRECT[kind - 5]
        M7.frame_setup(m, rng, "play")
        m.mem[0x81] = 0x0C + rng.randrange(3)
        in_domain(m, rng)
        perturb(m, rng, addr, v)
        m.random = [rng.randrange(256) for _ in range(12)]
        force(m, addr, v)
        x = rng.randrange(4)
        k = S.ADDR[addr][1] if S.ADDR[addr][0] == "GhostState" else None
        if k is not None and rng.random() < 0.8:
            x = k
        try:
            m.call(entry, x=x)
        except Exception:
            pass
        return
    if kind < 4:
        mode, entry = (("game", 0xA6CC), ("play", 0xA6CC), ("title", 0xA6CC), ("play", 0xA5FD))[kind]
        M7.frame_setup(m, rng, mode)
        m.mem[0x81] = 0x0C + rng.randrange(3)
        in_domain(m, rng)
        perturb(m, rng, addr, v)
        m.random = [rng.randrange(256) for _ in range(12)]
        force(m, addr, v)
        try:
            m.call(entry)
        except Exception:
            pass
    else:
        for a2, val in ((0x1B, rng.choice([0, 1, 2, 4, 6, 8, 10, 12])), (0x1E, rng.choice([0, 0, 5])), (0x02F1, rng.choice([0, 0, 1])), (0x02FC, rng.choice([0x21, 0x21, 0xFF, 0x1C])),
                        (0x0284, rng.choice([1, 1, 0])), (0x0285, rng.choice([1, 1, 0])), (0xD01F, rng.choice([7, 6, 5, 3, 4, 2, 1, 0, 6, 5, 3]))):
            m.mem[a2] = val
        m.mem[0x3C], m.mem[0x3D] = rng.randrange(256), 0x08 + rng.randrange(8)
        bias(m, rng)
        in_domain(m, rng)
        force(m, addr, v)
        try:
            M6.run_key_loop(m, bounce=None, spins=0)
        except Exception:
            pass


def targets():
    out = []
    for a, n, s_, d in S.STATES:
        for k in range(s_):
            out.append((a + k, "%s%s" % (n, "[%d]" % k if s_ > 1 else "")))
    return out


def run_drivers(rng, per_value=12):
    base = A.started_machine()
    total = 0
    for addr, label in targets():
        for v in domain_of(addr):
            for rep in range(per_value):
                for kind in range(KINDS):
                    context(base, rng, addr, v, kind)
                    total += 1
    return total


def run_bulk_drivers(rng):
    """the clears: InitBoard and Start, from every value of the domain of every state variable"""
    base = A.started_machine()
    total = 0
    CUR["level"] = "f"
    for addr, label in targets():
        for v in domain_of(addr):
            for rep in range(2):
                m = A.fresh(base)
                for a in range(0x100):
                    m.mem[a] = rng.randrange(256)
                in_domain(m, rng)
                force(m, addr, v)
                m.call(0xADAF)                                    # InitBoard
                total += 1
            m = C.Machine(A.ROM)                                  # Start: the zero page clear and what follows up to the key loop
            for a in range(0x100):
                m.mem[a] = rng.randrange(256)
            in_domain(m, rng)
            force(m, addr, v)
            try:
                m.call(0xA386, until=0xA477, limit=3000000)
            except Exception:
                pass
            total += 1
    return total


def pairs_of():
    """-> {(name, pc): {'f': set, 'd': set}} of the pairs old != new with old in the domain, and the count of stores from outside the domain"""
    out = collections.defaultdict(lambda: {"f": set(), "d": set()})
    outside = 0
    for (addr, pc), c in LOG.items():
        name = S.ADDR[addr][0]
        dom = set(S.DOMAIN[name])
        for (o, n, lv), k in c.items():
            if o == n:
                continue
            if o not in dom:
                outside += k
                continue
            out[(name, pc)][lv].add((o, n))
    return out, outside


def rules_by_site():
    by = collections.defaultdict(list)
    for r in S.RULES:
        for pc in r[3]:
            by[(r[0], pc)].append(r)
    return by


def rule_pairs(rule):
    var, froms, to, pcs, text = rule
    olds = range(256) if froms is None else froms
    out = set()
    for o in olds:
        if callable(to):
            for n in to(o):
                out.add((o, n))
        elif to == "+1":
            out.add((o, (o + 1) & 0xFF))
        else:
            out.add((o, to))
    return {p for p in out if p[0] != p[1]}


def allowed_pairs(name, pc, rules):
    dom = set(S.DOMAIN[name])
    out = set()
    for r in rules:
        out |= {p for p in rule_pairs(r) if p[0] in dom}
    a = next(a for a, n, s_, d in S.STATES if n == name)
    for cpc, lo, hi, text in S.BULK_CLEARS:
        if pc == cpc and lo <= a <= hi:
            out |= {(o, 0) for o in dom if o != 0}
    if pc in S.BOOT_PCS:
        out |= {(o, 0) for o in dom if o != 0}
    return out


def compare():
    pairs, outside = pairs_of()
    by = rules_by_site()
    keys = set(by) | set(pairs)
    res = []
    for (name, pc) in sorted(keys):
        if pc >= 0xC000:
            continue
        rules = by.get((name, pc), [])
        al = allowed_pairs(name, pc, rules)
        pf, pd = pairs[(name, pc)]["f"], pairs[(name, pc)]["d"]
        res.append({"var": name, "pc": pc, "rules": rules, "allowed": al, "f": pf, "d": pd,
                    "bad_f": sorted(pf - al), "guarded": sorted(pd - pf - al), "missing": sorted(al - pf - pd), "only_d": sorted((al & pd) - pf)})
    return res, outside


def condensed(pairs, domain):
    """a compact text of a set of pairs: 'old values -> new' groups"""
    by = collections.defaultdict(list)
    for o, n in sorted(pairs):
        by[n].append(o)
    parts = []
    for n, olds in sorted(by.items()):
        parts.append("%s -> %02X" % ("any" if set(olds) >= set(domain) - {n} else "/".join("%02X" % x for x in olds), n))
    return "; ".join(parts)


def report(total):
    res, outside = compare()
    L = []
    P = L.append
    P("Exactness of the transition rules (tools/check_state_rules.py): %d calls of the ROM in the interpreter (frames, vertical-blank handler, key loop with restart, InitBoard, Start, and 17 routines called directly), every state variable forced to each value of its domain" % total)
    P("")
    nbad = sum(len(x["bad_f"]) for x in res)
    nguard = sum(len(x["guarded"]) for x in res)
    nmiss = sum(len(x["missing"]) for x in res)
    nonly = sum(len(x["only_d"]) for x in res)
    P("writing instructions examined: %d; stores from an old value outside the domain (not tried, a count): %d" % (len(res), outside))
    P("pairs made at the frame level that no rule allows: %d" % nbad)
    P("pairs made only by a direct call of a routine that no rule allows (the caller's guard keeps them out): %d" % nguard)
    P("pairs a rule allows that no call made: %d" % nmiss)
    P("pairs a rule allows that only a direct call made (the frame level never did): %d" % nonly)
    P("")
    P("per writing instruction (variable, instruction): the pairs of the code at the frame level / only by a direct call")
    for x in res:
        if not x["f"] and not x["d"] and not x["rules"]:
            continue
        dom = S.DOMAIN[x["var"]]
        P("  %s $%04X: %s%s" % (x["var"], x["pc"], condensed(x["f"], dom) or "-", ("   [direct only: %s]" % condensed(x["d"] - x["f"], dom)) if x["d"] - x["f"] else ""))
    P("")
    if nbad:
        P("NOT ALLOWED at the frame level:")
        for x in res:
            for p in x["bad_f"]:
                P("  %s $%04X %02X -> %02X" % (x["var"], x["pc"], p[0], p[1]))
    P("guarded by the caller (made only when the routine is called directly):")
    for x in res:
        if x["guarded"]:
            P("  %s $%04X: %s" % (x["var"], x["pc"], condensed(x["guarded"], S.DOMAIN[x["var"]])))
    P("rule pairs no call made:")
    for x in res:
        if x["missing"]:
            P("  %s $%04X: %s" % (x["var"], x["pc"], condensed(x["missing"], S.DOMAIN[x["var"]])))
    P("rule pairs made only by a direct call:")
    for x in res:
        if x["only_d"]:
            P("  %s $%04X: %s" % (x["var"], x["pc"], condensed(x["only_d"], S.DOMAIN[x["var"]])))
    P("")
    P("exact pairs (EXACT variable instruction level old new; level f = the frame level, d = made only by a direct call):")
    for x in res:
        for o, n in sorted(x["f"]):
            P("EXACT %s %04X f %02X %02X" % (x["var"], x["pc"], o, n))
        for o, n in sorted(x["d"] - x["f"]):
            P("EXACT %s %04X d %02X %02X" % (x["var"], x["pc"], o, n))
    return L, res


def save_cache(path):
    with open(path, "w") as fh:
        json.dump({"%d:%d:%d:%d:%s" % (a, pc, o, n, lv): k for (a, pc), c in LOG.items() for (o, n, lv), k in c.items()}, fh)


def load_cache(path):
    with open(path) as fh:
        d = json.load(fh)
    for key, k in d.items():
        a, pc, o, n, lv = key.split(":")
        LOG[(int(a), int(pc))][(int(o), int(n), lv)] += k


def run_ov58_checks():
    """the OV-58 comparisons (tools/algorithm_models2.py .. 7): every instruction of the ROM is executed in them with thousands of contexts in which the state variables are random bytes (so every old value of every domain
    turns up); the frame-level ones (the key loop, the title and game frames, the vertical-blank handler) are logged as such, the routines called directly as 'd'"""
    import algorithm_models2 as M2
    import algorithm_models3 as M3
    import algorithm_models4 as M4
    import algorithm_models5 as M5
    n = 0

    def frame_level(mod, name):
        orig = getattr(mod, name)

        def f(*a, **k):
            old = CUR["level"]
            CUR["level"] = "f"
            try:
                return orig(*a, **k)
            finally:
                CUR["level"] = old
        setattr(mod, name, f)
    frame_level(M6, "check_key_loop")
    frame_level(M7, "check_frame")
    CUR["level"] = "d"
    for mod in (M2, M3, M4, M5, M6, M7):
        mod.report()
        n += 1
    CUR["level"] = "f"
    return n


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    if cache and os.path.exists(cache):
        load_cache(cache)
        total = int(open(cache + ".total").read())
    else:
        instrument()
        rng = random.Random(580)
        total = run_drivers(rng) + run_bulk_drivers(rng)
        run_ov58_checks()
        for rnd in range(3):
            res, outside = compare()
            und = collections.defaultdict(set)
            for x in res:
                for p in x["missing"]:
                    und[x["var"]].add(p[0])
            if not und:
                break
            base = A.started_machine()
            for name, olds in sorted(und.items()):
                a0 = next(a for a, n, s_, d in S.STATES if n == name)
                size = next(s_ for a, n, s_, d in S.STATES if n == name)
                for old in sorted(olds):
                    for k in range(size):
                        for i in range(300):
                            context(base, rng, a0 + k, old, i % KINDS)
                            total += 1
        if cache:
            save_cache(cache)
            open(cache + ".total", "w").write(str(total))
    L, res = report(total)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
