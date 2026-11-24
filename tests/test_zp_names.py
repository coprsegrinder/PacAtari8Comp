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

    def test_every_byte_has_the_catalogue_name(self):
        """checklist stage 3: the names of docs/25 are applied; a byte that is not the first of its variable is Name+k"""
        import zp_catalogue as Z
        for first, n, name, *_ in Z.ZP:
            if first in LB.OS_ZP or first in LB.GAME_ZP:
                continue
            self.assertEqual(LB.zp_name(first), name)
            for k in range(1, n):
                if first + k not in LB.GAME_ZP and first + k not in LB.OS_ZP:
                    self.assertEqual(LB.zp_name(first + k), "%s+%d" % (name, k))
        self.assertEqual((LB.zp_name(0x2D), LB.zp_name(0x61), LB.zp_name(0xE5), LB.zp_name(0x20)), ("Lives+1", "DliColors+3", "EatPause", "CountdownActive"))
        self.assertEqual(LB.zp_equate(0x2D), ("Lives", 0x2C))
        self.assertEqual(LB.zp_name(0x00), "zp_00")             # a byte the code does not use is not in the catalogue

    def test_no_generic_name_is_left_in_the_source(self):
        import re
        src = open(os.path.join(ROOT, "src", "asm", "pacman.s"), encoding="utf-8").read()
        self.assertEqual(re.findall(r"zp_[0-9A-F]{2}", src), [])
        self.assertRegex(src, r"(?m)^EatPause\s+= \$E5$")
        self.assertIn("Lives+1", src)
        self.assertRegex(src, r"(?m)^Lives\s+= \$2C$")
        self.assertNotRegex(src, r"(?m)^Lives\+1\s+=")

    def test_the_key_in_the_catalogue(self):
        doc = open(os.path.join(ROOT, "docs", "25-variable-catalogue.md"), encoding="utf-8").read()
        self.assertIn("**83 zero-page bytes that were `zp_XX` now have these names**", doc)
        self.assertIn("| `zp_E5` | `EatPause` | EatPause | 1 |", doc)

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
