"""Step C11 helper: catalogue every subroutine (JSR target) with size, callers and hardware use.
Usage: python -I tools/routine_catalog.py > analysis/routine-catalog.txt   Read-only."""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disasm6502 as D  # noqa: E402
import labels as LB  # noqa: E402

with open(os.path.join(os.path.dirname(HERE), "original", "Pac-Man.rom"), "rb") as fh:
    data = fh.read()
ENTRIES = [0xA386, 0xA6B4, 0xA5FD, 0xA573, 0xA5CE]
code, targets = D.trace(data, 0xA000, ENTRIES)
callers, callees = collections.defaultdict(set), collections.defaultdict(set)
dec = {a: D.decode(data, 0xA000, a) for a in code}
subs = sorted({d[3] for d in dec.values() if d[1] == "jsr" and 0xA000 <= d[3] < 0xC000})
roots = sorted(set(subs) | set(ENTRIES))


def owner(a):
    best = None
    for r in roots:
        if r <= a:
            best = r
    return best


for a, d in dec.items():
    if d[1] == "jsr" and 0xA000 <= d[3] < 0xC000:
        callers[d[3]].add(owner(a))
        callees[owner(a)].add(d[3])
print("%d subroutines (JSR targets); owner = nearest preceding entry/subroutine label" % len(subs))
print("%-6s %-5s %-7s %-34s %s" % ("addr", "bytes", "callers", "hardware/OS touched", "calls"))
for r in roots:
    nxt = [x for x in roots if x > r]
    end = nxt[0] if nxt else 0xC000
    size = sum(n for a, n in code.items() if r <= a < end)
    hw = set()
    for a, d in dec.items():
        if r <= a < end and d[2] in ("abs", "abx", "aby") and d[1] not in ("jsr", "jmp"):
            n = LB.hw_name(d[3], d[1])
            if n:
                hw.add(n)
    print("%04X   %-5d %-7d %-34s %s" % (r, size, len(callers[r]), " ".join(sorted(hw))[:34],
                                       " ".join("%04X" % c for c in sorted(callees[r]))))
