"""Stage 78c: the frame dispatcher in port form (tools/core_app_frame.py) against the ROM on the concrete 6502, class by class.  The 15 frame classes of docs/38 are the stratification: for each class random states that
make the dispatcher choose it (and nothing else) are built, the ROM's FrameDispatch `$A6CC` and the deferred handler `$A5FD` run on the machine, the port function runs on the World, and the whole zero page (except the
declared scratch bytes of check_ghost), the maze and its three copies, the title screen, the status rows, the colour shadows, the player-missile pages, the positions, the picture buffers, the ordered chip writes and the
number of RANDOM values are compared.  The class the ROM actually ran is also found from what it did (the entry address trace) and must be the class the state was built for.
Usage: python -I tools/check_app_frame.py [--write analysis/evidence-app-frame-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import check_app_board as CAB  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_play as CPL  # noqa: E402
import check_sound as CSO  # noqa: E402
import core_app_frame as AF  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402

ROOT = A.ROOT

# the 15 classes in the order of the dispatcher's decisions (docs/38 section 4): name, the ROM address that proves the class was chosen (the first instruction only that class runs)
MIXED = "mixed flags"
CLASSES = [
    ("copyright setup", 0xA6D7), ("copyright wait", 0xA711), ("title menu", 0xA719), ("title after game", 0xA719), ("paused", 0xA79C),
    ("board start", 0xA7C8), ("game-over countdown", 0xA7AA), ("level end", 0xAC18), ("start idle", 0xA7C7), ("start tune", 0xA7D3),
    ("turn control", 0xA80D), ("ready wait", 0xA81F), ("death", 0xA833), ("eaten pause", 0xA840), ("play", 0xA843),
]


def base_state(m, rng):
    """a state of the running game (check_sound's, then check_play's), the flags that choose the class left to `make`"""
    CSO.sound_setup(m, rng)
    CPL.play_pre(m, rng)
    m.mem[0x19] = 0                                        # GameState
    m.mem[0x9B] = 0                                        # Paused
    m.mem[0x1C] = rng.choice([0, 1, 3])                    # IntroRequest: not 2
    m.mem[0x20] = 0                                        # CountdownActive
    m.mem[0x26] = 0                                        # LevelComplete
    m.mem[0x21] = 1                                        # PlayStarted
    m.mem[0x22] = rng.choice([0, 1])                       # StartTuneActive
    m.mem[0x24] = 0                                        # WaitState
    m.mem[0x1A] = rng.randrange(2)
    m.mem[0x3C] = rng.randrange(256)                       # SrcPtr points into the ROM tables, as the ghost drawing leaves it (InitDisplay2's stray 16-byte copy READS from it: a pointer at a hardware register is not a state)
    m.mem[0x3D] = rng.randrange(0xBA, 0xC0)
    m.mem[0xE9] = rng.choice([0xFF, 0, 1, 2])             # the ghosts eaten in this frightened period: at most four in the game (a count above 3 makes the pop-up read a pointer past its table; check_play sets that case aside too)
    m.mem[0x1E] = rng.choice([0, 1, 2, 0xE2, rng.randrange(256)])
    m.mem[0x1B] = rng.choice([0, 1, 2, 6, 12, 255, rng.randrange(256)])
    for a in range(0x2000, 0x2050):
        if not (0x2A <= a - 0x2000 <= 0x2F or 0x47 <= a - 0x2000 <= 0x4C):
            m.mem[a] = rng.choice([0, 0x10, 0x12, rng.randrange(256)])
    M2.random_scores(m, rng)                              # the score cells hold digit codes (a cell with another value is not a state: the ROM adds in decimal mode)
    m.mem[0x2E] = rng.randrange(2)
    m.mem[0x2F] = rng.randrange(2)
    for lo, hi in ((0x0800, 0x0C00), (0x1000, 0x1800), (0x1C00, 0x2000)):
        for a in range(lo, hi):
            m.mem[a] = rng.randrange(256)


def make(name, m, rng):
    """the state in which the dispatcher chooses class `name`"""
    base_state(m, rng)
    if name == "copyright setup":
        m.mem[0x19] = 1
    elif name == "copyright wait":
        m.mem[0x19] = 2
        m.mem[0x1D] = m.mem[0x14] if rng.random() < 0.5 else (m.mem[0x14] + rng.randrange(1, 255)) & 0xFF
    elif name == "title menu":
        m.mem[0x19] = 3
    elif name == "title after game":
        m.mem[0x19] = rng.choice([4, 4, 5, 0xFF])
    elif name == "paused":
        m.mem[0x9B] = rng.choice([1, 1, 0x80, 0xFF])
    elif name == "board start":
        m.mem[0x1C] = 2
    elif name == "game-over countdown":
        m.mem[0x20] = rng.choice([1, 1, 0x80])
    elif name == "level end":
        m.mem[0x26] = rng.choice([1, 1, 0x80])
        m.mem[0x27] = rng.choice([0, 1, 2, 3, 4, 5, 255])
        m.mem[0x28] = rng.choice([0, 0, 1, 0x10, 0x40, rng.randrange(256)])
        m.mem[0x29] = rng.choice([0, 1, 1, 2, 7, rng.randrange(256)])
    elif name == "start idle":
        m.mem[0x21] = 0
        m.mem[0x22] = 0
    elif name == "start tune":
        m.mem[0x21] = 0
        m.mem[0x22] = rng.choice([1, 1, 0x80])
        m.mem[0xA3] = rng.choice([0, 1, 0x27, 0x28, 0x29, 0x3F, 0x40, rng.randrange(256)])
        m.mem[0x14] = rng.choice([0, 4, 8, 3, 1, 12, 0x28, rng.randrange(256)])
    elif name == "turn control":
        m.mem[0x24] = 1
        m.mem[0x23] = rng.choice([0, 0, 1, 2, 3, 4])
        m.mem[0x25] = rng.choice([0, 0, 1, 2, 0x30])
        m.mem[0x2C] = rng.choice([0, 1, 3])
        m.mem[0x2D] = rng.choice([0, 1, 3])
    elif name == "ready wait":
        m.mem[0x24] = rng.choice([2, 2, 3, 5, 0x80])
        m.mem[0x25] = rng.choice([0, 0, 1, 2, 0x40, rng.randrange(256)])
    elif name == "death":
        m.mem[0xED] = rng.choice([1, 2, 3, 4, 5, 6, 7, 0x80])
    elif name == "eaten pause":
        m.mem[0xED] = 0
        m.mem[0xE5] = rng.choice([1, 1, 0x80])
    elif name == "play":
        m.mem[0xED] = 0
        m.mem[0xE5] = 0
    elif name == MIXED:
        # several flags at once: the order of the dispatcher's tests decides (docs/38 section 4), so the order itself is checked
        r = rng.random
        m.mem[0x9B] = 1 if r() < 0.2 else 0
        m.mem[0x1C] = 2 if r() < 0.25 else rng.choice([0, 1, 3])
        m.mem[0x20] = 1 if r() < 0.25 else 0
        m.mem[0x26] = 1 if r() < 0.25 else 0
        m.mem[0x21] = 0 if r() < 0.3 else 1
        m.mem[0x22] = 1 if r() < 0.5 else 0
        m.mem[0x24] = rng.choice([0, 0, 1, 2, 3])
        m.mem[0x25] = rng.choice([0, 1, 5, 0x40])
        m.mem[0xED] = rng.choice([0, 0, 0, 1, 3, 6])
        m.mem[0xE5] = 1 if r() < 0.2 else 0
        m.mem[0x27] = rng.choice([0, 1, 2, 3, 4])
        m.mem[0xA3] = rng.choice([0, 1, 0x28, 0x40, rng.randrange(256)])
        m.mem[0x14] = rng.choice([0, 4, 8, rng.randrange(256)])


def diffs(m, w, rnd_used):
    d = CAB.diffs(m, w, CG.SCRATCH)
    if len(m.random_reads) != rnd_used:
        d.append("random %d != %d" % (len(m.random_reads), rnd_used))
    return d


def run_class(name, addr, port, n, seed, ran_check=True):
    """n states of class `name`; the ROM routine at `addr` (FrameDispatch or the handler) against `port(w, rnd)`; also the proof that the ROM ran the class"""
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    proof = name
    mark = dict(CLASSES).get(name)                        # the mixed-flags states have no one class to prove
    C.Machine.wr = CAB._wr
    C.Machine.rd = CPL._rd
    seen = 0
    try:
        for _ in range(n):
            vals = [rng.randrange(256) for _ in range(12)]
            m = A.fresh(base, list(vals))
            make(name, m, rng)
            m.hw = [m.mem[0xD000 + k] for k in range(16)]
            w = W.World().load(m.mem)
            w.collide = list(m.hw)
            del CAB.LOG[:]
            hit = []

            def spy(m_=m, mark_=mark, hit_=hit):
                pass
            # run the ROM routine, watching for the class's marker address
            orig_step = m.step

            def step(orig=orig_step, m_=m, mark_=mark, hit_=hit):
                if m_.pc == mark_:
                    hit_.append(1)
                return orig()
            m.step = step
            m.call(addr)
            m.step = orig_step
            it = CPL.Rnd(vals)
            port(w, it)
            if ran_check and mark is not None and not hit:
                bad.append(("the ROM did not run the class %s" % proof, []))
                continue
            seen += 1
            d = diffs(m, w, it.n)
            if d:
                bad.append((name, d[:4]))
    finally:
        C.Machine.wr = CAB._orig
        C.Machine.rd = CPL._orig_rd
    return n, bad


def report(quick=False):
    n = 150 if quick else 1500
    L = ["The frame dispatcher in port form (tools/core_app_frame.py) against the ROM on the concrete 6502 (tools/check_app_frame.py, stage 78c): FrameDispatch $A6CC and the handler $A5FD, for each of the 15 classes of docs/38: zero page (except the scratch), maze and its three copies, title screen, status rows, shadows, pages, positions, picture buffers, the ordered chip writes and the RANDOM count compared; the ROM must have run the class", ""]
    rows = []
    for name, mark in CLASSES + [(MIXED, None)]:
        nn, bad = run_class(name, 0xA6CC, AF.frame_dispatch, n if mark else 2 * n, 7 + len(name))
        rows.append(("frame_dispatch:" + name, bad))
        L.append("FrameDispatch, class '%s': %d states: %d differences" % (name, nn, len(bad)))
        for b in bad[:3]:
            L.append("  %s" % (b,))
    for name, mark in CLASSES + [(MIXED, None)]:
        nn, bad = run_class(name, 0xA5FD, AF.vbi_handler, n if mark else 2 * n, 91 + len(name))
        rows.append(("vbi_handler:" + name, bad))
        L.append("VbiHandler, class '%s': %d states: %d differences" % (name, nn, len(bad)))
        for b in bad[:3]:
            L.append("  %s" % (b,))
    return L, rows


def main():
    L, rows = report("--quick" in sys.argv)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if any(b for _, b in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
