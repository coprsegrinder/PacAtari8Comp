"""OV-58: tests of tools/algorithm_models2.py (more algorithms run against models in the 6502 interpreter).  Run:  python -I tests/test_algorithms2.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import algorithm_models2 as M  # noqa: E402


class Models(unittest.TestCase):
    def test_sight_test(self):
        n, bad, hits = M.check_sight_test(3000)
        self.assertEqual(bad, [])
        self.assertGreater(hits, 50)

    def test_force_chase(self):
        self.assertEqual(M.check_force_chase(800)[1], [])

    def test_chase_timer_siren(self):
        n, bad, f = M.check_chase_timer_siren(3000)
        self.assertEqual(bad, [])
        self.assertTrue(all(x > 100 for x in f), f)

    def test_frightened_sound(self):
        self.assertEqual(M.check_frightened_sound(2000)[1], [])

    def test_frightened_tick(self):
        n, bad, ended = M.check_frightened_tick(3000)
        self.assertEqual(bad, [])
        self.assertGreater(ended, 100)

    def test_eat_dot(self):
        n, bad, acted = M.check_eat_dot(2000)
        self.assertEqual(bad, [])
        self.assertGreater(acted, 100)

    def test_power_pellet(self):
        n, bad, eaten = M.check_power_pellet(2000)
        self.assertEqual(bad, [])
        self.assertGreater(eaten, 100)


class Sensitivity(unittest.TestCase):
    """a model that is wrong must be noticed"""

    def broken(self, name, wrapper, check):
        orig = getattr(M, name)
        setattr(M, name, wrapper(orig))
        try:
            self.assertGreater(len(check()[1]), 0, name)
        finally:
            setattr(M, name, orig)

    def test_wrong_force_chase(self):
        def w(orig):
            def f(mem, x):
                orig(mem, x)
                mem[M.CHASE_TIMER] = 0
            return f
        self.broken("model_force_chase", w, lambda: M.check_force_chase(200))

    def test_wrong_power_pellet(self):
        def w(orig):
            def f(mem):
                r = orig(mem)
                if r:
                    mem[M.COUNT] ^= 1
                return r
            return f
        self.broken("model_power_pellet", w, lambda: M.check_power_pellet(400))

    def test_wrong_frightened_tick(self):
        def w(orig):
            def f(mem):
                orig(mem)
                mem[M.FLASH] ^= 0x01
            return f
        self.broken("model_frightened_tick", w, lambda: M.check_frightened_tick(300))

    def test_wrong_eat_dot(self):
        def w(orig):
            def f(mem):
                orig(mem)
                mem[0xF6] ^= 1
            return f
        self.broken("model_eat_dot", w, lambda: M.check_eat_dot(300))


class Evidence(unittest.TestCase):
    def test_summary(self):
        with open(os.path.join(ROOT, "analysis", "evidence-algorithms2-summary.txt"), encoding="utf-8") as fh:
            txt = fh.read()
        self.assertEqual(txt.count(" 0 differences"), 8, txt)
        self.assertIn("sight_test: 20000 calls", txt)
        self.assertIn("power_pellet: 15000 calls", txt)
        self.assertIn("sight_exhaustive: 524288 calls", txt)


if __name__ == "__main__":
    unittest.main()
