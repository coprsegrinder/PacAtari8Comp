"""OV-31: tests of the tunnel-edge clipping (Sub_AB57, $AB57-$ABC8) and of tools/analyze_tunnel_clip.py.  Run:  python -I tests/test_tunnel_clip.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_tunnel_clip as A  # noqa: E402
import decode_streams as S  # noqa: E402


class Code(unittest.TestCase):
    """The bytes of the routine the model is derived from."""

    def test_constants(self):
        rd = S.rd
        self.assertEqual([rd(0xAB6D), rd(0xAB6E)], [0xC9, 0xC0])          # cmp #$C0: the right edge
        self.assertEqual([rd(0xAB95), rd(0xAB96)], [0xC9, 0x39])          # cmp #$39: the left edge
        self.assertEqual([rd(0xAB99), rd(0xAB9A)], [0xA9, 0x38])          # lda #$38: left mask reference
        self.assertEqual([rd(0xAB71), rd(0xAB72)], [0xA9, 0xC0])          # lda #$C0: right mask reference
        self.assertEqual([rd(0xAB7F), rd(0xAB80)], [0xC9, 0xCA])          # wrap right at X >= $CA
        self.assertEqual([rd(0xAB89), rd(0xAB8A)], [0xA9, 0x2A])          # ... to $2A
        self.assertEqual([rd(0xABA7), rd(0xABA8)], [0xC9, 0x2A])          # wrap left at X = $2A
        self.assertEqual([rd(0xABB1), rd(0xABB2)], [0xA9, 0xCA])          # ... to $CA
        self.assertEqual([rd(0xAB4C), rd(0xAB4D)], [0xC9, 0x74])          # only the tunnel row, EntityY = $74
        self.assertEqual([rd(0xABC1), rd(0xABC2)], [0x25, 0xFE])          # and zp_FE over the 16 rows


class Model(unittest.TestCase):
    def test_masks(self):
        self.assertEqual(A.model(0xC0, 8)[0], 0xFF)
        self.assertEqual(A.model(0xC3, 8)[0], 0xF8)                       # the mask seen in the screenshot test
        self.assertEqual(A.model(0xC2, 8)[0], 0xFC)
        self.assertEqual(A.model(0xC7, 8)[0], 0x80)
        self.assertEqual(A.model(0xC8, 8)[0], 0x00)
        self.assertEqual(A.model(0x38, 4)[0], 0xFF)
        self.assertEqual(A.model(0x37, 4)[0], 0x7F)
        self.assertEqual(A.model(0x31, 4)[0], 0x01)
        self.assertEqual(A.model(0x30, 4)[0], 0x00)
        self.assertEqual(A.model(0x39, 4)[0], 0xFF)
        self.assertEqual(A.model(0xBF, 8)[0], 0xFF)

    def test_wrap(self):
        self.assertEqual(A.model(0xCA, 8), (0, 0x2A, "right"))
        self.assertEqual(A.model(0xCA, 4), (0, 0xCA, None))               # going left at $CA: no wrap
        self.assertEqual(A.model(0xC9, 8), (0, 0xC9, None))               # not yet
        self.assertEqual(A.model(0x2A, 4), (0, 0xCA, "left"))
        self.assertEqual(A.model(0x2A, 8), (0, 0x2A, None))
        self.assertEqual(A.model(0x2B, 4), (0, 0x2B, None))


class RealLog(unittest.TestCase):
    def test_sweep_log(self):
        path = os.path.join(ROOT, "analysis", "raw-logs", "tunnel-clip.txt")
        if not os.path.exists(path):
            self.skipTest("raw log not present (gitignored)")
        calls = A.parse(path)
        L, bad = A.report(calls)
        self.assertFalse(bad)
        self.assertGreater(len(calls), 100000)


if __name__ == "__main__":
    unittest.main()
