"""Stage 65 (state management): the sensitivity experiment (tools/state_probe.py) on a few bytes with fixed seeds, the committed evidence of both experiments, and the chapter."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_state as AS  # noqa: E402
import state_probe as SP    # noqa: E402


class Probe(unittest.TestCase):
    def test_known_bytes(self):
        res = SP.trial(([0x2C, 0x2D, 0xD6, 0x94, 0x30], 30, 10, 3))
        modes = {b: {m for m, _, _ in v} for b, v in res.items()}
        self.assertIn("play1", modes[0x2C])                       # player 1's lives matter while player 1 plays
        self.assertNotIn("play1", modes[0x2D])                    # player 2's lives do not
        self.assertIn("play2", modes[0x2D])
        self.assertEqual(modes[0xD6], set())                      # WantVert: set before use, no influence
        self.assertIn("play1", modes[0x94])                       # ScoreAdd: a zero-at-rest invariant, not a temporary
        self.assertIn("play1", modes[0x30])                       # the level

    def test_names_and_structures(self):
        nm, st = AS.names(), AS.structures()
        self.assertEqual(nm[0x93], "EntityDir[4]")
        self.assertEqual(nm[0x2C], "Lives[0]")
        self.assertEqual(st[0x2D][0], "Player")
        self.assertTrue(st[0x94][1].startswith("zero between uses"))               # corrected in stage 65 (docs/30)
        self.assertTrue(st[0xD6][1].startswith("temporary"))


class Evidence(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_summary(self):
        t = self.read("analysis/evidence-state-summary.txt")
        self.assertIn("144 of the 256 zero-page bytes influence the future", t)
        self.assertIn("player 1 on turn only: $2C, $2E, $30, $32, $34, $36, $43; player 2 on turn only: $2D, $2F, $31, $33, $35, $37, $44", t)
        self.assertIn("InitBoard     player 1 on turn", t)
        self.assertIn("114 reset", t)

    def test_chapter(self):
        d = self.read("docs/43-state-management.md")
        for k in ("zero-at-rest", "InitBoard", "SavedMaze1", "144 zero-page bytes", "| Player | $2C-$37, $43-$44 | 14 |"):
            self.assertIn(k, d)

    def test_events_known_effects(self):
        # the events of tools/state_events.py on the concrete 6502, a few trials: InitBoard puts the entities on their start positions whatever they were
        import random
        import state_events as SE
        A, M6, M7, O, C = mods = SE._mods()
        base = A.started_machine()
        rng = random.Random(3)
        seen = set()
        for _ in range(12):
            m = SE.base_state(base, rng, mods)
            m.call(0xADAF)
            seen.add(tuple(m.mem[0x85:0x8F]))
        self.assertEqual(len(seen), 1)                            # one set of positions
        self.assertEqual(list(seen)[0], (100, 116, 116, 116, 164, 124, 124, 112, 136, 124))


if __name__ == "__main__":
    unittest.main()
