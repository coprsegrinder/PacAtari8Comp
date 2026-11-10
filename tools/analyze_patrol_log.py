"""Analyse a log made by tools/run_patrol_trace.ps1 against the patrol-route tables (step C11, nibble map).
Usage: python -I tools/analyze_patrol_log.py <log> [--summary-file <out>]
Checks, for every ROUTE_SELECT: the target junction equals PatrolStartPositions[route]; every PATROL_ROUTE step reads the table value;
every scripted step is followed by the ghost's next junction being the neighbour in that direction; the route wraps at its zero terminator.
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

NIB, _ = S.split_nibbles(0xBE95)
R = lambda a: NIB[a - 0x600]
YS = [S.rd(0xBB83 + i) for i in range(10)]
XS = [S.rd(0xBB8D + i) for i in range(10)]
OFFS = [S.rd(0xBD16 + i) for i in range(16)]
ROUTES = []
for i in range(16):
    o, st = OFFS[i], []
    while R(0x6AE + o + len(st)):
        st.append(R(0x6AE + o + len(st)))
    ROUTES.append(st)
START = [(S.rd(0xBCEE + 2 * i), S.rd(0xBCEE + 2 * i + 1)) for i in range(16)]    # (x, y)
DIRS = {1: (-1, 0), 2: (1, 0), 4: (0, -1), 8: (0, 1)}
NAME = {1: "U", 2: "D", 4: "L", 8: "R"}


def main(path):
    L = [l.rstrip("\n") for l in open(path, encoding="latin1", errors="replace")]
    out = []
    sel = [(i, int(m[1]), int(m[2]), int(m[3], 16), int(m[4], 16)) for i, l in enumerate(L)
           if (m := re.match(r"ROUTE_SELECT ghost=(\d) route=(\d+) target_x=\$(\w+) target_y=\$(\w+)", l))]
    sel = [(i, g, r, x, y) for i, g, r, x, y in sel]
    out.append("%d lines, %d route selections" % (len(L), len(sel)))
    cnt = collections.Counter(r for _, _, r, _, _ in sel)
    out.append("selections per route: " + " ".join("%d:%d" % (r, cnt.get(r, 0)) for r in range(16)))
    out.append("routes never selected: %s" % ([r for r in range(16) if r not in cnt] or "none"))
    bad = sum(1 for _, _, r, x, y in sel if (x, y) != START[r])
    out.append("selections whose target junction == PatrolStartPositions[route]: %d of %d" % (len(sel) - bad, len(sel)))
    # per ghost event streams
    pr_bad = pr = 0
    followed = interrupted = 0
    wraps = collections.Counter()
    maxstep = collections.defaultdict(int)
    last = {}
    pend = {}
    for i, l in enumerate(L):
        m = re.match(r"JUNCTION ent=(\d) ptr=\$(\w+) col=(\d+)", l)
        if m:
            g = int(m[1])
            if g == 4:
                continue
            cell = ((int(m[2], 16) - 0x60E) // 10, int(m[3]))
            if g in pend:
                d, at = pend.pop(g)
                if cell == (at[0] + DIRS[d][0], at[1] + DIRS[d][1]):
                    followed += 1
                else:
                    interrupted += 1
            last[g] = cell
            continue
        m = re.match(r"PATROL_ROUTE ghost=(\d) route=(\d+) step=(\d+) dir=\$(\w+)", l)
        if m:
            g, r, st, d = int(m[1]), int(m[2]), int(m[3]), int(m[4], 16)
            pr += 1
            expect = ROUTES[r][st] if st < len(ROUTES[r]) else 0       # the terminator read at step == length is the wrap
            if st > len(ROUTES[r]) or d != expect:
                pr_bad += 1
            maxstep[r] = max(maxstep[r], st)
            if g in last:
                pend[g] = (d, last[g])
            continue
        m = re.match(r"PATROL_WRAP ghost=(\d) route=(\d+)", l)
        if m:
            wraps[int(m[2])] += 1
    out.append("PATROL_ROUTE reads: %d (including %d terminator reads at wrap time), differing from the table: %d" % (pr, sum(wraps.values()), pr_bad))
    out.append("scripted steps followed by the next junction being the neighbour in that direction: %d, other (frightened reversal, route end, etc.): %d" % (followed, interrupted))
    # live loop closure: per ghost, junction cells seen between a ROUTE_SELECT and the next wrap/selection
    closed = collections.Counter(); episodes = collections.Counter()
    cur = {}
    for i, l in enumerate(L):
        m = re.match(r"ROUTE_SELECT ghost=(\d) route=(\d+)", l)
        if m:
            cur[int(m[1])] = {"route": int(m[2]), "cells": [], "steps": 0, "armed": False}
            continue
        m = re.match(r"PATROL_ROUTE ghost=(\d) route=(\d+) step=(\d+)", l)
        if m:
            g = int(m[1])
            if g in cur and cur[g]["route"] == int(m[2]):
                cur[g]["armed"] = True
                cur[g]["steps"] = int(m[3])
            continue
        m = re.match(r"JUNCTION ent=(\d) ptr=\$(\w+) col=(\d+)", l)
        if m and int(m[1]) != 4:
            g = int(m[1]); e = cur.get(g)
            if e and e["armed"]:
                e["cells"].append(((int(m[2], 16) - 0x60E) // 10, int(m[3])))
            continue
        m = re.match(r"PATROL_WRAP ghost=(\d) route=(\d+)", l)
        if m:
            g = int(m[1]); e = cur.get(g)
            if e and e["route"] == int(m[2]) and e["cells"]:
                x, y = START[e["route"]]
                startcell = (YS.index(y), XS.index(x))
                episodes[e["route"]] += 1
                if e["cells"][-1] == startcell:
                    closed[e["route"]] += 1
                e["cells"] = []
    out.append("live loop closure (junction reached at the wrap == the route's start junction): " +
               " ".join("%d:%d/%d" % (r, closed[r], episodes[r]) for r in range(16) if episodes[r]))
    out.append("route: length, furthest step reached, wraps seen")
    for r in range(16):
        out.append("  %2d: %2d steps  %-30s reached step %2d  wraps %d" % (r, len(ROUTES[r]), "".join(NAME[d] for d in ROUTES[r]), maxstep[r], wraps[r]))
    return out, L, sel


if __name__ == "__main__":
    out, _, _ = main(sys.argv[1])
    print("\n".join(out))
    if "--summary-file" in sys.argv:
        open(sys.argv[sys.argv.index("--summary-file") + 1], "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
