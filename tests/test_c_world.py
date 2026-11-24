"""Stage 75a (docs/51): the generated C World and tables (src/c/core/world.[ch], tables.[ch]) against the Python World and tables.
The C is built with clang and with gcc (whichever exist) into build/c75a-<compiler>/, a 64 KB image goes through C (load, store) and through tools/core_world.py,
every region and every table is compared by name, a misspelt field is shown not to compile, and a deliberately wrong dump is shown to be caught."""
import os
import random
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import c_blob  # noqa: E402
import algorithm_models as A  # noqa: E402
import core_tables as T  # noqa: E402
import core_world as W  # noqa: E402
import make_c_tables as MCT  # noqa: E402
import make_c_world as MCW  # noqa: E402

CORE = os.path.join(ROOT, "src", "c", "core")


def build(cc):
    """configure and build src/c with the compiler `cc`; returns the build folder, or None when it is not installed"""
    if not (shutil.which(cc) and shutil.which("cmake") and shutil.which("ninja")):
        return None
    out = os.path.join(ROOT, "build", "c75a-" + cc)
    subprocess.run(["cmake", "-S", os.path.join(ROOT, "src", "c"), "-B", out, "-G", "Ninja", "-DCMAKE_C_COMPILER=" + cc], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", out], check=True, capture_output=True)
    c_blob.ensure(out)
    return out


def exe(folder):
    return os.path.join(folder, "tests", "world_check.exe" if os.name == "nt" else "world_check")


def parse(path):
    regions, tables = {}, {}
    with open(path, encoding="ascii") as fh:
        for line in fh:
            p = line.split()
            if p[0] == "R":
                regions[p[1]] = (int(p[2]), int(p[3]), bytes.fromhex(p[4]))
            elif p[0] == "T":
                tables[p[1]] = (int(p[2]), int(p[3]), bytes.fromhex(p[4]))
    return regions, tables


def differences(regions, tables, mem, w):
    """the names whose C value differs from the Python World / tables"""
    bad = []
    for name, addr, n in W.FIELDS:
        a, c, data = regions[name]
        v = getattr(w, name)
        want = bytes([v]) if n == 1 else bytes(v)
        if (a, c, data) != (addr, n, want):
            bad.append(name)
    for name, extra in (("maze", w.maze), ("status", w.status), ("shadow", w.shadow), ("stick", w.stick), ("collide", w.collide), ("pm", w.pm), ("hpos", w.hpos), ("picbuf", w.picbuf), ("maze_orig", w.maze_orig), ("saved1", w.saved1), ("saved2", w.saved2), ("title", w.title)):
        if regions[name][2] != bytes(extra):
            bad.append(name)
    for name, src, addr, n, _ in MCT.ALL:
        if tables[name] != (addr, n, bytes(getattr(T, name))):
            bad.append(name)
    return bad


class CWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folders = [(cc, build(cc)) for cc in ("clang", "gcc")]
        cls.folders = [(cc, f) for cc, f in cls.folders if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def run_c(self, folder, image, tag):
        d = os.path.join(folder, "t75a")
        os.makedirs(d, exist_ok=True)
        i, o, dump = (os.path.join(d, tag + s) for s in (".in", ".out", ".txt"))
        with open(i, "wb") as fh:
            fh.write(image)
        rel = lambda p: os.path.relpath(p, ROOT)           # the tool opens files through platform/fs.c: relative paths under the main folder (stage 75b)
        r = subprocess.run([exe(folder), rel(i), rel(o), rel(dump)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        with open(o, "rb") as fh:
            back = fh.read()
        return back, parse(dump)

    def images(self):
        m = A.started_machine()
        yield "rom", bytes(m.mem)
        rng = random.Random(75)
        for k in range(4):
            yield "rnd%d" % k, bytes(rng.randrange(256) for _ in range(65536))
        yield "ones", bytes([0xFF]) * 65536

    def test_selftest(self):
        for cc, f in self.folders:
            r = subprocess.run([exe(f)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, cc + ": " + r.stdout)

    def test_roundtrip_equals_python(self):
        for cc, f in self.folders:
            for tag, img in self.images():
                back, (regions, tables) = self.run_c(f, img, tag)
                w = W.World().load(img)
                want = bytearray(0x10000)
                w.store(want)
                self.assertEqual(back, bytes(want), cc + " " + tag + ": image -> C -> image differs from image -> Python -> image")
                self.assertEqual(differences(regions, tables, img, w), [], cc + " " + tag)

    def test_negative_control(self):
        """a dump with one byte wrong is caught"""
        f = self.folders[0][1]
        img = bytes(A.started_machine().mem)
        _, (regions, tables) = self.run_c(f, img, "neg")
        w = W.World().load(img)
        a, c, data = regions["maze"]
        regions["maze"] = (a, c, bytes([data[0] ^ 1]) + data[1:])
        a, c, data = tables["JUNCTION_Y"]
        tables["JUNCTION_Y"] = (a, c, data[:3] + bytes([data[3] ^ 0x10]) + data[4:])
        self.assertEqual(differences(regions, tables, img, w), ["maze", "JUNCTION_Y"])

    def test_misspelt_field_does_not_compile(self):
        for cc, f in self.folders:
            d = os.path.join(f, "t75a")
            os.makedirs(d, exist_ok=True)
            src = os.path.join(d, "bad.c")
            for field, ok in (("GameState", True), ("GameStat", False), ("ghostState", False)):
                with open(src, "w") as fh:
                    fh.write('#include "world.h"\nint main(void) { World w; w.%s = 1; return w.GameState; }\n' % field)
                r = subprocess.run([cc, "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-Werror", "-I", CORE, "-c", src, "-o", os.path.join(d, "bad.o")], capture_output=True, text=True)
                self.assertEqual(r.returncode == 0, ok, cc + " " + field + ": " + r.stderr)


class Generated(unittest.TestCase):
    def test_files_are_current(self):
        for name, text in (("world.h", MCW.header()), ("world.c", MCW.source()), ("tables.h", MCT.header()), ("tables.c", MCT.source())):
            with open(os.path.join(CORE, name), encoding="utf-8", newline="") as fh:
                self.assertEqual(fh.read(), text, name + " is not what the generator writes: run tools/make_c_world.py / make_c_tables.py")

    def test_counts(self):
        self.assertEqual(len(W.FIELDS), 181)
        self.assertEqual(len(MCT.ALL), 17)
        self.assertEqual(sum(n for _, _, n in W.FIELDS), 256)      # every zero-page byte is in exactly one field
        self.assertEqual(len({n for n, _, _ in W.FIELDS} & {e[0] for e in MCW.EXTRA}), 0)


if __name__ == "__main__":
    unittest.main()
