"""OV-67: the frightened tick, the eaten ghost and the eyes-and-house routine in port form (tools/core_frame.py) against the ROM on the concrete 6502: zero page, shadows, the ordered sound-chip writes and the number of RANDOM
values used are compared (the maze and status rows too, except where a routine draws).
Usage: python -I tools/check_frame.py [--write analysis/evidence-frame-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_sound as CSO  # noqa: E402
import core_frame as F  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402

ROOT = A.ROOT


def frame_pre(m, rng):
    for g in range(4):
        m.mem[0xCE + g] = rng.choice([0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x42, 0x44, 0x80, 0x82, 0x84, 0x88, 0x90, 0xA0, 0xC2, 0xC4, 0x46, 0x4C])
    if rng.random() < 0.4:                               # eyes at the door, on their way to it, in the house
        g = rng.randrange(4)
        m.mem[0xCE + g] = rng.choice([0x42, 0x42, 0x44, 0xC2])
        m.mem[0x8A + g], m.mem[0x85 + g] = rng.choice([(0x7C, 0x64), (0x7C, 0x64), (0x70, 0x74), (0x88, 0x74), (0x7C, 0x74), (0x7C, 0x70)])
    lv = m.mem[0x30 + (m.mem[0x2B] & 1)]
    end = CG.T.ram(0x0672 + lv)
    m.mem[0xFC] = rng.choice([0, 1, 2, end, end, max(end - 1, 0), rng.randrange(256)])
    m.mem[0xFD] = rng.choice([0, 0, 0, 1, rng.randrange(256)])
    m.mem[0xFB] = rng.choice([0, 1, 0x18, rng.randrange(256)])
    m.mem[0xF2] = rng.choice([0, 0, 1, 5])
    m.mem[0xE8] = rng.choice([0xFF, 0, 1, 2, 3])
    m.mem[0xE9] = rng.choice([0xFF, 0, 1, 2, 3, 4, rng.randrange(256)])


def run(addr, port, n, seed, pre=None, maze=False, with_x=False):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    C.Machine.wr = CSO._wr
    try:
        for _ in range(n):
            rnd = [rng.randrange(256) for _ in range(8)]
            m = A.fresh(base, list(rnd))
            CSO.sound_setup(m, rng)
            frame_pre(m, rng)
            x = rng.randrange(4)
            w = W.World().load(m.mem)
            del CSO.LOG[:]
            it = iter(rnd)
            if with_x:
                m.call(addr, x=x)
                port(w, x, it)
            else:
                m.call(addr)
                port(w, it)
            used = len(rnd) - len(list(it))
            d = CSO.diffs(m, w, maze)
            if with_x and m.mem[0xE9] > 3 and 'pm' in d:
                d.remove('pm')                                    # the pop-up picture is read through GhostScorePtrs[2 * count]: a count above 3 is not a state of the game (the pointer comes from other table bytes)
            if len(m.random_reads) != used:
                d.append("random %d != %d" % (len(m.random_reads), used))
            if d:
                bad.append(d[:4])
    finally:
        C.Machine.wr = CSO._orig
    return n, bad


def report(quick=False):
    N = 1500 if quick else 5000
    rows = [("frightened_tick", "FrightenedTick $AF54 (phase 0 with the siren, the countdown, every phase against the level's end phase, the end)", 0xAF54, lambda w, it: F.frightened_tick(w), False, False),
            ("ghost_eaten", "GhostEaten $A886 (every ghost, the count before $FF .. 4 and wrapped values)", 0xA886, lambda w, x, it: F.ghost_eaten(w, x), False, True),
            ("eyes_and_house", "EyesAndHousePerFrame $B69E (eyes steering to the door, the arrival, the house, the whistle, the leaving)", 0xB69E, lambda w, it: F.eyes_and_house_per_frame(w, it), False, False)]
    L = ["The frightened tick, the eaten ghost and the eyes and house in port form (tools/core_frame.py) against the ROM routines (tools/check_frame.py, OV-67): zero page (except the scratch), shadows, sound-chip writes and RANDOM reads compared", ""]
    res = []
    for name, what, addr, fn, maze, wx in rows:
        n, bad = run(addr, fn, N, 11, None, maze, wx)
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
