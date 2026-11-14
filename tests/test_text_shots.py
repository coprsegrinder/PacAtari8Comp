"""OV-53: the display list of the title and tests of tools/check_text_shots.py.  Run:  python -I tests/test_text_shots.py"""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_text_shots as T  # noqa: E402
import decode_streams as S  # noqa: E402


def decode_dl(a):
    """[(scanline, mode, scanlines, lms or None, dli)] of a display list (the first line is scanline 8)."""
    out, i, scan = [], 0, 8
    while True:
        b = S.rd(a + i)
        m = b & 15
        if m == 1:
            return out
        if m == 0:
            n = ((b >> 4) & 7) + 1
            scan += n
            i += 1
            continue
        lines = {2: 8, 4: 8, 6: 8, 7: 16}[m]
        lms = None
        if b & 0x40:
            lms = S.rd(a + i + 1) | S.rd(a + i + 2) << 8
            i += 3
        else:
            i += 1
        out.append((scan, m, lines, lms, bool(b & 0x80)))
        scan += lines


class DisplayList(unittest.TestCase):
    def test_title_rows_match_the_rom(self):
        dl = decode_dl(0xBF81)
        mine = [(r[0], r[1], r[2]) for r in T.TITLE_ROWS]
        self.assertEqual([(a, b, c) for a, b, c, d, e in dl], mine)
        self.assertEqual([d for a, b, c, d, e in dl if d], [0x2000, 0x1C00, 0x0F70])        # the three LMS addresses
        rows = T.rows_with_addresses(T.TITLE_ROWS)
        self.assertEqual(rows[2][4], 0x1C00)
        self.assertEqual(rows[-1][4], 0x0F70)
        self.assertEqual(rows[-2][4] + rows[-2][3], 0x1C00 + 20 * 3 + 20 * 5 + 20 + 40 + 20 * 10)   # the rows follow each other without a gap

    def test_status_rows_match_the_game_list(self):
        dl = decode_dl(0xBFA3)
        self.assertEqual([(a, b, c, d) for a, b, c, d, e in dl][:2], [(24, 2, 8, 0x2000), (32, 2, 8, None)])


class Labels(unittest.TestCase):
    def test_label_codes(self):
        # Sub_AD9F / Sub_AD87: "1UP" = $11 $35 $30, "2UP" = $12 $35 $30
        self.assertEqual([S.rd(0xAD9F + 1), S.rd(0xAD87 + 1)], [0x11, 0x12])
        self.assertEqual(T.text_of({0x2004: 0x11, 0x2005: 0x35, 0x2006: 0x30}, 0x2004, 3), "1UP")


class RealShots(unittest.TestCase):
    def test_shots(self):
        d = os.path.join(ROOT, "analysis", "shots", "item-shots")
        if not os.path.isfile(os.path.join(d, "Title_2P.log")):
            self.skipTest("screenshots are local evidence only")
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "check_text_shots.py"), d], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-600:])


if __name__ == "__main__":
    unittest.main()
