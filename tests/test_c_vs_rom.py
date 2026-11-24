"""Stage 86: the C port against the ROM itself (tools/check_c_vs_rom.py), kept short for the test run: a seeded random game and the first frames of a session are compared frame by frame with the ROM on the
concrete 6502 (clang and gcc), and the comparison is shown to SEE a difference (a corrupted byte of the zero page, the maze, a chip write, the RANDOM count).  The full runs (95,517 frames) are in
analysis/evidence-c-vs-rom-summary.txt.  Needs the owner's ROM (original/Pac-Man.rom), the asset blob and a C build."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import check_c_vs_rom as X  # noqa: E402
import make_rom_fuzz_replays as F  # noqa: E402
import test_c_ghost as TG  # noqa: E402

WORK = os.path.join(ROOT, "build", "t86-test")


def exe(cc):
    f = TG.build(cc)
    return os.path.join(f, "shell", "pacman_a8.exe" if os.name == "nt" else "pacman_a8") if f else None


class CVersusRom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exes = [e for e in (exe("clang"), exe("gcc")) if e and os.path.exists(e)]
        if not cls.exes or not os.path.exists(os.path.join(ROOT, "original", "Pac-Man.rom")) or not os.path.exists(os.path.join(ROOT, "resources", "pack", "assets.pmab")):
            raise unittest.SkipTest("no C build, ROM or asset blob")
        os.makedirs(WORK, exist_ok=True)
        cls.replay = os.path.join(WORK, "fuzz3.pmrp")
        F.make(cls.replay, 3, 1500)

    def test_a_random_game_equals_the_rom_frame_by_frame(self):
        for e in self.exes:
            self.assertTrue(X.run(self.replay, e), e)

    def test_the_comparison_sees_a_difference(self):
        orig = X.read_states
        try:
            for kind, frame in (("zp", 700), ("maze", 900), ("pokey", 800), ("rnd", 600)):
                def rs(path, n, kind=kind, frame=frame):
                    s = orig(path, n)
                    st, log, rr = s[frame]
                    if kind == "zp":
                        st = st[:0x50] + bytes([st[0x50] ^ 1]) + st[0x51:]
                    elif kind == "maze":
                        st = st[:0x300] + bytes([st[0x300] ^ 1]) + st[0x301:]
                    elif kind == "pokey":
                        log = [(0xD200, 1)] + log[1:] if log else [(0xD200, 1)]
                    else:
                        rr += 1
                    s[frame] = (st, log, rr)
                    return s
                X.read_states = rs
                self.assertFalse(X.run(self.replay, self.exes[0], 1000), kind)
        finally:
            X.read_states = orig


if __name__ == "__main__":
    unittest.main()
