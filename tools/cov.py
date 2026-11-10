"""Step C9 helper: coverage of the recursive trace for a set of entry points; lists untraced gaps.
Usage: python -I tools/cov.py ENTRY [ENTRY...]   (hex). Read-only."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disasm6502 as D
data = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "original", "Pac-Man.rom"), "rb").read()
code, tg = D.trace(data, 0xA000, [int(a, 16) for a in sys.argv[1:]])
covered = bytearray(len(data))
for a, n in code.items():
    for k in range(n):
        covered[a - 0xA000 + k] = 1
print("%d instrs, %d bytes = %.1f%%" % (len(code), sum(covered), 100 * sum(covered) / len(data)))
i = 0
gaps = []
while i < len(data):
    if not covered[i]:
        j = i
        while j < len(data) and not covered[j]:
            j += 1
        gaps.append((0xA000 + i, j - i))
        i = j
    else:
        i += 1
print("%d gaps; largest:" % len(gaps), sorted(gaps, key=lambda g: -g[1])[:12])
print("all gaps:", " ".join("%04X+%d" % g for g in gaps))
