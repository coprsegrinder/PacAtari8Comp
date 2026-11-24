"""OV-64: the static worst-case instruction cycles of the vertical-blank handler (tools/static_wcet.py): the cycle table, the loop bounds, and the bound of some classes."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import static_wcet as W  # noqa: E402


class Cycles(unittest.TestCase):
    def test_table(self):
        self.assertEqual(W.cost({0x1000: (2, "lda", "imm", 1)}, 0x1000, 0x1002), 2)
        self.assertEqual(W.cost({0x1000: (3, "lda", "abx", 0x2000)}, 0x1000, 0x1003), 4)     # a table that starts on a page never crosses
        self.assertEqual(W.cost({0x1000: (3, "lda", "abx", 0x20F0)}, 0x1000, 0x1003), 5)     # index unknown: a crossing is possible
        self.assertEqual(W.cost({0x1000: (3, "lda", "abx", 0x20F0)}, 0x1000, 0x1003, 0x05), 4)   # index known: no crossing
        self.assertEqual(W.cost({0x1000: (3, "lda", "abx", 0x20F0)}, 0x1000, 0x1003, 0x20), 5)   # index known: crossing
        self.assertEqual(W.cost({0x1000: (3, "sta", "abx", 0x2000)}, 0x1000, 0x1003), 5)
        self.assertEqual(W.cost({0x1000: (2, "inc", "zp", 5)}, 0x1000, 0x1002), 5)
        self.assertEqual(W.cost({0x1000: (3, "jsr", "abs", 0x2000)}, 0x1000, 0x2000), 6)
        self.assertEqual(W.cost({0x10F0: (2, "bne", "rel", 0x1000)}, 0x10F0, 0x10F2), 2)     # not taken
        self.assertEqual(W.cost({0x10F0: (2, "bne", "rel", 0x1100)}, 0x10F0, 0x1100), 4)     # taken, other page
        self.assertEqual(W.cost({0x1000: (2, "bne", "rel", 0x1010)}, 0x1000, 0x1010), 3)     # taken, same page


class Bounds(unittest.TestCase):
    def test_quick_classes(self):
        self.assertEqual(W.class_bound("paused")[0], 3114)
        self.assertEqual(W.class_bound("death")[0], 5923)

    def test_level_end_by_stages(self):
        b, _ = W.class_bound("level end")
        self.assertEqual(b, 17581)                                            # without the stages: over the budget
        lb, per = W.level_end_bound()
        self.assertEqual(per, {"level end 0": 6096, "level end 1": 3197, "level end 2": 3165, "level end 3": 10322, "level end 4": 14846})
        self.assertEqual(lb, 14846)
        self.assertLess(lb, 16100)
        self.assertTrue(W.check_level_end_chain())                            # stage 3 leaves LevelEndStep = 4 and the start positions on every path

    def test_tunnel_edges(self):
        b2, _ = W.class_bound("level end", heavy=2)
        b3, _ = W.class_bound("level end", heavy=3)
        self.assertEqual(b2, 16003)
        self.assertGreater(b3, 16100)

    def test_no_cycle_remains(self):
        start, succ, prog = W.bounded_graph(0xA5FD, 6_000_000, W.CLASSES["paused"])
        self.assertEqual(W.find_cycles(succ, start), {})                      # every loop is followed or bounded


class Display(unittest.TestCase):
    def test_model(self):
        import dma_model as D
        steal, dli = D.steal_table()
        self.assertEqual(sorted(dli), [39, 47, 207, 215, 231])                 # the lines of the measured display-list interrupts (38)
        self.assertEqual(D.budget(), 16425)
        for cls, bound, measured in (("paused", 3114, 234), ("death", 5939, 3038), ("level end", 18616, 26729), ("turn control", 17001, 25706)):
            self.assertGreaterEqual(D.elapsed(bound), measured)                # the model never undercounts a measured frame
        self.assertLess(D.elapsed(5939), 262 * 114)                            # death fits
        self.assertGreater(D.elapsed(18616), 262 * 114)                        # level end is not proved to fit


class Evidence(unittest.TestCase):
    def test_loop_bounds_respected(self):
        p = os.path.join(ROOT, "analysis", "evidence-loopbounds-summary.txt")
        with open(p, encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("every bound respected: yes", txt)
        for pc in (0xACDF, 0xAFF3, 0xB018, 0xB53D, 0xB8E8, 0xB9F2):
            self.assertIn("$%04X" % pc, txt)
            self.assertIn(pc, W.ANNOT)
        self.assertNotIn(0xAB7B, W.ANNOT)                                      # followed by the search, not claimed

    def test_rare_session(self):
        p = os.path.join(ROOT, "analysis", "evidence-mainloop-rare-summary.txt")
        with open(p, encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("gaps 0; handler still running when the next entry came: 0", txt)
        flat = " ".join(txt.split())
        for t in ("paused -> start tune", "start tune -> paused", "start tune -> start idle", "play -> title menu", "play -> start idle"):
            self.assertIn(t, flat)


class Budget(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(ROOT, "analysis", name), encoding="utf-8") as fh:
            return fh.read()

    def test_measured_budget(self):
        txt = self.read("evidence-budget-summary.txt")
        self.assertIn("game | 23323 | 644: 23323 | 16100", txt)
        self.assertIn("19750", txt)

    def test_table_against_the_budget(self):
        tab = self.read("evidence-wcet-summary.txt")
        for k in (" 17581 ", "with at most 2 entities in a tunnel zone: 16003", "= max of 6096 / 3197 / 3165 / 10322 / 14846", "stage 3 leaves LevelEndStep 4 at the start positions): passed", " 14226 ", " 32049 ", " 3114 "):
            self.assertIn(k, tab)
        # every class that is claimed to fit is below the budget of its screen; the play-type ones are not
        got = {}
        for ln in tab.splitlines()[2:]:
            name, rest = ln[:20].strip(), ln[20:].split()
            got[name] = int(rest[0])
        for name in ("paused", "board start", "start idle", "game-over countdown", "death", "eaten pause", "turn control"):
            self.assertLess(got[name], 16100)
        for name in ("title menu", "title after game", "copyright setup", "copyright wait"):
            self.assertLess(got[name], 19750)
        for name in ("play", "start tune", "ready wait"):
            self.assertGreater(got[name], 16100)

    def test_tunnel_fact_tested(self):
        txt = self.read("evidence-clip-summary.txt")
        self.assertIn("most heavy calls in any frame: 2", txt)


class Concrete(unittest.TestCase):
    """the static bounds against the real handler on the concrete 6502 (tools/check_bounds_concrete.py)"""
    def test_no_concrete_frame_above_its_bound(self):
        import check_bounds_concrete as CB
        rows = CB.check(n=25, seed=7)
        for cls, bound, top in rows:
            self.assertLessEqual(top, bound, cls)
        self.assertEqual(len(rows), 19)

    def test_evidence(self):
        with open(os.path.join(ROOT, "analysis", "evidence-bounds-concrete-summary.txt"), encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("frames above their bound: 0 classes", txt)
        with open(os.path.join(ROOT, "analysis", "evidence-fuzz-summary.txt"), encoding="utf-8") as fh:
            fz = fh.read()
        self.assertIn("heaviest frame: 11806", fz)
        self.assertIn("heaviest frame: 9228", fz)
        self.assertIn("heaviest of all: 14278 on arbitrary memory", fz)
        self.assertIn("11026 inside the domains", fz)


class SetSearch(unittest.TestCase):
    """the C++ search of tools/wcet_sets reproduces the Python search when the ghost bytes are not followed (skipped when there is no C++ compiler)"""
    def test_same_bounds(self):
        import shutil
        import wcet_sets as WS
        if not os.path.isfile(WS.EXE) and shutil.which("g++") is None:
            self.skipTest("no g++")
        for cls, bound in (("paused", 3114), ("death", 5923), ("level end", 17581)):
            out, err = WS.run(cls, ghosts=False)
            self.assertIn("longest %d" % bound, out)


class Chapter(unittest.TestCase):
    def test_chapter_states_the_bounds(self):
        with open(os.path.join(ROOT, "docs", "39-worst-case-time.md"), encoding="utf-8") as fh:
            txt = fh.read()
        for k in ("17,581", "16,003", "14,846", "14,226", "32,049", "16,100", "19,750", "11,806"):
            self.assertIn(k, txt)
        for pc in list(W.ANNOT) + [0xAB7B, 0xABA3]:
            self.assertIn("$%04X" % pc, txt)


if __name__ == "__main__":
    unittest.main()
