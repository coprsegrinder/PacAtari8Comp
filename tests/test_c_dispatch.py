"""Stage 79c (docs/51): the frame dispatcher in C (src/c/app/dispatch.c) against the vector sets of tools/core_app_frame.py (stage 78c, which equal the ROM class by class and in stories).
1. The quick sets of check_app_frame (build/t79c/: FrameDispatch and the handler for the 15 classes and for states with several flags at once) run by the C runner built with clang and gcc: every call equal.
2. The stories (the copyright screen into the title, the start tune into play, the level end, the hand-over, a death) as sequence sets, run in chain mode from the state the C itself made: equal; a changed call in
   the middle of a story is caught.
3. Negative controls: a changed byte of the after-state in the title memory, the status rows, the shadows, GameState, the countdown timer, WaitTimer or ATRACT is caught; every function of core_app_frame.py has its C twin."""
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
import core_app_frame as AF  # noqa: E402
import test_c_board as TB  # noqa: E402
import test_c_ghost as TG  # noqa: E402
import vecfmt as V  # noqa: E402

OUT = os.path.join("build", "t79c")


class DispatchInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_vectors.py"), "--quick", "--out", OUT, "--only", "check_app_frame"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        r = subprocess.run([sys.executable, "-I", os.path.join("tools", "make_app_sequences.py"), "--quick", "--out", OUT], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.sets = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith("core_app_frame.") and f.endswith(".vec"))
        cls.seqs = [f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith("seq_core_app_frame.") and f.endswith(".vec")]
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def test_the_two_sets_equal_in_c(self):
        self.assertEqual(len(self.sets), 2)
        for cc, folder in self.folders:
            for f in self.sets:
                r = TG.run(folder, os.path.join(OUT, f))
                self.assertEqual(r.returncode, 0, "%s %s: %s" % (cc, f, r.stdout))
                m = re.search(r": (\d+) calls of '[^']+': (\d+) equal, 0 different", r.stdout)
                self.assertTrue(m, r.stdout)
                self.assertEqual(m.group(1), m.group(2))
                self.assertGreater(int(m.group(1)), 1000)

    def test_the_stories_equal_in_chain_mode(self):
        self.assertEqual(len(self.seqs), 1)
        for cc, folder in self.folders:
            r = subprocess.run([TG.runner(folder), "--chain", os.path.join(OUT, self.seqs[0])], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, "%s: %s" % (cc, r.stdout))
            m = re.search(r"chain mode: (\d+) frames run from the state the C had made itself, in (\d+) runs \(longest (\d+) frames\)", r.stdout)
            self.assertTrue(m, r.stdout)
            self.assertGreater(int(m.group(1)), 1500)
            self.assertEqual(int(m.group(3)), 520)                      # the start tune story

    def test_a_changed_call_in_the_middle_of_a_story_is_caught(self):
        ro = lambda n: sum(V.EXTRA_SIZE[e] for e in V.EXTRA_ORDER[:V.EXTRA_ORDER.index(n)]) + 0x100
        r = TB.tamper(self.folders[0][1], self.seqs[0][:-4], 0xA3, 150, ("--chain",), directory=OUT)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("1 different", r.stdout)

    def test_a_changed_byte_is_caught(self):
        ro = lambda n: sum(V.EXTRA_SIZE[e] for e in V.EXTRA_ORDER[:V.EXTRA_ORDER.index(n)]) + 0x100
        for setname, offset, what in (("core_app_frame.frame_dispatch", ro("title") + 0x90, "the title text"), ("core_app_frame.frame_dispatch", ro("status") + 0x2E, "the score line"),
                                      ("core_app_frame.frame_dispatch", ro("shadow") + 0x30, "SDLSTL"), ("core_app_frame.frame_dispatch", 0x19, "GameState"),
                                      ("core_app_frame.vbi_handler", 0x1E, "CountdownTimer"), ("core_app_frame.vbi_handler", 0x25, "WaitTimer"), ("core_app_frame.vbi_handler", 0x4D, "ATRACT"),
                                      ("core_app_frame.vbi_handler", 0x45, "KeyDebounce")):
            r = TB.tamper(self.folders[0][1], setname, offset, 3, directory=OUT)
            self.assertEqual(r.returncode, 1, setname + " " + what + ": " + r.stdout)
            self.assertIn("1 different", r.stdout)

    def test_every_function_has_its_twin(self):
        with open(os.path.join(ROOT, "src", "c", "app", "dispatch.h"), encoding="utf-8") as fh:
            header = fh.read()
        with open(os.path.join(ROOT, "src", "c", "tests", "world_functions.c"), encoding="utf-8") as fh:
            glue = fh.read()
        for name, fn in inspect.getmembers(AF, inspect.isfunction):
            if fn.__module__ == "core_app_frame":
                c_name = {"_wait_state": "wait_state", "_tail": "clear_scores_tail"}.get(name, name)
                if name in ("_wait_state", "_tail"):
                    continue                                              # file-local in C
                self.assertRegex(header, r"\b%s\(" % c_name, name + " is not in dispatch.h")
        for f in self.sets:
            self.assertIn('"%s"' % f[:-4], glue, f + " has no entry in the runner's table")


if __name__ == "__main__":
    unittest.main()
