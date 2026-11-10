"""Compare the live sight tests in a log (tools/altirra_sight.cmd) with tools/sight_model.py (step C11).
Usage: python -I tools/analyze_sight_log.py <log> [--summary-file out]"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sight_model as M  # noqa: E402


def main(path):
    L = [l.rstrip("\n") for l in open(path, encoding="latin1", errors="replace")]
    tests = []   # (kind, args, line_index)
    yes_after = {}
    for i, l in enumerate(L):
        m = re.match(r"SIGHT_(ROW|COL) ghost=(\d) gx=(\d+) gy=(\d+) gdir=(\d+) px=(\d+) py=(\d+) rtc=(\d+)", l)
        if m:
            tests.append((m[1], tuple(int(m[k]) for k in range(2, 9)), i))
        m = re.match(r"SIGHT_YES ghost=(\d)", l)
        if m and tests:
            yes_after[len(tests) - 1] = int(m[1])
    agree = dis = pos = 0
    kinds = collections.Counter()
    bad = []
    for n, (kind, a, i) in enumerate(tests):
        ghost, gx, gy, gdir, px, py, rtc = a
        want = yes_after.get(n) == ghost
        got = M.sees(ghost, gx, gy, gdir, px, py, rtc)
        kinds[(kind, got)] += 1
        if want:
            pos += 1
        if got == want:
            agree += 1
        else:
            dis += 1
            bad.append((kind, a, got, want))
    out = ["%d lines, %d same-row/column sight tests, %d ended in chase (SIGHT_YES)" % (len(L), len(tests), pos),
           "model == game on %d of %d tests (%d disagreements)" % (agree, len(tests), dis),
           "model decisions by kind: " + ", ".join("%s sees=%s: %d" % (k[0], k[1], v) for k, v in sorted(kinds.items()))]
    if bad:
        out.append("first disagreements: %s" % bad[:5])
    # which pixel positions of the blockers decided the live 'no' answers
    return out


if __name__ == "__main__":
    out = main(sys.argv[1])
    print("\n".join(out))
    if "--summary-file" in sys.argv:
        open(sys.argv[sys.argv.index("--summary-file") + 1], "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
