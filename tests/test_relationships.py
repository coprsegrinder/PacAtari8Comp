"""Stage 40: tests of tools/analyze_relationships.py and docs/24-function-relationships.md.  Run:  python -I tests/test_relationships.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_relationships as R  # noqa: E402

ROM, F, MISSING, EXTRA = R.build()


class Assignment(unittest.TestCase):
    def test_every_routine_has_one_subsystem(self):
        self.assertEqual(MISSING, [])
        self.assertEqual(EXTRA, [])
        for e in F:
            self.assertIn(R.ROLE[e][0], R.SUBSYSTEMS)

    def test_no_routine_is_still_called_sub(self):
        self.assertEqual([f.name for f in F.values() if f.name.startswith("Sub_")], [])
        self.assertEqual(len(R.RENAMED), 39)
        for e in R.RENAMED:
            self.assertTrue(F[e].name[0].isupper() and not F[e].name.startswith("Sub_"))


class Order(unittest.TestCase):
    def calls(self):
        out = []
        for a in sorted(F[0xA6CC].body):
            if 0xA78C <= a <= 0xAA2C:
                n, m, mode, op = ROM.ins[a]
                if m in ("jsr", "jmp") and op in F:
                    out.append((a, F[op].name))
        return out

    def test_frame_order(self):
        names = [n for a, n in self.calls()]
        order = ["DeathSequence", "EyesAndHousePerFrame", "BonusItemUpdate", "PowerPelletCheck", "FrightenedTick", "DotSoundSweep", "ToggleLegPhase", "MovePacMan", "EatDotAtPacMan", "HouseWaitingTick", "ChaseTimerSirenSight", "GhostBehaviour"]
        pos = [names.index(n) for n in order]
        self.assertEqual(pos, sorted(pos), "the per-frame order of the code changed")

    def test_pac_man_before_ghosts(self):
        d = dict((n, a) for a, n in self.calls())
        self.assertLess(d["MovePacMan"], d["GhostBehaviour"])
        self.assertLess(d["DeathSequence"], d["MovePacMan"])


class Dependencies(unittest.TestCase):
    def test_leaf_subsystems(self):
        sub = {e: R.ROLE[e][0] for e in F}
        for k in ("GHOST", "SOUND", "MAZE", "DECOMP"):
            for e, f in F.items():
                if sub[e] != k:
                    continue
                for c in list(f.calls.values()) + list(f.tail):
                    if c in F:
                        self.assertEqual(sub[c], k, "%s calls out of %s" % (f.name, k))


class Document(unittest.TestCase):
    def test_document_is_up_to_date(self):
        want = "\n".join(R.report(ROM, F)) + "\n"
        with open(os.path.join(ROOT, "docs", "24-function-relationships.md"), encoding="utf-8", newline="") as fh:
            got = fh.read().replace("\r\n", "\n")
        self.assertEqual(got, want, "run: python -I tools/analyze_relationships.py --write docs/24-function-relationships.md")


if __name__ == "__main__":
    unittest.main()
