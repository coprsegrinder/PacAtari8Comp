"""OV-64: how many entities take the HEAVY path of ClipEntityAtTunnel in one frame (an entity in a tunnel zone: X above $C0, `$AB71`, or below $39, `$AB99`), per frame class, from the logs of
`tools/run_mainloop_audit.ps1 -Clip` (VB lines of the main-loop audit, CE = a call of ClipEntityAtTunnel, CR = the right-zone path, CLL = one pass of the left-zone loop).
Usage: python -I tools/analyze_clip.py analysis/raw-logs/clipmainloop-*.txt [--write analysis/evidence-clip-summary.txt]"""
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import analyze_mainloop as M  # noqa: E402

TAG = re.compile(r"^(CE|CR|CLL) f=(\d+)")


def scan(paths):
    per_class = defaultdict(Counter)            # class -> {heavy calls in a frame: frames}
    calls_total = Counter()
    for p in paths:
        cls_of = {}
        heavy = defaultdict(int)
        calls = defaultdict(int)
        cur = None                               # (frame, heavy so far in this call)
        with open(p, encoding="ascii", errors="replace") as fh:
            for ln in fh:
                if not ln.endswith(chr(10)):
                    continue
                if ln.startswith("VB "):
                    m = M.VB.match(ln)
                    if m:
                        r = dict(zip(M.FIELDS, [int(x) for x in m.groups()[:16]]))
                        cls_of[r["f"]] = M.classify(r)
                    continue
                m = TAG.match(ln)
                if not m:
                    continue
                kind, f = m.group(1), int(m.group(2))
                if kind == "CE":
                    calls[f] += 1
                    cur = [f, False]
                elif cur is not None and cur[0] == f and not cur[1]:
                    cur[1] = True                # the first heavy mark of this call
                    heavy[f] += 1
        for f, cl in cls_of.items():
            if f > 36:
                per_class[cl][heavy.get(f, 0)] += 1
                calls_total[cl] += calls.get(f, 0)
    return per_class


def lines(paths):
    pc = scan(paths)
    L = ["Heavy calls of ClipEntityAtTunnel (an entity in a tunnel zone) in one handler frame, by frame class (%d logs of tools/run_mainloop_audit.ps1 -Clip):" % len(paths),
         "class | frames | frames with 0 / 1 / 2 / 3 / 4 / 5 heavy calls | most in one frame"]
    worst = 0
    for name, _ in M.CLASSES:
        c = pc.get(name)
        if not c:
            continue
        n = sum(c.values())
        mx = max(c)
        worst = max(worst, mx)
        L.append("%-20s %7d | %s | %d" % (name, n, " / ".join(str(c.get(k, 0)) for k in range(6)), mx))
    L.append("most heavy calls in any frame: %d" % worst)
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
