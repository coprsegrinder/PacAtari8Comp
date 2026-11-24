"""Stage 79a (docs/51): the state initialisation in C (src/c/app/init.c) against the vector sets of tools/core_app_init.py (stage 78a, which equal the ROM).
The sets of check_app_init (quick run, build/t79a/) are run by the C runner built with clang and gcc: every call equal, the whole World (zero page, the maze and its three copies, status rows, shadows, pages,
positions, buffers, chip writes).  The sets contain the corner cases of the code (the level clamp of 6, the level-255 skip of NewBoardInit, the clock's bit 7 at level 0).  A copy of a set with one byte of the
after-state changed is caught.  Every function of core_app_init.py has its C twin and its entry in the runner's table."""
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
import core_app_init as AI  # noqa: E402
import make_vectors as MV  # noqa: E402
import test_c_ghost as TG  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t79a")


class InitInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_app_init"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.sets = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith("core_app_init.") and f.endswith(".vec"))
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_nine_sets_equal_in_c(self):
        self.assertEqual(len(self.sets), 9)
        for cc, folder in self.folders:
            for f in self.sets:
                r = TG.run(folder, os.path.join(OUT, f))
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, f, r.stdout))
                m = re.search(r": (\d+) calls of '[^']+': (\d+) equal, 0 different", r.stdout)
                self.assertTrue(m, r.stdout)
                self.assertEqual(m.group(1), m.group(2))

    def test_the_corner_cases_are_in_the_vectors(self):
        _, _, _, recs = V.read_set(os.path.join(ROOT, OUT, "core_app_init.new_board_init.vec"))
        seen = {"level255": 0, "level0_high_clock": 0, "level0_low_clock": 0}
        for r in recs:
            w = V.unpack_state(r["before"])
            lv = w.Level[w.CurrentPlayer]
            if lv == 255:
                seen["level255"] += 1
            elif lv == 0:
                seen["level0_high_clock" if w.RTCLOK2 & 0x80 else "level0_low_clock"] += 1
        for k, v in seen.items():
            self.assertGreater(v, 5, k)
        _, _, _, recs = V.read_set(os.path.join(ROOT, OUT, "core_app_init.init_board.vec"))
        levels = {V.unpack_state(r["before"]).Level[V.unpack_state(r["before"]).CurrentPlayer] for r in recs[:400]}
        self.assertTrue(any(l > 6 for l in levels) and any(l < 6 for l in levels))

    def test_a_changed_byte_is_caught(self):
        ro = lambda n: sum(V.EXTRA_SIZE[e] for e in V.EXTRA_ORDER[:V.EXTRA_ORDER.index(n)]) + 0x100
        for setname, offset, what in (("core_app_init.init_board", 0x80, "MazePtr"), ("core_app_init.init_board", ro("shadow") + 0xC3, "a colour shadow"),
                                      ("core_app_init.new_board_init", 0xCB, "a release timer"), ("core_app_init.new_game_init", 0x2C, "Lives"),
                                      ("core_app_init.copy_0c00_to_1000", ro("saved1") + 5, "the saved maze"), ("core_app_init.copy_0800_to_0c00", ro("maze") + 7, "the screen maze"),
                                      ("core_app_init.set_release_timers", 0xCC, "a timer"), ("core_app_init.clear_player_counters", 0x32, "PelletFlags")):
            _, nm, _, recs = V.read_set(os.path.join(ROOT, OUT, setname + ".vec"))
            path = os.path.join(OUT, "tampered.vec")
            w = V.SetWriter(os.path.join(ROOT, path), V.KIND_WORLD, nm, V.pack_state(MV.base_world()))
            for k, rec in enumerate(recs):
                after = bytearray(rec["after"])
                if k == 3:
                    after[offset] ^= 0x10
                w.world(rec["args"], rec["rnd"], rec["ret"], rec["before"], bytes(after), rec["pokey"])
            w.close()
            r = TG.run(self.folders[0][1], path)
            os.remove(os.path.join(ROOT, path))
            self.assertEqual(r.returncode, 1, setname + " " + what + ": " + r.stdout)
            self.assertIn("1 different", r.stdout)

    def test_every_function_has_its_twin(self):
        with open(os.path.join(ROOT, "src", "c", "app", "init.h"), encoding="utf-8") as fh:
            header = fh.read()
        with open(os.path.join(ROOT, "src", "c", "tests", "world_functions.c"), encoding="utf-8") as fh:
            glue = fh.read()
        for name, fn in inspect.getmembers(AI, inspect.isfunction):
            if fn.__module__ == "core_app_init":
                c_name = {"set_zp": "world_zp_set"}.get(name, name)
                self.assertRegex(header, r"\b%s\(" % c_name, name + " is not in init.h")
        for f in self.sets:
            self.assertIn('"%s"' % f[:-4], glue, f + " has no entry in the runner's table")


if __name__ == "__main__":
    unittest.main()
