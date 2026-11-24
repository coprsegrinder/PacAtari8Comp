"""OV-64: the CPU cycles the vertical-blank handler's thread really gets between its entry and the next interrupt (tools/altirra_budget.cmd and its title / copyright variants): the iterations of a 25-cycle counting loop per frame.
Usage: python -I tools/analyze_budget.py analysis/raw-logs/budget.txt analysis/raw-logs/budget_title.txt analysis/raw-logs/budget_copyright.txt [--write analysis/evidence-budget-summary.txt]"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LINE = re.compile(r"^BUD f=(\d+) t1=(\d+) n=(\d+)")
LOOP = 25                                                  # cycles of one iteration of the counting loop


def lines(paths):
    L = ["Cycles the handler's thread gets between its entry and the next interrupt (tools/altirra_budget*.cmd: a counting loop of %d cycles an iteration takes the place of the handler; display, display-list interrupts and OS work are all inside it):" % LOOP,
         "screen | frames measured | iterations a frame (value: frames) | cycles (the loop's last partial iteration is below %d)" % LOOP]
    for p in paths:
        name = os.path.basename(p)[len("budget"):-4].lstrip("_") or "game"
        c = Counter()
        with open(p, encoding="ascii", errors="replace") as fh:
            f0 = None
            for ln in fh:
                if not ln.endswith(chr(10)):
                    continue
                m = LINE.match(ln)
                if not m or m.group(2) != "1":
                    continue
                if f0 is None:
                    f0 = int(m.group(1))
                if int(m.group(1)) >= f0 + 3 and int(m.group(3)) > 0:          # the first entries after the take-over are not yet steady
                    c[int(m.group(3))] += 1
        n = sum(c.values())
        mn = min(c)
        L.append("%s | %d | %s | %d" % (name, n, ", ".join("%d: %d" % kv for kv in sorted(c.items())), mn * LOOP))
    return L


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and a.endswith(".txt") and "evidence" not in a and os.path.isfile(a)]
    txt = chr(10).join(lines(paths)) + chr(10)
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
