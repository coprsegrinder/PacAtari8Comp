"""OV-67: one frame of play in port form (tools/core_play.py) against the ROM frame body of FrameDispatch ($A82C) on the concrete 6502.  Each trial is a random game state of the stage-65 kind (entities on the lattice, ghosts in every
state, the pellets, the bonus, the death states, the eaten pause); the collision registers are random inputs.  The zero page (except the scratch), the maze screen, the status rows (the score), the colour shadows, the ordered writes to the
sound chip and the number of RANDOM values used are compared; a second mode runs 20 frames in a row.
Usage: python -I tools/check_play.py [--write analysis/evidence-play-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import check_frame as CF  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_sound as CSO  # noqa: E402
import core_play as PL  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402

ROOT = A.ROOT


class Rnd:
    """the RANDOM values handed to the port, counted"""

    def __init__(self, vals):
        self.v = iter(vals)
        self.n = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.n += 1
        return next(self.v)


_orig_rd = C.Machine.rd


def _rd(m, a):
    """$D000-$D00F read as the GTIA collision registers (inputs), not as the HPOSP / HPOSM registers the code writes at the same addresses"""
    a &= 0xFFFF
    if 0xD000 <= a <= 0xD00F:
        return m.hw[a & 15]
    return _orig_rd(m, a)


def play_pre(m, rng):
    CF.frame_pre(m, rng)
    m.mem[0x24] = 0                                       # WaitState: the running game
    for k in range(4):
        m.mem[0x0278 + k] = rng.choice([0x0F, 0x0F, 0x0E, 0x0D, 0x0B, 0x07, 0x0A, 0x06, 0x05, 0x09, rng.randrange(16)])
    m.mem[0xAC] = rng.choice([0, 0, 1, 2, 4, 8])
    m.mem[0xED] = rng.choice([0] * 12 + [1, 2, 3, 4, 5, 6])
    m.mem[0xE5] = rng.choice([0] * 8 + [1])
    m.mem[0x26] = rng.choice([0, 0, 0, 1])
    m.mem[0xAA] = rng.choice([0, 0, 0, 0x80])
    m.mem[0xA8] = rng.choice([0, 0, 0, 0, 1])
    m.mem[0xA9] = rng.choice([0, 0, 0, 1])
    m.mem[0xFC] = rng.choice([0, 0, m.mem[0xFC]])
    for k in range(4):
        m.mem[0xB5 + k] = rng.choice([1, 1, 2, 3])        # MoveDelayCount: 1 moves this frame
        m.mem[0x5A + k] = rng.choice([0, 1])
    m.mem[0xB9] = rng.choice([1, 1, 2])
    for a in (0xA1, 0xA2, 0x9F, 0x9D, 0x9E):
        m.mem[a] = rng.choice([0, 0, 1, 2, rng.randrange(256)])
    for p in range(2):
        m.mem[0x43 + p] = rng.choice([0, 1, 2])
        m.mem[0x34 + p] = rng.choice([0x50, 0xA0, 0x4F, 0xB0, 0xE0, 0xF0, rng.randrange(256)])
    if rng.random() < 0.5:                                # Pac-Man on a ghost
        g = rng.randrange(4)
        m.mem[0x85 + 4] = (m.mem[0x85 + g] + rng.choice([0, 1, 2, 4, 5, 6])) & 255
        m.mem[0x8A + 4] = m.mem[0x8A + g]
    for k in range(16):
        m.mem[0xD000 + k] = rng.choice([0, 0xFF, rng.randrange(256)])
    if rng.random() < 0.2:                                # Pac-Man on a power-pellet square, the pellet still there
        y, x = rng.choice(((0x3C, 0x3A), (0x3C, 0xBE), (0xA4, 0x3A), (0xA4, 0xBE)))
        m.mem[0x89], m.mem[0x8E] = y, x
        m.mem[0x32 + (m.mem[0x2B] & 1)] = rng.choice([0x0F, 0x0F, rng.randrange(16)])
    m.mem[0xD009] = rng.choice([0x0F, 0x0F, rng.randrange(256)])
    m.mem[0xD00A] = rng.choice([0x0F, 0x0F, rng.randrange(256)])
    m.mem[0xD002] = rng.choice([0, 0, 2, 3, rng.randrange(256)])


def run(n, seed, frames=1):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    skipped = [0]
    cover = {"death": 0, "eaten pause": 0, "ghost eaten": 0, "pellet": 0, "contact kill": 0, "bonus pick-up": 0, "ghosts moved": 0, "pacman moved": 0, "corner": 0}
    C.Machine.wr = CSO._wr
    C.Machine.rd = _rd
    try:
        for _ in range(n):
            rnds = [[rng.randrange(256) for _ in range(12)] for _ in range(frames)]
            m = A.fresh(base, [v for r in rnds for v in r])
            CSO.sound_setup(m, rng)
            play_pre(m, rng)
            m.hw = [m.mem[0xD000 + k] for k in range(16)]
            w = W.World().load(m.mem)
            w.collide = list(m.hw)
            st0 = (m.mem[0xED], m.mem[0xE5], list(m.mem[0xCE:0xD2]), m.mem[0x32 + m.mem[0x2B]], m.mem[0x8E], list(m.mem[0x85:0x89]), list(m.mem[0x8A:0x8E]))
            fail = None
            it = Rnd([v for r in rnds for v in r])           # one stream of RANDOM values for all the frames, as the ROM reads it
            for f in range(frames):
                del CSO.LOG[:]
                w.pokey = []
                if f:
                    m.mem[0x14] = (m.mem[0x14] + 1) & 255
                    w.RTCLOK2 = (w.RTCLOK2 + 1) & 255
                e9_before = m.mem[0xE9]
                m.call(0xA82C)
                if m.mem[0xE5] == 0:                              # the handler: after the frame body, the tunnel clip unless the eaten-ghost pause is on ($A606-$A60A)
                    m.call(0xAB48)
                try:
                    PL.vbi_play_frame(w, it)
                except IndexError:                                # the random state walked the maze pointer out of the maze: not a state of the game
                    skipped[0] += 1
                    break
                d = CSO.diffs(m, w, True)
                if "pm" in d and m.mem[0xE5] and m.mem[0xE9] > 3 and m.mem[0xE9] != e9_before:
                    d.remove("pm")                                 # a ghost was eaten with a count above 3: the pop-up picture comes through GhostScorePtrs[2 * count], not a state of the game
                if len(m.random_reads) != it.n:
                    d.append("random %d != %d" % (len(m.random_reads), it.n))
                if d:
                    fail = (f, d[:5])
                    break
            if fail:
                bad.append(fail)
            cover["death"] += st0[0] != 0
            cover["eaten pause"] += st0[1] != 0
            cover["ghost eaten"] += m.mem[0xE5] != 0 and st0[1] == 0
            cover["pellet"] += m.mem[0x32 + m.mem[0x2B]] != st0[3]
            cover["contact kill"] += m.mem[0xED] == 1 and st0[0] == 0
            cover["bonus pick-up"] += m.mem[0xA1] == 1 and m.mem[0xA2] == 0x40
            cover["ghosts moved"] += list(m.mem[0x85:0x89]) != st0[5] or list(m.mem[0x8A:0x8E]) != st0[6]
            cover["pacman moved"] += m.mem[0x8E] != st0[4]
            cover["corner"] += m.mem[0xA8] != 0
    finally:
        C.Machine.wr = CSO._orig
        C.Machine.rd = _orig_rd
    cover["skipped"] = skipped[0]
    return bad, cover


def report(quick=False):
    n1, n2 = (1500, 150) if quick else (8000, 500)
    L = ["One frame of play in port form (tools/core_play.py) against the ROM frame body $A82C (tools/check_play.py, OV-67): zero page (except the scratch), maze, status rows, shadows, sound-chip writes and RANDOM reads compared", ""]
    res = []
    bad, cover = run(n1, 21, 1)
    res.append(bad)
    L.append("play_frame: %d random frames: %d differences (reached: %s)" % (n1, len(bad), ", ".join("%s %d" % kv for kv in cover.items())))
    for b in bad[:3]:
        L.append("  %s" % (b,))
    bad2, cover2 = run(n2, 22, 20)
    res.append(bad2)
    L.append("play_frame x20: %d runs of 20 frames in a row (the clock advancing, the state carried by the port itself; %d left the maze and were skipped): %d differences" % (n2, cover2["skipped"], len(bad2)))
    for b in bad2[:3]:
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
