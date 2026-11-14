"""OV-34: tests of tools/analyze_pregame.py and of the code bytes it relies on.  Run:  python -I tests/test_pregame.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_pregame as A  # noqa: E402
import decode_streams as S  # noqa: E402


class Code(unittest.TestCase):
    def test_title_code(self):
        rd = S.rd
        self.assertEqual([rd(0xA72D), rd(0xA72E)], [0xA9, 0x12])            # zp_1A = 0: $1C90 := $12 ("2")
        self.assertEqual([rd(0xA738), rd(0xA739)], [0xA9, 0x11])            # zp_1A <> 0: $1C90 := $11 ("1")
        self.assertEqual([rd(0xA71D), rd(0xA71E)], [0x09, 0x50])            # $1C54 := (zp_1A + 1) | $50
        self.assertEqual([rd(0xAD87 + 1), rd(0xAD9F + 1)], [0x12, 0x11])    # the labels: "2UP" and "1UP"
        self.assertEqual([rd(0xAD8A), rd(0xAD8C)], [0x35, 0x30])            # U P

    def test_text_tables(self):
        self.assertEqual(A.text(A.rom(0xBFC6, 11)), "PLAYER GAME")
        self.assertEqual(A.text(A.rom(0xBFD1, 16)), "PRESS SELECT FOR")
        self.assertEqual(A.text(A.rom(0xBDD6, 17)), "CHANGE DIFFICULTY")


class Model(unittest.TestCase):
    def test_expected(self):
        e1 = A.expected_title(0, 0)
        e2 = A.expected_title(1, 0)
        self.assertEqual((e1[0x1C54], e1[0x1C90]), (0x51, 0x12))
        self.assertEqual((e2[0x1C54], e2[0x1C90]), (0x52, 0x11))
        self.assertEqual(e1[0x1C92], e1[0x1C56] & 0xBF)

    def test_label_check(self):
        frs = [dict(f=i, z19=0, z1a=1, cp=0, fa=i // 16 % 2, l1=A.UP1 if (i // 16) % 2 else A.BLANK, l2=A.UP2, t1=0, t7=1) for i in range(64)]
        cnt, dev, runs = A.check_labels(frs)
        self.assertFalse(dev)
        frs[5]["l2"] = A.BLANK                                              # the other player's label must not blink
        cnt, dev, runs = A.check_labels(frs)
        self.assertTrue(dev)


class RealLog(unittest.TestCase):
    def test_log(self):
        path = os.path.join(ROOT, "analysis", "raw-logs", "pregame.txt")
        if not os.path.exists(path):
            self.skipTest("raw log not present (gitignored)")
        L, problems = A.report(path)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
