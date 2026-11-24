"""Stage 64 (output processing): the write map of tools/output_map.py (the static classification of every store of the ROM, its check on the concrete 6502), the display lists, and the committed evidence and chapter."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import output_map as O   # noqa: E402
import analyze_output as AO  # noqa: E402


class Static(unittest.TestCase):
    def test_every_store_is_classified(self):
        self.assertEqual(len(O.STATIC), 574)
        for pc, regs in O.STATIC.items():
            self.assertTrue(regs and "?" not in regs, "$%04X %r" % (pc, regs))

    def test_the_fourteen_indirect_stores(self):
        izy = sorted(pc for pc, (ln, m, mode, op) in O.INS.items() if m == "sta" and mode == "izy")
        self.assertEqual(len(izy), 14)
        self.assertEqual(izy, sorted(O.IZY))                                    # the table of docs/29 has all of them, and no other

    def test_known_stores(self):
        self.assertEqual(O.STATIC[0xA636], {"StatusRows"})                       # TitleClearScores1P: sta $2020,x
        self.assertEqual(O.STATIC[0xB100], {"PmMissiles"})                       # FillPlayerPages: sta $2300,x
        self.assertIn("Gtia", O.STATIC[0xA614])                                  # InitDisplay2: sta HPOSP0,x
        self.assertEqual(O.region_of(0x2300), "PmMissiles")
        self.assertEqual(O.region_of(0x0F97), "MazeScreen")
        self.assertEqual(O.region_of(0x3010), "GameCharset")

    def test_output_regions_have_their_writers(self):
        dyn, st = O.census(O.Recorder())
        for r in ("PmPlayers", "PmMissiles", "MazeScreen", "StatusRows", "TitleScreen", "PictureBuffers"):
            self.assertTrue(st.get(r), r)
        # the data regions are written by the expansion of Start and by nothing else
        for r in ("OriginalMaze", "RamTables", "GameCharset"):
            self.assertEqual(set(st[r]), {"WriteDstByte"}, r)


class Dynamic(unittest.TestCase):
    def test_no_store_outside_its_classification(self):
        rec, stats, seqs = O.run(200)
        self.assertEqual(rec.bad, [])
        self.assertGreater(sum(rec.stores.values()), 100000)
        strays = {pc for (pc, r) in rec.stores if r == "Rom"}
        self.assertEqual(strays, {0xB993})                                       # the only stray write of the original into the ROM: InitDisplay2's jump into the drawing tail

    def test_display_lists(self):
        game = AO.decode_dl(0xBFA3)
        self.assertEqual([r[0] + r[2] + 8 - 1 for r in game if r[4]], [39, 47, 207, 215, 231])     # the lines of the five interrupts (docs/38, docs/35)
        self.assertEqual([r[3] for r in game if r[3]], [0x2000, 0x0C00])
        title = AO.decode_dl(0xBF81)
        self.assertEqual(sum(1 for r in title if r[4]), 5)


class Evidence(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_evidence(self):
        t = self.read("analysis/evidence-output-summary.txt")
        self.assertIn("574 store instructions of the ROM classified", t)
        self.assertIn("stores, 0 outside the classification", t)
        self.assertIn("$B993 (InitDisplay2)", t)
        self.assertIn("MazeScreen      $0C00-$0FFF: 41 store instructions in 12 routines, 41 executed", t)

    def test_chapter(self):
        d = self.read("docs/42-output-processing.md")
        for r in AO.ORDER:
            self.assertIn("| %s |" % r, d)
        for k in ("Two strays of the original", "InitDisplay2", "DliHandler1", "0 outside the classification"):
            self.assertIn(k, d)
        self.assertIn("| 8 | 2 | blank (8 lines) |", d)


if __name__ == "__main__":
    unittest.main()
