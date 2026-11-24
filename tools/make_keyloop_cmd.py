"""OV-65: a counter for every outcome of every conditional branch of the key loop `$A4BA-$A572` (docs/38 section 3), as Altirra debugger commands to be appended to a session harness.
Each branch gets two 16-bit counters in RAM ($4300 + 4 k: taken, not taken), saturating at 65535 (the debugger clamps a word, it does not wrap it), that a breakpoint at the branch instruction increments from the processor flags (the flags at the
branch decide it), and a tracepoint at the entry of the vertical-blank handler writes all counters to the log once a frame (`KC f=<frame> p=<passes of the loop in the last frame> t0 n0 t1 n1 ...`).  Nothing is written to the game's memory or registers.
`--blocks a4ed,a4f1` counts how often an instruction ran (for points that are cold: $A4ED runs only while the game-over countdown is on, $A4F1 once when it ends).  `--only a4eb,a4ef` counts only those branches (a targeted run: the key loop executes about 140 passes a frame and every counted branch costs a breakpoint hit, so a full run is slow); the others stay 0 in the log.
Usage: python -I tools/make_keyloop_cmd.py [--out tools/keyloop_counters.cmd] [--only a4eb,a4ef] [--nopass]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import absint6502 as AB  # noqa: E402

LO, HI = 0xA4BA, 0xA572
# the flag of each branch, from the processor status @p (the debugger's >> is not a shift: masks and divisions)
BR = {"bpl": "1-((@p&$80)/$80)", "bmi": "((@p&$80)/$80)", "bvc": "1-((@p&$40)/$40)", "bvs": "((@p&$40)/$40)", "bcc": "1-(@p&1)", "bcs": "(@p&1)", "bne": "1-((@p&2)/2)", "beq": "((@p&2)/2)"}
BASE = 0x4300


def branches():
    p = AB.Program()
    return [(a, p.ins[a][1], p.ins[a][3]) for a in sorted(p.ins) if LO <= a <= HI and p.ins[a][1] in BR]


def commands(only=None, passes=True, blocks=None):
    out = ["# OV-65: the outcome counters of the key loop (tools/make_keyloop_cmd.py); the counters are 16-bit words at $%04X, two a branch (taken, not taken), saturating at 65535 (so that 'ever happened' survives)%s" % (
        BASE, "; the passes of the loop in a frame are counted by a word at $4400 that is cleared once a frame" if passes else "")]
    n_br = 0
    for k, (a, m, tgt) in enumerate(branches()):
        n_br += 1
        if only is not None and a not in only:
            continue                                                   # a targeted run: the branches not asked for stay 0 in the log
        t, n = BASE + 4 * k, BASE + 4 * k + 2
        out.append('bp -n %x "ew $%x (dw($%x)+(%s)*(dw($%x)<65535)); ew $%x (dw($%x)+(1-(%s))*(dw($%x)<65535))"' % (a, t, t, BR[m], t, n, n, BR[m], n))
    if passes:
        out.append('bp -n a4ba "ew $4400 (dw($4400)+1)"')
        out.append('bp -n a603 "ew $4400 0"')                          # cleared just after the entry of the handler, so that the tracepoint at the entry logs the passes of the frame before
    fmt = "KC f=%d p=%d " + " ".join("%d %d" for _ in range(n_br))
    args = " ".join("dw($%x) dw($%x)" % (BASE + 4 * k, BASE + 4 * k + 2) for k in range(n_br))
    if not blocks or only is None or len(only) > 1 or passes:
        out.append('bt a5fd "%s" @frame dw($4400) %s' % (fmt, args))
    if blocks:                                                         # block counters for COLD points: how many times an instruction ran (words at $4600 +2 k, saturating), logged as `KB f=<frame> n0 n1 ...`
        for k, a in enumerate(blocks):
            out.append('bp -n %x "ew $%x (dw($%x)+(dw($%x)<65535))"' % (a, 0x4600 + 2 * k, 0x4600 + 2 * k, 0x4600 + 2 * k))
        out.append('bt a5fd "KB f=%d ' + " ".join("%d" for _ in blocks) + '" @frame ' + " ".join("dw($%x)" % (0x4600 + 2 * k) for k in range(len(blocks))))
    return out


if __name__ == "__main__":
    a = sys.argv
    path = a[a.index("--out") + 1] if "--out" in a else os.path.join(HERE, "keyloop_counters.cmd")
    only = {int(x, 16) for x in a[a.index("--only") + 1].split(",")} if "--only" in a else None
    blocks = [int(x, 16) for x in a[a.index("--blocks") + 1].split(",")] if "--blocks" in a else None
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(commands(only, "--nopass" not in a, blocks)) + "\n")
    print(len(branches()), "branches ->", path)
