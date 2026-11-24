"""Stage 50: tests of tools/cpu6502.py and tools/algorithm_models.py (the ROM run against models).  Run:  python -I tests/test_algorithms.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import algorithm_models as A  # noqa: E402
import cpu6502 as C  # noqa: E402


class Cpu(unittest.TestCase):
    def machine(self):
        return C.Machine(A.ROM)

    def test_decimal_addition_known_results(self):
        # NMOS 6502 results (6502.org decimal-mode tutorial): A, M, carry in -> A, carry out
        cases = [(0x58, 0x46, 1, 0x05, 1), (0x12, 0x34, 0, 0x46, 0), (0x15, 0x26, 0, 0x41, 0), (0x81, 0x92, 0, 0x73, 1), (0x99, 0x01, 0, 0x00, 1), (0x09, 0x01, 0, 0x10, 0), (0x00, 0x00, 1, 0x01, 0)]
        for a, mm, c, want, wc in cases:
            m = self.machine()
            m.d, m.c, m.a = 1, c, a
            m.adc(mm)
            self.assertEqual((m.a, m.c), (want, wc), "%02X+%02X+%d" % (a, mm, c))

    def test_binary_flags(self):
        m = self.machine()
        m.c, m.a = 0, 0x7F
        m.adc(0x01)
        self.assertEqual((m.a, m.n, m.v, m.c, m.z), (0x80, 1, 1, 0, 0))
        m.c, m.a = 1, 0x50
        m.sbc(0xB0)
        self.assertEqual((m.a, m.c, m.v), (0xA0, 0, 1))
        m.cmp(5, 5)
        self.assertEqual((m.z, m.c, m.n), (1, 1, 0))

    def test_stack_and_calls(self):
        m = self.machine()
        n = m.call(0xB0E6)                                  # ClearPokeyRegisters: eight stores and an RTS
        self.assertGreater(n, 8)
        self.assertEqual(m.s, 0xFF)

    def test_rom_is_read_only(self):
        m = self.machine()
        m.wr(0xA386, 0x55)
        self.assertEqual(m.mem[0xA386], A.ROM[0x386])

    def test_random_values_are_supplied_in_order(self):
        m = C.Machine(A.ROM, [7, 9])
        self.assertEqual((m.rd(0xD20A), m.rd(0xD20A), m.rd(0xD20A)), (7, 9, 0))
        self.assertEqual(m.random_reads, [7, 9, 0])


class Models(unittest.TestCase):
    def test_start_expansion(self):
        parts, steps = A.check_start_expansion()
        self.assertEqual([ok for n, ok in parts], [True] * 5)
        self.assertEqual(steps, 32751)

    def test_add_to_score(self):
        n, bad, extra = A.check_add_to_score(800)
        self.assertEqual(bad, [])
        self.assertGreater(extra, 100)                      # the extra life is exercised

    def test_known_scores(self):
        cells = [0, 0, 0, 0x11, 0x11, 0x11]                 # 111
        new, flag, lives = A.model_add_to_score(cells, [0, 0, 0, 0, 5, 0], 0, 0, 2)
        self.assertEqual(new, [0, 0, 0, 0x11, 0x16, 0x11])  # 161
        new, flag, lives = A.model_add_to_score([0, 0x19, 0x19, 0x19, 0x19, 0x19], [0, 0, 0, 0, 0, 1], 0, 0, 2)
        self.assertEqual((new, flag, lives), ([0x11, 0x10, 0x10, 0x10, 0x10, 0x10], 1, 3))     # 99,999 + 1 = 100,000: the extra life

    def test_move_delay_tick(self):
        n, bad = A.check_move_delay_tick()
        self.assertEqual((n, bad), (10241, []))

    def test_release_timers(self):
        n, bad = A.check_release_timers()
        self.assertEqual((n, bad), (256, []))

    def test_junction_lookup(self):
        n, bad = A.check_junction_lookup()
        self.assertEqual(bad, [])
        self.assertEqual(n, 29184)

    def test_steer_to_target(self):
        n, bad, reads = A.check_steer_to_target(4000)
        self.assertEqual(bad, [])
        self.assertGreater(reads[0], 500)
        self.assertGreater(reads[1], 500)


class Sensitivity(unittest.TestCase):
    """a model that is wrong must be noticed"""

    def test_broken_blanking_rule_is_found(self):
        orig = A.model_add_to_score

        def broken(cells, add, player, flag, lives):
            new, carry = list(cells), 0
            for y in range(5, -1, -1):
                s = (cells[y] & 0x0F) + carry + add[y]
                carry = 1 if s >= 10 else 0
                d = s % 10
                code = 0x10 | d
                if d == 0:
                    code = 0 if y == 0 else (0x10 if cells[y - 1] != 0 else 0)
                new[y] = code
            f, lv = flag, lives
            if flag == 0 and new[1] != 0:
                f, lv = flag + 1, lives + 1
            return new, f, lv
        A.model_add_to_score = broken
        try:
            self.assertGreater(len(A.check_add_to_score(1500)[1]), 0)
        finally:
            A.model_add_to_score = orig

    def test_broken_steering_is_found(self):
        orig = A.model_steer
        A.model_steer = lambda *a: (lambda r: (8 if r[0] == 1 else r[0],) + r[1:])(orig(*a))
        try:
            self.assertGreater(len(A.check_steer_to_target(500)[1]), 0)
        finally:
            A.model_steer = orig

    def test_broken_junction_rule_is_found(self):
        orig = A.model_junction
        A.model_junction = lambda m, e, x, y, d, s: (0x0C if (y == 0x64 and x == 0x76 and e == 1) else orig(m, e, x, y, d, s)[0], orig(m, e, x, y, d, s)[1])
        try:
            self.assertGreater(len(A.check_junction_lookup()[1]), 0)
        finally:
            A.model_junction = orig


class Evidence(unittest.TestCase):
    def test_summary(self):
        path = os.path.join(ROOT, "analysis", "evidence-algorithms-summary.txt")
        with open(path, encoding="utf-8") as fh:
            txt = fh.read()
        self.assertEqual(txt.count(" 0 differences"), 5, txt)
        self.assertIn("(32751 instructions)", txt)
        self.assertNotIn("DIFFERENT", txt)
        self.assertIn("add_to_score: 6000 additions", txt)
        self.assertIn("move_delay_tick: 10241 calls", txt)
        self.assertIn("junction_lookup: 29184 calls", txt)
        self.assertIn("steer_to_target: 30000 calls", txt)


if __name__ == "__main__":
    unittest.main()
