"""Stage 78c (docs/51): the frame dispatcher in port form (tools/core_app_frame.py).
1. Against the ROM, class by class: a quick run of tools/check_app_frame.py (the 15 frame classes of docs/38 for FrameDispatch and for the handler: 30 rows, 0 differences, the ROM proved to have run the class) and the
   line coverage of core_app_frame.py during it.
2. The frame-by-frame story: the ROM and the port run side by side for hundreds of frames from the start of a screen (the copyright screen to the title, the start tune into play, the READY! wait, the level end,
   the hand-over between two players, the game over, a death), the whole state compared after EVERY frame with the clock moving; together they visit at least 11 of the 15 classes.
3. Negative controls: a dispatcher that tests the level end before the board start, a title menu with a shifted text and a game frame that forgets the attract timer are each caught."""
import inspect
import os
import random
import sys
import trace
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import algorithm_models as A  # noqa: E402
import check_app_board as CAB  # noqa: E402
import check_app_frame as CAF  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_play as CPL  # noqa: E402
import core_app_board as AB  # noqa: E402
import core_app_frame as AF  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402


class AgainstTheRom(unittest.TestCase):
    def test_every_class_equals_the_rom_and_every_line_runs(self):
        path = os.path.abspath(AF.__file__)
        ran = set()

        def local(frame, event, arg):
            if event == "line":
                ran.add(frame.f_lineno)
            return local

        def glob(frame, event, arg):
            return local if os.path.abspath(frame.f_code.co_filename) == path else None
        sys.settrace(glob)
        try:
            lines, rows = CAF.report(True)
        finally:
            sys.settrace(None)
        self.assertEqual(len(rows), 32)
        for name, bad in rows:
            self.assertEqual(bad, [], name)
        executable = set(trace._find_executable_linenos(path))
        body = set()
        for name, fn in inspect.getmembers(AF, inspect.isfunction):
            if fn.__module__ == AF.__name__:
                first = fn.__code__.co_firstlineno
                last = first + len(inspect.getsource(fn).splitlines()) - 1
                body |= {ln for ln in executable if first < ln <= last}
        missing = sorted(body - ran)
        self.assertEqual(missing, [], "lines of core_app_frame.py never run: %s" % missing)


MARKS = {a: c for c, a in CAF.CLASSES}


def story(seed, frames, make):
    """the ROM's handler `$A5FD` and the port's `vbi_handler` run `frames` frames in a row on one state; returns (the first difference or None, the set of classes the ROM ran)"""
    base = A.started_machine()
    rng = random.Random(seed)
    vals = [rng.randrange(256) for _ in range(frames * 12)]
    m = A.fresh(base, list(vals))
    CAF.base_state(m, rng)
    make(m, rng)
    for k in range(4):
        m.mem[0x0278 + k] = 0x0F
    for k in range(16):
        m.mem[0xD000 + k] = 0
    m.hw = [0] * 16
    w = W.World().load(m.mem)
    w.collide = [0] * 16
    it = CPL.Rnd(vals)
    classes = set()
    orig_step = m.step

    def step():
        if m.pc in MARKS:
            classes.add(MARKS[m.pc])
        return orig_step()
    m.step = step
    C.Machine.wr = CAB._wr
    C.Machine.rd = CPL._rd
    try:
        for f in range(frames):
            del CAB.LOG[:]
            w.pokey = []
            m.call(0xA5FD)
            try:
                AF.vbi_handler(w, it)
            except IndexError:                          # the random start walked the maze pointer out of the maze: not a state of the game (check_play skips these too)
                return None, classes
            d = CAF.diffs(m, w, it.n)
            if d:
                return (f, d[:4]), classes
            m.mem[0x14] = (m.mem[0x14] + 1) & 0xFF
            w.RTCLOK2 = (w.RTCLOK2 + 1) & 0xFF
    finally:
        C.Machine.wr = CAB._orig
        C.Machine.rd = CPL._orig_rd
    return None, classes


