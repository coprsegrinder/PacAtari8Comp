"""OV-30: tests of tools/analyze_timer_budgets.py (the budget analysis of the transitions log).  Run:  python -I tests/test_timer_budgets.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_timer_budgets as A  # noqa: E402


def row(f, site, g=1, old=0x20, chase=0, gt=0):
    return dict(f=f, site=site, g=g, old=old, dots=0, chase=chase, gt=gt, fright=0)


class Budgets(unittest.TestCase):
    def test_patrol_budget_in_window(self):
        rows = [row(100, "B853", old=0x01), row(100 + 1200, "B8C7", old=0x10)]
        res = A.analyse(rows)
        self.assertEqual(res["budgets"]["patrol"], [(1, 1200)])

    def test_decrement_pairs(self):
        rows = [row(100, "B8C7", chase=100), row(260, "B8C7", chase=80), row(420, "B8C7", chase=60)]
        cls, fg, un = A.classify_pairs(rows)
        self.assertEqual(cls["ok: 1 step per 8 frames"], 2)
        self.assertFalse(un)

    def test_eaten_freeze_and_unexplained(self):
        rows = [row(100, "A888", chase=100), row(260, "B8C7", chase=84)]      # 160 frames, 16 steps: 32 frames missing
        cls, fg, un = A.classify_pairs(rows)
        self.assertEqual(fg, [32])
        rows = [row(100, "B8C7", chase=100), row(260, "B8C7", chase=84)]      # the same without an eating: unexplained
        cls, fg, un = A.classify_pairs(rows)
        self.assertEqual(len(un), 1)

    def test_real_log(self):
        path = os.path.join(ROOT, "analysis", "raw-logs", "transitions.txt")
        if not os.path.exists(path):
            self.skipTest("raw log not present (gitignored)")
        rows = A.parse(path)
        res = A.analyse(rows)
        L, problems = A.report(rows, res)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
