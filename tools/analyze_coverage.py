"""Stages 53 / 54: execution coverage of the Pac-Man ROM in the real game (Altirra, tools/run_coverage_audit.ps1).

Input: analysis/raw-logs/coverage-<harness>.txt with one line `C XXXX` for every instruction the first time it executes (a self-clearing breakpoint on every instruction), after the sentinel line `SENT`.
Result: per routine, how many of its instructions the game executed; the routines never entered; the call sites (JSR) executed, that is the call edges of `23-function-table.md` seen at run time; the branches whose
two outcomes... (not measured: only first execution of the instruction itself); which harness added how many instructions; and the instructions that no harness reached, grouped by routine.
Usage: python -I tools/analyze_coverage.py analysis/raw-logs/coverage-*.txt [--write analysis/evidence-coverage-summary.txt]  |  --instructions (lists the instruction addresses for the harness script)
"""
import collections
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_stack as AS  # noqa: E402

ROOT = os.path.dirname(HERE)


def instruction_addresses():
    rom, F, owner = AS.load()
    return rom, F, owner, sorted(rom.ins)


def parse(path):
    seen = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("C ") and len(line.strip()) == 6:
                try:
                    seen.append(int(line[2:6], 16))
                except ValueError:
                    pass
    return seen


def summarise(paths):
    rom, F, owner, addrs = instruction_addresses()
    allset = set(addrs)
    per = {}
    for p in paths:
        name = os.path.basename(p)[len("coverage-"):-len(".txt")]
        per[name] = [a for a in parse(p) if a in allset]
    reached = set()
    added = {}
    for name in per:                                   # in the given order: the number each harness adds to what came before
        new = set(per[name]) - reached
        added[name] = len(new)
        reached |= new
    return rom, F, owner, addrs, per, reached, added


def report(paths):
    rom, F, owner, addrs, per, reached, added = summarise(paths)
    L = []
    P = L.append
    total = len(addrs)
    P("Execution coverage (tools/run_coverage_audit.ps1, tools/analyze_coverage.py): %d harness logs, %d of %d instructions executed (%.1f %%)" % (len(per), len(reached), total, 100.0 * len(reached) / total))
    P("")
    P("%-20s %8s %8s" % ("harness", "own", "new"))
    for name in per:
        P("%-20s %8d %8d" % (name, len(set(per[name])), added[name]))
    P("")
    by = collections.defaultdict(lambda: [0, 0])
    for a in addrs:
        rn = F[owner[a]].name
        by[rn][1] += 1
        if a in reached:
            by[rn][0] += 1
    never = [rn for rn, (x, y) in by.items() if x == 0]
    full = [rn for rn, (x, y) in by.items() if x == y]
    P("Routines: %d of %d entered at least once; %d fully executed; never entered: %s" % (len(by) - len(never), len(by), len(full), ", ".join(sorted(never)) or "none"))
    jsr = [a for a, i in rom.ins.items() if i[1] == "jsr"]
    jmp = [a for a, i in rom.ins.items() if i[1] == "jmp"]
    P("Call sites: %d of %d JSR executed; jumps: %d of %d JMP executed" % (sum(1 for a in jsr if a in reached), len(jsr), sum(1 for a in jmp if a in reached), len(jmp)))
    P("")
    P("Instructions never executed, by routine (address, mnemonic):")
    miss = collections.defaultdict(list)
    for a in addrs:
        if a not in reached:
            miss[F[owner[a]].name].append(a)
    for rn in sorted(miss, key=lambda r: min(miss[r])):
        lst = miss[rn]
        P("  %-26s %3d of %3d: %s" % (rn, len(lst), by[rn][1], " ".join("%04X" % a for a in lst[:24]) + (" ..." if len(lst) > 24 else "")))
    return L, reached, miss, by


def main():
    if "--instructions" in sys.argv:
        for a in instruction_addresses()[3]:
            print("%04x" % a)
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        args = [a for a in args if a != out]
    paths = sorted(p for a in args for p in glob.glob(a))
    L = report(paths)[0]
    txt = "\n".join(L) + "\n"
    if out:
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
