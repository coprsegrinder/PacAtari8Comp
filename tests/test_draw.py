"""OV-69: the drawing in port form (tools/core_draw.py) against the ROM, the scene for the collision model, a negative control, the evidence and the chapter."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_collide as AC  # noqa: E402
import check_draw as CD  # noqa: E402
import core_draw as D  # noqa: E402
import core_world as W  # noqa: E402
import platform_iface as PI  # noqa: E402


class AgainstTheRom(unittest.TestCase):
    def test_every_routine(self):
        L, res = CD.report(True)
        for bad, line in zip(res, L[2:]):
            self.assertEqual(bad, [], line[:80])
        self.assertEqual(len(res), 6)

    def test_negative_control(self):
        """a wrong carry in the missile positions (the carry of one add goes into the next) must show"""
        good = D.draw_pacman

        def bad(w, y, a):
            good(w, y, a)
            w.hpos[4] = (w.hpos[4] + 1) & 0xFF
        D.draw_pacman = bad
        try:
            n, found = CD.run("draw_pacman", lambda m, a: m.call(0xB2E9, a=a[1], y=a[0]), lambda w, a: D.draw_pacman(w, a[0], a[1]), 60, 3, None, CD.t_pac)
        finally:
            D.draw_pacman = good
        self.assertGreater(len(found), 30)

    def test_play_frame_includes_the_clip(self):
        import check_play as CPL
        bad, cover = CPL.run(300, 41, 1)
        self.assertEqual(bad, [])
        bad, cover = CPL.run(20, 42, 20)
        self.assertEqual(bad, [])


class Scene(unittest.TestCase):
    def setUp(self):
        self.charset = AC.rom_charset()

    def world(self):
        w = W.World()
        w.EntityY = [100, 60, 80, 90, 100]
        w.EntityX = [150, 90, 100, 110, 150]
        w.EntityDir = [4, 4, 4, 4, 8]
        w.GhostState = [0, 0, 0, 0]
        w.LegPhase = 0
        return w

    def test_scene_of_a_drawn_world(self):
        w = self.world()
        D.draw_all_in_place(w)
        hpos, mp, pp, pf = D.scene(w, self.charset)
        self.assertEqual(hpos[:4], [150, 90, 100, 110])                    # the ghosts' players
        self.assertEqual(hpos[4:], [156, 154, 152, 150])                   # Pac-Man's four missiles: PacX + 6, 4, 2, 0
        self.assertTrue(any(mp[100:116]))
        self.assertTrue(any(pp[0][100:116]))

    def test_registers_of_the_port_scene(self):
        plat = PI.GtiaCollisions(lambda w: D.scene(w, self.charset))
        w = self.world()
        w.pokey = []
        D.draw_all_in_place(w)                                              # ghost 0 on Pac-Man (same row, same column): the contact registers
        plat.frame_done(w)
        c = plat.collisions(w)
        self.assertTrue(c[9] & 1 and c[10] & 1)                              # M1PL and M2PL bit 0: the contact test would see ghost 0
        w2 = self.world()
        w2.EntityX[0] = 220                                                 # far away: no contact with ghost 0
        w2.pokey = [(0xD01E, 0)]
        D.draw_all_in_place(w2)
        plat.frame_done(w2)
        c = plat.collisions(w2)
        self.assertFalse(c[9] & 1 and c[10] & 1)


class Evidence(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_evidence(self):
        t = self.read("analysis/evidence-draw-summary.txt")
        diffs = re.findall(r": (\d+) differences", t)
        self.assertEqual(len(diffs), 6)
        self.assertTrue(all(d == "0" for d in diffs))
        calls = [int(c) for c in re.findall(r": (\d+) calls", t)]
        self.assertTrue(all(c >= 4000 for c in calls))

    def test_chapter(self):
        d = self.read("docs/44-core-algorithms.md")
        for k in ("core_draw", "OV-69", "player-missile pages", "vbi_play_frame", "tunnel clip"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
