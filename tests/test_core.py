"""Stage 66 (core algorithms): the port-form reference tools/core_ref.py against the ROM (a smaller run of tools/check_core.py), its tables against the ROM, the committed evidence and the chapter."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import algorithm_models as A  # noqa: E402
import check_core as K  # noqa: E402
import core_ref as R  # noqa: E402
import core_tables as T  # noqa: E402
import make_core_tables as MT  # noqa: E402


class Tables(unittest.TestCase):
    def test_tables_equal_rom_and_ram(self):
        m = A.started_machine()
        for name, src, addr, n, _ in MT.TABLES:
            want = tuple(m.mem[addr:addr + n]) if src == "ram" else tuple(A.rd(addr + i) for i in range(n))
            self.assertEqual(getattr(T, name), want, name)
        for name, src, addr, n, _ in MT.IMAGES:
            want = bytes(m.mem[addr:addr + n]) if src == "ram" else bytes(A.rd(addr + i) for i in range(n))
            self.assertEqual(getattr(T, name), want, name)


class Reference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = A.started_machine()

    def test_pacing_release_levels(self):
        self.assertEqual(K.check_pacing(self.base)[1], [])
        self.assertEqual(K.check_release(self.base)[1], [])
        self.assertEqual(K.check_bonus(self.base)[1], [])

    def test_frightened(self):
        n, bad, lengths = K.check_fright(self.base)
        self.assertEqual(bad, [])
        self.assertGreater(lengths, 200)

    def test_score_and_points(self):
        self.assertEqual(K.check_score(self.base, 1500)[1], [])
        self.assertEqual(K.check_ghost_points(self.base)[1], [])
        # the quirks the comparison found
        self.assertEqual(R.score_add(999992, 2000, 0, 1), (1992, 1, 2))      # a wrap gives the life: the old cell to the left was not blank
        self.assertEqual(R.score_add(0, 100000, 0, 1), (100000, 1, 2))
        self.assertEqual(R.score_add(9990, 10, 0, 1), (10000, 1, 2))
        self.assertEqual(R.score_add(5000, 10, 1, 1)[2], 1)
        self.assertEqual([R.ghost_points(n) for n in (0, 1, 2, 3, 255)], [200, 400, 800, 1600, 1600])

    def test_ghost_ai(self):
        self.assertEqual(K.check_steer(self.base, 3000)[1], [])
        n, bads = K.check_ghost_rules(self.base, 800)
        self.assertTrue(all(not v for v in bads.values()), bads)

    def test_junction(self):
        self.assertEqual(K.check_junction(self.base)[1], [])

    def test_known_values(self):
        self.assertEqual(R.release_timers(0), (0x30, 0x60, 0x90))
        self.assertEqual(R.fright_total_frames(0), 255 + (R.fright_end_phase(0) - 2) * 24 + 2)
        self.assertIsNone(R.fright_total_frames(70))
        self.assertEqual(R.bonus_points(12), 5000)
        self.assertEqual(R.count_dot(3, 1), (4, 1, True))


class Evidence(unittest.TestCase):
    def test_files(self):
        with open(os.path.join(ROOT, "analysis", "evidence-core-summary.txt"), encoding="utf-8") as fh:
            t = fh.read()
        self.assertEqual(t.count(" 0 differences"), 12)
        self.assertNotIn("calls: 1 differences", t)
        with open(os.path.join(ROOT, "docs", "44-core-algorithms.md"), encoding="utf-8") as fh:
            d = fh.read()
        for k in ("0 differences", "**old** cell", "NOT clamped" if False else "not clamped", "OV-67"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
