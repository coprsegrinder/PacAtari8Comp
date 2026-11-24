"""OV-67: Pac-Man's movement in port form (tools/core_pacman.py) against MovePacMan on the concrete 6502; the zero page (except the drawing and junction scratch), the maze, the status rows and the colour shadows are compared.
Usage: python -I tools/check_pacman.py [--write analysis/evidence-pacman-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import check_ghost as CG  # noqa: E402
import core_pacman as P  # noqa: E402
import core_tables as T  # noqa: E402
import core_world as W  # noqa: E402

ROOT = A.ROOT


def setup(m, rng):
    M2.randomize(m, rng)
    x, y = CG.lattice(rng)
    if rng.random() < 0.15:
        x, y = rng.choice([0x2A, 0xCA, 0x2B, 0xC9]), 0x74
    m.mem[0x8E], m.mem[0x89] = x, y
    m.mem[0x93] = rng.choice([1, 2, 4, 8, 8, 4, 0, 3])
    m.mem[0xAC] = rng.choice([0, 1, 2, 4, 8, 3, 5, 12, rng.randrange(256)])
    m.mem[0xA8] = rng.choice([0, 0, rng.randrange(16)])
    m.mem[0xA6] = rng.choice([0, 1, 2, 3, 3, rng.randrange(256)])
    m.mem[0x82] = rng.choice([0, 1, 2, 3, 3, rng.randrange(256)])
    m.mem[0xA7] = rng.choice([0, 0, 0, 1])
    m.mem[0xAA] = rng.choice([0, 0, 0, 0x80])
    m.mem[0xAB] = rng.choice([0, 1, 2, 3, rng.randrange(256)])
    m.mem[0x83] = rng.choice([y, (y + 2) & 255, rng.randrange(256)])
    m.mem[0x84] = rng.choice([x, (x + 1) & 255, (x - 1) & 255, rng.randrange(256)])
    ptr = 0x0C00 + rng.randrange(0x400)
    m.mem[0x80], m.mem[0x81] = ptr & 0xFF, ptr >> 8
    m.mem[0x2B] = rng.randrange(2)
    for k in range(4):
        m.mem[0x0278 + k] = rng.choice([0x0F, 0x0E, 0x0D, 0x0B, 0x07, 0x0A, 0x06, 0x05, 0x09, 0x00, 0x03, rng.randrange(256), rng.randrange(16)])


def run(n, seed):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, moved, tunnel, corner, joy = [], 0, 0, 0, 0
    for _ in range(n):
        m = A.fresh(base)
        setup(m, rng)
        w = W.World().load(m.mem)
        x0, c0, atr0 = m.mem[0x8E], m.mem[0xA8], m.mem[0x4D]
        m.call(0xB179)
        P.move_pacman(w)
        d = CG.world_diff(m, w, None)
        moved += m.mem[0x8E] != x0
        tunnel += abs(m.mem[0x8E] - x0) > 2
        corner += m.mem[0xA8] != c0
        joy += m.mem[0x4D] != atr0
        if d:
            bad.append((d[:5],))
    return bad, moved, tunnel, corner, joy


def report(quick=False):
    n = 4000 if quick else 40000
    bad, moved, tunnel, corner, joy = run(n, 71)
    L = ["Pac-Man's movement in port form (tools/core_pacman.py) against MovePacMan $B179 on the concrete 6502 (tools/check_pacman.py, OV-67): the whole zero page (except the scratch), maze, status rows, colour shadows compared", "",
         "move_pacman: %d calls (random positions on and off the lattice, the tunnel mouths, every direction, sub-cell, hold, frozen, cornering and joystick value): %d differences (%d moved sideways, %d through a tunnel, %d set the cornering flag, %d took a joystick direction)" % (n, len(bad), moved, tunnel, corner, joy)]
    for b in bad[:3]:
        L.append("  %s" % (b,))
    return L, bad


def main():
    L, bad = report("--quick" in sys.argv)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
