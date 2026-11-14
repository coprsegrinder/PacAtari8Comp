"""OV-35: the code facts behind the frightened-ghost cases and tests of tools/analyze_frightened_cases.py.  Run:  python -I tests/test_frightened_cases.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_frightened_cases as A  # noqa: E402
import decode_streams as S  # noqa: E402


def code(a, n):
    return [S.rd(a + i) for i in range(n)]


class Code(unittest.TestCase):
    def test_frightened_ends(self):
        # $AF8C: lda GhostState,x; bpl skip; cmp #$80; beq $AF9A (-> $00); and #$BB; beq skip; bne $AF9E (-> $20)
        self.assertEqual(code(0xAF8C, 12), [0xB5, 0xCE, 0x10, 0x12, 0xC9, 0x80, 0xF0, 0x06, 0x29, 0xBB, 0xF0, 0x0A])
        self.assertEqual(code(0xAF9A, 4), [0xA9, 0x00, 0xF0, 0x02])
        self.assertEqual(code(0xAF9E, 4), [0xA9, 0x20, 0x95, 0xCE])
        # any frightened state but $80 has bit 7 set, and bit 7 survives AND #$BB, so the result is never 0: $81 -> $20
        for s in range(0x81, 0x100):
            if s & 0x40:
                continue
            self.assertNotEqual(s & 0xBB, 0)

    def test_behaviour_runs_chase_for_frightened(self):
        # GhostBehaviour $B7F5: lda GhostState,x; bpl normal; lsr; lsr; lsr; bcc GhostChase ($B80E); rts
        self.assertEqual(code(0xB7F5, 10), [0xB5, 0xCE, 0x10, 0x06, 0x4A, 0x4A, 0x4A, 0x90, 0x10, 0x60])
        self.assertEqual(code(0xB80E, 3), [0x4C, 0xEF, 0xB8])             # jmp GhostChase

    def test_one_ghost_eaten_per_frame(self):
        # the contact loop leaves through AddToScore after the first eaten ghost: ... jmp AddToScore ($A920) = 4C 23 B4
        self.assertEqual(code(0xA920, 3), [0x4C, 0x23, 0xB4])
        self.assertEqual(code(0xA886, 4), [0xA9, 0x42, 0x95, 0xCE])        # GhostEaten: state := $42
        # eaten ghosts (bit 6) are skipped by the contact test: asl a; bmi next
        self.assertEqual(code(0xA851, 4), [0xB5, 0xCE, 0x0A, 0x30])


class Analyzer(unittest.TestCase):
    def test_kind(self):
        self.assertEqual([A.kind_of(b) for b in (1, 2, 3, 4)], [0, 1, 2, 0])

    def test_real_log(self):
        path = os.path.join(ROOT, "analysis", "raw-logs", "frightened-cases.txt")
        if not os.path.exists(path):
            self.skipTest("raw log not present (gitignored)")
        L, problems = A.run(path)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
