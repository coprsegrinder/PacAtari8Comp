"""Stage 89: the edge-case replays (tools/make_rom_edge_replays.py) and the regression runner (tools/run_regression.py): the replays are valid, deterministic and really contain the edge inputs they are named for;
the golden file, when it is there, is well formed and names the games of the runner."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_replay as MR  # noqa: E402
import make_rom_edge_replays as ED  # noqa: E402
import run_regression as RR  # noqa: E402

WORK = os.path.join(ROOT, "build", "t89-test")


def load(path):
    with open(path, "rb") as fh:
        return MR.read_replay(fh.read())


class Edge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(WORK, exist_ok=True)
        cls.r = {}
        for p in ED.PROFILES:
            path = os.path.join(WORK, p + ".pmrp")
            ED.make(path, p, 1, 1200)
            cls.r[p] = load(path)

    def test_every_profile_is_a_valid_replay_with_random_bytes(self):
        for p, rp in self.r.items():
            self.assertEqual(len(rp["frames"]), 1200, p)
            self.assertTrue(rp["flags"] & MR.FLAG_RANDOM, p)
            self.assertTrue(all(len(f["random"]) == 64 for f in rp["frames"]), p)

    def test_every_profile_can_be_made_for_many_seeds(self):
        """the generator once stopped with a KeyError on `mixed` seed 4 (shared state between profiles): 12 seeds of every profile are made"""
        path = os.path.join(WORK, "seeds.pmrp")
        for p in ED.PROFILES:
            for seed in range(1, 13):
                ED.make(path, p, seed, 700)

    def test_the_replays_are_deterministic(self):
        again = os.path.join(WORK, "again.pmrp")
        for p in ("sticks", "mixed"):
            ED.make(again, p, 1, 1200)
            self.assertEqual(open(again, "rb").read(), open(os.path.join(WORK, p + ".pmrp"), "rb").read(), p)

    def test_each_profile_has_its_edge_input(self):
        fr = lambda p: self.r[p]["frames"]
        self.assertEqual({f["stick0"] for f in fr("sticks")}, set(range(16)), "all 16 stick values")
        self.assertGreaterEqual(len({f["console"] for f in fr("console")}), 6)
        self.assertTrue(any(f["key"] == 0x21 for f in fr("pause")) and any(f["keydelay"] for f in fr("pause")))
        self.assertIn(self.r["clock"]["start_clock"], (250, 255, 128))
        self.assertEqual({b for f in fr("rnd0") for b in f["random"]}, {0})
        self.assertEqual({b for f in fr("rnd1") for b in f["random"]}, {255})
        self.assertEqual({b for f in fr("rndalt") for b in f["random"]}, {0, 255})
        self.assertGreaterEqual(sum(1 for f in fr("hold") if f["console"] == 6), 600)
        self.assertGreaterEqual(len({(f["drkmsk"], f["colrsh"]) for f in fr("idle")}), 2)
        self.assertTrue(all(f["stick0"] == 0x0F and f["console"] == 7 for f in fr("idle")))

    def test_the_clock_wraps_in_the_clock_profile(self):
        clocks = [f["clock"] for f in self.r["clock"]["frames"]]
        self.assertTrue(any(b < a for a, b in zip(clocks, clocks[1:])), "RTCLOK2 wraps from 255 to 0")


class Generators(unittest.TestCase):
    def test_the_c_generators_run_and_change_nothing(self):
        """stage 90 (discrepancy 3 of docs/56): every tools/make_c_*.py runs (one of them stopped with an AssertionError for a stage because its sanity check had not followed a change of the asset list) and writes the
        same bytes into src/c as are there"""
        import hashlib
        import subprocess

        def tree():
            h = hashlib.sha256()
            for dp, _, fs in sorted(os.walk(os.path.join(ROOT, "src", "c"))):
                for f in sorted(fs):
                    with open(os.path.join(dp, f), "rb") as fh:
                        h.update(f.encode() + fh.read())
            return h.hexdigest()
        before = tree()
        for g in ("make_c_assets", "make_c_constants", "make_c_palette", "make_c_rom_layout", "make_c_tables", "make_c_world"):
            r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", g + ".py")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, g + ": " + r.stderr[-300:])
        self.assertEqual(tree(), before, "a generator wrote something different into src/c")


class Golden(unittest.TestCase):
    def test_the_golden_file_is_well_formed(self):
        if not os.path.exists(RR.GOLDEN):
            self.skipTest("no golden file yet (python -I tools/run_regression.py --update-golden)")
        g = RR.read_golden()
        self.assertGreaterEqual(len(g), 30)
        for name, v in g.items():
            self.assertEqual(len(v), 5, name)
            self.assertTrue(v[0].isdigit() and all(len(x) == 16 and int(x, 16) >= 0 for x in v[1:]), name)
        for prof in ED.PROFILES:
            self.assertIn("edge-%s-1" % prof, g)


if __name__ == "__main__":
    unittest.main()
