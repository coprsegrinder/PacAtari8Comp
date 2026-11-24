"""Stage 76c (docs/51): Pac-Man, the score and the drawing in C (src/c/core/pacman.c, score.c, draw.c) against the vector sets of tools/core_pacman.py, core_score.py and core_draw.py.
The sets of check_pacman, check_score and check_draw (quick run, build/t76c/) are run by the C runner built with clang and gcc: every call equal, the whole World.  A copy of a set with one byte of the
after-state changed (zero page, maze, status rows, a player page, a position, the picture buffer) is caught.  Every function of the three Python modules has its C twin."""
import inspect
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import core_draw as D  # noqa: E402
import core_pacman as P  # noqa: E402
import core_score as S  # noqa: E402
import make_vectors as MV  # noqa: E402
import test_c_ghost as TG  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t76c")


class PacmanScoreDrawInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_pacman,check_score,check_draw"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        names = ("core_pacman.", "core_score.", "core_draw.")
        cls.sets = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith(names) and f.endswith(".vec"))
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_ten_sets(self):
        self.assertEqual(len(self.sets), 10, self.sets)

    def test_every_set_equal_in_c(self):
        for cc, folder in self.folders:
            total = 0
            for f in self.sets:
                r = TG.run(folder, os.path.join(OUT, f))
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, f, r.stdout))
                m = re.search(r": (\d+) calls of '[^']+': (\d+) equal, 0 different", r.stdout)
                self.assertTrue(m, r.stdout)
                self.assertEqual(m.group(1), m.group(2))
                total += int(m.group(1))
            self.assertGreater(total, 10000, cc)

    def tampered(self, setname, offset, which=3):
        _, nm, _, recs = V.read_set(os.path.join(ROOT, OUT, setname + ".vec"))
        path = os.path.join(OUT, "tampered.vec")
        w = V.SetWriter(os.path.join(ROOT, path), V.KIND_WORLD, nm, V.pack_state(MV.base_world()))
        for k, rec in enumerate(recs):
            after = bytearray(rec["after"])
            if k == which:
                after[offset] ^= 0x10
            w.world(rec["args"], rec["rnd"], rec["ret"], rec["before"], bytes(after), rec["pokey"])
        w.close()
        r = TG.run(self.folders[0][1], path)
        os.remove(os.path.join(ROOT, path))
        return r

    def test_a_changed_byte_is_caught(self):
        ro = TG.region_offset
        for setname, offset, what in (("core_pacman.move_pacman", 0x8E, "PacX"),
                                      ("core_pacman.move_pacman", ro("hpos") + 5, "a missile position"),
                                      ("core_pacman.move_pacman", ro("picbuf") + 5, "the picture buffer"),
                                      ("core_score.add_to_score", ro("status") + 0x2A, "a score cell"),
                                      ("core_score.draw_lives", ro("maze") + 0x374, "a life icon"),
                                      ("core_score.eat_dot", 0x94 + 4, "ScoreAdd"),
                                      ("core_score.power_pellet_check", 0xCE, "a ghost state"),
                                      ("core_draw.draw_pacman", ro("pm") + 0x3A0, "a page byte"),
                                      ("core_draw.clip_entities_on_tunnel_row", 0xFE, "ClipMask"),
                                      ("core_draw.clear_player_memory", ro("pm") + 0x2F0, "a cleared page")):
            r = self.tampered(setname, offset)
            self.assertEqual(r.returncode, 1, setname + " " + what + ": " + r.stdout)
            self.assertIn("1 different", r.stdout, setname + " " + what)

    def test_every_function_has_its_twin(self):
        texts = {}
        for h in ("pacman.h", "score.h", "draw.h"):
            with open(os.path.join(ROOT, "src", "c", "core", h), encoding="utf-8") as fh:
                texts[h] = fh.read()
        header = "\n".join(texts.values())
        with open(os.path.join(ROOT, "src", "c", "tests", "world_functions.c"), encoding="utf-8") as fh:
            glue = fh.read()
        c_names = {"rom": "draw_rom", "rom_word": "draw_rom_word", "_put": "draw_put", "_get": "draw_get"}
        skipped = {"scene", "_ptr", "_set_ptr", "_step"}                      # scene: the collision model (stage 77a); the rest are file-local in C
        for mod in (D, P, S):
            for name, fn in inspect.getmembers(mod, inspect.isfunction):
                if fn.__module__ != mod.__name__ or name in skipped:
                    continue
                self.assertRegex(header, r"\b%s\(" % c_names.get(name, name), name + " is not in the C headers")
        for f in self.sets:
            self.assertIn('"%s"' % f[:-4], glue, f + " has no entry in the runner's table")


if __name__ == "__main__":
    unittest.main()
