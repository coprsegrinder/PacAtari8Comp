"""OV-58: what the model comparisons of tools/algorithm_models*.py cover of the ROM code.

All seven sets are run with the interpreter counting every instruction it executes (and, for a conditional branch, whether it was taken and whether it fell through).  Result: per routine, the instructions and the
branch outcomes executed in a comparison against a model; the instructions and outcomes that no comparison reached, grouped by routine.  An instruction that is not reached is either code the original never
executes or a case the tests do not produce yet; the list is the work that remains for OV-58.
Usage: python -I tools/analyze_model_coverage.py [--write analysis/evidence-model-coverage-summary.txt]   (about 8 minutes)
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpu6502 as C  # noqa: E402
import analyze_stack as AS  # noqa: E402

ROOT = os.path.dirname(HERE)
BRANCHES = (0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0)
EXEC = set()
OUTCOME = collections.defaultdict(set)         # branch address -> {"taken", "fallthrough"}


EXPLAIN = {
    0xA48F: "`lda GameState / bne`: GameState is 0 on every way into $A477 (the START key clears it, `Start` clears the zero page): the outcome cannot happen",
    0xA561: "`inc StartLevel / bne`: StartLevel is 0-12, never $FF",
    0xA56B: "`inc StartLevel / bne`: StartLevel is 0-12, never $FF",
    0xA86C: "`sbc / bne` in the contact test: the branch is only reached when Pac-Man's y is below the ghost's, so the difference is never 0",
    0xA999: "`lda EatPause / bne` after the frightened tick: EatPause is 0 here (a non-zero value returned at $A83C)",
    0xAA17: "`beq` after `sta HalfSpeedToggle,x` with A = 0 from the `cmp #0 / bne` above it: always taken",
    0xABEA: "`inc BonusSoundStep / bne`: BonusSoundStep is 1-10, never $FF",
    0xABF8: "`tay / beq` after `lda #$00`: always taken",
    0xACDF: "`dec DstPtrL / bne` (three times): the low byte is never 0 while the loop runs (it ends at the index test before)",
    0xB2D1: "`tya / beq` after `ldy #$00`: always taken",
    0xB2D9: "`inc ChompPhase / bne`: the counter is 1-4, never $FF",
    0xAD75: "`inc LabelBlink / bne`: the flag is 1",
    0xAD85: "`tax / tay / beq` after `lda LabelBlink / bne` fell through (A = 0): always taken",
    0xAD9D: "`tax / tay / beq` after `lda LabelBlink / bne` fell through (A = 0): always taken",
    0xAF96: "`and #$BB / beq` on a state that has bit 7 set: the result keeps bit 7, never 0 (dead branch in the original)",
    0xB531: "`adc SirenTone / bne` of the siren: SirenStep is 2-5 and the pitch below $40, so the sum is never 0",
    0xB413: "`lsr x3 / and #$3B / beq` on a state with bit 7 set: bit 7 becomes bit 4, so the result is never 0 (dead branch in the original)",
    0xB454: "`tya / beq` after `cpy #0 / bne` fell through: Y is 0, always taken",
    0xB4FE: "`and #$0E / bne` in the door-square rule: the exits of the two door squares are $0D (up, left, right); after the no-reverse mask they still hold left or right ($0C, $05 -> $04, $09 -> $08), so the result is never 0",
    0xB5B6: "`lda PacMoveDelayBase,y / bpl`: the table holds 8, 12, 16 and 20, never a value of $80 or more",
    0xB6CC: "`lda EntityY,x / bne` after the up-arrival test at y $64: the y coordinate is $64, never 0",
    0xB9E8: "`lda WantVert,x / bne`: reached only with a non-zero vertical wish (tested at $B9D3)",
    0xB9EC: "`lda WantHoriz,x / bne`: reached only with a non-zero horizontal wish (tested at $B9DB / $B9F2)",
    0xBA4B: "`iny / bne` in the scan of the sight lists: the scan would need 256 steps; the lists are 3-6 long and end with $FF",
    0xBA64: "`iny / bne` in the scan of the sight lists (see above)",
    0xBA90: "`iny / bne` in the scan of the sight lists (see above)",
    0xBAA9: "`iny / bne` in the scan of the sight lists (see above)",
}
COMPLEMENT = {"bne": "beq", "beq": "bne", "bpl": "bmi", "bmi": "bpl", "bcc": "bcs", "bcs": "bcc", "bvc": "bvs", "bvs": "bvc"}


def idiom(rom, addrs, idx, a):
    """a branch that cannot fall through by construction: the flags of an immediate load, the complement of the branch just before, `clc / bcc`, `sec / bcs`"""
    m = rom.ins[a][1]
    i = idx[a] - 1
    while i >= 0 and rom.ins[addrs[i]][1] in ("sta", "stx", "sty", "pha"):
        i -= 1
    p = addrs[i]
    pm = rom.ins[p]
    if pm[1] in COMPLEMENT and COMPLEMENT[pm[1]] == m and p == addrs[idx[a] - 1]:
        return "the complement of the branch before it"
    if pm[1] in ("lda", "ldx", "ldy") and pm[2] == "imm":
        v = pm[3]
        if (m == "bne" and v != 0) or (m == "beq" and v == 0) or (m == "bpl" and v < 0x80) or (m == "bmi" and v >= 0x80):
            return "the flags of an immediate load"
    if (pm[1] == "clc" and m == "bcc") or (pm[1] == "sec" and m == "bcs"):
        return "after clc / sec"
    return None


def instrument():
    orig = C.Machine.step

    def step(self):
        pc = self.pc
        op = self.mem[pc]
        orig(self)
        EXEC.add(pc)
        if op in BRANCHES:
            OUTCOME[pc].add("fallthrough" if self.pc == (pc + 2) & 0xFFFF else "taken")
    C.Machine.step = step


def run_all():
    import algorithm_models as M1
    import algorithm_models2 as M2
    import algorithm_models3 as M3
    import algorithm_models4 as M4
    import algorithm_models5 as M5
    import algorithm_models6 as M6
    import algorithm_models7 as M7
    for mod in (M1, M2, M3, M4, M5, M6, M7):
        mod.report()
        print("ran", mod.__name__, len(EXEC), "instructions so far", file=sys.stderr)


def report():
    rom, F, owner = AS.load()
    addrs = sorted(rom.ins)
    per = collections.OrderedDict()
    for a in addrs:
        per.setdefault(owner[a], []).append(a)
    L = []
    P = L.append
    total = sum(1 for a in addrs if a in EXEC)
    P("Coverage of the ROM code by the model comparisons of tools/algorithm_models*.py (tools/analyze_model_coverage.py, OV-58)")
    P("")
    P("instructions executed: %d of %d" % (total, len(addrs)))
    branches = [a for a in addrs if rom.ins[a][1] in ("bpl", "bmi", "bvc", "bvs", "bcc", "bcs", "bne", "beq")]
    both = sum(1 for a in branches if len(OUTCOME.get(a, ())) == 2)
    P("conditional branches taken and not taken: %d of %d (%d never executed)" % (both, len(branches), sum(1 for a in branches if a not in EXEC)))
    idx = {a: i for i, a in enumerate(addrs)}
    one_sided = [a for a in branches if a in EXEC and len(OUTCOME.get(a, ())) == 1]
    never = [a for a in addrs if a not in EXEC]
    idioms = {a: idiom(rom, addrs, idx, a) for a in one_sided}
    by_idiom = [a for a in one_sided if idioms[a] and OUTCOME[a] == {"taken"}]
    by_text = [a for a in one_sided if a not in by_idiom and a in EXPLAIN]
    unexplained = [a for a in one_sided if a not in by_idiom and a not in EXPLAIN]
    P("branches with one outcome only: %d (%d cannot fall through by construction: %s; %d explained one by one below; %d NOT explained)" % (len(one_sided), len(by_idiom), "the flags of an immediate load, the complement of the branch before, clc / sec", len(by_text), len(unexplained)))
    P("instructions never executed: %d" % len(never))
    P("")
    P("branches with one outcome that are explained one by one (the outcome that does not happen is impossible in the original or needs a hardware condition the model cannot make):")
    for a in by_text:
        P("  $%04X %s (%s): %s" % (a, owner_name(F, owner, a), "never falls through" if OUTCOME[a] == {"taken"} else "never taken", EXPLAIN[a]))
    for a in unexplained:
        P("  $%04X %s: NOT EXPLAINED (%s)" % (a, owner_name(F, owner, a), sorted(OUTCOME[a])))
    for a in never:
        P("  $%04X %s: NEVER EXECUTED" % (a, owner_name(F, owner, a)))
    P("")
    P("routines with every instruction executed and both outcomes of every branch, or only the explained ones missing: %d of %d" % (sum(1 for e, lst in per.items() if all(x in EXEC for x in lst) and not [x for x in lst if x in unexplained]), len(per)))
    return L


def owner_name(F, owner, a):
    return F[owner[a]].name


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    if cache and os.path.exists(cache):
        import json
        with open(cache) as fh:
            d = json.load(fh)
        EXEC.update(d["exec"])
        for k, v in d["outcome"].items():
            OUTCOME[int(k)].update(v)
    else:
        instrument()
        run_all()
        if cache:
            import json
            with open(cache, "w") as fh:
                json.dump({"exec": sorted(EXEC), "outcome": {str(k): sorted(v) for k, v in OUTCOME.items()}}, fh)
    L = report()
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
