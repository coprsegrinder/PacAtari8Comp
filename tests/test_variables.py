"""Stage 41: tests of tools/analyze_variables.py and docs/25-variable-catalogue.md.  Run:  python -I tests/test_variables.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_variables as V  # noqa: E402
import decode_streams as S  # noqa: E402
import labels as LB  # noqa: E402

ROM, F, ACC, AREAS = V.build()
rd = S.rd


class Coverage(unittest.TestCase):
    def test_groups_do_not_overlap_and_cover_every_accessed_byte(self):
        seen = set()
        for first, n, name, kind, role, ev in V.ZP:
            self.assertTrue(role and ev and name, name)
            for a in range(first, first + n):
                self.assertNotIn(a, seen, "%s overlaps" % name)
                seen.add(a)
        self.assertEqual(sorted(set(ACC) - seen), [])

    def test_every_accessed_ram_address_is_in_an_area(self):
        for a in AREAS:
            self.assertTrue(any(f <= a <= l for f, l, *_ in V.AREAS), hex(a))

    def test_names_agree_with_the_labels(self):
        for first, n, name, kind, role, ev in V.ZP:
            lbl = LB.zp_name(first)
            if not lbl.startswith("zp_"):
                self.assertTrue(name.startswith(lbl) or lbl.startswith(name), "%s vs %s" % (name, lbl))

    def test_array_sizes(self):
        sizes = {n: c for _, c, n, *_ in V.ZP}
        self.assertEqual((sizes["EntityX"], sizes["EntityY"], sizes["EntityDir"], sizes["GhostState"], sizes["Lives"], sizes["Level"]), (5, 5, 5, 4, 2, 2))


class CodeFacts(unittest.TestCase):
    """The roles that were read from the code and not tested live are pinned to the code that shows them."""

    def test_pause_key(self):
        # $A4D1: LDA CH / CMP #$21 / BNE; the toggle of zp_9B at $A4D8-$A4E2
        self.assertEqual([rd(0xA4D1), rd(0xA4D4), rd(0xA4D5)], [0xAD, 0xC9, 0x21])
        self.assertEqual([rd(0xA4D8), rd(0xA4D9)], [0xA5, 0x9B])
        self.assertEqual([rd(0xA798), rd(0xA799), rd(0xA79C), rd(0xA79D), rd(0xA79E), rd(0xA79F)], [0xA5, 0x9B, 0x4C, 0xE6, 0xB0, 0x20])

    def test_ready_spends_a_life(self):
        self.assertEqual([rd(0xAD0E), rd(0xAD11), rd(0xAD13), rd(0xAD14)], [0x20, 0xA6, 0xD6, 0x2C])      # JSR DrawAllInPlace / LDX CurrentPlayer / DEC zp_2C,X
        self.assertEqual([rd(0xAC7A), rd(0xAC7B)], [0xF6, 0x2C])                                           # AdvanceLevel: INC zp_2C,X

    def test_level_complete_threshold(self):
        self.assertEqual([rd(0xB394), rd(0xB395), rd(0xB396), rd(0xB397)], [0xB5, 0x34, 0xC9, 0x04])      # dots eaten low byte = 4 with a non-zero high byte: 260
        self.assertEqual([rd(0xB39A), rd(0xB39B), rd(0xB39C)], [0xA9, 0x01, 0x85])
        self.assertEqual(rd(0xB39D), 0x26)

    def test_pac_man_cell_pointer_steps(self):
        self.assertEqual([rd(0xB202), rd(0xB203)], [0xE9, 0x28])                                           # SBC #$28: one row up
        self.assertEqual([rd(0xB22C), rd(0xB22D)], [0x69, 0x28])                                           # ADC #$28: one row down


class Document(unittest.TestCase):
    def test_document_is_up_to_date(self):
        want = "\n".join(V.report(ROM, F, ACC, AREAS)) + "\n"
        with open(os.path.join(ROOT, "docs", "25-variable-catalogue.md"), encoding="utf-8", newline="") as fh:
            got = fh.read().replace("\r\n", "\n")
        self.assertEqual(got, want, "run: python -I tools/analyze_variables.py --write docs/25-variable-catalogue.md")


if __name__ == "__main__":
    unittest.main()
