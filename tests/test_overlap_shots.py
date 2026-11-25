"""OV-52: the priority register of the game and tests of tools/check_overlap_shots.py.  Run:  python -I tests/test_overlap_shots.py"""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import decode_streams as S  # noqa: E402

rd = S.rd


class Priority(unittest.TestCase):
    def test_gprior_values(self):
        # the game writes GPRIOR ($026F) at three places: $11 at the board set-up and after a pop-up, $14 during the ghost-eaten pop-up
        self.assertEqual([rd(0xA49E), rd(0xA49F), rd(0xA4A0), rd(0xA4A1), rd(0xA4A2)], [0xA9, 0x11, 0x8D, 0x6F, 0x02])
        self.assertEqual([rd(0xB096), rd(0xB097), rd(0xB098), rd(0xB099), rd(0xB09A)], [0xA9, 0x11, 0x8D, 0x6F, 0x02])
        self.assertEqual([rd(0xA8FB), rd(0xA8FC), rd(0xA8FD), rd(0xA8FE), rd(0xA8FF)], [0xA9, 0x14, 0x8D, 0x6F, 0x02])
        for v in (0x11, 0x14):
            self.assertEqual(v & 0x20, 0)                                   # bit 5 (overlapping players ORed) is clear: no mixed colours
        self.assertEqual(0x11 & 0x0F, 0x01)                                 # players in front of the playfield, lowest player number first
        self.assertEqual(0x14 & 0x0F, 0x04)                                 # PF0-PF1 in front of the players during the pop-up

    def test_only_three_writes(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import asm_source
        src = open(asm_source.path(), encoding="utf-8").read()
        self.assertEqual(src.count("sta GPRIOR"), 3)


class RealShots(unittest.TestCase):
    def test_shots(self):
        d = os.path.join(ROOT, "analysis", "shots", "item-shots")
        if not os.path.isfile(os.path.join(d, "Overlap_A.log")):
            self.skipTest("screenshots are local evidence only")
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "check_overlap_shots.py"), d], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-600:])


if __name__ == "__main__":
    unittest.main()
