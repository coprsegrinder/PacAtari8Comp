"""OV-67: the scoring, dot and power-pellet logic on the named World (tools/core_score.py) against the ROM routines.  Usage: python -I tools/check_score.py [--write analysis/evidence-score-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import check_ghost as CG  # noqa: E402
import core_score as S  # noqa: E402
import core_world as W  # noqa: E402

ROOT = A.ROOT


def setup(m, rng):
    M2.randomize(m, rng)
    M2.random_scores(m, rng)
    for k in range(6):
        m.mem[0x94 + k] = rng.choice([0, 0, 0, rng.randrange(10)])
    for p in range(2):
        m.mem[0x2E + p] = rng.choice([0, 0, 1])
        m.mem[0x2C + p] = rng.choice([0, 1, 2, 3, 4, 255, rng.randrange(256)])
        m.mem[0x34 + p] = rng.choice([rng.randrange(256), 3, 255, 4])
        m.mem[0x36 + p] = rng.choice([0, 0, 1])
        m.mem[0x32 + p] = rng.choice([0x0F, 0x0F, rng.randrange(16), rng.randrange(256)])
    ptr = 0x0C00 + rng.randrange(0x400)
    m.mem[0x80], m.mem[0x81] = ptr & 0xFF, ptr >> 8
    m.mem[ptr] = rng.choice([0, 1, 1, 1, 2, 3, 0x80])
    m.mem[0x82] = rng.choice([0, 0, 0, 1])
    m.mem[0xA6] = rng.choice([0, 0, 0, 1])
    m.mem[0x8E], m.mem[0x89] = rng.randrange(256), rng.randrange(256)
    m.mem[0x84], m.mem[0x83] = (m.mem[0x8E], m.mem[0x89]) if rng.random() < 0.3 else (rng.randrange(256), rng.randrange(256))
    if rng.random() < 0.6:
        y, x = rng.choice(((0x3C, 0x3A), (0x3C, 0xBE), (0xA4, 0x3A), (0xA4, 0xBE)))
        m.mem[0x89], m.mem[0x8E] = y, x
    for g in range(4):
        m.mem[0xCE + g] = rng.choice(CG.STATES)
        m.mem[0x8F + g] = rng.choice([1, 2, 4, 8])
    m.mem[0xF6] = rng.randrange(2)


def run(addr, port, n, seed):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        setup(m, rng)
        w = W.World().load(m.mem)
        m.call(addr)
        port(w)
        d = CG.world_diff(m, w, None)
        if d:
            bad.append(d[:5])
    return n, bad


def report(quick=False):
    N = 3000 if quick else 20000
    rows = [("add_to_score", "AddToScore $B423 (score cells, extra life, DrawLives, the carry byte)", 0xB423, S.add_to_score),
            ("draw_lives", "DrawLives $AD15", 0xAD15, S.draw_lives),
            ("eat_dot", "EatDotAtPacMan $B33A (dot, pellet cell, cell memory, dot count, level-complete flag)", 0xB33A, S.eat_dot),
            ("power_pellet", "PowerPelletCheck $B39F (and PowerPelletEaten $B3DE)", 0xB39F, S.power_pellet_check)]
    L = ["Scoring, dots and power pellets on the named World (tools/core_score.py) against the ROM routines (tools/check_score.py, OV-67): zero page (except the scratch), maze, status rows, shadows compared", ""]
    res = []
    for name, what, addr, fn in rows:
        n, bad = run(addr, fn, N, 3)
        res.append(bad)
        L.append("%s: %s: %d calls: %d differences" % (name, what, n, len(bad)))
        for b in bad[:3]:
            L.append("  %s" % (b,))
    return L, res


def main():
    L, res = report("--quick" in sys.argv)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if any(res) else 0


if __name__ == "__main__":
    sys.exit(main())
