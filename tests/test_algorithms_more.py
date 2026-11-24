"""OV-58: tests of tools/algorithm_models3.py .. algorithm_models7.py (the rest of the algorithms run against models in the 6502 interpreter).  Run:  python -I tests/test_algorithms_more.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import algorithm_models3 as M3  # noqa: E402
import algorithm_models4 as M4  # noqa: E402
import algorithm_models5 as M5  # noqa: E402
import algorithm_models6 as M6  # noqa: E402
import algorithm_models7 as M7  # noqa: E402


class House(unittest.TestCase):
    def test_house_and_drawing(self):
        for f in (M3.check_step_and_draw, M3.check_house_bob, M3.check_house_leave, M3.check_house_enter, M3.check_house_waiting_tick, M3.check_eyes_sound):
            self.assertEqual(f(600)[1], [], f.__name__)

    def test_eyes_and_house(self):
        n, bad, hits = M3.check_eyes_and_house(500)
        self.assertEqual(bad, [])
        self.assertGreater(hits[0], 50)


class PacManAndGhosts(unittest.TestCase):
    def test_move_pacman(self):
        n, bad, turns = M4.check_move_pacman(1500)
        self.assertEqual(bad, [])
        self.assertGreater(turns, 100)

    def test_bonus_ghost_eaten_sound(self):
        self.assertEqual(M4.check_bonus_update(1500)[1], [])
        self.assertEqual(M4.check_ghost_eaten(800)[1], [])
        self.assertEqual(M4.check_dot_sound(800)[1], [])
        self.assertEqual(M4.check_ghost_eaten_pause(1500)[1], [])


class Leaves(unittest.TestCase):
    def test_scores_and_clip(self):
        self.assertEqual(M5.check_compare_high_score(800)[1], [])
        self.assertEqual(M5.check_clip(800)[1], [])
        self.assertEqual(M5.check_bonus_sound(800)[1], [])

    def test_drawing(self):
        for f in (M5.check_draw_level_indicator, M5.check_draw_lives, M5.check_draw_all, M5.check_labels, M5.check_colours_copies, M5.check_siren, M5.check_level_complete):
            self.assertEqual(f(300)[1], [], f.__name__)

    def test_init_and_death(self):
        for nm, n, bad in M5.check_init_and_levels():
            self.assertEqual(bad, [], nm)
        self.assertEqual(M5.check_death_sequence(1000)[1], [])
        self.assertEqual(M5.check_death_animation(1000)[1], [])


class DisplayAndFrame(unittest.TestCase):
    def test_display_and_key_loop(self):
        self.assertEqual(M6.check_simple(300)[1], {})
        n, bad, ways = M6.check_key_loop(500)
        self.assertEqual(bad, [])
        self.assertGreaterEqual(len(ways), 6)

    def test_ghost_behaviour_and_turns(self):
        self.assertEqual(M7.check_ghost_behaviour(1500)[1], [])
        self.assertEqual(M7.check_turn_control(800)[1], [])

    def test_frames(self):
        self.assertEqual(M7.check_title(300)[1], [])
        n, bad, paths = M7.check_frame_dispatch(600)
        self.assertEqual(bad, [])
        n, bad, paths = M7.check_play(800)
        self.assertEqual(bad, [])
        cov = M7.COVERAGE["play"]
        self.assertGreater(cov["death started"], 20)
        self.assertGreater(cov["ghost eaten"], 20)
        self.assertGreater(cov["bonus picked"], 20)
        n, bad, paths = M7.check_vbi(600)
        self.assertEqual(bad, [])


class Sensitivity(unittest.TestCase):
    """a model that is wrong must be noticed"""

    def broken(self, mod, name, wrapper, check):
        orig = getattr(mod, name)
        setattr(mod, name, wrapper(orig))
        try:
            self.assertGreater(len(check()[1]), 0, name)
        finally:
            setattr(mod, name, orig)

    def test_wrong_step(self):
        def w(orig):
            def f(mem, x, a):
                orig(mem, x, a)
                mem[0x041C] ^= 0xFF
            return f
        self.broken(M3, "model_step_and_draw", w, lambda: M3.check_step_and_draw(200))

    def test_wrong_move_pacman(self):
        def w(orig):
            def f(mem, rnd):
                r = orig(mem, rnd)
                mem[0xA6] ^= 1
                return r
            return f
        self.broken(M4, "model_move_pacman", w, lambda: M4.check_move_pacman(200))

    def test_wrong_death_animation(self):
        def w(orig):
            def f(mem):
                orig(mem)
                mem[0xEB] ^= 1
            return f
        self.broken(M5, "model_death_animation", w, lambda: M5.check_death_animation(200))

    def test_wrong_ghost_behaviour(self):
        def w(orig):
            def f(mem, x, R):
                orig(mem, x, R)
                mem[0xBE + x] ^= 1
            return f
        self.broken(M7, "model_ghost_behaviour", w, lambda: M7.check_ghost_behaviour(300))

    def test_wrong_frame(self):
        def w(orig):
            def f(mem, R):
                orig(mem, R)
                mem[0x0DF3] ^= 1
            return f
        self.broken(M7, "model_play_frame", w, lambda: M7.check_play(300))


class Evidence(unittest.TestCase):
    def test_summaries(self):
        for k, count in ((3, 7), (4, 5), (5, 17), (6, 2), (7, 6)):
            path = os.path.join(ROOT, "analysis", "evidence-algorithms%d-summary.txt" % k)
            with open(path, encoding="utf-8") as fh:
                txt = fh.read()
            self.assertEqual(txt.count(" 0 differences"), count, (k, txt))
            self.assertNotIn("DIFFERENT", txt)


class Coverage(unittest.TestCase):
    def test_every_instruction_is_reached_and_every_one_sided_branch_is_explained(self):
        with open(os.path.join(ROOT, "analysis", "evidence-model-coverage-summary.txt"), encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("instructions executed: 2925 of 2925", txt)
        self.assertIn("(0 never executed)", txt)
        self.assertIn("instructions never executed: 0", txt)
        self.assertIn("0 NOT explained", txt)
        self.assertNotIn("NEVER EXECUTED", txt)
        self.assertIn("79 of 79", txt)

    def test_explanations_name_branches_of_the_rom(self):
        import analyze_model_coverage as K
        import analyze_stack as AS
        rom, F, owner = AS.load()
        for a in K.EXPLAIN:
            self.assertIn(rom.ins[a][1], ("bpl", "bmi", "bvc", "bvs", "bcc", "bcs", "bne", "beq"), hex(a))


if __name__ == "__main__":
    unittest.main()
