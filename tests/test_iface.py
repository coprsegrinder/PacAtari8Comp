"""Stage 67: the external interface - the static list of what the ROM reads from outside, the closure run on the concrete 6502 (small), the negative control, the platform interface of the port, the evidence and the chapter."""
import os
import random
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import algorithm_models as A  # noqa: E402
import check_play as CPL  # noqa: E402
import check_sound as CSO  # noqa: E402
import core_world as W  # noqa: E402
import iface_map as I  # noqa: E402
import output_map as O  # noqa: E402
import platform_iface as PI  # noqa: E402


class Static(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.st = I.static_report()

    def test_every_read_is_a_declared_input(self):
        for s in self.st["reads"]:
            lo, hi = (s["op"], s["op"] + (255 if s["mode"] in ("abx", "aby", "zpx") else 0))
            ok = any(dlo <= s["op"] <= dhi for n, dlo, dhi in I.DECLARED)
            self.assertTrue(ok, "$%04X reads $%04X" % (s["pc"], s["op"]))
        self.assertEqual(len(self.st["reads"]), 35)

    def test_the_declared_inputs_are_all_read(self):
        addrs = {s["op"] for s in self.st["reads"]}
        for n, lo, hi in I.DECLARED:
            self.assertTrue(any(lo <= a <= hi for a in addrs), n)

    def test_control_transfers(self):
        self.assertEqual([(m, op) for pc, m, op in self.st["control_out"]], [("jsr", 0xE45C), ("jmp", 0xE462)])
        self.assertEqual((self.st["indirect_jumps"], self.st["brk"]), (0, 0))
        self.assertEqual(self.st["rti"], [0xA5CD, 0xA5FC])

    def test_no_files_no_serial_no_pia(self):
        for k in ("page3", "pia", "serial", "osrom"):
            self.assertEqual(self.st["refs"][k][0], 0, k)

    def test_the_read_list_agrees_with_stage_57(self):
        import analyze_io as IO
        self.assertEqual({s["pc"] for s in self.st["sites"]}, {s["pc"] for s in IO.sites()})


class Dynamic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = I.run(6, 68)

    def test_reads_stay_in_the_list(self):
        self.assertEqual(self.res["bad_reads"], [])
        self.assertGreater(sum(self.res["reads"].values()), 1000)

    def test_closure(self):
        self.assertEqual(self.res["closure_bad"], [])
        self.assertEqual(sum(n for n, ok in self.res["kinds"].values()), 6 * len(I.KINDS))

    def test_unused_areas_are_untouched(self):
        for (rw, k), v in self.res["cls"].items():
            self.assertNotIn(k, ("OsPage3", "Pia", "SerialData", "OsRom", "HwOther"))

    def test_the_check_can_fail(self):
        """negative control: poison the joystick shadow as well (it is an input) and the result must differ in some runs"""
        base = A.started_machine()
        ys, xs = O.load_junction_lists()
        probe = I.Probe()
        probe.install()
        diff = 0
        try:
            for t in range(40):
                a = I.make_trial("vbi-play", base, random.Random(t), ys, xs)
                b = I.make_trial("vbi-play", base, random.Random(t), ys, xs)
                keep = set(I.DECLARED_ADDRS) - {0x0278, 0x0279}
                I.poison(b, random.Random(t + 1000), keep)
                ra, rb = I.go(a, "vbi-play"), I.go(b, "vbi-play")
                diff += I.snapshot(a, ra) != I.snapshot(b, rb)
        finally:
            probe.remove()
        self.assertGreater(diff, 3)


class PlatformPort(unittest.TestCase):
    def state(self, seed):
        base = A.started_machine()
        rng = random.Random(seed)
        m = A.fresh(base, [0] * 12)
        CSO.sound_setup(m, rng)
        CPL.play_pre(m, rng)
        return W.World().load(m.mem)

    def frames(self, seed, sticks, n=12):
        w = self.state(seed)
        p = PI.ScriptedPlatform(seed=seed, sticks=sticks)
        out = []
        for _ in range(n):
            try:
                f = PI.run_frame(w, p)
            except IndexError:                               # a random state walked the maze pointer out of the maze (not a game state)
                break
            out.append((tuple(f.pokey), tuple(f.maze), tuple(f.status), tuple(f.colours), f.randoms))
        return out, p, w

    def test_deterministic(self):
        a, _, _ = self.frames(11, [0x0F, 0x07, 0x0B, 0x0E, 0x0D])
        b, _, _ = self.frames(11, [0x0F, 0x07, 0x0B, 0x0E, 0x0D])
        self.assertEqual(a, b)
        self.assertGreater(len(a), 3)

    def test_the_inputs_matter_and_come_only_through_the_platform(self):
        differs = 0
        for seed in range(80):
            a, pa, _ = self.frames(seed, [0x0F])
            b, pb, _ = self.frames(seed, [0x0E, 0x0D, 0x0B, 0x07])
            differs += a != b
            for p in (pa, pb):
                self.assertEqual(p.calls["clock"], p.calls["attract"])
        self.assertGreater(differs, 5)

    def test_random_through_the_platform(self):
        used = tot = 0
        for seed in range(30):
            out, p, w = self.frames(seed, [0x0F, 0x0E])
            used += sum(f[4] for f in out)
            tot += p.calls["random"]
        self.assertEqual(used, tot)
        self.assertGreater(used, 0)

    def test_clock_counts_frames(self):
        w = self.state(3)
        p = PI.ScriptedPlatform(seed=1, start_clock=250)
        n = 0
        for _ in range(8):
            try:
                PI.run_frame(w, p)
            except IndexError:
                break
            n += 1
        self.assertGreater(n, 2)
        self.assertEqual(w.RTCLOK2, (250 + n - 1) & 0xFF)          # the clock read at the last frame: it wrapped past 255


class Evidence(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_evidence(self):
        t = self.read("analysis/evidence-iface-summary.txt")
        self.assertIn("static: 133 instructions touch an input or an output register (35 reads, 98 writes)", t)
        self.assertRegex(t, r"0 outside the static list or the declared inputs")
        m = re.search(r"closure: (\d+) random game states .*: (\d+) differences", t)
        self.assertTrue(m)
        self.assertGreaterEqual(int(m.group(1)), 3000)
        self.assertEqual(m.group(2), "0")
        self.assertIn("inputs no run was sensitive to: none", t)

    def test_chapter(self):
        d = self.read("docs/45-external-interface.md")
        for k in ("14 things from the outside", "PCOLR0-3", "OV-69", "The list is closed", "no file, device, serial, network or PIA access", "ScriptedPlatform", "`$B09D`"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
