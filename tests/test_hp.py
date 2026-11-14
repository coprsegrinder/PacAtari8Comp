"""Tests of the high-pass channel pair pieces: the alias-free renderer, the latch-timing hooks, and the controlled-test program of tools/hp_test.py (docs/22-sound.md, OPEN-VERIFICATION.md OV-13d).
Run:  python -I tests/test_hp.py
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_ghost_sweep as G  # noqa: E402
import disasm6502 as D  # noqa: E402
import hp_test as H  # noqa: E402


def writes(*items):
    return sorted((c, r, v, 0) for (c, r, v) in items)


class Render(unittest.TestCase):
    def test_band_limited_render_matches_the_box_average_on_a_clean_square_wave(self):
        G.CPU = 315e6 / 88 / 2
        rate = 44100.0
        step = G.CPU / rate
        per = int(G.CPU / 440 / 2)
        bps = np.arange(0, int(G.CPU), per).astype(float)
        lev = (np.arange(len(bps)) % 2).astype(float) * 8
        a = G.bandpass(G.render(bps, lev, 0.0, 44100, step), rate)
        b = G.bandpass(G.render_bl(bps, lev, 0.0, 44100, step, ac=False), rate)
        m = slice(2000, -2000)
        self.assertGreater(float(np.dot(a[m], b[m]) / np.linalg.norm(a[m]) / np.linalg.norm(b[m])), 0.995)
        self.assertAlmostEqual(float(np.std(b[m]) / np.std(a[m])), 1.0, delta=0.01)

    def test_band_limited_render_has_no_energy_outside_the_band(self):
        G.CPU = 315e6 / 88 / 2
        rate = 44100.0
        step = G.CPU / rate
        bps = np.arange(0, int(G.CPU * 0.5), 29).astype(float)                    # a very dense step train (aliases badly in a box average)
        lev = ((np.arange(len(bps)) * 7) % 3).astype(float)
        y = G.render_bl(bps, lev, 0.0, 22050, step, ac=False)
        F = np.abs(np.fft.rfft(y))
        f = np.fft.rfftfreq(len(y), 1 / rate)
        self.assertLess(float(F[(f < 90) | (f > 5100)].max()), 1e-6 * float(F.max()) + 1e-9)


class Latch(unittest.TestCase):
    def setUp(self):
        # channel 1 and channel 3 at the same pitch: tone, AUDCTL = $84
        self.w = writes((1000, 0, 10), (1000, 4, 10), (1010, 1, 0xA8), (1010, 5, 0xA0), (1010, 8, 0x84))

    def test_hp_dt_moves_only_the_latch_updates(self):
        # unequal periods (10 and 13): the audible channel-1 signal is a pulse train; moving the latch by -56 cycles (2 ticks) moves the pulse ends and nothing else
        w = writes((1000, 0, 10), (1000, 4, 13), (1010, 1, 0xA8), (1010, 5, 0xA0), (1010, 8, 0x84))
        m = G.Model(w)
        try:
            G.HP_DT = 0.0
            b0, t0 = m.mixed(6000, 30000, {1: 0, 3: 0, 4: 0}, 1, True, 1)
            G.HP_DT = -56.0
            b1, t1 = m.mixed(6000, 30000, {1: 0, 3: 0, 4: 0}, 1, True, 1)
        finally:
            G.HP_DT = 0.0
        self.assertTrue(np.array_equal(b0, b1))                          # channel 4 idles at AUDF 0 and fires on every tick, so every grid point is a breakpoint anyway
        diff = np.flatnonzero(t0 != t1)
        self.assertGreater(len(diff), 5)                                  # the pulses end 2 ticks earlier: some levels change
        self.assertLess(len(diff), 0.5 * len(t0))                         # ... but only around the latch updates (pulses are a few ticks wide, so a 2-tick move touches many levels)
        self.assertTrue(set(np.round(t0, 6)) == set(np.round(t1, 6)))      # the same levels occur: only their timing moved


class Program(unittest.TestCase):
    def test_flush_burst_and_sets(self):
        for name in ("sweep", "pairs", "edges", "replay1", "replay", "hold", "nohp", "bis", "dur", "abs", "abs0", "disp1", "disp2", "volsw", "phase", "uneq"):
            H.ACTIVE["set"] = name
            code, table = H.program()
            self.assertEqual(table[-1], 0, name)
            self.assertEqual(len(table), 10 * len(H.configs()) + 1, name)
            self.assertLessEqual(len(table), 255, name)                          # the program indexes the table with an 8-bit register
            data, a = bytes(code), 0x600
            ops = []
            while a < 0x600 + len(data):
                n, mn, mode, op = D.decode(data, 0x600, a)
                ops.append((a, mn))
                a += n
            self.assertEqual(a, 0x600 + len(data), name)                          # no instruction is cut off
            self.assertIn((0x642, "sta"), ops)                                    # the flush burst: STA $07FF repeated 256 times
        H.ACTIVE["set"] = "sweep"

    def test_hold_set_frames_and_pairs_differences(self):
        H.ACTIVE["set"] = "hold"
        code, table = H.program()
        self.assertEqual([table[10 * i] for i in range(len(H.configs()))], H.HOLD_FRAMES)
        H.ACTIVE["set"] = "pairs"
        self.assertEqual([c[0][1] - c[0][0] for c in H.configs()][:6], [0, 2, 4, 8, -4, -8])
        H.ACTIVE["set"] = "sweep"


class Mixer(unittest.TestCase):
    def test_peakgain_is_the_linear_sum_scaled_by_the_gain_of_the_curve_at_the_peak(self):
        # channel 1 and channel 4 at volume 8 each (AUDCTL = 0): the sum of two squares is linear, scaled by f(0.272)/0.272 = 0.919 (Altirra's saturation curve at the level of both high)
        w = writes((1000, 0, 10), (1000, 6, 13), (1010, 1, 0xA8), (1010, 7, 0xA8), (1010, 8, 0x00))
        m = G.Model(w)
        m.mixer = "linear"
        _, lin = m.mixed(6000, 30000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
        m.mixer = "peakgain"
        _, pg = m.mixed(6000, 30000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
        ratio = pg[lin > 0] / lin[lin > 0]
        self.assertTrue(np.allclose(ratio, ratio[0]))
        x = 2 * 2 * 0.56 / 8.24
        expected = (0.14 + (1 - np.exp(-2.85 * (x - 0.14))) / 2.85) / x
        self.assertAlmostEqual(float(ratio[0]), float(expected), places=6)
        self.assertAlmostEqual(float(expected), 0.919, places=3)

    def test_one_channel_is_not_scaled(self):
        w = writes((1000, 0, 10), (1010, 1, 0xA8), (1010, 8, 0x00))
        m = G.Model(w)
        m.mixer = "linear"
        _, lin = m.mixed(6000, 30000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
        m.mixer = "peakgain"
        _, pg = m.mixed(6000, 30000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
        self.assertTrue(np.allclose(lin, pg))                                  # 0.136 < 0.14: the linear part of the curve


    def test_invtable_indexes_the_table_by_the_channels_that_are_low(self):
        # channels 1 and 4, volume 8, AUDCTL = 0: the levels are 0 (both high), -f(8) (one low) and -f(16) (both low), f = Altirra's curve in volume units; an instantaneous curve on the HIGH channels
        # would give 0, f(8), f(16) with the opposite curvature
        w = writes((1000, 0, 10), (1000, 6, 13), (1010, 1, 0xA8), (1010, 7, 0xA8), (1010, 8, 0x00))
        m = G.Model(w)
        m.mixer = "invtable"
        _, tot = m.mixed(6000, 60000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
        lv = sorted(set(np.round(tot, 4)))
        f8, f16 = float(G.altirra_level(0.0, 0.0, 2.0)), float(G.altirra_level(0.0, 0.0, 4.0))
        self.assertEqual(len(lv), 3)
        self.assertAlmostEqual(lv[2], 0.0, places=4)
        self.assertAlmostEqual(lv[1], -f8, places=3)
        self.assertAlmostEqual(lv[0], -f16, places=3)
        self.assertLess(abs(lv[0] - lv[1]), abs(lv[1] - lv[2]))              # the second step is smaller: saturation toward the "both low" end
        # a volume change of a channel that is HIGH changes nothing
        w2 = writes((1000, 0, 10), (1010, 1, 0xA8), (1010, 8, 0x00), (30000, 1, 0xA4))
        m2 = G.Model(w2)
        m2.mixer = "invtable"
        b, t2 = m2.mixed(6000, 60000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
        hi = t2[np.array([m2.audc[1].at(int(c)) for c in b]) >= 0xA0]
        self.assertTrue(set(np.round(hi, 3)) <= {0.0, round(-float(G.altirra_level(0.0, 0.0, 2.0)), 3), round(-float(G.altirra_level(0.0, 0.0, 1.0)), 3)})

    def test_config_gains_follow_the_table_on_average(self):
        g = G.config_gains([8, 8, 0], 0.5)
        self.assertAlmostEqual(g[0], 0.9193, places=3)
        self.assertAlmostEqual(g[0], g[1], places=9)
        self.assertEqual(g[2], 1.0)
        self.assertAlmostEqual(G.config_gains([8, 8, 8], 0.5)[0], 0.8116, places=3)
        self.assertAlmostEqual(G.config_gains([8, 0, 0], 0.5)[0], 1.0, places=9)             # a lone channel below the saturation threshold is not scaled
        self.assertLess(G.config_gains([15, 1, 0], 0.5)[1], G.config_gains([15, 1, 0], 0.5)[0])

    def test_cfggain_keeps_the_shape_of_the_linear_sum_and_does_not_depend_on_the_phase(self):
        # two channels of equal period and volume 8, in phase and 90 degrees apart: the same scale factor (an instantaneous curve would differ)
        out = []
        for d in (0, 5):
            w = writes((1000, 0, 10), (1000 + 28 * d, 6, 10), (1010, 1, 0xA8), (1010 + 28 * d, 7, 0xA8), (1010, 8, 0x00))
            m = G.Model(w)
            m.mixer = "linear"
            _, lin = m.mixed(6000, 60000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
            m.mixer = "cfggain"
            _, cg = m.mixed(6000, 60000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
            r = cg[lin > 0] / lin[lin > 0]
            self.assertTrue(np.allclose(r, r[0]))
            out.append(float(r[0]))
        self.assertAlmostEqual(out[0], out[1], places=9)
        self.assertAlmostEqual(out[0], 0.9193, places=3)


class Anchor(unittest.TestCase):
    def test_anchor_finds_the_alignment_even_when_the_first_sound_belongs_to_another_row(self):
        # 'bis' set: 15 rows of 72 frames.  The synthetic recording has NO sound in row 0, so the first-sound estimate (first step against the first candidate fire) is wrong by one row (72 frames = 76,800 ticks).
        import pokey_noise as PN
        H.ACTIVE["set"] = "bis"
        cfgs = H.configs()
        base = 1_000_000
        w = []
        ends = []
        for i, cfg in enumerate(cfgs):
            c = base + i * 72 * H.FC
            af = cfg[0]
            w += [(c - 263, 0, af[0], 0x618), (c - 239, 1, 0xA8, 0x618), (c - 131, 4, af[1], 0x618), (c - 108, 5, 0xA0, 0x618), (c - 59, 6, af[2], 0x618), (c - 23, 7, 0xA0, 0x618), (c, 8, 0x84, 0x618)]
            ends.append(c)
        w.sort()
        mod = G.Model(w)
        rate = 44100.0
        step = H.CPU / rate
        c_true = 12345.0 * 28 + 5.0
        fires = []
        for i in range(1, len(cfgs)):
            for k in (1, 3):
                fires += [f + 2 for f in PN.edges(mod.timers[k], ends[i] + int(0.3 * 72 * H.FC), ends[i] + 72 * H.FC)]
        n = int((ends[-1] + 72 * H.FC - c_true) / step) + 10
        x = np.zeros(n)
        sign = 1.0
        for f in sorted(fires):
            idx = int(round((f - c_true) / step))
            x[idx:] += sign * 0.1
            sign = -sign
        got = H.anchor(x, rate, mod, ends)
        self.assertLess(abs(got - c_true), 2 * 28)
        H.ACTIVE["set"] = "sweep"


if __name__ == "__main__":
    unittest.main()
