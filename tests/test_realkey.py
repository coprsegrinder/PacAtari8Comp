"""OV-61: the real key press through the OS keyboard IRQ routine - the analyzer on a synthetic log and the committed evidence."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_realkey as R  # noqa: E402

GOOD = ("KBCODE_READ pc=$FFCB f=100\nCHW pc=$FFDC v=$21 f=100\nKEY_TOGGLE f=120 new=1 old=0\nCHW pc=$A4E6 v=$FF f=120\n"
        "KBCODE_READ pc=$FFCB f=300\nCHW pc=$FFDC v=$21 f=300\nKEY_TOGGLE f=310 new=0 old=1\nCHW pc=$A4E6 v=$FF f=310\n")


def run(text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "k.txt")
        with open(p, "w") as fh:
            fh.write(text)
        return R.report(p)


class Analyzer(unittest.TestCase):
    def test_good(self):
        L, ok = run(GOOD)
        self.assertTrue(ok)

    def test_toggle_without_os_key_is_noticed(self):
        L, ok = run(GOOD.replace("KBCODE_READ pc=$FFCB f=100\n", "").replace("CHW pc=$FFDC v=$21 f=100\n", ""))
        self.assertFalse(ok)

    def test_game_poke_is_not_an_os_key(self):
        L, ok = run(GOOD.replace("CHW pc=$FFDC v=$21 f=100", "CHW pc=$A900 v=$21 f=100").replace("KBCODE_READ pc=$FFCB f=100", "KBCODE_READ pc=$A900 f=100"))
        self.assertFalse(ok)


class Evidence(unittest.TestCase):
    def test_evidence(self):
        with open(os.path.join(ROOT, "analysis", "evidence-realkey-summary.txt"), encoding="utf-8") as fh:
            t = fh.read()
        self.assertIn("toggles of Paused: 2", t)
        self.assertIn("0->1", t)
        self.assertIn("1->0", t)
        self.assertIn("every press reached the game through the OS keyboard IRQ routine", t)


if __name__ == "__main__":
    unittest.main()
