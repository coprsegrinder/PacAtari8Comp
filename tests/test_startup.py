"""Stage 61 (startup): the committed evidence and chapter, the log parser on a synthetic log, and the fill experiment (random RAM against zero) on a short run."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_startup as S  # noqa: E402
import startup_poison as SP  # noqa: E402

LOG = """MS_INIT f=22 vp=195 hp=7 ret=$F1BC
MS_RUN f=32 vp=63 hp=6 s=$FF p=$31 a=$04 x=$00 y=$80 ret=$E790
MS_SETVBV f=39 vp=195 hp=76 a=$07 x=$A5 y=$FD
GS_WRITE pc=$A3A1 v=$01 f=32 vp=90
HDR_READ a=$BFFC pc=$F244 f=3
---RUN_P4
0400: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 |................|
---RUN_END
"""


class Parser(unittest.TestCase):
    def test_read_log(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.txt")
            with open(p, "w") as fh:
                fh.write(LOG)
            r = S.read_log(p)
        self.assertEqual(r["init"][0][0], 22)
        self.assertEqual(r["ms"]["MS_RUN"][0], 32)
        self.assertEqual(r["gs"], [(0xA3A1, 1, 32, 90)])
        self.assertEqual(r["hdr"], [(0xBFFC, 0xF244, 3)])
        self.assertEqual(sum(S.dump_bytes(r["sections"]["RUN_P4"][0]).values()), 0)


class Poison(unittest.TestCase):
    def test_fill_experiment_finds_the_known_dependencies(self):
        zero, zst = SP.run(0, 700, fill="zero")
        rnd = [SP.run(1, 700)]
        self.assertEqual(zst["start_frame"], 481)                     # the START press at frame 480 starts the game, with or without garbage
        self.assertEqual(rnd[0][1]["start_frame"], 481)
        cl = SP.classify(rnd)
        names = {n for n, _ in cl}
        self.assertTrue({"Copy0800To0C00", "DrawAllInPlace", "InitDisplay2", "DliHandler2", "VbiHandler"} <= names)
        diffs = SP.compare(zero, [m for m, _ in rnd])
        self.assertTrue(all(a == 0x45 or 0x0F98 <= a < 0x1800 or 0x2300 <= a < 0x2800 for a in diffs), sorted(hex(a) for a in diffs)[:10])
        self.assertTrue(all(not (0x18 <= a < 0x100) or a == 0x45 for a in diffs))      # no game variable depends on the fill

    def test_the_experiment_notices_a_poisoned_read(self):
        m, st = SP.run(2, 60)
        self.assertTrue(m.rbw)
        self.assertTrue(all(a < 0xA000 for a in m.rbw))


class Evidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(S.SUMMARY, encoding="utf-8") as fh:
            cls.txt = fh.read()

    def test_tables_equal_on_all_machines(self):
        self.assertEqual(self.txt.count("EQUAL to the interpreter's expansion"), 3)
        self.assertNotIn("DIFFERENT", self.txt)

    def test_entry_state_and_zero_areas(self):
        self.assertIn("s=$FF p=$31 a=$04 x=$00 y=$80", self.txt)
        self.assertEqual(self.txt.count("$0400-$043F all zero; $0B98-$0BFF all zero"), 3)
        self.assertIn("SETVBV a=$07 x=$A5 y=$FD".replace("SETVBV ", ""), self.txt)

    def test_warm_start(self):
        self.assertIn("warm start", self.txt)
        self.assertIn("jumps to RUN again", self.txt)
        self.assertIn("all zero", self.txt.split("warm start")[1])

    def test_chapter(self):
        with open(os.path.join(ROOT, "docs", "37-startup.md"), encoding="utf-8") as fh:
            doc = fh.read()
        for s in ("## 1. The result", "## 2. From power-on to RUN", "## 3. What `Start` does", "## 4. What the game takes from the power-on state", "## 5. The warm start", "## 6. Limits"):
            self.assertIn(s, doc)


if __name__ == "__main__":
    unittest.main()
