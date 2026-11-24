"""Stage 79d (docs/51): the main program, the new game and the start-up in C (src/c/app/keyloop.c, newgame.c, start.c, app.c) and, with them, the whole program: a whole game in C, headless, from power-on.
1. Whole sessions (tools/make_app_sequences.py: the Python program of tools/core_app.py, which equals the ROM after every frame of the same sessions, tests/test_app.py): one record a frame with the inputs of the frame, the
   RANDOM values it took, the World after it and where the main program is; the C runs them in chain mode FROM POWER-ON with its own state (it runs Start itself, computes the collision registers with its own GTIA
   model and latch) and must equal every frame: a one-player game to the game over and the title, a session of keys, a level end, a clock that wraps.  A changed frame, or a changed place of the main program,
   is caught.
2. The main program from every place it can be in, from random states and inputs (tools/check_app_keyloop.py): equal in C.  3. The power-on RAM for every clock value.  4. The maze data is the ROM's.
5. Every function of tools/core_app.py has its C twin (frame_class is the Python story labeller, not ported)."""
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
import core_app as APP  # noqa: E402
import test_c_board as TB  # noqa: E402
import test_c_ghost as TG  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t79d")


def run(folder, name, *extra):
    return subprocess.run([TG.runner(folder), *extra, os.path.join(OUT, name)], cwd=ROOT, capture_output=True, text=True)


class AppInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_app_sequences.py"), "--quick", "--out", OUT], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        if not os.path.exists(os.path.join(ROOT, "resources", "vectors", "gtia.charset.bin")):
            import analyze_collide as AC
            os.makedirs(os.path.join(ROOT, "resources", "vectors"), exist_ok=True)
            with open(os.path.join(ROOT, "resources", "vectors", "gtia.charset.bin"), "wb") as fh:
                fh.write(AC.rom_charset())
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_whole_sessions_from_power_on_equal_in_c(self):
        want = {"session_1p.vec": (2400, 1), "session_keys.vec": (2600, 1), "session_level.vec": (1400, 2), "session_clock.vec": (700, 1)}
        for cc, folder in self.folders:
            for name, (calls, runs) in want.items():
                r = run(folder, name, "--chain")
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, name, r.stdout))
                m = re.search(r"chain mode: (\d+) frames run from the state the C had made itself, in (\d+) runs \(longest (\d+) frames\)", r.stdout)
                self.assertTrue(m, r.stdout)
                self.assertEqual(int(m.group(2)), runs, name)               # the level end's test aid breaks the chain once; nothing else does
                self.assertIn("%d equal, 0 different" % calls, r.stdout)

    def test_the_sessions_go_through_the_game(self):
        """the Python records of the sessions: the copyright screen, the title, the game, a pause, a new game from the keys"""
        _, _, _, recs = V.read_set(os.path.join(ROOT, OUT, "session_keys.vec"))
        states = {V.unpack_state(r["after"]).GameState for r in recs}
        self.assertTrue({0, 2, 3} <= states, states)                       # the copyright wait, the title and the game
        paused = any(V.unpack_state(r["after"]).Paused for r in recs[690:780])
        self.assertTrue(paused)                                           # the space bar paused the game

    def test_a_full_game_to_game_over_if_made(self):
        p = os.path.join(ROOT, "resources", "vectors", "session_1p.vec")
        if not os.path.exists(p):
            self.skipTest("the full sessions are not made (python -I tools/make_app_sequences.py)")
        for cc, folder in self.folders:
            r = subprocess.run([TG.runner(folder), "--chain", os.path.join("resources", "vectors", "session_1p.vec")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, cc + ": " + r.stdout)
            self.assertIn("9000 equal, 0 different", r.stdout)

    def test_a_changed_frame_or_place_is_caught(self):
        folder = self.folders[0][1]
        ro = lambda n: sum(V.EXTRA_SIZE[e] for e in V.EXTRA_ORDER[:V.EXTRA_ORDER.index(n)]) + 0x100
        for off, what in ((0x19, "GameState"), (ro("title") + 0x54, "the title"), (0x2B, "the player on turn")):
            r = TB.tamper(folder, "session_1p", off, 1500, ("--chain",), directory=OUT)
            self.assertEqual(r.returncode, 1, what + ": " + r.stdout)
            self.assertIn("1 different", r.stdout)
        # the place of the main program: the return value of one record changed
        _, nm, _, recs = V.read_set(os.path.join(ROOT, OUT, "session_keys.vec"))
        path = os.path.join(OUT, "tampered.vec")
        w = V.SetWriter(os.path.join(ROOT, path), V.KIND_WORLD, nm, bytes(V.pack_state(__import__("make_vectors").base_world())))
        for k, rec in enumerate(recs):
            ret = rec["ret"] ^ (1 << 8) if k == 400 else rec["ret"]
            w.world(rec["args"], rec["rnd"], ret, rec["before"], rec["after"], rec["pokey"])
        w.close()
        r = subprocess.run([TG.runner(folder), "--chain", path], cwd=ROOT, capture_output=True, text=True)
        os.remove(os.path.join(ROOT, path))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("returned", r.stdout)

    def test_the_main_program_from_every_place_and_the_power_on_ram(self):
        for cc, folder in self.folders:
            for name, n in (("keyloop_states.vec", 1200), ("keyloop_power_on.vec", 256)):
                r = run(folder, name)
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, name, r.stdout))
                self.assertIn("%d equal, 0 different" % n, r.stdout)
        r = TB.tamper(self.folders[0][1], "keyloop_states", 0x19, 5, directory=OUT)
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_the_maze_is_not_in_the_sources(self):
        """since 2026-11-22 the maze (and every other table) is installed from the owner's ROM at start-up: the generated maze_data files are gone (tests/test_c_assets.py scans the sources for ROM bytes)"""
        self.assertFalse(os.path.exists(os.path.join(ROOT, "src", "c", "app", "maze_data.c")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "src", "c", "app", "maze_data.h")))

    def test_every_function_has_its_twin(self):
        with open(os.path.join(ROOT, "src", "c", "app", "keyloop.h"), encoding="utf-8") as fh:
            header = fh.read()
        with open(os.path.join(ROOT, "src", "c", "tests", "world_functions.c"), encoding="utf-8") as fh:
            glue = fh.read()
        twins = {"power_on_world": "power_on_world", "start": "start", "key_loop": "key_loop", "read_inputs": "app_read_inputs", "_restart_clear": "restart_clear",
                 "_restart_tail": "restart_tail", "_new_game": "new_game"}
        for name, fn in inspect.getmembers(APP, inspect.isfunction):
            if fn.__module__ != "core_app" or name in ("maze_stream", "frame_class") or name in ("_colours", "_set_title", "_pass", "_read", "_released", "_signature"):
                continue                                                   # the maze comes from the installed tables; frame_class labels stories; the rest are file-local in keyloop.c
            self.assertRegex(header, r"\b%s\(" % twins[name], name + " is not in keyloop.h")
        self.assertRegex(header, r"\bapp_frame\(")                         # App.frame
        for n in ("app.frame", "app.key_loop", "app.power_on_world"):
            self.assertIn('"%s"' % n, glue)


if __name__ == "__main__":
    unittest.main()
