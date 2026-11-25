"""Step C10 test: the rebuilt ROM must be byte-identical, and the check must catch a change.
Run:  python -I tests/test_rebuild.py
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_rom as B  # noqa: E402

ORIG = os.path.join(ROOT, "original", "Pac-Man.rom")
import asm_source  # noqa: E402

SRC = asm_source.path()                          # made from the ROM when it is not there


class Rebuild(unittest.TestCase):
    def test_identical_and_reproducible(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            r1, r2 = B.build(SRC, t1), B.build(SRC, t2)
            with open(r1, "rb") as f1, open(r2, "rb") as f2, open(ORIG, "rb") as fo:
                a, b, o = f1.read(), f2.read(), fo.read()
            self.assertEqual(a, o)
            self.assertEqual(a, b)

    def test_mutation_is_detected(self):
        with open(SRC) as fh:
            text = fh.read()
        self.assertIn(".byte $4A,$4A,$48", text)
        with tempfile.TemporaryDirectory() as t:
            bad = os.path.join(t, "bad.s")
            with open(bad, "w", newline="\n") as fh:
                fh.write(text.replace(".byte $4A,$4A,$48", ".byte $4B,$4A,$48", 1))
            rom = B.build(bad, t)
            self.assertFalse(B.compare(rom, ORIG))


if __name__ == "__main__":
    unittest.main(verbosity=2)
