"""OV-64 (part 4): are the hand-argued loop bounds of tools/static_wcet.py (ANNOT) respected by the real game?  From the logs of `tools/run_mainloop_audit.ps1 -Loops`:
  EN pc=<routine> f=<frame>   an entry of the routine the bound is per call of;   LP pc=<pc> f=<frame>   an execution of the bounded instruction.
For every bounded pc: the most executions between two entries of its routine, and in how many calls it ran at all.  A count above the bound would refute it.
Usage: python -I tools/analyze_loopbounds.py analysis/raw-logs/loopmainloop-*.txt [--write analysis/evidence-loopbounds-summary.txt]"""
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import static_wcet as W  # noqa: E402

# the routine entry each bounded pc is counted per call of (the owner of tools/static_wcet.py ANNOT; None there means one ghost update = GhostBehaviour)
OWNER = {0xB8E8: 0xB7F5, 0xACDF: 0xAC93, 0xB018: 0xAFD7, 0xAFF3: 0xAFD7, 0xB53D: 0xAF54, 0xB9F2: 0xB999}
LINE = re.compile(r"^(EN|LP) pc=([0-9a-f]{4}) f=(\d+)")


def scan(paths):
    mx = defaultdict(int)
    calls = defaultdict(int)
    hit = defaultdict(int)
    for p in paths:
        cur = defaultdict(int)
        with open(p, encoding="ascii", errors="replace") as fh:
            for ln in fh:
                if not ln.endswith(chr(10)):
                    continue
                m = LINE.match(ln)
                if not m:
                    continue
                pc = int(m.group(2), 16)
                if m.group(1) == "EN":
                    for lp, ow in OWNER.items():
                        if ow == pc:
                            if cur[lp]:
                                hit[lp] += 1
                            cur[lp] = 0
                            calls[lp] += 1
                else:
                    cur[pc] += 1
                    mx[pc] = max(mx[pc], cur[pc])
    return mx, calls, hit


def lines(paths):
    mx, calls, hit = scan(paths)
    L = ["Loop bounds of tools/static_wcet.py against the real game (%d logs of tools/run_mainloop_audit.ps1 -Loops):" % len(paths),
         "pc | bound (executions per call) | most seen | calls of the routine | calls in which the pc ran"]
    ok = True
    for pc in sorted(OWNER):
        bound = W.ANNOT[pc][1]
        L.append("$%04X | %d | %d | %d | %d" % (pc, bound, mx[pc], calls[pc], hit[pc]))
        if mx[pc] > bound:
            ok = False
    L.append("every bound respected: %s" % ("yes" if ok else "NO"))
    return L, ok


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and a.endswith(".txt") and "evidence" not in a and os.path.isfile(a)]
    L, ok = lines(paths)
    txt = chr(10).join(L) + chr(10)
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
