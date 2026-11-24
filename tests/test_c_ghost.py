"""Stage 76b (docs/51): the ghost state machine and the ghost house in C (src/c/core/ghost.c, house.c, draw.c) against the vector sets of tools/core_ghost.py.
The sets of check_ghost (quick run, build/t76b/) are run by the C runner built with clang and gcc: every call equal, the whole World (zero page, maze, status rows, shadows, player-missile pages,
positions, picture buffers), the chip writes and the number of RANDOM values.  A copy of a set with one byte of the after-state changed (in the zero page, a page, a position, a shadow) or with a RANDOM
value withheld is caught.  Every public function of core_ghost.py that takes the World has its C twin in ghost.h and its entry in the runner's table."""
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
import core_ghost as G  # noqa: E402
import make_vectors as MV  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t76b")


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


def run(folder, rel):
    return subprocess.run([runner(folder), rel], cwd=ROOT, capture_output=True, text=True)


def region_offset(name):
    k = 0x100
    for e in V.EXTRA_ORDER:
        if e == name:
            return k
        k += V.EXTRA_SIZE[e]
    raise KeyError(name)


class GhostInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_ghost"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.sets = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith("core_ghost.") and f.endswith(".vec"))
        cls.folders = [(cc, f) for cc, f in ((cc, build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_eleven_sets(self):
        self.assertEqual(len(self.sets), 11)

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
            self.assertGreater(total, 10000, cc)

    def tampered(self, setname, change, which=3):
        """a copy of a set in which call `which` is changed by change(rec) -> rec; returns the runner's result"""
        _, nm, _, recs = V.read_set(os.path.join(ROOT, OUT, setname + ".vec"))
        path = os.path.join(OUT, "tampered.vec")
        w = V.SetWriter(os.path.join(ROOT, path), V.KIND_WORLD, nm, V.pack_state(MV.base_world()))
        for k, rec in enumerate(recs):
            if k == which:
                rec = change(dict(rec))
            w.world(rec["args"], rec["rnd"], rec["ret"], rec["before"], rec["after"], rec["pokey"])
        w.close()
        r = run(self.folders[0][1], path)
        os.remove(os.path.join(ROOT, path))
        return r

    @staticmethod
    def flip(rec, offset):
        a = bytearray(rec["after"])
        a[offset] ^= 0x10
        rec["after"] = bytes(a)
        return rec

    def test_a_changed_state_byte_is_caught(self):
        zp = lambda r: self.flip(r, 0xCE)                                    # GhostState[0]
        pm = lambda r: self.flip(r, region_offset("pm") + 0x3A0)             # a page byte
        hp = lambda r: self.flip(r, region_offset("hpos") + 1)               # a position
        sh = lambda r: self.flip(r, region_offset("shadow") + 0xC1)          # a colour shadow
        pb = lambda r: self.flip(r, region_offset("picbuf") + 0x1C)          # the feet row
        for setname, change, region in (("core_ghost.ghost_behaviour", zp, "0xce"), ("core_ghost.step_entity", pm, "pm"), ("core_ghost.step_entity", hp, "hpos"),
                                        ("core_ghost.house_enter_step", sh, "shadow"), ("core_ghost.step_entity", pb, "picbuf")):
            r = self.tampered(setname, change)
            self.assertEqual(r.returncode, 1, setname + " " + region + ": " + r.stdout)
            self.assertIn("1 different", r.stdout, setname + " " + region)

    def test_a_withheld_random_value_is_caught(self):
        _, _, _, recs = V.read_set(os.path.join(ROOT, OUT, "core_ghost.ghost_behaviour.vec"))
        k = next(i for i, r in enumerate(recs) if r["rnd"])

        def drop(rec):
            rec["rnd"] = rec["rnd"][:-1]
            return rec
        r = self.tampered("core_ghost.ghost_behaviour", drop, which=k)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RANDOM", r.stdout)

    def test_every_function_has_its_twin(self):
        with open(os.path.join(ROOT, "src", "c", "core", "ghost.h"), encoding="utf-8") as fh:
            header = fh.read()
        with open(os.path.join(ROOT, "src", "c", "core", "draw.h"), encoding="utf-8") as fh:
            draw_header = fh.read()
        with open(os.path.join(ROOT, "src", "c", "core", "draw.h"), encoding="utf-8") as fh:
            draw_header = fh.read()
        with open(os.path.join(ROOT, "src", "c", "tests", "world_functions.c"), encoding="utf-8") as fh:
            glue = fh.read()
        for name, fn in inspect.getmembers(G, inspect.isfunction):
            if fn.__module__ != "core_ghost" or name.startswith("_"):
                continue
            c_name = {"rom_word": "draw_rom_word", "sees": "ghost_sees"}.get(name, name)      # the helpers have a prefix in C
            self.assertRegex(header + draw_header, r"\b%s\(" % c_name, name + " is not in ghost.h / draw.h")
        for f in self.sets:
            self.assertIn('"%s"' % f[:-4], glue, f + " has no entry in the runner's table")


if __name__ == "__main__":
    unittest.main()
