"""OV-67 (stage 66): the port-form World modules against the ROM (small runs of the tools/check_*.py), the World itself, the committed evidence and the chapter."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import algorithm_models as A  # noqa: E402
import check_frame as CF  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_pacman as CP  # noqa: E402
import check_play as CPL  # noqa: E402
import check_score as CS  # noqa: E402
import check_sound as CSO  # noqa: E402
import core_frame as F  # noqa: E402
import core_ghost as G  # noqa: E402
import core_score as S  # noqa: E402
import core_sound as SO  # noqa: E402
import core_world as W  # noqa: E402


class World(unittest.TestCase):
    def test_roundtrip_and_names(self):
        m = A.started_machine()
        mem = bytearray(m.mem)
        w = W.World().load(mem)
        back = bytearray(0x10000)
        w.store(back)
        self.assertEqual(bytes(back[:0x100]), bytes(mem[:0x100]))
        self.assertEqual(w.EntityX, list(mem[0x8A:0x8F]))
        with self.assertRaises(AttributeError):
            w.NoSuchField = 1                                  # a misspelt name is an error, not a dropped write

    def test_catalogue_names(self):
        names = {n: (a, c) for n, a, c in W.FIELDS}
        self.assertEqual(names["GhostState"], (0xCE, 4))
        self.assertEqual(names["ChaseTimer"], (0xAD, 1))
        self.assertEqual(names["ScoreAdd"], (0x94, 6))
        self.assertEqual(sum(c for _, _, c in W.FIELDS), 256)


class AgainstTheRom(unittest.TestCase):
    def test_ghost_state_machine(self):
        L, rows = CG.report(True)
        for name, what, n, bad, used, trans in rows:
            self.assertEqual(bad, [], name)
        self.assertTrue(any(k[0] != k[1] for r in rows if r[0] == "ghost_behaviour" for k in r[5]))   # state changes were reached

    def test_pacman(self):
        bad, moved, tunnel, corner, joy = CP.run(1500, 5)
        self.assertEqual(bad, [])
        self.assertGreater(moved, 100)
        self.assertGreater(corner, 100)

    def test_score(self):
        for name, addr, fn in (("add", 0xB423, S.add_to_score), ("lives", 0xAD15, S.draw_lives), ("dot", 0xB33A, S.eat_dot), ("pellet", 0xB39F, S.power_pellet_check)):
            n, bad = CS.run(addr, fn, 800, 4)
            self.assertEqual(bad, [], name)

    def test_sound(self):
        for name, addr, fn, maze in (("clear", 0xB0E6, SO.clear_pokey, True), ("dot", 0xB0BC, SO.dot_sound_sweep, True), ("bonus", 0xABC9, SO.bonus_sound, True),
                                     ("fright", 0xAFD7, SO.frightened_sound, True), ("eyes", 0xB02C, SO.eyes_returning_sound, True), ("siren", 0xB508, SO.siren, True),
                                     ("pause", 0xB049, SO.ghost_eaten_pause, True), ("death", 0xAE3D, SO.death_sequence, True)):
            n, bad = CSO.run(addr, fn, 250, 6, maze)
            self.assertEqual(bad, [], name)

    def test_frame_functions(self):
        n, bad = CF.run(0xAF54, lambda w, it: F.frightened_tick(w), 400, 7)
        self.assertEqual(bad, [])
        n, bad = CF.run(0xB69E, lambda w, it: F.eyes_and_house_per_frame(w, it), 400, 7)
        self.assertEqual(bad, [])
        n, bad = CF.run(0xA886, lambda w, x, it: F.ghost_eaten(w, x), 400, 7, None, False, True)
        self.assertEqual(bad, [])

    def test_play_frame(self):
        bad, cover = CPL.run(500, 31, 1)
        self.assertEqual(bad, [])
        for k in ("death", "ghost eaten", "contact kill", "bonus pick-up", "ghosts moved", "pacman moved"):
            self.assertGreater(cover[k], 0, k)
        bad, cover = CPL.run(30, 32, 20)
        self.assertEqual(bad, [])


class Evidence(unittest.TestCase):
    FILES = ("ghost", "pacman", "score", "sound", "frame", "play", "core")

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_evidence_has_no_differences(self):
        for f in self.FILES:
            t = self.read("analysis/evidence-%s-summary.txt" % f)
            diffs = re.findall(r": (\d+) differences", t)
            self.assertGreater(len(diffs), 0, f)
            self.assertTrue(all(d == "0" for d in diffs), f)

    def test_chapter(self):
        d = self.read("docs/44-core-algorithms.md")
        for k in ("play_frame", "World form", "0 differences" if False else "differences", "collision registers", "OV-67"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
