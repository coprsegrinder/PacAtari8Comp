"""Stage 87: tools/check_behaviour.py (behavioural equivalence of the C port and the ROM): the rule graph, the routine addresses taken from the C headers, a short seeded game compared on frame classes,
state transitions and the whole state, and the comparison shown to SEE a difference in each of the three.  The full runs are in analysis/evidence-behaviour-summary.txt."""
import os
import sys
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import check_behaviour as B  # noqa: E402
import check_c_vs_rom as X  # noqa: E402
import make_rom_fuzz_replays as F  # noqa: E402
import test_c_vs_rom as T  # noqa: E402

WORK = os.path.join(ROOT, "build", "t87-test")


class Graph(unittest.TestCase):
    def test_the_rule_graph(self):
        E = B.edges()
        self.assertTrue(B.reachable(E["GameState"], 0, 1))
        self.assertTrue(B.reachable(E["GameState"], 1, 3))          # 1 -> 2 -> 3
        self.assertTrue(B.reachable(E["TwoPlayers"], 0, 1))
        self.assertFalse(B.reachable(E["TwoPlayers"], 0, 5))
        self.assertFalse(B.reachable(E["Paused"], 0, 7))

    def test_the_routines_of_the_c_headers(self):
        named = B.c_functions()
        self.assertGreater(len(named), 60)
        self.assertEqual(named["ghost_eaten"], 0xA886)
        ed, _ = B.entries_of_interest()
        self.assertGreater(len(ed), 15)


class Headers(unittest.TestCase):
    def test_every_routine_address_in_the_c_headers_is_the_label_of_the_assembly(self):
        """a comment `Name $ADDR` after a declaration names a routine of the ROM: the address must be the one of `Name:` in src/asm/pacman.s (six comments were 1-4 bytes off before stage 87)"""
        asm = B.asm_labels()
        checked = 0
        for cname, rname, addr in B.c_routines():
            if rname in asm:
                checked += 1
                self.assertEqual(addr, asm[rname], "%s: %s" % (cname, rname))
        self.assertGreater(checked, 40)


class Bot(unittest.TestCase):
    def test_the_player_that_plays_on_purpose_makes_a_valid_replay_and_is_deterministic(self):
        """tools/make_rom_bot_replay.py (OV-70): the replay is valid, carries RANDOM, and the same seed gives the same inputs; 900 frames reach the start of play and the first decisions"""
        import make_replay as MR
        import make_rom_bot_replay as BOT
        os.makedirs(WORK, exist_ok=True)
        a, b = os.path.join(WORK, "bot_a.pmrp"), os.path.join(WORK, "bot_b.pmrp")
        for out in (a, b):
            BOT.run(out, 5, 900, 1, False)
        ra, rb = MR.read_replay(open(a, "rb").read()), MR.read_replay(open(b, "rb").read())
        self.assertEqual(len(ra["frames"]), 900)
        self.assertTrue(ra["flags"] & MR.FLAG_RANDOM)
        self.assertEqual(ra, rb)
        self.assertTrue(any(f["stick0"] != 0x0F for f in ra["frames"][340:]), "the player moved the stick once play had begun")


class Run(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exes = [e for e in (T.exe("gcc"),) if e and os.path.exists(e)]
        if not cls.exes or not os.path.exists(os.path.join(ROOT, "original", "Pac-Man.rom")) or not os.path.exists(os.path.join(ROOT, "resources", "pack", "assets.pmab")):
            raise unittest.SkipTest("no C build, ROM or asset blob")
        os.makedirs(WORK, exist_ok=True)
        cls.replay = os.path.join(WORK, "fuzz1.pmrp")
        F.make(cls.replay, 1, 1600)
        cls.ed, _ = B.entries_of_interest()
        cls.E = B.edges()

    def go(self):
        return B.run_one(self.replay, self.exes[0], self.ed, B.Counting(self.ed.keys()), Counter(), self.E)

    def test_a_game_behaves_like_the_rom(self):
        r = self.go()
        self.assertEqual((r["class diffs"], r["transition diffs"], r["no rule"], r["state diffs"]), ([], [], [], []))
        self.assertGreater(r["transitions"], 10)

    def test_the_comparison_sees_a_difference(self):
        orig = X.read_states
        try:
            def zp(path, n):                                  # GameState ($19) wrong in the C dump at frame 900
                s = orig(path, n)
                st, log, rr = s[900]
                s[900] = (st[:0x19] + bytes([st[0x19] ^ 1]) + st[0x1A:], log, rr)
                return s
            B.X.read_states = zp
            r = self.go()
            self.assertTrue(r["transition diffs"] and r["state diffs"])
            self.assertEqual(r["transition diffs"][0][:2], (900, "GameState"))
            self.assertTrue(r["class diffs"], "the C's own class one frame later")
        finally:
            B.X.read_states = orig


if __name__ == "__main__":
    unittest.main()
