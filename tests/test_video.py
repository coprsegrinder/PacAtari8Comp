"""tools/video.py: the NTSC defaults every earlier session used stay unchanged, PAL (OV-42) has its own constants, and the SKCTL zero point is read from a trace.
Run:  python -I tests/test_video.py"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")


def run(code, pal):
    env = dict(os.environ)
    env.pop("PACMAN_VIDEO", None)
    if pal:
        env["PACMAN_VIDEO"] = "pal"
    return subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r)\n%s" % (TOOLS, code)], env=env, capture_output=True, text=True, check=True).stdout.strip()


class VideoConstants(unittest.TestCase):
    def test_ntsc_default(self):
        out = run("import video as V, pokey_noise as PN, analyze_ghost_sweep as G\nprint(V.PAL, V.FRAME_CYC, round(V.CPU, 3), round(V.FRAME_HZ, 4), G.PHASE, PN.T0)", False)
        self.assertEqual(out, "False 29868 1789772.727 59.9228 26 678973")

    def test_pal(self):
        out = run("import video as V, analyze_ghost_sweep as G\nprint(V.PAL, V.FRAME_CYC, V.CPU, round(V.FRAME_HZ, 4), round(G.HALF_CYCLE_RATE, 2))", True)
        self.assertEqual(out, "True 35568 1773447.0 49.8607 63337.39")

    def test_skctl_t0(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.txt")
            with open(p, "w") as fh:
                fh.write("SNDW a=$D20F v=$00 pc=$F280 f=3 vp=9 hp=14\nSNDW a=$D20F v=$03 pc=$E955 f=22 vp=191 hp=103\nSNDW a=$D20F v=$03 pc=$E955 f=30 vp=1 hp=1\n")
            out = run("import video as V\nprint(V.skctl_t0(%r))" % p, False)
            self.assertEqual(out, str(22 * 29868 + 191 * 114 + 103))
            out = run("import video as V\nprint(V.skctl_t0(%r))" % p, True)
            self.assertEqual(out, str(22 * 35568 + 191 * 114 + 103))
            with open(p, "w") as fh:
                fh.write("SNDW a=$D200 v=$03 pc=$E955 f=22 vp=191 hp=103\n")
            self.assertEqual(run("import video as V\nprint(V.skctl_t0(%r))" % p, False), "None")


if __name__ == "__main__":
    unittest.main()
