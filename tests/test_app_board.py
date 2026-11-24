"""Stage 78b (docs/51): the board, turn, level-end, intro and label routines in port form (tools/core_app_board.py).
1. Against the ROM: a quick run of tools/check_app_board.py (every routine, 0 differences) and the line coverage of core_app_board.py during it (every line runs).
2. Sequences, not single calls: TurnControl and the level-end sequence are called again and again on the same state, the ROM and the port side by side, and the whole state is compared after every call
   (the hand-over between two players with its waits, the game over, the level end from the stop to the next board).
3. Negative controls: four mutated copies of the port (a digit offset, the saved mazes swapped, the flash colours swapped, the item row shifted) are each caught."""
import os
import random
import sys
import trace
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_app_board as CAB  # noqa: E402
import core_app_board as AB  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402


class AgainstTheRom(unittest.TestCase):
    def test_every_routine_equals_the_rom_and_every_line_runs(self):
        path = os.path.abspath(AB.__file__)
        ran = set()

        def local(frame, event, arg):
            if event == "line":
                ran.add(frame.f_lineno)
            return local

        def glob(frame, event, arg):
            return local if os.path.abspath(frame.f_code.co_filename) == path else None
        sys.settrace(glob)
        try:
            lines, rows = CAB.report(True)
        finally:
            sys.settrace(None)
        self.assertEqual(len(rows), 10)
        for name, bad in rows:
            self.assertEqual(bad, [], name)
        # the executable lines of the function bodies (not the `def` lines, which run at import)
        import inspect
        executable = set(trace._find_executable_linenos(path))
        body = set()
        for name, fn in inspect.getmembers(AB, inspect.isfunction):
            if fn.__module__ == AB.__name__:
                first = fn.__code__.co_firstlineno
                last = max(ln for ln in executable if ln >= first and (ln == first or True) and ln <= first + len(inspect.getsource(fn).splitlines()))
                body |= {ln for ln in executable if first < ln <= last}
        missing = sorted(body - ran)
        self.assertEqual(missing, [], "lines of core_app_board.py never run: %s" % missing)


def sequence(addr, port, rng, calls, pre=None):
    """the routine called `calls` times on one state, the ROM and the port side by side; the state is compared after every call; returns the list of the differences"""
    base = CAB.A.started_machine()
    m = CAB.A.fresh(base)
    CAB.setup(m, rng)
    if pre:
        pre(m, rng)
    w = W.World().load(m.mem)
    bad = []
    C.Machine.wr = CAB._wr
    try:
        for k in range(calls):
            del CAB.LOG[:]
            w.pokey = []
            m.call(addr)
            port(w)
            d = CAB.diffs(m, w, CAB.DRAW_POINTERS)
            if d:
                bad.append((k, d[:4]))
                break
            # the frame clock moves between calls, as in the game
            m.mem[0x14] = (m.mem[0x14] + 1) & 0xFF
            w.RTCLOK2 = (w.RTCLOK2 + 1) & 0xFF
    finally:
        C.Machine.wr = CAB._orig
    return bad, w


class Sequences(unittest.TestCase):
    def test_turn_control_runs_the_hand_over_in_order(self):
        """two players, the player on turn has lost a life: the stage goes 0 -> (2 or 1) -> 3 -> 0 with the waits between, the mazes swapped, the labels drawn"""
        seen = set()
        for seed in range(60):
            rng = random.Random(seed)

            def pre(m, rng):
                m.mem[0x1A] = 1
                m.mem[0x23] = 0
                m.mem[0x25] = 0
                m.mem[0x2C], m.mem[0x2D] = rng.choice([(2, 3), (3, 2), (1, 1), (0, 2), (2, 0), (0, 0)])
            bad, w = sequence(0xAA2D, AB.turn_control, rng, 140, pre)
            self.assertEqual(bad, [], seed)
            seen.add((w.CurrentPlayer, w.TurnSwitchState, w.CountdownActive))
        self.assertGreater(len(seen), 2)

    def test_the_game_over_countdown_is_started(self):
        started = 0
        for seed in range(60):
            rng = random.Random(100 + seed)

            def pre(m, rng):
                m.mem[0x1A] = rng.randrange(2)
                m.mem[0x23] = 0
                m.mem[0x2C] = m.mem[0x2D] = 0
            bad, w = sequence(0xAA2D, AB.turn_control, rng, 6, pre)
            self.assertEqual(bad, [], seed)
            if w.CountdownActive == 1 and w.CountdownTimer == 0xE2 and w.WaitState == 0:
                started += 1
        self.assertGreater(started, 30)

    def test_the_level_end_sequence_from_the_stop_to_the_next_board(self):
        reached = set()
        for seed in range(30):
            rng = random.Random(200 + seed)

            def pre(m, rng):
                m.mem[0x27] = 0
                m.mem[0x26] = 1
                m.mem[0x28] = 0
                m.mem[0x29] = 0
            bad, w = sequence(0xAC18, AB.level_end_step, rng, 200, pre)
            self.assertEqual(bad, [], seed)
            reached.add(w.LevelEndStep)
            if w.WaitState == 2:
                reached.add("advanced")
        self.assertIn("advanced", reached)


class NegativeControls(unittest.TestCase):
    def check_caught(self, name, mutated):
        spec = {r[0]: r for r in CAB.ROUTINES}[name]
        _, what, addr, port, pre, regs, excl = spec
        _, bad = CAB.run(addr, mutated, 300, 5, pre, regs, excl)
        self.assertGreater(len(bad), 0, name)

    def test_a_digit_offset_in_the_high_score_is_caught(self):
        def wrong(w, r):
            x = r["x"]
            for y in range(6):
                a, b = w.status[x + y], w.status[0x39 + y]
                if a == b:
                    continue
                if a < b:
                    return
                for k in range(y + 1, 6):                      # one digit short
                    w.status[0x39 + k] = w.status[x + k]
                return
        self.check_caught("compare_high_score", wrong)

    def test_swapped_saved_mazes_are_caught(self):
        def wrong(w, r):
            w.saved1, w.saved2 = w.saved2, w.saved1
            AB.turn_control(w)
        self.check_caught("turn_control", wrong)

    def test_swapped_flash_colours_are_caught(self):
        orig = AB.level_end_step

        def wrong(w, r):
            before = w.shadow[0xC4]
            orig(w)
            if w.LevelEndStep == 2 and w.shadow[0xC4] in (0x0C, 0x86) and w.shadow[0xC4] != before and w.LevelEndFlashes != 7:
                w.shadow[0xC4] ^= 0x8A                          # 0x0C <-> 0x86
        self.check_caught("level_end_step", wrong)

    def test_a_shifted_item_row_is_caught(self):
        def wrong(w, r):
            AB.draw_level_indicator(w)
            w.maze[0x1EF] = (w.maze[0x1EF] + 1) & 0xFF
        self.check_caught("draw_level_indicator", wrong)


if __name__ == "__main__":
    unittest.main()
