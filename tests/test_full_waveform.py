"""Tests of tools/analyze_full_waveform.py on synthetic register histories (docs/22-sound.md, OPEN-VERIFICATION.md OV-14).  Run:  python -I tests/test_full_waveform.py
The tool itself was checked against Altirra's real audio: whole recordings of the game, 99.9-100% of all 50 ms windows at correlation >= 0.90 (97-98% before the OV-14d fix) (analysis/evidence-fullwave-*.txt).
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_full_waveform as F  # noqa: E402
import analyze_ghost_sweep as G  # noqa: E402
import pokey_noise as PN  # noqa: E402
import pokey_timers as PT  # noqa: E402


def writes(*items):
    return sorted((c, r, v, 0) for (c, r, v) in items)


class Clock(unittest.TestCase):
    def test_cpu_clock_is_the_exact_ntsc_value(self):
        self.assertAlmostEqual(G.CPU, 1789772.7272727, places=3)               # 1,789,773 would drift by one audio sample in 150 s
        drift_samples = 150.0 * (1789773.0 - G.CPU) / G.CPU * 44100.0
        self.assertGreater(drift_samples, 0.9)


class Runs(unittest.TestCase):
    def test_tone_runs_follow_the_audc_modes(self):
        m = G.Model(writes((1000, 7, 0xA8), (5000, 7, 0xA4), (9000, 7, 0x00), (12000, 7, 0xA1), (15000, 7, 0x10)))
        self.assertEqual(F.tone_runs(m, 4, 20000), [(1000, 9000), (12000, 15000)])
        self.assertEqual(F.tone_runs(m, 3, 20000), [])                         # channel 3 never plays

    def test_run_events_toggle_at_every_edge_and_flip_complements(self):
        w0, w1 = 900000, 903000
        m = G.Model(writes((w0 - 20, 6, 10), (w0, 7, 0xA8), (w1, 7, 0x00)))
        t0, s0 = F.run_events(m, 4, w0, w1, 0)
        t1, s1 = F.run_events(m, 4, w0, w1, 1)
        self.assertEqual(t0, t1)
        self.assertTrue(all(a != b for a, b in zip(s0[:-1], s1[:-1])))             # the whole run complemented (the final 0 is silence)
        self.assertEqual(s0[-1], 0)
        body = s0[:-1]
        self.assertTrue(all(a != b for a, b in zip(body, body[1:])))               # a tone toggles at every edge

    def test_start_state_is_the_noise_bit_xor_the_pair_constant_not_the_fire_parity(self):
        # OV-14d: the state at the start of a run does not depend on how many fires the channel has had since reset (that parity belongs to the sweep model's constant, not to a state);
        # it is the noise bit XOR 1 for channels 3/4 and XOR 0 for channels 1/2 (output = flip-flop XOR the high-pass flip-flop at 1).  Measured: 896 of 896 controlled starts (tools/start_state_test.py).
        import pokey_noise as PNm
        for k, pol in ((1, 0), (2, 0), (3, 1), (4, 1)):
            for shift in (0, 28 * 5):                                         # moves the tone start by 5 fires: the fire-count parity changes, the noise bit may too
                w0 = 900000 + shift
                m = G.Model(writes((w0 - 20, 2 * (k - 1) + 1 - 1, 10), (w0, 2 * (k - 1) + 1, 0xA4), (w0 + 3000, 2 * (k - 1) + 1, 0x00)))
                v, _ = PNm.noise_state_before(m, k, w0)
                t, st = F.run_events(m, k, w0, w0 + 3000, 0)
                self.assertEqual(st[0], v ^ pol)
                n_before = (PNm.ecount(m.timers[k], w0 - 1) or 0)
                self.assertEqual(st[0], v ^ pol)                                # independent of n_before's parity
                self.assertIsNotNone(n_before)

    def test_a_write_on_a_fire_removes_that_edge_from_the_run(self):
        # AUDF of channel 4 changes on the very cycle of a fire: that fire gives no edge, so the run has one toggle fewer than fires
        w0 = 900000
        pre = G.Model(writes((w0 - 20, 6, 10), (w0, 7, 0xA8)))
        fire = pre.timers[4].fires(w0 + 1000, w0 + 20000)[3]
        m = G.Model(writes((w0 - 20, 6, 10), (w0, 7, 0xA8), (fire, 6, 11), (fire + 5000, 7, 0x00)))
        self.assertIn(fire, m.timers[4].fires(fire - 1, fire + 1))
        self.assertNotIn(fire, PN.edges(m.timers[4], fire - 1, fire + 1))
        t, s = F.run_events(m, 4, w0, fire + 5000, 0)
        self.assertEqual(len(t), 2 + len(PN.edges(m.timers[4], w0, fire + 5000)))
        self.assertEqual(len(t), 2 + len(m.timers[4].fires(w0, fire + 5000)) - 1)
        # an unchanged rewrite of AUDF on a fire does nothing
        m2 = G.Model(writes((w0 - 20, 6, 10), (w0, 7, 0xA8), (fire, 6, 10), (fire + 5000, 7, 0x00)))
        self.assertEqual(m2.timers[4].coinc, [])


class Mix(unittest.TestCase):
    def test_general_levels_mixes_with_the_altirra_curve(self):
        w0 = 900000
        m = G.Model(writes((w0 - 20, 0, 10), (w0, 1, 0xA8), (w0 - 20, 4, 13), (w0, 5, 0xA8), (w0 + 4000, 1, 0), (w0 + 4000, 5, 0)))
        ev = {k: F.channel_events(m, k, w0 + 8000) for k in (1, 2, 3, 4)}
        bps, tot = F.general_levels(m, w0, w0 + 4000, ev)
        vals = sorted(set(np.round(tot, 6)))
        self.assertEqual(vals[0], 0.0)
        # (different pitches, so that both are sometimes high) two channels of volume 8 both high = the saturated two-channel level (0.92 of the linear 16 units), one high = 8 units
        self.assertTrue(any(abs(v - 8.0) < 1e-6 for v in vals))
        self.assertTrue(any(abs(v / 16.0 - 0.920) < 0.003 for v in vals))


class Filter(unittest.TestCase):
    def test_band_keeps_the_pass_band_and_removes_the_rest(self):
        rate = 44100
        t = np.arange(rate * 2) / rate
        keep, drop_lo, drop_hi = np.sin(2 * np.pi * 1000 * t), np.sin(2 * np.pi * 20 * t), np.sin(2 * np.pi * 15000 * t)
        y = F.band(keep + drop_lo + drop_hi, rate)
        self.assertLess(float(np.max(np.abs(y - keep)[2000:-2000])), 0.02)

    def test_ac_coupling_attenuates_low_frequencies_like_a_one_pole_high_pass(self):
        rate = 44100
        t = np.arange(rate * 2) / rate
        for f, gain in ((100.0, 0.853), (1000.0, 0.9999)):
            x = np.sin(2 * np.pi * f * t)
            y = F.band(x, rate, lo=1.0, hi=20000.0, ac=True)
            g = float(np.sqrt(np.mean(y[4000:-4000] ** 2)) / np.sqrt(np.mean(x[4000:-4000] ** 2)))
            z1 = np.exp(-2j * np.pi * f / G.HALF_CYCLE_RATE)             # Altirra's two discrete one-pole stages (OV-44)
            expect = 1.0
            for c in (np.exp(-1.0 / (63920.0 * G.AC_TAU)), 1.0 - 0.00063413100049954767):
                expect *= abs((1 - z1) / (1 - c * z1))
            self.assertAlmostEqual(g, expect, delta=0.002)
            self.assertAlmostEqual(g, gain, delta=0.01)


if __name__ == "__main__":
    unittest.main()
