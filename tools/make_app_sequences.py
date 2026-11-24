"""Stage 79b (docs/51): writes the SEQUENCE vector sets of the application layer into resources/vectors/ (derived data, git-ignored): the Python port (tools/core_app_board.py, whose sequences equal the ROM call by call:
tests/test_app_board.py) is called again and again on one state, the clock advancing by one between the calls, and every call is a record whose "before" is the previous "after" with RTCLOK2 + 1 - the form the vector
runner's `--chain` mode recognises and runs from the state the C itself made.  A difference that only shows after several calls (a counter that is off by one, a state that is not carried) cannot hide.
  seq_core_app_board.turn_control        60 two-player and game-over states x 140 calls  (the hand-over with its waits, the maze swaps, the game over)
  seq_core_app_board.level_end_step      30 states x 200 calls  (the level end from the stop to the next board)
  seq_core_app_frame.vbi_handler         the stories of tests/test_app_frame.py (the copyright screen into the title, the start tune into play, the level end, the hand-over, a death): 12-520 frames each
  session_*.vec                          whole sessions from power-on (stage 79d: a one-player game to the title, a session of keys, a level end, a clock that wraps, a two-player game): one record a frame
Usage: python -I tools/make_app_sequences.py [--quick] [--out DIR]    (--quick: 10 and 6 runs instead of 60 and 30, for the tests)"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import check_app_board as CAB  # noqa: E402
import core_app_board as AB  # noqa: E402
import core_world as W  # noqa: E402
import core_app_frame as AF  # noqa: E402
import make_vectors as MV  # noqa: E402
import vecfmt as V  # noqa: E402

ROOT = A.ROOT


def write(path, name, fn, states, calls):
    base = V.pack_state(MV.base_world())
    out = V.SetWriter(path, V.KIND_WORLD, name, base)
    n = 0
    for w in states:
        for _ in range(calls):
            w.pokey = []
            before = V.pack_state(w)
            fn(w)
            out.world([], [], None, before, V.pack_state(w), list(w.pokey))
            n += 1
            w.RTCLOK2 = (w.RTCLOK2 + 1) & 0xFF
    out.close()
    return n


def turn_states(n):
    base = A.started_machine()
    for seed in range(n):
        rng = random.Random(seed)
        m = A.fresh(base)
        CAB.setup(m, rng)
        m.mem[0x1A] = 1 if seed % 4 else 0
        m.mem[0x23] = 0
        m.mem[0x25] = 0
        m.mem[0x2C], m.mem[0x2D] = rng.choice([(2, 3), (3, 2), (1, 1), (0, 2), (2, 0), (0, 0)])
        yield W.World().load(m.mem)


def level_end_states(n):
    base = A.started_machine()
    for seed in range(n):
        rng = random.Random(200 + seed)
        m = A.fresh(base)
        CAB.setup(m, rng)
        m.mem[0x27] = 0
        m.mem[0x26] = 1
        m.mem[0x28] = 0
        m.mem[0x29] = 0
        yield W.World().load(m.mem)


class RecordingFeed:
    """the RANDOM values of a run, handed out one by one and remembered per frame"""

    def __init__(self, vals):
        self.v = iter(vals)
        self.taken = []

    def __iter__(self):
        return self

    def __next__(self):
        x = next(self.v)
        self.taken.append(x)
        return x


def write_stories(path, quick):
    """the stories of tests/test_app_frame.py (the ROM and the port equal after every frame): the Python handler run frame after frame from a constructed state, every frame a record (with the RANDOM values it took)"""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_app_frame as T
    import check_app_frame as CAF
    base = A.started_machine()
    out = V.SetWriter(path, V.KIND_WORLD, "core_app_frame.vbi_handler", V.pack_state(MV.base_world()))
    n = 0
    stories = (("copyright", T.make_copyright, 40, 2 if quick else 5), ("title", T.make_title, 12, 2 if quick else 5), ("start tune", T.make_start_tune, 520, 2 if quick else 6),
               ("level end", T.make_level_end, 420, 2 if quick else 6), ("turn control", T.make_turn, 300, 3 if quick else 10), ("death", T.make_death, 500, 3 if quick else 8))
    for name, make, frames, seeds in stories:
        for seed in range(seeds):
            rng = random.Random(1000 + seed)
            vals = [rng.randrange(256) for _ in range(frames * 12)]
            m = A.fresh(base, list(vals))
            CAF.base_state(m, rng)
            make(m, rng)
            for k in range(4):
                m.mem[0x0278 + k] = 0x0F
            w = W.World().load(m.mem)
            w.collide = [0] * 16
            it = iter(vals)
            for f in range(frames):
                w.pokey = []
                feed = RecordingFeed(it)
                before = V.pack_state(w)
                try:
                    AF.vbi_handler(w, feed)
                except IndexError:                        # the random start walked the maze pointer out of the maze: not a state of the game
                    break
                out.world([], feed.taken, None, before, V.pack_state(w), list(w.pokey))
                n += 1
                w.RTCLOK2 = (w.RTCLOK2 + 1) & 0xFF
    out.close()
    return n


PC_CODE = {"top": 0, "read": 1, "debounce": 2, "release": 3, "clock_wait": 4}


def kl_number(kl):
    pc, acc, clock = kl.state()
    return PC_CODE[pc] | acc << 8 | clock << 16


def hold(f0, n, v):
    return {f: v for f in range(f0, f0 + n)}


def write_session(path, seed, frames, keys=None, triggers=None, keyboard=None, clock=0, aid=None, stop=None):
    """a whole session of the Python program (tools/core_app.py, equal to the ROM after every frame: tests/test_app.py) from power-on: one record per frame, the inputs of the frame as arguments, the RANDOM values it
    took, the World after it and where the main program is as the return value.  `aid(f, app)` is a test aid applied to the state before frame f (it breaks the chain: the next record starts from the file's state)"""
    import analyze_collide as AC
    import check_app as CA
    import core_app as APP
    p = CA.GameScript(seed, AC.rom_charset(), keys, triggers, keyboard=keyboard)
    p.t = clock
    app = APP.App(p, clock=clock)
    p.t = clock
    power_on = V.pack_state(APP.power_on_world(clock))
    out = V.SetWriter(path, V.KIND_WORLD, "app.frame", V.pack_state(MV.base_world()))
    n = 0
    for f in range(frames):
        p.begin_frame()
        if aid:
            aid(f, app)
        if f == 0:
            before = power_on
        else:
            b = bytearray(V.pack_state(app.w))
            b[0x14] = (b[0x14] + 1) & 0xFF                       # the clock moves between frames: the form `--chain` recognises
            before = bytes(b)
        att = p.attract()
        args = [f, p.stick(0), p.trigger(0), p.trigger(1), p.console(), p.key(), p.key_delay(), p.clock(), att[0], att[1]]
        app.frame()
        out.world(args, list(p.taken), kl_number(app.kl), before, V.pack_state(app.w), list(app.w.pokey))
        n += 1
        if stop and stop(app):
            break
    out.close()
    return n


def write_keyloop_states(path, n_per_phase):
    """the main program from every place it can be in between two frames, from random states and inputs (tools/check_app_keyloop.py, equal to the ROM): one record per state, args = the place (0 top, 2 debounce, 3 release,
    4 clock wait), the accumulator, the clock of the wait and the console; the return value is where the program is afterwards"""
    import check_app_keyloop as KL
    import core_app as APP
    names = {0: APP.TOP, 2: APP.DEBOUNCE, 3: APP.RELEASE, 4: APP.CLOCK_WAIT}
    base = A.started_machine()
    out = V.SetWriter(path, V.KIND_WORLD, "app.key_loop", V.pack_state(MV.base_world()))
    n = 0
    for code, phase in names.items():
        rng = random.Random(500 + code)
        for _ in range(n_per_phase):
            m = A.fresh(base, [rng.randrange(256) for _ in range(12)])
            acc = KL.setup(m, rng, phase)
            console = m.mem[0xD01F]
            w = W.World().load(m.mem)
            kl = APP.KeyLoop()
            kl.pc = phase
            kl.acc = acc if phase in (APP.DEBOUNCE, APP.RELEASE) else 0
            kl.clock = m.a if phase == APP.CLOCK_WAIT else 0
            w.pokey = []
            before = V.pack_state(w)
            args = [code, kl.acc, kl.clock, console]
            APP.key_loop(w, KL.Stub(console), kl, console)
            out.world(args, [], kl_number(kl), before, V.pack_state(w), list(w.pokey))
            n += 1
    out.close()
    return n


def write_power_on(path):
    """the RAM after the OS's power-on clear for every clock value (tools/core_app.power_on_world), from an arbitrary World: the whole state is replaced"""
    import core_app as APP
    rng = random.Random(9)
    out = V.SetWriter(path, V.KIND_WORLD, "app.power_on_world", V.pack_state(MV.base_world()))
    for clock in range(256):
        w = W.World()
        for name, addr, n in W.FIELDS:
            setattr(w, name, rng.randrange(256) if n == 1 else [rng.randrange(256) for _ in range(n)])
        before = V.pack_state(w)
        after = V.pack_state(APP.power_on_world(clock))
        out.world([clock], [], None, before, after, [])
    out.close()
    return 256


def write_sessions(out, quick):
    n = 0
    n += write_session(os.path.join(out, "session_1p.vec"), 1, 2400 if quick else 9000, keys=hold(480, 6, 6))
    n += write_session(os.path.join(out, "session_keys.vec"), 3, 2600, keys={**hold(100, 4, 3), **hold(200, 4, 5), **hold(220, 4, 3), **hold(240, 4, 3), **hold(260, 4, 3), **hold(300, 4, 5),
                                                                          **hold(1200, 6, 6), **hold(1800, 4, 3), **hold(2100, 5, 6)}, triggers=hold(330, 3, 0), keyboard={700: 0x21, 760: 0x21})

    def level_aid(f, app):
        if f == 600:
            app.w.LevelComplete = 1
    n += write_session(os.path.join(out, "session_level.vec"), 4, 1400, keys=hold(480, 6, 6), aid=level_aid)
    n += write_session(os.path.join(out, "session_clock.vec"), 5, 700, keys=hold(250 + 480, 6, 6), clock=250)
    if not quick:
        n += write_session(os.path.join(out, "session_2p.vec"), 2, 30000, keys={**hold(300, 4, 5), **hold(330, 6, 6)}, stop=lambda a: a.w.GameState == 4 and a.frames > 2000)
    return n


def main():
    out = os.path.join(ROOT, "resources", "vectors")
    if "--out" in sys.argv:
        out = os.path.join(ROOT, sys.argv[sys.argv.index("--out") + 1])
    os.makedirs(out, exist_ok=True)
    quick = "--quick" in sys.argv
    # the C's collision model reads the maze cells with the game's character set: the vector runner loads it from here.  It is the ROM's own set (no emulator log is needed), so the sessions can be run on a clean copy of the project
    # (found by tools/check_clean_build.py, stage 97: without it `vectors_sessions` failed there; tools/make_collide_vectors.py writes the same file)
    import analyze_collide as AC
    with open(os.path.join(out, "gtia.charset.bin"), "wb") as fh:
        fh.write(AC.rom_charset())
    n1 = write(os.path.join(out, "seq_core_app_board.turn_control.vec"), "core_app_board.turn_control", AB.turn_control, turn_states(10 if quick else 60), 140)
    n2 = write(os.path.join(out, "seq_core_app_board.level_end_step.vec"), "core_app_board.level_end_step", AB.level_end_step, level_end_states(6 if quick else 30), 200)
    n3 = write_stories(os.path.join(out, "seq_core_app_frame.vbi_handler.vec"), quick)
    write_power_on(os.path.join(out, "keyloop_power_on.vec"))
    write_keyloop_states(os.path.join(out, "keyloop_states.vec"), 300 if quick else 4000)
    n4 = write_sessions(out, quick)
    print("turn_control %d calls, level_end_step %d calls, vbi_handler stories %d calls, sessions %d frames" % (n1, n2, n3, n4))


if __name__ == "__main__":
    main()
