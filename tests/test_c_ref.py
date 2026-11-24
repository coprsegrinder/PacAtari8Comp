"""Stage 76a (docs/51): the pure functions in C (src/c/core/ref.[ch]) against the vector sets of tools/core_ref.py.
The sets of check_core are written (quick run, build/t76a/), every set is run by the C runner built with clang and gcc (all calls equal), a tampered set is shown to be caught
(one result changed in a copy), and every public function of core_ref.py has its twin in ref.h and its entry in the runner's table."""
import inspect
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import c_blob  # noqa: E402
import core_ref as R  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t76a")


def build(cc):
    if not (shutil.which(cc) and shutil.which("cmake") and shutil.which("ninja")):
        return None
    out = os.path.join(ROOT, "build", "c-" + cc)
    subprocess.run(["cmake", "-S", os.path.join(ROOT, "src", "c"), "-B", out, "-G", "Ninja", "-DCMAKE_C_COMPILER=" + cc], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", out], check=True, capture_output=True)
    c_blob.ensure(out)
    return out


def runner(folder):
    return os.path.join(folder, "tests", "vector_runner" + (".exe" if os.name == "nt" else ""))


def run(folder, rel, *extra):
    return subprocess.run([runner(folder), *extra, rel], cwd=ROOT, capture_output=True, text=True)


class RefInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_core"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.sets = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith("core_ref.") and f.endswith(".vec"))
        cls.folders = [(cc, f) for cc, f in ((cc, build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_sixteen_sets(self):
        self.assertEqual(len(self.sets), 16)

    def test_every_set_equal_in_c(self):
        for cc, folder in self.folders:
            total = 0
            for f in self.sets:
                r = run(folder, os.path.join(OUT, f))
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, f, r.stdout))
                m = re.search(r": (\d+) calls of '[^']+': (\d+) equal, 0 different", r.stdout)
                self.assertTrue(m, r.stdout)
                self.assertEqual(m.group(1), m.group(2))
                total += int(m.group(1))
            self.assertGreater(total, 50000, cc)

    def test_a_tampered_set_is_caught(self):
        cc, folder = self.folders[0]
        for name, tamper in (("core_ref.steer", lambda res: 1 if res != 1 else 2),
                             ("core_ref.junction_exits", lambda res: [res[0] ^ 1, res[1]]),
                             ("core_ref.power_pellet_ghosts", lambda res: [res[0], [res[1][0] ^ 4] + res[1][1:]]),
                             ("core_ref.fright_total_frames", lambda res: 7 if res is None else None),
                             ("core_ref.move_delay_tick", lambda res: [res[0], res[1], res[2] + 1])):
            kind, nm, count, recs = V.read_set(os.path.join(ROOT, OUT, name + ".vec"))
            path = os.path.join(OUT, "tampered.vec")
            w = V.SetWriter(os.path.join(ROOT, path), V.KIND_PURE, nm)
            for k, rec in enumerate(recs):
                w.pure(rec["args"], tamper(rec["result"]) if k == 3 else rec["result"])
            w.close()
            r = run(folder, path)
            self.assertEqual(r.returncode, 1, name + ": " + r.stdout)
            self.assertIn("1 different", r.stdout, name)
            os.remove(os.path.join(ROOT, path))

    def test_a_missing_random_value_is_caught(self):
        """steer called with a set that supplies fewer RANDOM values than the function takes"""
        cc, folder = self.folders[0]
        kind, nm, count, recs = V.read_set(os.path.join(ROOT, OUT, "core_ref.steer.vec"))
        used = [k for k, r in enumerate(recs) if r["args"][6]]
        self.assertTrue(used)
        path = os.path.join(OUT, "tampered.vec")
        w = V.SetWriter(os.path.join(ROOT, path), V.KIND_PURE, nm)
        for k, rec in enumerate(recs):
            args = list(rec["args"])
            if k == used[0]:
                args[6] = []
            w.pure(args, rec["result"])
        w.close()
        r = run(folder, path)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RANDOM", r.stdout)
        os.remove(os.path.join(ROOT, path))

    def test_branches_the_checkers_never_reach(self):
        """gcov over the recorded sets shows four branches of ref.c that no recorded call runs (the end phase 0 of fright_total_frames, the plain exit of a ghost on the door row, an eaten ghost and a ghost whose
        state has no bit in $3B0 in power_pellet_ghosts).  They are run here, exhaustively over their inputs, C against the Python reference (not against the ROM: the ROM checkers did not reach them)"""
        import random
        rng = random.Random(76)
        cases = {
            "core_ref.fright_total_frames": [[lv] for lv in range(256)],
            "core_ref.fright_frames": [[lv] for lv in range(256)],
            "core_ref.junction_exits": [[p, x, y, d, st] for p in (0, 1) for y in (0x64, 0x2C, 0x74, 0x00, 0xFF) for x in (0x76, 0x82, 0x7C, 0x3A, 0x00, 0xFF) for d in range(9) for st in range(256)],
            "core_ref.power_pellet_ghosts": [[[s] * 4, [d] * 4] for s in range(256) for d in range(9)] + [[[rng.randrange(256) for _ in range(4)], [rng.randrange(9) for _ in range(4)]] for _ in range(5000)],
            "core_ref.frightened_end": [[[s] * 4] for s in range(256)] + [[[rng.randrange(256) for _ in range(4)]] for _ in range(5000)],
            "core_ref.force_chase": [[[rng.choice((0, 1, 2, 8, 0x10, 0x20, 0x42, 0x80, rng.randrange(256))) for _ in range(4)], x] for x in range(4) for _ in range(500)],
            "core_ref.ghost_points": [[n] for n in range(256)],
            "core_ref.score_add": [[rng.randrange(1000000), rng.choice((10, 50, 200, 400, 800, 1600, 5000, rng.randrange(100000))), rng.randrange(2), rng.randrange(256)] for _ in range(5000)],
        }
        for cc, folder in self.folders:
            for name, calls in cases.items():
                fn = getattr(R, name.split(".")[1])
                path = os.path.join(OUT, "extra.vec")
                w = V.SetWriter(os.path.join(ROOT, path), V.KIND_PURE, name)
                for args in calls:
                    res = fn(*[list(a) if isinstance(a, list) else a for a in args])
                    w.pure(args, list(res) if isinstance(res, tuple) else res)
                w.close()
                r = run(folder, path)
                os.remove(os.path.join(ROOT, path))
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, name, r.stdout))
                self.assertIn("%d equal, 0 different" % len(calls), r.stdout)

    def test_every_function_has_its_twin(self):
        with open(os.path.join(ROOT, "src", "c", "core", "ref.h"), encoding="utf-8") as fh:
            header = fh.read()
        with open(os.path.join(ROOT, "src", "c", "tests", "pure_functions.c"), encoding="utf-8") as fh:
            glue = fh.read()
        for name, fn in inspect.getmembers(R, inspect.isfunction):
            if fn.__module__ == "core_ref" and not name.startswith("_"):
                self.assertRegex(header, r"\bref_%s\(" % name, name + " is not in ref.h")
        recorded = {f[:-4] for f in self.sets}
        for name in recorded:
            self.assertIn('"%s"' % name, glue, name + " has no entry in the runner's table")


if __name__ == "__main__":
    unittest.main()
