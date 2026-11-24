"""Stage 76d (docs/51): the sound, the frame logic and `play_frame` in C (src/c/core/sound.c, frame.c, play.c) against the vector sets of tools/core_sound.py, core_frame.py and core_play.py.
The sets of check_sound, check_frame and check_play (quick run, build/t76d/) are run by the C runner built with clang and gcc: every call equal (the whole World, the ordered chip writes, the RANDOM
count).  The chain mode runs the 20-frame runs of check_play from the state the C itself made (not the file's), frame after frame.  A copy of a set with one byte of the after-state, a chip write or a
RANDOM value changed is caught, also in a chain.  Every function of the three Python modules has its C twin."""
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
import core_frame as F  # noqa: E402
import core_play as PL  # noqa: E402
import core_sound as SO  # noqa: E402
import make_vectors as MV  # noqa: E402
import test_c_ghost as TG  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t76d")


def runner_args(folder, rel, *extra):
    return subprocess.run([TG.runner(folder), *extra, rel], cwd=ROOT, capture_output=True, text=True)


class PlayInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_sound,check_frame,check_play"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        names = ("core_sound.", "core_frame.", "core_play.")
        cls.sets = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith(names) and f.endswith(".vec"))
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_fourteen_sets(self):
        self.assertEqual(len(self.sets), 14, self.sets)

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

    def test_chain_mode_runs_frames_from_the_c_state(self):
        for cc, folder in self.folders:
            r = runner_args(folder, os.path.join(OUT, "core_play.vbi_play_frame.vec"), "--chain")
            self.assertEqual(r.returncode, 0, cc + ": " + r.stdout)
            m = re.search(r"chain mode: (\d+) frames run from the state the C had made itself, in (\d+) runs \(longest (\d+) frames\)", r.stdout)
            self.assertTrue(m, r.stdout)
            self.assertGreater(int(m.group(1)), 1000, r.stdout)           # the 19 follow-up frames of each of the 150 runs, less the skipped ones
            self.assertEqual(int(m.group(3)), 20)

    def rewrite(self, setname, change, which):
        """a copy of a set in which call `which` is changed by change(rec) -> rec"""
        _, nm, _, recs = V.read_set(os.path.join(ROOT, OUT, setname + ".vec"))
        path = os.path.join(OUT, "tampered.vec")
        w = V.SetWriter(os.path.join(ROOT, path), V.KIND_WORLD, nm, V.pack_state(MV.base_world()))
        for k, rec in enumerate(recs):
            if k == which:
                rec = change(dict(rec))
            w.world(rec["args"], rec["rnd"], rec["ret"], rec["before"], rec["after"], rec["pokey"])
        w.close()
        return path, recs

    def run_tampered(self, setname, change, which, *extra):
        path, recs = self.rewrite(setname, change, which)
        r = runner_args(self.folders[0][1], path, *extra)
        os.remove(os.path.join(ROOT, path))
        return r

    @staticmethod
    def flip(offset):
        def change(rec):
            a = bytearray(rec["after"])
            a[offset] ^= 0x10
            rec["after"] = bytes(a)
            return rec
        return change

    def test_a_changed_state_byte_is_caught(self):
        ro = TG.region_offset
        for setname, offset, what in (("core_sound.siren", 0xDE, "SirenTone"),
                                      ("core_sound.death_sequence", 0xED, "DeathState"),
                                      ("core_sound.death_animation", ro("pm") + 0x300, "a page byte"),
                                      ("core_sound.start_tune_step", ro("maze") + 0x374, "a life icon"),
                                      ("core_frame.ghost_eaten", ro("shadow") + 0xC7, "COLOR3"),
                                      ("core_frame.frightened_tick", ro("shadow") + 0xC1, "a ghost colour"),
                                      ("core_frame.eyes_and_house_per_frame", 0xF2, "EyesReturning"),
                                      ("core_play.vbi_play_frame", 0x8E, "PacX"),
                                      ("core_play.vbi_play_frame", ro("hpos") + 3, "a position")):
            r = self.run_tampered(setname, self.flip(offset), 3)
            self.assertEqual(r.returncode, 1, setname + " " + what + ": " + r.stdout)
            self.assertIn("1 different", r.stdout, setname + " " + what)

    def test_a_changed_chip_write_is_caught(self):
        _, _, _, recs = V.read_set(os.path.join(ROOT, OUT, "core_sound.siren.vec"))

        def value(rec):
            rec["pokey"] = [(rec["pokey"][0][0], rec["pokey"][0][1] ^ 1)] + rec["pokey"][1:]
            return rec

        def order(rec):
            rec["pokey"] = list(reversed(rec["pokey"]))
            return rec

        def extra(rec):
            rec["pokey"] = rec["pokey"] + [(0xD208, 0)]
            return rec
        for fn in (value, order, extra):
            r = self.run_tampered("core_sound.siren", fn, 3)
            self.assertEqual(r.returncode, 1, fn.__name__ + ": " + r.stdout)
            self.assertIn("chip write", r.stdout)

    def test_a_withheld_random_value_is_caught(self):
        _, _, _, recs = V.read_set(os.path.join(ROOT, OUT, "core_play.vbi_play_frame.vec"))
        k = next(i for i, r in enumerate(recs) if r["rnd"])

        def drop(rec):
            rec["rnd"] = rec["rnd"][:-1]
            return rec
        r = self.run_tampered("core_play.vbi_play_frame", drop, k)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RANDOM", r.stdout)

    def test_a_difference_in_the_middle_of_a_chain_is_caught(self):
        """the frame after a changed frame must not hide it: the runner reports the changed frame and goes on from the file's state"""
        _, _, _, recs = V.read_set(os.path.join(ROOT, OUT, "core_play.vbi_play_frame.vec"))
        start = next(k for k in range(len(recs) - 3) if recs[k + 1]["before"] != recs[k]["before"] and self.is_next(recs[k], recs[k + 1]) and self.is_next(recs[k + 1], recs[k + 2]))
        r = self.run_tampered("core_play.vbi_play_frame", self.flip(0x8A), start + 1, "--chain")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("1 different", r.stdout)

    @staticmethod
    def is_next(a, b):
        e = bytearray(a["after"])
        e[0x14] = (e[0x14] + 1) & 0xFF
        return bytes(e) == b["before"]

    def test_every_function_has_its_twin(self):
        header = ""
        for h in ("sound.h", "frame.h", "play.h"):
            with open(os.path.join(ROOT, "src", "c", "core", h), encoding="utf-8") as fh:
                header += fh.read()
        with open(os.path.join(ROOT, "src", "c", "tests", "world_functions.c"), encoding="utf-8") as fh:
            glue = fh.read()
        c_names = {"wr": "sound_wr", "move_delay_tick": "move_delay_tick_w", "_pick_up_bonus": None, "_contact_and_bonus": None, "_glide_up": None,
                   "_eaten_pause_end": None, "_flash_colours": None}
        for mod in (SO, F, PL):
            for name, fn in inspect.getmembers(mod, inspect.isfunction):
                if fn.__module__ != mod.__name__:
                    continue
                c = c_names.get(name, name)
                if c is None:
                    continue                                               # file-local in C
                self.assertRegex(header, r"\b%s\(" % c, name + " is not in the C headers")
        for f in self.sets:
            self.assertIn('"%s"' % f[:-4], glue, f + " has no entry in the runner's table")


if __name__ == "__main__":
    unittest.main()
