"""Stage 56: runtime register inspection - the register claims of docs/23-function-table.md checked against the real game.

Input: analysis/raw-logs/registers-<harness>.txt of tools/run_register_audit.ps1, lines
  RE <entry> a=.. x=.. y=.. s=.. p=.. f=N     before the first instruction of a routine
  RX <rts>   a=.. x=.. y=.. s=.. p=.. f=N     before an RTS / RTI of a routine
An entry is paired with the exit that has the same stack pointer S (the stack is balanced in every routine, `28-stack.md`; an interrupt runs deeper, so contexts never share an S).  A routine entered by a tail jump
(`jmp` into another routine) is a second entry at the same S: the exit closes the whole chain, and the claims of every routine of the chain are checked from its own entry.
The claims (tools/analyze_functions.py, the 'saves and restores' and 'clobbers' of docs/23): a register the routine PRESERVES must have the same value at the exit as at the entry in every call; a register
that is not in its 'clobbers' set (A, X, Y; including its callees) must be unchanged too.  What is also reported: the registers that did change, the number of calls, and the carry at the exit of the routines whose result is C.
Usage: python -I tools/analyze_registers.py analysis/raw-logs/registers-*.txt [--write analysis/evidence-registers-summary.txt]  |  --probes (the Altirra lines for the harness script)
"""
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402

ROOT = os.path.dirname(HERE)
LINE = re.compile(r"^(RE|RX) ([0-9A-F]{4}) a=([0-9A-F]{2}) x=([0-9A-F]{2}) y=([0-9A-F]{2}) s=([0-9A-F]{2}) p=([0-9A-F]{2}) f=(\d+)")
REGS = ("A", "X", "Y")


def load():
    rom, F = AF.analyse()
    AF.solve(rom, F)
    owner = {}
    for a in rom.ins:
        owner[a] = min((e for e in F if a in F[e].body), key=lambda e: (len(F[e].body), e))
    tails = {}
    for e in F:
        seen, work = set(), [e]
        while work:
            x = work.pop()
            for t in F[x].tail:
                if t not in seen:
                    seen.add(t)
                    work.append(t)
        tails[e] = seen
    return rom, F, owner, tails


def probes():
    rom, F, owner, tails = load()
    out = ['bt a386 "SENT f=%d pc=$%04X" @frame pc']
    fmt = "a=%02X x=%02X y=%02X s=%02X p=%02X f=%d"
    for e in sorted(F):
        out.append('bt %04x "RE %04X %s" @a x y s p @frame' % (e, e, fmt))
    for a, (n, m, mode, op) in sorted(rom.ins.items()):
        if m in ("rts", "rti"):
            out.append('bt %04x "RX %04X %s" @a x y s p @frame' % (a, a, fmt))
    return out


def parse(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[0] == "R" and (line.startswith("RE ") or line.startswith("RX ")):
                m = LINE.match(line)
                if m:
                    yield (m.group(1), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16), int(m.group(5), 16), int(m.group(6), 16), int(m.group(7), 16), int(m.group(8)))


def summarise(paths):
    rom, F, owner, tails = load()
    calls = collections.Counter()
    changed = collections.defaultdict(collections.Counter)         # routine -> register -> calls in which it changed
    viol = []                                                      # (routine, register, kind, entry value, exit value, frame, harness)
    carry = collections.defaultdict(collections.Counter)
    unmatched_exit = unmatched_entry = chains = 0
    for path in paths:
        name = os.path.basename(path)[len("registers-"):-len(".txt")]
        open_ = collections.defaultdict(list)                      # s -> [(entry, regs, frame)]
        for kind, addr, a, x, y, s, p, f in parse(path):
            if kind == "RE":
                lst = open_[s]
                while lst and addr not in tails.get(lst[-1][0], ()):
                    lst.pop()                                      # a stale entry (a routine that never returned: Start, a restart) or a finished chain
                    unmatched_entry += 1
                lst.append((addr, {"A": a, "X": x, "Y": y}, f))
            else:
                lst = open_.get(s)
                if not lst:
                    unmatched_exit += 1
                    continue
                if len(lst) > 1:
                    chains += 1
                ex = {"A": a, "X": x, "Y": y}
                for entry, regs, f0 in lst:
                    fn = F[entry]
                    calls[entry] += 1
                    for r in REGS:
                        if regs[r] != ex[r]:
                            changed[entry][r] += 1
                        if r in fn.preserved and regs[r] != ex[r]:
                            viol.append((fn.name, r, "preserved", regs[r], ex[r], f0, name))
                        if r not in fn.may and regs[r] != ex[r]:
                            viol.append((fn.name, r, "not clobbered", regs[r], ex[r], f0, name))
                    if "C" in fn.out:
                        carry[entry][p & 1] += 1
                open_[s] = []
    return rom, F, owner, calls, changed, viol, carry, (unmatched_entry, unmatched_exit, chains)


def report(paths):
    rom, F, owner, calls, changed, viol, carry, (ue, ux, chains) = summarise(paths)
    L = []
    P = L.append
    nrts = sum(1 for i in rom.ins.values() if i[1] in ("rts", "rti"))
    P("Register audit (tools/run_register_audit.ps1, tools/analyze_registers.py): %d harness logs, %d routines called (of %d), %d completed calls; tail-jump chains closed %d, stale entries dropped %d, exits without entry %d" % (
        len(paths), len(calls), len(F), sum(calls.values()), chains, ue, ux))
    claims_pres = sum(len(F[e].preserved & set(REGS)) for e in calls)
    claims_not = sum(len(set(REGS) - F[e].may) for e in calls)
    checks = sum(calls[e] * (len(F[e].preserved & set(REGS)) + len(set(REGS) - F[e].may - F[e].preserved)) for e in calls)
    P("Claims checked in every call: %d 'preserved' register claims and %d 'never clobbered' register claims over the routines that ran (%d register checks in all)" % (claims_pres, claims_not, checks))
    P("Violations of a claim: %d" % len(viol))
    for v in viol[:10]:
        P("  %s %s (%s): entry $%02X exit $%02X, frame %d, %s" % v)
    P("")
    P("%-24s %9s %-10s %-10s %-10s %s" % ("routine", "calls", "preserved", "never chg.", "changed in", "result C (exit carry 0 / 1)"))
    for e in sorted(calls, key=lambda x: F[x].name):
        f = F[e]
        pres = "".join(r for r in REGS if r in f.preserved) or "-"
        never = "".join(r for r in REGS if r not in f.may) or "-"
        ch = " ".join("%s %d" % (r, changed[e][r]) for r in REGS if changed[e][r]) or "-"
        cy = ("%d / %d" % (carry[e][0], carry[e][1])) if "C" in f.out else ""
        P("%-24s %9d %-10s %-10s %-10s %s" % (f.name, calls[e], pres, never, ch, cy))
    P("")
    nocall = sorted(F[e].name for e in F if e not in calls)
    P("Routines never completed a call in these runs: %s" % (", ".join(nocall) or "none"))
    return L, viol, calls, changed


def main():
    if "--probes" in sys.argv:
        for line in probes():
            print(line)
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