def make_copyright(m, rng):
    m.mem[0x19] = 1
    m.mem[0x1D] = (m.mem[0x14] + 3) & 0xFF            # CopyrightEnd: the wait ends after three frames


def make_title(m, rng):
    m.mem[0x19] = 3
    m.mem[0x1A] = rng.randrange(2)


def make_start_tune(m, rng):
    m.mem[0x19] = 0
    m.mem[0x1C] = 2                                    # board start
    m.mem[0x21] = 0
    m.mem[0x22] = 0
    m.mem[0xA3] = 0
    m.mem[0xCE:0xD2] = bytes([0, 0, 0, 0])
    for p in range(2):
        m.mem[0x2C + p] = 3


def make_level_end(m, rng):
    m.mem[0x19] = 0
    m.mem[0x26] = 1
    m.mem[0x27] = 0
    m.mem[0x28] = 0
    m.mem[0x29] = 0
    m.mem[0x21] = 1


def make_turn(m, rng):
    m.mem[0x19] = 0
    m.mem[0x21] = 1
    m.mem[0x24] = 1
    m.mem[0x23] = 0
    m.mem[0x25] = 0
    m.mem[0x1A] = 1
    m.mem[0x2B] = rng.randrange(2)
    m.mem[0x2C], m.mem[0x2D] = rng.choice([(2, 3), (3, 2), (0, 2), (2, 0), (0, 0)])


def make_death(m, rng):
    m.mem[0x19] = 0
    m.mem[0x21] = 1
    m.mem[0x24] = 0
    m.mem[0xED] = 1
    m.mem[0xEE] = 0x20
    m.mem[0x1A] = rng.randrange(2)


class Stories(unittest.TestCase):
    def test_the_stories_equal_the_rom_frame_by_frame(self):
        seen = set()
        for name, make, frames, seeds in (("copyright to title", make_copyright, 40, range(5)), ("title", make_title, 12, range(5)),
                                          ("start tune into play", make_start_tune, 520, range(6)), ("level end", make_level_end, 420, range(6)),
                                          ("turn control", make_turn, 300, range(10)), ("death", make_death, 500, range(8))):
            for seed in seeds:
                d, classes = story(1000 + seed, frames, make)
                self.assertIsNone(d, "%s seed %d: %s" % (name, seed, d))
                seen |= classes
        self.assertGreaterEqual(len(seen), 11, sorted(seen))
        for c in ("copyright setup", "copyright wait", "title after game", "board start", "start tune", "level end", "turn control", "death", "play"):
            self.assertIn(c, seen)


class NegativeControls(unittest.TestCase):
    def caught(self, mutated, classes=None, n=120):
        total = 0
        for name, mark in CAF.CLASSES + [(CAF.MIXED, None)]:
            if classes and name not in classes:
                continue
            _, bad = CAF.run_class(name, 0xA6CC, mutated, n, 5 + len(name), ran_check=False)
            total += len(bad)
        self.assertGreater(total, 0)

    def test_the_level_end_before_the_board_start_is_caught(self):
        orig = AF.game_frame

        def wrong(w, rnd):
            if w.LevelComplete and w.IntroRequest == 2 and not w.Paused:
                return AB.level_end_step(w)
            return orig(w, rnd)
        self.caught(lambda w, rnd: wrong(w, rnd) if w.GameState == 0 else AF.frame_dispatch(w, rnd), ("mixed flags",))

    def test_a_shifted_title_text_is_caught(self):
        orig = AF.title_menu

        def wrong(w):
            orig(w)
            w.title[0x7A] = (w.title[0x7A] + 1) & 0xFF
        self.caught(lambda w, rnd: wrong(w) if w.GameState >= 3 else AF.frame_dispatch(w, rnd), ("title menu", "title after game"))

    def test_forgetting_the_attract_timer_is_caught(self):
        self.caught(_no_attract_clear, ("board start",))


def _no_attract_clear(w, rnd):
    saved = w.ATRACT
    AF.frame_dispatch(w, rnd)
    w.ATRACT = saved


if __name__ == "__main__":
    unittest.main()
