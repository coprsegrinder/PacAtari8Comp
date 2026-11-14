"""OV-36: the zero-page names of the dot counter and the siren step; the source must keep them and still rebuild.  Run:  python -I tests/test_zp_names.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import labels as LB  # noqa: E402


class Names(unittest.TestCase):
    def test_names(self):
        self.assertEqual((LB.zp_name(0x34), LB.zp_name(0x36), LB.zp_name(0x9C), LB.zp_name(0xAD)), ("DotsEatenLo", "DotsEatenHi", "SirenStep", "ChaseTimer"))

    def test_source(self):
        src = open(os.path.join(ROOT, "src", "asm", "pacman.s"), encoding="utf-8").read()
        for line in ("DotsEatenLo = $34", "DotsEatenHi = $36", "SirenStep = $9C"):
            self.assertIn(line, src)
        self.assertIn("inc z:DotsEatenLo,x        ; B388  F6 34", src)
        self.assertIn("sta z:SirenStep            ; B5FF  85 9C", src)
        for old in ("zp_34", "zp_36", "zp_9C"):
            self.assertNotIn(old, src)

    def test_rebuild(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import hashlib
        import tempfile
        import build_rom as B
        with tempfile.TemporaryDirectory() as d:
            rom = B.build(os.path.join(ROOT, "src", "asm", "pacman.s"), d)
            built = open(rom, "rb").read()
        orig = open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb").read()
        self.assertEqual(hashlib.sha256(built).hexdigest(), hashlib.sha256(orig).hexdigest())


if __name__ == "__main__":
    unittest.main()
