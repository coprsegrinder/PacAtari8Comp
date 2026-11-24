"""Stage 77b (docs/51): the platform layer in C (src/c/platform: hal.h, hal_scripted.c, pokey_random.c; src/c/app/run_frame.c).
1. The POKEY RANDOM model (owner decision D1): the C generator equals the Python one of tools/pokey_noise.py bit for bit over the whole period of 131,071 steps; the unit test checks the period, distinct states,
   the all-ones seed and the shape of the byte.
2. run_frame on a platform that replays the inputs of every recorded frame (the 17,979 frames of core_play.vbi_play_frame, plain and in chain mode) equals the vectors; a changed vector is caught.
3. Determinism, a different seed, "inputs only through the platform" (poisoned input fields change nothing) and the count of every input call, on states of the game (tests/../platform_check --frames);
   a run_frame that does NOT read the clock from the platform is shown to fail the poison check (a mutated copy of the source, built here)."""
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import make_vectors as MV  # noqa: E402
import pokey_noise as PN  # noqa: E402
import test_c_ghost as TG  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t77b")


def exe(folder, name):
    return os.path.join(folder, "tests", name + (".exe" if os.name == "nt" else ""))


class Platform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")
        os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_play"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.vec = os.path.join(OUT, "core_play.vbi_play_frame.vec")
        recs = V.read_set(os.path.join(ROOT, cls.vec))[3]
        picks = [r for r in recs if r["rnd"]][:8]          # states in which the frame takes RANDOM values
        cls.states = os.path.join(OUT, "states.bin")
        with open(os.path.join(ROOT, cls.states), "wb") as fh:
            for r in picks:
                fh.write(r["before"])
        cls.npicks = len(picks)

    def test_unit_checks(self):
        for cc, f in self.folders:
            r = subprocess.run([exe(f, "platform_check")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, cc + ": " + r.stdout)

    def test_the_poly17_equals_the_python_generator(self):
        n = 131071
        want = "".join(str(int(b)) for b in PN.S17[:n])
        for cc, f in self.folders:
            r = subprocess.run([exe(f, "platform_check"), "--bits", str(n)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), want, cc)

    def test_run_frame_equals_the_vectors_plain_and_chained(self):
        for cc, f in self.folders:
            for extra in (["--platform"], ["--platform", "--chain"]):
                r = subprocess.run([TG.runner(f), *extra, self.vec], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, extra, r.stdout))
                self.assertIn("0 different", r.stdout)

    def test_a_changed_vector_is_caught_through_the_platform(self):
        _, nm, _, recs = V.read_set(os.path.join(ROOT, self.vec))
        path = os.path.join(OUT, "tampered.vec")
        w = V.SetWriter(os.path.join(ROOT, path), V.KIND_WORLD, nm, V.pack_state(MV.base_world()))
        for k, rec in enumerate(recs):
            after = bytearray(rec["after"])
            if k == 7:
                after[0x8E] ^= 0x10
            w.world(rec["args"], rec["rnd"], rec["ret"], rec["before"], bytes(after), rec["pokey"])
        w.close()
        r = subprocess.run([TG.runner(self.folders[0][1]), "--platform", path], cwd=ROOT, capture_output=True, text=True)
        os.remove(os.path.join(ROOT, path))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("1 different", r.stdout)

    def test_frames_on_the_scripted_platform(self):
        self.assertGreaterEqual(self.npicks, 4)
        for cc, f in self.folders:
            r = subprocess.run([exe(f, "platform_check"), "--frames", self.states], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, cc + ": " + r.stdout)

    def test_the_gtia_platform_latch_frame_by_frame(self):
        import analyze_collide as AC
        cs = os.path.join(OUT, "charset.bin")
        with open(os.path.join(ROOT, cs), "wb") as fh:
            fh.write(AC.rom_charset())
        for cc, f in self.folders:
            r = subprocess.run([exe(f, "platform_check"), "--gtia", self.states, cs], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, cc + ": " + r.stdout)

    def test_a_run_frame_that_ignores_the_platform_clock_fails_the_poison_check(self):
        """negative control: a copy of the source tree in which run_frame does not read the clock from the platform; the poisoned copy of the World then runs with another clock and must differ"""
        cc = self.folders[0][0]
        dst = os.path.join(ROOT, OUT, "mut")
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(os.path.join(ROOT, "src", "c"), dst, ignore=shutil.ignore_patterns("CMakeLists.txt"))
        p = os.path.join(dst, "app", "run_frame.c")
        with open(p, encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("w->RTCLOK2 = p->clock(p->ctx);", s)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(s.replace("w->RTCLOK2 = p->clock(p->ctx);", "(void)p->clock(p->ctx);"))
        srcs = []
        for d in ("core", "platform", "app", "assets"):                       # the assets loader boots the tables (stage 80a); install_assets.c is a program of its own
            srcs += [os.path.join(dst, d, f) for f in sorted(os.listdir(os.path.join(dst, d))) if f.endswith(".c") and f != "install_assets.c"]
        srcs.append(os.path.join(dst, "tests", "platform_check.c"))
        out = os.path.join(dst, "platform_check_mut" + (".exe" if os.name == "nt" else ""))
        r = subprocess.run([cc, "-std=c99", "-O1", "-I", os.path.join(dst, "core"), "-I", os.path.join(dst, "platform"), "-o", out, *srcs], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        r = subprocess.run([out, "--frames", self.states], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("a poisoned input field changed the frame", r.stdout)
        shutil.rmtree(dst)


if __name__ == "__main__":
    unittest.main()
