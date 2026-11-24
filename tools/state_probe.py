"""Stage 65 (state management): WHICH BYTES OF THE ZERO PAGE ARE STATE?  A sensitivity experiment on the concrete 6502 (tools/cpu6502.py).
For a byte b of the zero page: two copies of the same game state run the handler for K frames with the same random numbers and the same clock; in the second copy byte b was changed before the first frame.  If the outputs (every store to the screen,
the player-missile pages, the character sets, the OS shadows and the chip registers, in order) or the state at the end (the zero page except b itself, the maze screen, the status rows) differ in any trial, the byte INFLUENCES the future: it is state.
A byte that never makes a difference (it is overwritten before it is read, or it is not used) is scratch.  Done for a game of player 1, a game of player 2 (the per-player arrays), the title frames and the frames of the mixed set-up.
Usage: python -I tools/state_probe.py --workers 10 --trials 8 --frames 10 [--write analysis/evidence-state-summary.txt] (the analysis: tools/analyze_state.py)"""
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

MODES = ("play1", "play2", "title", "classes")


def _setup():
    import algorithm_models as A
    import algorithm_models6 as M6
    import algorithm_models7 as M7
    import output_map as O
    return A, M6, M7, O


def make_state(base, rng, mode, mods):
    A, M6, M7, O = mods
    import static_wcet as W
    ys, xs = O.load_junction_lists()
    m = M6.prepare(base, rng)
    M7.frame_setup(m, rng, {"play1": "play", "play2": "play", "title": "title", "classes": "play"}[mode])
    O.realistic(m, rng, ys, xs, "title" if mode == "title" else None)
    if mode in ("play1", "play2", "classes"):
        if mode == "classes":                                   # one of the frame classes of docs/38, with its dispatcher variables
            cls = rng.choice([c for c in W.CLASSES if c not in ("any", "level end", "title menu", "title after game", "copyright setup", "copyright wait")])
            vals = W.CLASSES[cls]
            for a in (0x19, 0x9B, 0x1C, 0x20, 0x26, 0x27, 0x21, 0x22, 0x24, 0xED, 0xE5):
                m.mem[a] = vals.get(a, rng.choice([0, 0, 1]) if a in (0x27, 0x22) else (1 if a == 0x21 else 0))
            if cls == "game-over countdown":
                m.mem[0x1E] = rng.choice([0, 1, 50, 200])
            if cls == "turn control":
                m.mem[0x23] = rng.choice([0, 1, 2, 3])
            if cls == "ready wait":
                m.mem[0x25] = rng.choice([0, 1, 40])
            if cls == "level end 4" or cls.startswith("level end"):
                m.mem[0x28] = rng.choice([0, 0, 1, 20])
                m.mem[0x29] = rng.randrange(1, 9)
            if cls == "death":
                m.mem[0xED] = rng.choice([1, 2, 3, 4, 5, 6])
                m.mem[0xEE] = rng.choice([0, 1, 40, 96])
            if cls == "eaten pause":
                m.mem[0xE5] = 1
                m.mem[0xE6], m.mem[0xE7] = rng.choice([0, 1, 2]), rng.randrange(0x40, 0x90)
        else:
            for a, v in ((0x19, 0), (0x9B, 0), (0x1C, 0), (0x20, 0), (0x26, 0), (0x21, 1), (0x22, 1), (0x24, 0), (0x23, 0), (0xAA, 0), (0xED, 0), (0xE5, 0)):
                m.mem[a] = v                                   # the dispatcher in the play frame
        m.mem[0x1A] = 1 if mode == "play2" else rng.randrange(2)    # TwoPlayers
        m.mem[0x2B] = 1 if (mode == "play2" or (mode == "classes" and m.mem[0x1A] and rng.random() < 0.5)) else 0   # the player on turn
        if rng.random() < 0.7:                                  # entities on junction cells: the steering code runs only there
            for g in range(5):
                m.mem[0x85 + g] = rng.choice(ys)
                m.mem[0x8A + g] = rng.choice(xs)
        if rng.random() < 0.85:                                 # no remembered turn: a buffered corner sets the corner flag, and with it the ghosts do not move that frame (docs/41)
            m.mem[0xAC] = 0
            m.mem[0xA8] = 0
        m.mem[0x83] = m.mem[0x89] if rng.random() < 0.5 else rng.randrange(256)      # the cell of the last dot test: the same as Pac-Man's, or one coordinate of it, or none
        m.mem[0x84] = m.mem[0x8E] if rng.random() < 0.5 else (m.mem[0x8E] + 1) & 255
        if rng.random() < 0.6:                                  # the ghosts: any of the documented states, moving this frame, with short timers
            for g in range(4):
                m.mem[0xCE + g] = rng.choice([0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x42, 0x44, 0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0])
                m.mem[0xB5 + g] = rng.choice([1, 1, 2])             # MoveDelayTick counts down: 1 means the ghost moves this frame
                m.mem[0xCA + g] = rng.choice([0, 0, 1, 50, 0x96])
        if rng.random() < 0.5:                                  # Pac-Man on a dot: the cell counters at zero and a dot (or a power pellet cell) under the maze pointer
            m.mem[0x82] = m.mem[0xA6] = 0
            ptr = m.mem[0x80] | m.mem[0x81] << 8
            m.mem[ptr] = rng.choice([1, 1, 2, 3])
    return m


