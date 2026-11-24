"""OV-67: the sound and death routines in port form (tools/core_sound.py) against the ROM on the concrete 6502: the zero page and the ordered writes to the sound chip ($D200-$D20F) and HITCLR ($D01E) are compared.
Usage: python -I tools/check_sound.py [--write analysis/evidence-sound-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_score as CS  # noqa: E402
import core_sound as SO  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402

ROOT = A.ROOT
LOG = []
_orig = C.Machine.wr


def _wr(m, a, v):
    a &= 0xFFFF
    if 0xD200 <= a <= 0xD20F or a == 0xD01E:
        LOG.append((a, 0 if a == 0xD01E else v & 0xFF))      # HITCLR: any value clears
    _orig(m, a, v)


def sound_setup(m, rng):
    CS.setup(m, rng)
    CG.setup(m, rng)
    rv = rng.choice
    m.mem[0xF4] = rv([0, 1, 1])
    m.mem[0xF5] = rv([0, 1, 5, 6, 7, rng.randrange(256)])
    m.mem[0xF6] = rv([0, 1])
    m.mem[0xF7] = rv([0, 1, 2, 5, 6, 7, 8, 9, 10, rng.randrange(256)])
    m.mem[0xF8] = rv([0xB4, 0xAF, 0x78, 0x7D, 0x7F, 0xFB, 0xFF, rng.randrange(256)])
    m.mem[0xE1] = rv([0x90, 0x40, 0x50, 0xF0, 0x80, rng.randrange(256)])
    m.mem[0xE2] = rv([1, 2])
    m.mem[0xE3] = rv([3, 4, 5, rng.randrange(256)])
    m.mem[0xE4] = rv([0, 1])
    m.mem[0xF3] = rv([0, 0x0C, 0x16, 0x17, rng.randrange(256)])
    m.mem[0xDE] = rv([0x28, 0x3F, 0x40, 0x41, 0x27, 0xFF, rng.randrange(256)])
    m.mem[0xDF] = rv([1, 2, 0])
    m.mem[0xE0] = rv([0, 1])
    m.mem[0x9C] = rv([2, 3, 4, 5, 6, 8, 16])      # the siren step is 2 to 5 in the game; a step with step + tone = 0 (mod 256) below $28 would loop for ever in the ROM
    m.mem[0xE5] = rv([0, 1])
    m.mem[0xE6] = rv([1, 2, 3, rng.randrange(256)])
    m.mem[0xE7] = rv([0x84, 0x14, 0x18, 0x13, 0x17, rng.randrange(256)])
    for k in range(4):
        m.mem[0x02C0 + k] = rv([0xDC, 0xDC, 0x0C, rng.randrange(256)])
    m.mem[0xED] = rv([1, 2, 3, 4, 5, 6, 7, 0])
    m.mem[0xEE] = rv([0, 1, 40, 97])
    m.mem[0xEF] = rv([0x35, 0x6D, 0x69, 0x25, 0x2D, 0x31, rng.randrange(256)])
    m.mem[0xF0] = rng.randrange(256)
    m.mem[0xF1] = rv([0, 1, 2, 3, 4, 0x80, rng.randrange(256)])
    m.mem[0xEA] = rv([0, 1])
    m.mem[0xEB] = rv([0, 1, 14, 15, rng.randrange(256)])
    m.mem[0xEC] = rv([0, 1, 7, 0x80, 0x81, rng.randrange(256)])
    m.mem[0x14] = rv([0, 4, 8, 12, 16, rng.randrange(256)])


def diffs(m, w, maze):
    d = CG.world_diff(m, w, None)
    d = [x for x in d if maze or x not in ("maze", "status")]
    if LOG != w.pokey:
        d.append("pokey %s != %s" % (LOG[:4], w.pokey[:4]))
    return d


def run(addr, port, n, seed, maze=True, pre=None, until_fn=None):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    C.Machine.wr = _wr
    try:
        for _ in range(n):
            m = A.fresh(base)
            sound_setup(m, rng)
            if pre:
                pre(m, rng)
            w = W.World().load(m.mem)
            del LOG[:]
            port(w)
            if until_fn:
                m.call(addr, until=until_fn(w))
            else:
                m.call(addr)
            d = diffs(m, w, maze)
            if d:
                bad.append(d[:4])
    finally:
        C.Machine.wr = _orig
    return n, bad


def tune_pre(m, rng):
    m.mem[0xA3] = rng.choice([0, 1, 0x27, 0x28, 0x29, 0x3F, 0x40, rng.randrange(0x41)])
    m.mem[0x14] = rng.choice([0, 4, 8, 3, 1, 12, rng.randrange(256)])


def report(quick=False):
    N = 2000 if quick else 4000
    rows = [
        ("clear_pokey", "ClearPokeyRegisters $B0E6", 0xB0E6, SO.clear_pokey, True),
        ("dot_sound_sweep", "DotSoundSweep $B0BC", 0xB0BC, SO.dot_sound_sweep, True),
        ("bonus_sound", "BonusSound $ABC9 (every step of the sweep, the wrap of the pitch)", 0xABC9, SO.bonus_sound, True),
        ("frightened_sound", "FrightenedSound $AFD7", 0xAFD7, SO.frightened_sound, True),
        ("eyes_returning_sound", "EyesReturningSound $B02C", 0xB02C, SO.eyes_returning_sound, True),
        ("siren", "the siren $B508", 0xB508, SO.siren, True),
        ("ghost_eaten_pause", "GhostEatenPause $B049 (both sweeps, the end with Pac-Man's step and the dot)", 0xB049, SO.ghost_eaten_pause, True),
        ("death_sequence", "DeathSequence $AE3D (states 1-6 and the others)", 0xAE3D, SO.death_sequence, True),
        ("death_animation", "DeathAnimation $AEF7 (the counters and the pictures, OV-69)", 0xAEF7, SO.death_animation, False),
    ]
    L = ["The sound and the death in port form (tools/core_sound.py) against the ROM routines (tools/check_sound.py, OV-67): zero page (except the scratch), shadows and the ordered writes to the sound chip and HITCLR compared", ""]
    res = []
    for name, what, addr, fn, maze in rows:
        n, bad = run(addr, fn, N, 5, maze)
        res.append(bad)
        L.append("%s: %s: %d calls: %d differences" % (name, what, n, len(bad)))
        for b in bad[:3]:
            L.append("  %s" % (b,))
    # the start tune: the ROM block $A7D3; at step $40 the code goes on into the frame logic at $A805, where the run is stopped
    holder = {}

    def tune_port(w):
        holder["r"] = SO.start_tune_step(w)

    n, bad = run(0xA7D3, tune_port, N, 9, False, tune_pre, lambda w: 0xA805 if holder["r"] == "play" else None)
    res.append(bad)
    L.append("start_tune_step: the start tune block of FrameDispatch $A7D3 (steps 0-$40, the READY! step $28; every RTCLOK2): %d calls: %d differences" % (n, len(bad)))
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
