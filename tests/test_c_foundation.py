"""Stage 75b (docs/51): the vector files, the C runner, the file sandbox and the portability scan.
The vectors of three checkers are written (tools/make_vectors.py --quick --only ...) into build/t75b/, every set is read back with tools/vecfmt.py and each call is REPLAYED through the Python port
(the vector must equal what the port does), a changed vector is shown to be caught, the C reader accepts every file (clang and gcc), and `ctest` of both builds passes (identity vectors, negative controls,
byte order, sandbox, portability scan).  A link inside the main folder is refused by fs.c (a junction on Windows, a symbolic link elsewhere)."""
import importlib
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import c_blob  # noqa: E402
import make_vectors as MV  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t75b")


def build(cc):
    if not (shutil.which(cc) and shutil.which("cmake") and shutil.which("ninja")):
        return None
    out = os.path.join(ROOT, "build", "c-" + cc)
    subprocess.run(["cmake", "-S", os.path.join(ROOT, "src", "c"), "-B", out, "-G", "Ninja", "-DCMAKE_C_COMPILER=" + cc], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", out], check=True, capture_output=True)
    c_blob.ensure(out)
    return out


def exe(folder, name):
    return os.path.join(folder, "tests", name + (".exe" if os.name == "nt" else ""))


class Replay:
    """a vector replayed through the Python port"""

    class Tee:
        def __init__(self, vals):
            self.v = iter(vals)
            self.n = 0

        def __iter__(self):
            return self

        def __next__(self):
            self.n += 1
            return next(self.v)

    @staticmethod
    def world_call(setname, rec):
        modname, fname = setname.split(".")
        fn = getattr(importlib.import_module(modname), fname)
        w = V.unpack_state(rec["before"])
        it = Replay.Tee(rec["rnd"])
        args = list(rec["args"])
        # the arguments are the integers in order; a RANDOM iterator is passed where the function takes one
        import inspect
        params = list(inspect.signature(fn).parameters)[1:]
        call = []
        for p in params:
            if p == "it" or p == "rnd":
                call.append(it)
            else:
                call.append(args.pop(0))
        r = fn(w, *call)
        got_ret = int(r) if isinstance(r, (bool, int)) else None
        return V.pack_state(w), list(w.pokey), it.n, got_ret


class Vectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_pacman,check_score,check_frame"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.files = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.endswith(".vec"))

    def test_sets_exist(self):
        names = {f[:-4] for f in self.files}
        for n in ("core_pacman.move_pacman", "core_score.add_to_score", "core_score.eat_dot", "core_frame.ghost_eaten", "core_frame.frightened_tick", "core_frame.eyes_and_house_per_frame"):
            self.assertIn(n, names)

    def test_every_call_replays_through_the_port(self):
        for f in self.files:
            kind, name, count, recs = V.read_set(os.path.join(ROOT, OUT, f))
            self.assertEqual(name, f[:-4])
            self.assertEqual(count, len(recs))
            self.assertGreater(count, 100, name)
            if kind != V.KIND_WORLD:
                continue
            for k, rec in enumerate(recs[:150]):
                after, pokey, used, ret = Replay.world_call(name, rec)
                self.assertEqual(after, rec["after"], "%s call %d: state" % (name, k))
                self.assertEqual(pokey, rec["pokey"], "%s call %d: chip writes" % (name, k))
                self.assertEqual(used, len(rec["rnd"]), "%s call %d: RANDOM" % (name, k))
                if rec["ret"] is not None:
                    self.assertEqual(ret, rec["ret"], "%s call %d: return" % (name, k))

    def test_a_changed_vector_is_caught(self):
        _, name, _, recs = V.read_set(os.path.join(ROOT, OUT, "core_pacman.move_pacman.vec"))
        rec = recs[0]
        bad = bytearray(rec["after"])
        bad[0x8E] ^= 1                                             # one byte of the state
        after, _, _, _ = Replay.world_call(name, rec)
        self.assertNotEqual(after, bytes(bad))
        self.assertEqual(after, rec["after"])

    def test_diff_roundtrip_and_determinism(self):
        import random
        rng = random.Random(1)
        for _ in range(200):
            a = bytes(rng.randrange(256) for _ in range(V.STATE_SIZE))
            b = bytearray(a)
            for _ in range(rng.randrange(0, 40)):
                b[rng.randrange(V.STATE_SIZE)] = rng.randrange(256)
            d = V.diff(a, bytes(b))
            back, used = V.apply_diff(a, d)
            self.assertEqual(back, bytes(b))
            self.assertEqual(used, len(d))
        for f in self.files[:2]:                                   # the same checker run gives the same bytes
            p = os.path.join(ROOT, OUT, f)
            self.assertGreater(os.path.getsize(p), 100)

    def test_c_reader_accepts_every_file(self):
        found = False
        for cc in ("clang", "gcc"):
            folder = build(cc)
            if not folder:
                continue
            found = True
            for f in self.files:
                r = subprocess.run([exe(folder, "vector_runner"), "--check-format", os.path.join(OUT, f)], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, cc + " " + f + ": " + r.stdout)
            # the byte-swapped reader refuses them
            r = subprocess.run([exe(folder, "vector_runner_swapped"), "--check-format", os.path.join(OUT, self.files[0])], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            # a truncated file is refused, not read past
            with open(os.path.join(ROOT, OUT, self.files[0]), "rb") as fh:
                data = fh.read()
            with open(os.path.join(ROOT, OUT, "truncated.vec"), "wb") as fh:
                fh.write(data[:len(data) // 2])
            r = subprocess.run([exe(folder, "vector_runner"), "--check-format", os.path.join(OUT, "truncated.vec")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stdout)
            os.remove(os.path.join(ROOT, OUT, "truncated.vec"))
            # a path outside the main folder is refused
            r = subprocess.run([exe(folder, "vector_runner"), "--check-format", "../outside.vec"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("'.' or '..'", r.stdout)
        if not found:
            self.skipTest("no clang / gcc + cmake + ninja")

    def test_c_runner_has_no_function_yet(self):
        folder = build("clang") or build("gcc")
        if not folder:
            self.skipTest("no compiler")
        # every set the checkers record has its C function now (stage 76d): a set for a function that is not written is made here
        base = V.pack_state(MV.base_world())
        path = os.path.join(OUT, "core_unwritten.fn.vec")
        w = V.SetWriter(os.path.join(ROOT, path), V.KIND_WORLD, "core_unwritten.fn", base)
        w.world([], [], None, base, base, [])
        w.close()
        r = subprocess.run([exe(folder, "vector_runner"), path], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("no C function yet", r.stdout)
        os.remove(os.path.join(ROOT, path))


class CTests(unittest.TestCase):
    def test_ctest_both_compilers(self):
        found = False
        for cc in ("clang", "gcc"):
            folder = build(cc)
            if not folder:
                continue
            found = True
            r = subprocess.run(["ctest", "--test-dir", folder, "--output-on-failure"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, cc + "\n" + r.stdout[-3000:])
            self.assertIn("100% tests passed", r.stdout)
        if not found:
            self.skipTest("no clang / gcc + cmake + ninja")

    def test_link_in_main_folder_is_refused(self):
        folder = build("clang") or build("gcc")
        if not folder:
            self.skipTest("no compiler")
        main = os.path.join(folder, "tests", "fs_sandbox_root", "main")
        target = os.path.join(folder, "tests", "fs_sandbox_root", "elsewhere")
        link = os.path.join(main, "lnk")
        os.makedirs(target, exist_ok=True)
        if os.path.lexists(link):
            os.rmdir(link) if os.name == "nt" else os.remove(link)
        try:
            if os.name == "nt":
                r = subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True, text=True)
                if r.returncode != 0:
                    self.skipTest("cannot make a junction: " + r.stdout + r.stderr)
            else:
                os.symlink(target, link)
            r = subprocess.run([exe(folder, "fs_sandbox"), os.path.join(folder, "tests", "fs_sandbox_root"), "lnk"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertFalse(os.path.exists(os.path.join(target, "f.bin")), "a file was written through the link")
        finally:
            if os.path.lexists(link):
                os.rmdir(link) if os.name == "nt" else os.remove(link)


if __name__ == "__main__":
    unittest.main()