def clone(m, A, base):
    c = A.fresh(base)
    c.mem[:] = m.mem
    c.random = list(m.random)
    c.os_calls = []
    return c


class Trace:
    def __init__(self, O, C):
        self.O, self.C = O, C
        self.log = []
        self.orig = C.Machine.wr

    def install(self):
        tr = self

        def wr(m, a, v):
            r = tr.O.region_of(a & 0xFFFF)
            if r in tr.O.OUTPUT:
                tr.log.append((a & 0xFFFF, v & 0xFF))
            tr.orig(m, a, v)
        self.C.Machine.wr = wr

    def remove(self):
        self.C.Machine.wr = self.orig


def run_frames(m, K, seed, tr):
    rng = random.Random(seed)
    del tr.log[:]
    for k in range(K):
        m.mem[0x14] = (m.mem[0x14] + 1) & 255                  # the OS clock
        m.random = [rng.randrange(256) for _ in range(12)]
        m.call(0xA5FD)
    return list(tr.log)


def final_state(m, skip):
    return (bytes(b for i, b in enumerate(m.mem[:0x100]) if i != skip), bytes(m.mem[0x0C00:0x0F98]), bytes(m.mem[0x2000:0x2050]))


def trial(args):
    """-> {byte: [mode, ...]} the modes in which a trial showed a difference"""
    byte_range, T, K, seed = args
    A, M6, M7, O = _setup()
    import cpu6502 as C
    base = A.started_machine()
    tr = Trace(O, C)
    tr.install()
    out = {}
    try:
        for b in byte_range:
            hits = []
            for mode in MODES:
                diff = 0
                done = 0
                for t in range(T):
                    rng = random.Random((seed * 1000003 + b * 131 + t * 7 + MODES.index(mode)) & 0xFFFFFFFF)
                    m0 = make_state(base, rng, mode, (A, M6, M7, O))
                    ma, mb = clone(m0, A, base), clone(m0, A, base)
                    old = mb.mem[b]
                    other = ma.mem[rng.randrange(0x100)]                       # a value another byte holds: an equality test against it can be hit
                    mb.mem[b] = rng.choice([v for v in (0, 1, 2, 4, 8, 0x10, 0x20, 0x40, 0x80, 0xFF, rng.randrange(256), old ^ 0xFF, (old + 1) & 255, other, other, ma.mem[0x89], ma.mem[0x8E]) if v != old])
                    fseed = rng.randrange(1 << 30)
                    try:
                        ta = run_frames(ma, K, fseed, tr)
                        tb = run_frames(mb, K, fseed, tr)
                    except Exception:
                        try:
                            run_frames(ma, K, fseed, tr)
                            diff += 1                          # only the changed copy fails: the byte matters
                            done += 1
                        except Exception:
                            pass
                        continue
                    done += 1
                    if ta != tb or final_state(ma, b) != final_state(mb, b):
                        diff += 1
                if diff:
                    hits.append((mode, diff, done))
            out[b] = hits
    finally:
        tr.remove()
    return out


def probe(workers=10, trials=8, frames=10, seed=1, bytes_=range(256)):
    chunks = [list(bytes_)[i::workers * 3] for i in range(workers * 3)]
    res = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for part in ex.map(trial, [(c, trials, frames, seed) for c in chunks]):
            res.update(part)
    return res


if __name__ == "__main__":
    a = sys.argv
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 10
    trials = int(a[a.index("--trials") + 1]) if "--trials" in a else 8
    frames = int(a[a.index("--frames") + 1]) if "--frames" in a else 10
    only = [int(x, 16) for x in a[a.index("--bytes") + 1].split(",")] if "--bytes" in a else None
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 1
    res = probe(workers, trials, frames, seed, only if only else range(256))
    path = os.path.join(ROOT, "analysis", "raw-logs", "state-probe-extra.json" if only else "state-probe.json")
    with open(path, "w") as fh:
        json.dump({"trials": trials, "frames": frames, "modes": MODES, "result": {str(k): v for k, v in res.items()}}, fh)
    print("bytes with a difference:", sum(1 for v in res.values() if v), "of", len(res), "->", path)
