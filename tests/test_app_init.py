"""Stage 78a (docs/51): the state initialisation in port form (tools/core_app_init.py).
1. Against the ROM: a quick run of tools/check_app_init.py (every routine, 0 differences) and the coverage of the branches of the code (the level and clock cases of NewBoardInit, the level clamp of InitBoard).
2. **The reset / keep / compute matrices of docs/43 hold**: the same 600 trials of tools/state_events.py are run once with the ROM routine and once with the port function; the two classifications are identical
   and the counts equal the rows of the table in docs/43.
3. Negative controls: a port that clears one byte too few, or reads the release-timer table from the wrong place, is caught by the check and changes the matrix."""
import os
import random
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_app_init as CAI  # noqa: E402
import core_app_init as AI  # noqa: E402
import core_world as W  # noqa: E402
import state_events as SE  # noqa: E402

EVENTS = ("InitBoard", "NewGameInit", "NewBoardInit")


def port_for(fn):
    def run(m):
        w = W.World().load(m.mem)
        fn(w)
        w.store(m.mem)
    return run


def doc_rows():
    """the rows of the table of docs/43 section 4 for the three events: {(event, case): (reset, kept, computed)}"""
    with open(os.path.join(ROOT, "docs", "43-state-management.md"), encoding="utf-8") as fh:
        t = fh.read()
    rows = {}
    for m in re.finditer(r"^\| `(\w+)` \| ([^|]+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", t, re.M):
        if m.group(1) in EVENTS:
            rows[(m.group(1), m.group(2).strip())] = (int(m.group(4)), int(m.group(5)), int(m.group(6)), int(m.group(3)))
    return rows


class AgainstTheRom(unittest.TestCase):
    def test_every_routine_equals_the_rom(self):
        lines, rows = CAI.report(quick=True)
        for name, bad in rows:
            self.assertEqual(bad, [], name)
        self.assertEqual(len(rows), 9)

    def test_the_branches_of_the_code_are_reached(self):
        """the same random states the check uses: NewBoardInit sees level 0 with the clock above and below $80, a level of 255, other levels; InitBoard sees levels below and above the clamp of 6"""
        rng = random.Random(1 + len("new_board_init"))
        seen = {"level0_clock_high": 0, "level0_clock_low": 0, "level255": 0, "other": 0}
        base = CAI.A.started_machine()
        for _ in range(400):
            m = CAI.A.fresh(base)
            CAI.setup(m, rng)
            lv, clk = m.mem[0x30 + m.mem[0x2B]], m.mem[0x14]
            if lv == 0:
                seen["level0_clock_high" if clk & 0x80 else "level0_clock_low"] += 1
            elif lv == 255:
                seen["level255"] += 1
            else:
                seen["other"] += 1
        for k, v in seen.items():
            self.assertGreater(v, 5, k)
        rng = random.Random(1 + len("init_board"))
        above = below = 0
        for _ in range(400):
            m = CAI.A.fresh(base)
            CAI.setup(m, rng)
            if m.mem[0x30 + m.mem[0x2B]] >= 6:
                above += 1
            else:
                below += 1
        self.assertGreater(above, 50)
        self.assertGreater(below, 50)


class Matrices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = {"InitBoard": port_for(AI.init_board), "NewGameInit": port_for(AI.new_game_init), "NewBoardInit": port_for(AI.new_board_init)}
        cls.rom = SE.run(600, 1, only=EVENTS)
        cls.ported = SE.run(600, 1, only=EVENTS, port=cls.port)

    def test_the_port_classifies_every_byte_as_the_rom_does(self):
        self.assertEqual(set(self.rom), set(EVENTS))
        for ev in EVENTS:
            self.assertEqual(self.rom[ev]["groups"], self.ported[ev]["groups"], ev)

    def test_the_counts_are_the_table_of_docs_43(self):
        want = doc_rows()
        self.assertEqual(len(want), 6)
        for ev in EVENTS:
            for lab, g in self.ported[ev]["groups"].items():
                row = want[(ev, lab)]
                self.assertEqual((len(g["reset"]), len(g["kept"]), len(g["computed"]), g["trials"]), row, (ev, lab))

    def test_the_names_of_what_init_board_resets(self):
        """docs/43 lists the first of the 114 bytes InitBoard resets: the start positions are among them, every value the table of constants"""
        g = self.ported["InitBoard"]["groups"]["player 1 on turn"]
        reset = g["reset"]
        self.assertEqual(reset[0x80], 0x93)
        self.assertEqual((reset[0x85], reset[0x89], reset[0x8A], reset[0x8E]), (0x64, 0xA4, 0x7C, 0x7C))
        self.assertEqual(len([b for b in reset if b >= 0x80]), len(reset))      # all in $80-$FF
        self.assertNotIn(0xB5, reset)                                         # the move delays are computed (they depend on the level)
        self.assertIn(0xB5, g["computed"])


class NegativeControls(unittest.TestCase):
    def test_a_port_that_clears_one_byte_too_few_is_caught(self):
        orig = AI.clear_zp

        def short(w, lo, hi):
            orig(w, lo, hi - 1)                                                # the last byte ($FF) is left
        AI.clear_zp = short
        try:
            _, bad = CAI.run(0xADAF, lambda w, r: AI.init_board(w), 200, 1)
            self.assertGreater(len(bad), 0)
            rom = SE.run(600, 1, only=("InitBoard",))
            ported = SE.run(600, 1, only=("InitBoard",), port={"InitBoard": port_for(AI.init_board)})
            self.assertNotEqual(rom["InitBoard"]["groups"], ported["InitBoard"]["groups"])
        finally:
            AI.clear_zp = orig

    def test_a_wrong_release_timer_window_is_caught(self):
        orig = AI.set_release_timers

        def wrong(w, y):
            orig(w, min(y + 1, 255))
        AI.set_release_timers = wrong
        try:
            for addr, fn in ((0xAE02, AI.new_board_init), (0xADF1, AI.new_game_init)):
                _, bad = CAI.run(addr, lambda w, r, f=fn: f(w), 200, 2)
                self.assertGreater(len(bad), 0, hex(addr))
        finally:
            AI.set_release_timers = orig

    def test_the_level_255_quirk_matters(self):
        """a port that always sets the timers (no skip at level 255) differs from the ROM on exactly the level-255 states"""
        orig = AI.new_board_init

        def always(w):
            w.maze = list(w.maze_orig)
            AI.S.draw_lives(w)
            p = w.CurrentPlayer
            y = w.Level[p]
            AI.set_release_timers(w, 0 if (y == 0 and w.RTCLOK2 & 0x80) else (y + 1) & 0xFF)     # no skip when (y + 1) & 255 == 0
            AI.clear_player_counters(w, p)
        _, bad = CAI.run(0xAE02, lambda w, r: always(w), 600, 3)
        self.assertGreater(len(bad), 0)
        self.assertEqual(AI.new_board_init, orig)


if __name__ == "__main__":
    unittest.main()
