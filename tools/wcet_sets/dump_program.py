"""Dump what tools/wcet_sets/wcet_sets.cpp needs from the Python side: the decoded instructions of the ROM, the RAM tables $0600-$07FF, and the registers every routine preserves (tools/analyze_functions.py).
Usage: python -I tools/wcet_sets/dump_program.py <out.txt>"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import absint6502 as AB  # noqa: E402

p = AB.Program()
out = []
ins = sorted(p.ins.items())
out.append("INS %d" % len(ins))
for pc, (ln, m, mode, op) in ins:
    out.append("%d %d %s %s %d" % (pc, ln, m, mode, op if isinstance(op, int) else -1))
tabs = sorted(p.tables.items())
out.append("TAB %d" % len(tabs))
for a, v in tabs:
    out.append("%d %d" % (a, v))
pres = []
for e, f in sorted(p.F.items()):
    mask = (1 if "A" in f.preserved else 0) | (2 if "X" in f.preserved else 0) | (4 if "Y" in f.preserved else 0)
    pres.append((e, mask))
out.append("PRES %d" % len(pres))
for e, mk in pres:
    out.append("%d %d" % (e, mk))
with open(sys.argv[1], "w", newline="\n") as fh:
    fh.write("\n".join(out) + "\n")
print("instructions", len(ins), "table bytes", len(tabs), "routines", len(pres))
