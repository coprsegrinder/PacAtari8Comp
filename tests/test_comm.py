"""Stage 68: communication - nothing leaves or enters the machine, and the contexts inside it share a listed set of variables (static sets, the concrete run, a negative control, the evidence and the chapter)."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import comm_map as K  # noqa: E402
import iface_map as I  # noqa: E402


class Static(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.st = K.static_sets()
        cls.sh = K.shared(cls.st)

    def test_five_contexts(self):
        self.assertEqual([c[0] for c in K.CONTEXTS], ["key", "newgame", "vbi", "dli1", "dli2"])
        self.assertGreater(self.st["vbi"][2], 2000)
        self.assertLess(self.st["dli1"][2], 60)

    def test_display_list_handlers_write_only_their_counter_and_the_chips(self):
        for c in ("dli1", "dli2"):
            self.assertEqual({k for k in self.st[c][1] if k[0] == "zp"}, {("zp", "BandCounter")})
            self.assertEqual({k for k in self.st[c][1] if k[0] == "mem"}, {("mem", "Antic"), ("mem", "Gtia")})

    def test_display_list_handlers_read_few_variables(self):
        self.assertEqual({k[1] for k in self.st["dli2"][0]}, {"BandCounter", "DliColors"})
        self.assertEqual({k[1] for k in self.st["dli1"][0]}, {"BandCounter", "DliColors", "ItemColor", "DRKMSK", "COLRSH"})

    def test_the_key_loop_hand_over(self):
        names = {k[1] for k in self.st["key"][1] if k[0] == "zp"}
        for n in ("GameState", "Paused", "TwoPlayers", "StartLevel", "IntroRequest", "KeyDebounce", "DliColors", "ATRACT", "CountdownActive"):
            self.assertIn(n, names)
        self.assertEqual(len(self.st["key"][1]), 11)
        # the key loop touches no game variable of the frame (entities, ghosts, scores)
        for n in ("EntityX", "GhostState", "ScoreAdd", "ChaseTimer", "Level", "Lives"):
            self.assertNotIn(("zp", n), self.st["key"][1])

    def test_nothing_outside_the_machine(self):
        for c in self.st:
            for k in self.st[c][0] | self.st[c][1]:
                self.assertNotIn(k, {("mem", "Pia")}, c)

    def test_shared_counts(self):
        zp = [k for k in self.sh if k[0] == "zp"]
        self.assertGreater(len(zp), 90)
        names, mat = K.pair_matrix(self.sh)
        self.assertEqual(mat[("dli1", "dli2")], 1)       # BandCounter


class Dynamic(unittest.TestCase):
    def test_every_cell_is_in_the_static_set(self):
        bad, ran = K.dynamic(3, 70)
        self.assertEqual(bad, [])
        self.assertGreater(sum(ran.values()), 20)

    def test_the_check_can_fail(self):
        """negative control: take a variable out of the static sets and the run must report it"""
        st = K.static_sets()
        gone = ("zp", "BandCounter")
        st2 = {c: (st[c][0] - {gone}, st[c][1] - {gone}, st[c][2]) for c in st}
        bad, ran = K.dynamic(3, 71, st2)
        self.assertTrue(any(b[3] == 0x18 for b in bad))


class Evidence(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_evidence(self):
        t = self.read("analysis/evidence-comm-summary.txt")
        m = re.search(r"run: (\d+) contexts runs .*: (\d+) outside", t)
        self.assertTrue(m)
        self.assertGreaterEqual(int(m.group(1)), 900)
        self.assertEqual(m.group(2), "0")

    def test_chapter(self):
        d = self.read("docs/46-communication.md")
        for k in ("No communication with the outside", "The hand-over variables", "IntroRequest", "No race-freedom proof", "Two players are not communication", "`DliColors`"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
