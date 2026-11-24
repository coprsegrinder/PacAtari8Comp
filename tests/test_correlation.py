"""Stage 60: the behaviour correlation (tools/analyze_correlation.py) - no problem found, the chapter is current, and the check notices what it should."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_correlation as C  # noqa: E402


class Correlation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.L, cls.D = C.doc_lines()

    def test_no_problem(self):
        self.assertEqual(self.D["problems"], [])

    def test_every_routine_has_a_behaviour(self):
        self.assertEqual(len(self.D["nroutine"]), 81)
        self.assertTrue(all(self.D["rb"][r] for r in self.D["nroutine"]))

    def test_every_algorithm_is_carried(self):
        self.assertEqual(len(self.D["algs"]), 22)
        self.assertTrue(all(a in self.D["alg_beh"] for a in self.D["algs"]))

    def test_only_the_paths_and_machines_items_are_open(self):
        self.assertEqual(self.D["open"], ["OV-71", "OV-72", "OV-75", "OV-76"])

    def test_instruction_totals(self):
        self.assertEqual(self.D["ntotal"], 2925)
        self.assertEqual(self.D["head"], ("2920", "2925"))

    def test_chapter_is_current(self):
        with open(os.path.join(ROOT, "docs", "36-behaviour-correlation.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "\n".join(self.L) + "\n", "run: python -I tools/analyze_correlation.py --doc docs/36-behaviour-correlation.md")

    def test_a_missing_test_file_is_noticed(self):
        old = C.BEHAVIOURS[0]
        try:
            C.BEHAVIOURS[0] = old[:6] + (["test_does_not_exist"],)
            self.assertTrue(any("test_does_not_exist" in p for p in C.build()["problems"]))
        finally:
            C.BEHAVIOURS[0] = old

    def test_an_unknown_register_entry_is_noticed(self):
        old = C.BEHAVIOURS[1]
        try:
            C.BEHAVIOURS[1] = old[:4] + (["C-999"],) + old[5:]
            self.assertTrue(any("C-999" in p for p in C.build()["problems"]))
        finally:
            C.BEHAVIOURS[1] = old

    def test_a_routine_without_behaviour_is_noticed(self):
        saved = list(C.BEHAVIOURS)
        try:
            C.BEHAVIOURS[:] = [b for b in saved if "A04" not in b[2]]       # nothing carries the display-list interrupts any more
            probs = C.build()["problems"]
            self.assertTrue(any("DliHandler1" in p for p in probs))
            self.assertTrue(any("A04" in p for p in probs))
        finally:
            C.BEHAVIOURS[:] = saved


if __name__ == "__main__":
    unittest.main()
