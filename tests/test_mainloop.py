"""Stage 62 (main loop): the frame classifier and the parser on synthetic frames, and the committed evidence and chapter."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_mainloop as M  # noqa: E402

BASE = dict(f=100, vp=256, gs=0, v1c=0, v20=0, v21=1, v22=1, v23=0, v24=0, v26=0, v27=0, e5=0, ed=0, p9b=0, a3=0, cnt=0)


def rec(**kw):
    r = dict(BASE)
    r.update(kw)
    return r


class Classifier(unittest.TestCase):
    def test_title_states(self):
        self.assertEqual(M.classify(rec(gs=1)), "copyright setup")
        self.assertEqual(M.classify(rec(gs=2)), "copyright wait")
        self.assertEqual(M.classify(rec(gs=3)), "title menu")
        self.assertEqual(M.classify(rec(gs=4)), "title after game")

    def test_order_of_the_dispatcher(self):
        self.assertEqual(M.classify(rec()), "play")
        self.assertEqual(M.classify(rec(p9b=1, ed=1, e5=1, v26=1)), "paused")           # the pause is tested first
        self.assertEqual(M.classify(rec(v1c=2, v26=1)), "board start")
        self.assertEqual(M.classify(rec(v20=1, v26=1)), "game-over countdown")
        self.assertEqual(M.classify(rec(v26=1, ed=1)), "level end")
        self.assertEqual(M.classify(rec(v21=0, v22=0)), "start idle")
        self.assertEqual(M.classify(rec(v21=0, v22=1)), "start tune")
        self.assertEqual(M.classify(rec(v24=1, ed=1)), "turn control")
        self.assertEqual(M.classify(rec(v24=2)), "ready wait")
        self.assertEqual(M.classify(rec(ed=3, e5=1)), "death")                          # a death is tested before the eaten-ghost pause
        self.assertEqual(M.classify(rec(e5=1)), "eaten pause")

    def test_every_class_is_reachable(self):
        got = {M.classify(rec(**kw)) for kw in ({"gs": 1}, {"gs": 2}, {"gs": 3}, {"gs": 4}, {"p9b": 1}, {"v1c": 2}, {"v20": 1}, {"v26": 1}, {"v21": 0, "v22": 0}, {"v21": 0, "v22": 1}, {"v24": 1}, {"v24": 2}, {"ed": 1}, {"e5": 1}, {})}
        self.assertEqual(got, {n for n, _ in M.CLASSES})


class Parser(unittest.TestCase):
    def test_scan_lines_across_the_frame_border(self):
        txt = ("VB f=100 vp=256 gs=0 v1c=0 v20=0 v21=1 v22=1 v23=0 v24=0 v26=0 v27=0 e5=0 ed=0 p9b=0 a3=0 cnt=0\n" "VF f=101 vp=10 \n" "VF f=101 vp=10\n" "VX f=101 vp=12\n")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.txt")
            with open(p, "w") as fh:
                fh.write(txt)
            fr = M.parse(p)
        self.assertEqual(len(fr), 1)
        self.assertEqual(fr[0]["vf"], 262 + 10 - 256)
        self.assertEqual(fr[0]["vx"], 262 + 12 - 256)
        self.assertEqual(fr[0]["class"], "play")

    def test_cycles_and_margin(self):
        base = "gs=0 v1c=0 v20=0 v21=1 v22=1 v23=0 v24=0 v26=0 v27=0 e5=0 ed=0 p9b=0 a3=0 cnt=0"
        txt = ("VB f=100 vp=256 %s hp=20\n" "VX f=101 vp=12 hp=30\n" "VB f=101 vp=256 %s hp=20\n" "VX f=101 vp=300 hp=0\n") % (base, base)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.txt")
            with open(p, "w") as fh:
                fh.write(txt)
            fr = M.parse(p)
        self.assertEqual(fr[0]["vxc"], (262 + 12 - 256) * 114 + 30 - 20)         # entry to exit in cycles
        self.assertEqual(fr[0]["hp"], 20)
        old = "VB f=1 vp=256 %s\nVX f=1 vp=260\n" % base                         # logs without hp still parse
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "o.txt")
            with open(p, "w") as fh:
                fh.write(old)
            fr = M.parse(p)
        self.assertIsNone(fr[0]["vxc"])
        self.assertEqual(fr[0]["vx"], 4)


class Evidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(M.SUMMARY, encoding="utf-8") as fh:
            cls.txt = fh.read()

    def test_no_missed_frame_and_no_overrun(self):
        self.assertIn("gaps 0; handler still running when the next entry came: 0", self.txt)

    def test_every_class_seen(self):
        for name, _ in M.CLASSES:
            line = [ln for ln in self.txt.splitlines() if ln.startswith(name + " ") and "|" in ln]
            self.assertTrue(line, name)

    def test_chapter(self):
        with open(os.path.join(ROOT, "docs", "38-main-loop.md"), encoding="utf-8") as fh:
            doc = fh.read()
        for s in ("## 1. The result", "## 2. The programs", "## 3. The key loop", "## 4. The frame", "## 5. The frame state machine", "## 6. The frame by frame story", "## 7. The time budget", "## 8. Limits"):
            self.assertIn(s, doc)


if __name__ == "__main__":
    unittest.main()
