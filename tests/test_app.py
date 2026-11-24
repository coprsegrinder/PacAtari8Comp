"""Stage 78d (docs/51): the whole program in port form (tools/core_app.py): start-up, the main program (key loop) and the frame, on a platform, against the ROM from power-on.
1. Start: the state at the first pass of the main program equals the ROM's (several clock values, the wrap included).
2. The main program branch by branch: tools/check_app_keyloop.py (from every place it can be in between two frames, random states and inputs, 0 differences) and the coverage of every line of its port.
3. Whole sessions, compared after EVERY frame with the ROM (the zero page, the maze and its copies, the title screen, the status rows, the shadows, the pages, the positions, the picture buffers, the chip writes, the
   RANDOM count, the place the main program is in): a one-player game from power-on to the game-over countdown and back to the title; a two-player game with the hand-overs; a session of keys (the copyright screen
   skipped, SELECT, OPTION, the trigger, the space bar, START and OPTION in the middle of a game); a level end; a clock that wraps.  The lengths of the classes of frames are the ones measured in the real game (docs/38).
4. Negative controls: a start-level cycle with a wrong step, a pause that does not toggle and a START that is ignored are each caught."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_app as K  # noqa: E402
import check_app_keyloop as KL  # noqa: E402
import core_app as APP  # noqa: E402


def hold(f0, n, v):
    return {f: v for f in range(f0, f0 + n)}


def lengths(classes):
    out = {}
    for c, n in K.runs(classes):
        out.setdefault(c, []).append(n)
    return out


class Start(unittest.TestCase):
    def test_the_state_at_the_first_pass_equals_the_rom(self):
        for clock in (0, 1, 7, 128, 255):
            self.assertEqual(K.compare_start(clock), [], clock)


class KeyLoop(unittest.TestCase):
    def test_every_phase_equals_the_rom_and_every_line_runs(self):
        import inspect
        import trace
        path = os.path.abspath(APP.__file__)
        ran = set()

        def local(frame, event, arg):
            if event == "line":
                ran.add(frame.f_lineno)
            return local

        def glob(frame, event, arg):
            return local if os.path.abspath(frame.f_code.co_filename) == path else None
        sys.settrace(glob)
        try:
            lines, rows = KL.report(True)
        finally:
            sys.settrace(None)
        self.assertEqual(len(rows), 4)
        for name, bad in rows:
            self.assertEqual(bad, [], name)
        executable = {ln for ln in trace._find_executable_linenos(path) if ln is not None}
        body = set()
        for name in ("_colours", "_new_game", "_set_title", "_pass", "_read", "_released", "key_loop"):
            fn = getattr(APP, name)
            first = fn.__code__.co_firstlineno
            last = first + len(inspect.getsource(fn).splitlines()) - 1
            body |= {ln for ln in executable if first < ln <= last}
        with open(path, encoding="utf-8") as fh:
            src = fh.read().splitlines()
        body = {ln for ln in body if "raise RuntimeError" not in src[ln - 1]}      # the guard against a loop that does not settle
        self.assertEqual(sorted(body - ran), [], "lines of the main program never run")


class Sessions(unittest.TestCase):
    def test_a_one_player_game_from_power_on_to_game_over_and_the_title(self):
        first, classes, app = K.run_game(1, 9000, keys=hold(480, 6, 6))
        self.assertIsNone(first)
        self.assertEqual(len(classes), 9000)
        ln = lengths(classes)
        self.assertEqual(ln["start tune"], [260])                         # docs/38: the start tune 260 frames
        self.assertEqual(set(ln["death"]), {354})                         # a death is 354 frames
        self.assertEqual(set(ln["ready wait"]), {65})                     # the READY! wait 65
        self.assertEqual(len(ln["death"]), 3)                             # three lives
        self.assertEqual(ln["turn control"], [1, 1, 1])
        self.assertTrue(1795 <= ln["game-over countdown"][0] <= 1808, ln["game-over countdown"])   # up to 1,800 (30 s)
        self.assertEqual(classes[-1], "title after game")
        self.assertEqual(app.w.GameState, 4)

    def test_a_two_player_game_with_the_hand_overs(self):
        keys = {}
        keys.update(hold(300, 4, 5))                                      # SELECT: two players
        keys.update(hold(330, 6, 6))                                      # START
        first, classes, app = K.run_game(2, 30000, keys=keys, stop=lambda a: a.w.GameState == 4 and a.frames > 2000)
        self.assertIsNone(first)
        ln = lengths(classes)
        self.assertEqual(set(ln["turn control"]) - {1}, {51})             # a hand-over between the players is 51 frames of turn control
        self.assertGreaterEqual(len(ln["death"]), 6)                      # three lives each
        self.assertEqual(app.w.GameState, 4)

    def test_a_session_of_keys(self):
        keys = {}
        keys.update(hold(100, 4, 3))                                      # OPTION on the copyright screen: on to the title
        keys.update(hold(200, 4, 5))                                      # SELECT: two players
        for f in (220, 240, 260):
            keys.update(hold(f, 4, 3))                                    # OPTION: the start level 1, 2, 4
        keys.update(hold(300, 4, 5))                                      # SELECT: one player again
        keys.update(hold(1200, 6, 6))                                     # START in the middle of the game: a new game
        keys.update(hold(1800, 4, 3))                                     # OPTION in the middle of a game: back to the title
        keys.update(hold(2100, 5, 6))                                     # START
        first, classes, app = K.run_game(3, 2600, keys=keys, triggers=hold(330, 3, 0), keyboard={700: 0x21, 760: 0x21})
        self.assertIsNone(first)
        ln = lengths(classes)
        self.assertIn("paused", ln)                                       # the space bar paused the game
        self.assertGreaterEqual(len(ln["start tune"]), 3)                 # three new games
        self.assertEqual(ln["copyright wait"], [104])                     # the copyright screen was left when the key pressed at frame 100 was released (frame 104)

    def test_a_level_end_and_the_next_board(self):
        def before(f, app, rom):
            if f == 600:                                                  # a test aid on BOTH sides: the board is cleared
                app.w.LevelComplete = 1
                rom.m.mem[0x26] = 1
        first, classes, app = K.run_game(4, 1400, keys=hold(480, 6, 6), before_frame=before)
        self.assertIsNone(first)
        ln = lengths(classes)
        self.assertIn("level end", ln)
        self.assertEqual(app.w.Level[0], 1)                               # the next level
        self.assertGreaterEqual(sum(ln["level end"]), 180)                # docs/38: the level end 187 frames

    def test_a_clock_that_wraps(self):
        first, classes, app = K.run_game(5, 700, keys=hold(250 + 480, 6, 6), clock=250)          # the script's frames count the clock: START at clock 730
        self.assertIsNone(first)
        self.assertEqual(lengths(classes)["copyright wait"], [255])


class NegativeControls(unittest.TestCase):
    def caught(self, mutate, phases=(APP.TOP, APP.RELEASE, APP.DEBOUNCE)):
        orig = {k: getattr(APP, k) for k in ("_pass", "_released", "_read", "_new_game")}
        try:
            mutate()
            total = 0
            for ph in phases:
                _, bad, _ = KL.run_phase(ph, 300, 99)
                total += len(bad)
            self.assertGreater(total, 0)
        finally:
            for k, v in orig.items():
                setattr(APP, k, v)

    def test_a_wrong_start_level_step_is_caught(self):
        orig = APP._released

        def wrong(w, kl):
            if w.KeyValue == APP.CONSOL_OPTION and w.GameState >= 3 and w.StartLevel >= 2 and w.StartLevel != 12:
                before = w.StartLevel
                orig(w, kl)
                w.StartLevel = (before + 1) & 0xFF                          # one step, not two
                return
            return orig(w, kl)
        self.caught(lambda: setattr(APP, "_released", wrong), (APP.RELEASE,))

    def test_a_pause_that_does_not_toggle_is_caught(self):
        orig = APP._pass

        def wrong(w, kl):
            p = w.Paused
            orig(w, kl)
            if p == 0 and w.Paused == 1:
                w.Paused = 0
        self.caught(lambda: setattr(APP, "_pass", wrong), (APP.TOP,))

    def test_a_start_that_is_ignored_is_caught(self):
        orig = APP._released

        def wrong(w, kl):
            if w.KeyValue == APP.CONSOL_START:
                kl.pc = APP.TOP
                return
            return orig(w, kl)
        self.caught(lambda: setattr(APP, "_released", wrong), (APP.RELEASE,))


if __name__ == "__main__":
    unittest.main()
