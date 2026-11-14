"""OV-32: tests of tools/check_item_shots.py and the code facts the screenshot check relies on.  Run:  python -I tests/test_item_shots.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_item_shots as C  # noqa: E402
import decode_streams as S  # noqa: E402


class Code(unittest.TestCase):
    def test_popup_colour_and_pictures(self):
        rd = S.rd
        self.assertEqual([rd(0xA8A6), rd(0xA8A7)], [0xA9, 0xDC])            # GhostEaten: lda #$DC (COLOR3 and the ghost's PCOLR)
        self.assertEqual([rd(0xB0A0), rd(0xB0A1)], [0xC9, 0xDC])            # $B09D: finds the player holding $DC ...
        self.assertEqual([rd(0xB0A8), rd(0xB0A9)], [0xA9, 0x0C])            # ... and makes it $0C (the eyes)
        for k in range(4):                                                  # four score pictures, 16 rows each, inside the ROM
            ptr = rd(0xBCD0 + 2 * k) | rd(0xBCD1 + 2 * k) << 8
            self.assertTrue(0xA000 <= ptr and ptr + 16 <= 0xC000)

    def test_dli_colour_table(self):
        self.assertEqual([S.rd(0xBBEE + i) for i in range(4)], [0x3A, 0x44, 0x2A, 0xDA])    # ColorsDli: peach, red, gold, light green
        self.assertEqual([S.rd(0xBBE2 + i) for i in range(8)][4:], [0x86, 0x0C, 0x00, 0x2A])  # ColorsGame[4-7]


class Timeline(unittest.TestCase):
    def test_bands(self):
        # two frames: base values at the OS copy (scan 250), then a DLI band at scan 48 and 216
        f1 = [(0xD017, 0x0C, 250), (0xD018, 0x00, 250), (0xD016, 0x86, 250), (0xD019, 0x2A, 250), (0xD01A, 0x00, 250)]
        f2 = [(0xD017, 0x44, 48), (0xD018, 0x3A, 48), (0xD016, 0xDA, 216)] + f1
        cw = [(r, v, vp, 0) for r, v, vp in f1 + f2 + f1]
        tl, use = C.timeline(cw)
        self.assertEqual(tl[0xD017][47], 0x0C)
        self.assertEqual(tl[0xD017][48], 0x44)
        self.assertEqual(tl[0xD016][215], 0x86)
        self.assertEqual(tl[0xD016][216], 0xDA)

    def test_render_expect_skips_pellet_cells(self):
        mem = {0x3000 + 8 * 1 + r: 0xFF for r in range(8)}
        tl = {r: [0x44] * 262 for r in C.REG}
        m2 = dict(mem)
        m2[0xC00 + 3 * 40 + 3] = 1
        m2[0xC00 + 5 * 40 + 5] = 1
        exp = C.render_expect(m2, tl, 40)
        cells = {(r, c) for _, _, _, _, _, r, c in exp}
        self.assertNotIn((3, 3), cells)
        self.assertIn((5, 5), cells)


class RealShots(unittest.TestCase):
    def test_shots(self):
        d = os.path.join(ROOT, "analysis", "shots", "item-shots")
        if not os.path.isdir(d):
            self.skipTest("screenshots are local evidence only")
        import subprocess
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "check_item_shots.py"), d], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-600:])


if __name__ == "__main__":
    unittest.main()
