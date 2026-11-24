"""Stage 77a (docs/51): the collision geometry of the GTIA in C (src/c/core/gtia.c) and its latch.
1. Synthetic scenes (made here, no logs needed): random scenes with random maze cells and character sets, the registers of the Python model (tools/gtia_collisions.py), the four latch modes: the C equals the model,
   directly and through a World (scene_of_world + the latch with HITCLR in the chip-write log); a changed expected register is caught; the model's neighbouring windows (visible clocks, scan lines) give other registers.
2. The hardware evidence (resources/vectors/gtia.*.vec, made by tools/make_collide_vectors.py from the Altirra logs; skipped when absent): the C equals the real GTIA on every random scene and every frame of play,
   and the neighbours of the model's windows (visible clocks 34-221, scan lines 8-247) still fail."""
import os
import random
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import gtia_collisions as G  # noqa: E402
import test_c_ghost as TG  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t77a")
VEC = os.path.join(ROOT, "resources", "vectors")


def run(folder, rel, *extra):
    return subprocess.run([TG.runner(folder), *extra, rel], cwd=ROOT, capture_output=True, text=True)


def synthetic(rng, n):
    """n scenes: (hpos, pages, cells, charset) with the Python model's registers; objects are placed so that they overlap one another and the maze often"""
    charset = bytes(rng.choice((0, 0, 0x55, 0xAA, 0xFF, 0xC3, rng.randrange(256))) for _ in range(1024))
    cells = [rng.randrange(256) for _ in range(920)]
    out = []
    for _ in range(n):
        base = rng.randrange(40, 200)
        hpos = [rng.choice((base + rng.randrange(-6, 7), rng.randrange(256))) for _ in range(8)]
        pages = [[0] * 256 for _ in range(5)]
        r0 = rng.randrange(8, 230)
        for pg in pages:
            top = r0 + rng.randrange(-4, 5)
            for k in range(16):
                if 0 <= top + k < 256:
                    pg[top + k] = rng.choice((0, 0xFF, 0x3C, rng.randrange(256)))
        pf = G.Playfield(cells, charset)
        regs = G.collision_registers(hpos, pages[0], pages[1:], pf)
        out.append((hpos, pages, regs))
    # edge scenes: two players that overlap in exactly one pixel at a window edge (clocks 33-35 and 220-222), and a line at the edge of the line window (7-9 and 246-248)
    edges = []
    for e in (33, 34, 35):
        edges.append(([e - 7, e, 0, 0, 0, 0, 0, 0], 100))
    for e in (220, 221, 222):
        edges.append(([e, e - 7, 0, 0, 0, 0, 0, 0], 100))
    for line in (7, 8, 9, 246, 247, 248):
        edges.append(([100, 100, 0, 0, 0, 0, 0, 0], line))
    for hpos, line in edges:
        pages = [[0] * 256 for _ in range(5)]
        pages[1][line] = 0xFF
        pages[2][line] = 0xFF
        pf = G.Playfield(cells, charset)
        out.append((hpos, pages, G.collision_registers(hpos, pages[0], pages[1:], pf)))
    return charset, cells, out


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = random.Random(77)
        cls.charset, cls.cells, cls.scenes = synthetic(rng, 3000)
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")
        os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
        # latch modes: 0 alone, 1 reset, 2 carry, 3 set from the file; the expected registers follow the same chain
        cls.path = os.path.join(OUT, "gtia.synthetic.vec")
        w = V.SceneWriter(os.path.join(ROOT, cls.path), "gtia.synthetic", cls.charset, cls.cells)
        latch = [0] * 16
        rng2 = random.Random(5)
        for k, (hpos, pages, regs) in enumerate(cls.scenes):
            mode = rng2.choice((0, 1, 2, 3)) if k < len(cls.scenes) - 12 else 0      # the 12 edge scenes stand alone: a carried latch could hide the overlap they test
            lat_in = None
            if mode in (0, 1):
                latch = [0] * 16
            elif mode == 3:
                lat_in = [rng2.choice((0, rng2.randrange(256))) for _ in range(16)]
                latch = list(lat_in)
            latch = [a | b for a, b in zip(latch, regs)]
            w.scene(mode, 0xFFFF, cls.cells, hpos, pages, latch, lat_in)
        w.close()
        cls.lines = list(range(len(cls.scenes)))

    def test_c_equals_the_model(self):
        for cc, folder in self.folders:
            for extra in ((), ("--via-world",)):
                r = run(folder, self.path, *extra)
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, extra, r.stdout))
                self.assertIn("3012 compared, 3012 equal, 0 different", r.stdout)

    def test_a_changed_register_is_caught(self):
        name, charset, cells, recs = V.read_scene_set(os.path.join(ROOT, self.path))
        path = os.path.join(OUT, "gtia.tampered.vec")
        for reg in (2, 9, 10, 0, 15):                                 # M2PF, M1PL, M2PL (the three the game reads), M0PF, P3PL
            w = V.SceneWriter(os.path.join(ROOT, path), "gtia.tampered", charset, cells)
            for k, r in enumerate(recs):
                exp = list(r["expected"])
                if k == 100:
                    exp[reg] ^= 1
                w.scene(r["mode"], r["mask"], r["cells"], r["hpos"], r["pages"], exp, r["latch_in"])
            w.close()
            res = run(self.folders[0][1], path)
            self.assertEqual(res.returncode, 1, "register %d: %s" % (reg, res.stdout))
            self.assertIn("1 different", res.stdout)
            self.assertIn("register %d" % reg, res.stdout)
        os.remove(os.path.join(ROOT, path))

    def test_the_masks_and_the_latch_are_used(self):
        """mask 0 = not compared but the latch still moves: a record with a wrong expected value and mask 0 passes, and the next record (carry) still equals the chain"""
        name, charset, cells, recs = V.read_scene_set(os.path.join(ROOT, self.path))
        path = os.path.join(OUT, "gtia.masked.vec")
        w = V.SceneWriter(os.path.join(ROOT, path), "gtia.masked", charset, cells)
        for k, r in enumerate(recs):
            exp = list(r["expected"])
            mask = r["mask"]
            if k == 50:
                exp = [0xFF] * 16
                mask = 0
            w.scene(r["mode"], mask, r["cells"], r["hpos"], r["pages"], exp, r["latch_in"])
        w.close()
        res = run(self.folders[0][1], path)
        os.remove(os.path.join(ROOT, path))
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("3011 compared, 3011 equal, 0 different", res.stdout)

    def test_neighbouring_windows_give_other_registers(self):
        folder = self.folders[0][1]
        for flag, win in (("--visible", "35,221"), ("--visible", "33,221"), ("--visible", "34,220"), ("--visible", "34,222"),
                          ("--lines", "9,247"), ("--lines", "7,247"), ("--lines", "8,246"), ("--lines", "8,248")):
            r = run(folder, self.path, flag, win)
            # the latch chain is in the file: with a moved window some scenes differ (the synthetic scenes put rows anywhere, so every window edge matters)
            self.assertEqual(r.returncode, 1, "%s %s: %s" % (flag, win, r.stdout))

    def test_a_truncated_scene_file_is_refused(self):
        with open(os.path.join(ROOT, self.path), "rb") as fh:
            data = fh.read()
        p = os.path.join(OUT, "gtia.truncated.vec")
        with open(os.path.join(ROOT, p), "wb") as fh:
            fh.write(data[:len(data) // 2])
        r = run(self.folders[0][1], p, "--check-format")
        os.remove(os.path.join(ROOT, p))
        self.assertEqual(r.returncode, 2, r.stdout)


@unittest.skipUnless(os.path.exists(os.path.join(VEC, "gtia.scenes.vec")) and os.path.exists(os.path.join(VEC, "gtia.play.vec")), "the hardware scene sets are not made (python -I tools/make_collide_vectors.py)")
class Hardware(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_every_set_equals_the_hardware(self):
        for cc, folder in self.folders:
            for name, extra in (("gtia.scenes", ()), ("gtia.scenes", ("--via-world",)), ("gtia.play", ()), ("gtia.play", ("--via-world",)), ("gtia.worlds", ()), ("gtia.worlds", ("--via-world",))):
                p = os.path.join("resources", "vectors", name + ".vec")
                if not os.path.exists(os.path.join(ROOT, p)):
                    continue
                r = run(folder, p, *extra)
                self.assertEqual(r.returncode, 0, "%s %s %s: %s" % (cc, name, extra, r.stdout))
        r = run(self.folders[0][1], os.path.join("resources", "vectors", "gtia.scenes.vec"))
        m = re.search(r"(\d+) scenes .*: (\d+) compared, (\d+) equal, 0 different", r.stdout)
        self.assertTrue(m, r.stdout)
        self.assertGreater(int(m.group(2)), 60000)
        r = run(self.folders[0][1], os.path.join("resources", "vectors", "gtia.play.vec"))
        m = re.search(r"(\d+) compared, (\d+) equal, 0 different", r.stdout)
        self.assertGreater(int(m.group(1)), 20000, r.stdout)

    def test_the_neighbours_of_the_windows_fail_on_the_hardware(self):
        folder = self.folders[0][1]
        p = os.path.join("resources", "vectors", "gtia.scenes.vec")
        for flag, win in (("--visible", "35,221"), ("--visible", "33,221"), ("--visible", "34,220"), ("--visible", "34,222"),
                          ("--lines", "8,246"), ("--lines", "8,248")):
            r = run(folder, p, flag, win)
            self.assertEqual(r.returncode, 1, "%s %s must differ from the real GTIA: %s" % (flag, win, r.stdout))
            m = re.search(r"(\d+) different", r.stdout)
            self.assertGreaterEqual(int(m.group(1)), 3)

    def test_the_lower_line_bound_is_not_fixed_by_the_evidence(self):
        """a limit, stated as a test: no recorded scene has a row at line 7 or 9 that matters (the scenes with rows anywhere are compared from line 32 on, docs/50), so 7 and 9 as the first line give the
        same registers as 8 on the hardware evidence; the bound 8 is the start of the picture, not a fitted value"""
        folder = self.folders[0][1]
        p = os.path.join("resources", "vectors", "gtia.scenes.vec")
        for win in ("9,247", "7,247"):
            r = run(folder, p, "--lines", win)
            self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
