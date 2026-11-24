"""Stage 79b (docs/51): the board, the turn, the end of a level, the READY! intro and the labels in C (src/c/app/intro.c, board.c, levelend.c, turn.c) against the vector sets of tools/core_app_board.py (stage 78b, which equal the ROM).
1. The quick sets of check_app_board (build/t79b/) run by the C runner built with clang and gcc: every call equal, the whole World and the ordered chip writes (HITCLR, COLPF3, the sound chip).
2. The sequence sets (tools/make_app_sequences.py): TurnControl 140 calls and the level-end sequence 200 calls on one state, run in chain mode from the state the C itself made: equal; a changed call in the middle of a
   run is caught.
3. Negative controls: a changed byte of the after-state (the status rows, the maze, a shadow, a hand-over stage, the high score, ItemColor) is caught; every function of core_app_board.py has its C twin."""
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
import core_app_board as AB  # noqa: E402
import make_vectors as MV  # noqa: E402
import test_c_ghost as TG  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t79b")


def tamper(folder, setname, offset, which, extra=(), directory=OUT):
    _, nm, _, recs = V.read_set(os.path.join(ROOT, directory, setname + ".vec"))
    path = os.path.join(OUT, "tampered.vec")
    w = V.SetWriter(os.path.join(ROOT, path), V.KIND_WORLD, nm, V.pack_state(MV.base_world()))
    for k, rec in enumerate(recs):
        after = bytearray(rec["after"])
        if k == which:
            after[offset] ^= 0x10
        w.world(rec["args"], rec["rnd"], rec["ret"], rec["before"], bytes(after), rec["pokey"])
    w.close()
    r = subprocess.run([TG.runner(folder), *extra, path], cwd=ROOT, capture_output=True, text=True)
    os.remove(os.path.join(ROOT, path))
    return r


class BoardInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_app_board"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_app_sequences.py"), "--quick", "--out", OUT], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.sets = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith("core_app_board.") and f.endswith(".vec"))
        cls.seqs = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith("seq_core_app_board.") and f.endswith(".vec"))
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_ten_sets_equal_in_c(self):
        self.assertEqual(len(self.sets), 10)
        for cc, folder in self.folders:
            for f in self.sets:
                r = TG.run(folder, os.path.join(OUT, f))
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, f, r.stdout))
                m = re.search(r": (\d+) calls of '[^']+': (\d+) equal, 0 different", r.stdout)
                self.assertTrue(m, r.stdout)
                self.assertEqual(m.group(1), m.group(2))

    def test_the_sequences_equal_in_chain_mode(self):
        self.assertEqual(len(self.seqs), 2)
        for cc, folder in self.folders:
            for f in self.seqs:
                r = subprocess.run([TG.runner(folder), "--chain", os.path.join(OUT, f)], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, f, r.stdout))
                m = re.search(r"chain mode: (\d+) frames run from the state the C had made itself, in (\d+) runs \(longest (\d+) frames\)", r.stdout)
                self.assertTrue(m, r.stdout)
                self.assertGreater(int(m.group(1)), 800)
                self.assertIn(int(m.group(3)), (140, 200))

    def test_a_changed_call_in_the_middle_of_a_sequence_is_caught(self):
        ro = lambda n: sum(V.EXTRA_SIZE[e] for e in V.EXTRA_ORDER[:V.EXTRA_ORDER.index(n)]) + 0x100
        for f, off, what in (("seq_core_app_board.turn_control", 0x23, "TurnSwitchState"), ("seq_core_app_board.level_end_step", 0x27, "LevelEndStep"),
                             ("seq_core_app_board.turn_control", ro("maze") + 0x1ED, "a GAME OVER cell")):
            r = tamper(self.folders[0][1], f, off, 70, ("--chain",))
            self.assertEqual(r.returncode, 1, f + " " + what + ": " + r.stdout)
            self.assertIn("1 different", r.stdout)

    def test_a_changed_byte_is_caught(self):
        ro = lambda n: sum(V.EXTRA_SIZE[e] for e in V.EXTRA_ORDER[:V.EXTRA_ORDER.index(n)]) + 0x100
        for setname, offset, what in (("core_app_board.draw_label_1up", ro("status") + 5, "the 1UP label"), ("core_app_board.clear_ready_text", ro("maze") + 0x1F0, "a READY! cell"),
                                      ("core_app_board.level_end_step", ro("shadow") + 0xC4, "COLOR0"), ("core_app_board.turn_control", 0x23, "a hand-over stage"),
                                      ("core_app_board.compare_high_score", ro("status") + 0x39, "the high score"), ("core_app_board.draw_level_indicator", 0xA0, "ItemColor"),
                                      ("core_app_board.advance_level", 0x24, "WaitState"), ("core_app_board.blink_player_label", 0xFA, "LabelBlink"),
                                      ("core_app_board.draw_ready_screen", 0x2C, "Lives")):
            r = tamper(self.folders[0][1], setname, offset, 3)
            self.assertEqual(r.returncode, 1, setname + " " + what + ": " + r.stdout)
            self.assertIn("1 different", r.stdout)

    def test_every_function_has_its_twin(self):
        with open(os.path.join(ROOT, "src", "c", "app", "board.h"), encoding="utf-8") as fh:
            header = fh.read()
        with open(os.path.join(ROOT, "src", "c", "tests", "world_functions.c"), encoding="utf-8") as fh:
            glue = fh.read()
        for name, fn in inspect.getmembers(AB, inspect.isfunction):
            if fn.__module__ == "core_app_board" and not name.startswith("_"):
                self.assertRegex(header, r"\b%s\(" % name, name + " is not in board.h")
        for f in self.sets:
            self.assertIn('"%s"' % f[:-4], glue, f + " has no entry in the runner's table")


if __name__ == "__main__":
    unittest.main()
