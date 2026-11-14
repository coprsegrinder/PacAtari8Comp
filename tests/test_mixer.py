"""Tests of the POKEY mixer model: Altirra's non-linear mix table, the AC coupling and the output clamp, and of the controlled-measurement program of tools/mixer_test.py (docs/22-sound.md, OPEN-VERIFICATION.md OV-13b).
Run:  python -I tests/test_mixer.py
The model itself was checked against Altirra's real audio: 18 tone configurations, 29 channel readings, RMS error 0.8% (analysis/evidence-mixer-test.txt).
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_ghost_sweep as G  # noqa: E402
import disasm6502 as D  # noqa: E402
import mixer_test as M  # noqa: E402


def units(*vols):
    """level in volume units for channels that all have their output high with the given volumes"""
    n0 = sum(v & 1 for v in vols)
    n1 = sum((v >> 1) & 1 for v in vols)
    n23 = sum(((v >> 2) & 1) + 2 * ((v >> 3) & 1) for v in vols)
    return float(G.altirra_level(np.array(n0), np.array(n1), np.array(n23)))


class Curve(unittest.TestCase):
    def test_single_channels_up_to_volume_8_are_linear(self):
        self.assertAlmostEqual(units(8), 8.0, places=9)
        self.assertAlmostEqual(units(4), 4.0, places=9)
        # the bit weights are uneven: volume 1 is 0.857 of the nominal unit, volume 2 is 1.857/2 ... (0.12 / 0.14, 0.26 / 0.14)
        self.assertAlmostEqual(units(1), 0.12 / 0.56 * 4, places=9)
        self.assertAlmostEqual(units(2), 0.26 / 0.56 * 4, places=9)

    def test_saturation_from_two_channels_on(self):
        lin = 16.0
        self.assertLess(units(8, 8), lin)
        self.assertAlmostEqual(units(8, 8) / lin, 0.920, delta=0.003)           # measured 0.916-0.921 (evidence-mixer-test.txt)
        self.assertAlmostEqual(units(8, 8, 8) / 24.0, 0.803, delta=0.005)       # level with all three high (the measured fundamentals are 0.81-0.82: a different quantity)
        self.assertAlmostEqual(units(15) / units(8), 1.725, delta=0.003)       # measured 1.725 (a single channel at volume 15 already saturates)

    def test_monotonic(self):
        x = np.linspace(0, 1.2, 400)
        y = G.altirra_level(x * 0 + 0, x * 0, x / G.BIT_LEVELS[2])
        self.assertTrue(np.all(np.diff(y) > 0))
        self.assertTrue(np.allclose(y[:20], x[:20] / G.UNIT, rtol=1e-9))     # linear below the threshold 0.14


class Chain(unittest.TestCase):
    def test_ac_coupling_step_decays_with_the_time_constant(self):
        n = int(0.02 * M.RATE_HC)
        y = M.ac_couple(np.concatenate([np.zeros(10), np.ones(n)]))
        k_tau = 10 + int(M.TAU * M.RATE_HC)
        self.assertAlmostEqual(y[10 + 1], 1.0, delta=0.01)
        self.assertAlmostEqual(y[k_tau] / y[11], np.exp(-1), delta=0.01)

    def test_predicted_ratios_match_the_measurements(self):
        # relative amplitude of channel 1's fundamental against channel 1 alone at volume 8, Altirra chain (with the output clamp), against the real audio (analysis/evidence-mixer-test.txt)
        ref = M.predicted_amps((8, 0, 0), "altirra")[1]
        for cfg, ch, measured in (((8, 8, 0), 1, 0.918), ((8, 8, 8), 1, 0.810), ((15, 15, 0), 1, 1.341), ((15, 15, 15), 1, 0.977)):
            r = M.predicted_amps(cfg, "altirra")[ch] / ref
            self.assertAlmostEqual(r, measured, delta=0.03, msg=str(cfg))

    def test_the_linear_sum_is_clearly_wrong_where_the_real_mixer_saturates(self):
        ref = M.predicted_amps((8, 0, 0), "linear")[1]
        self.assertAlmostEqual(M.predicted_amps((8, 8, 8), "linear")[1] / ref, 1.0, delta=0.01)    # measured 0.81


class Program(unittest.TestCase):
    def test_program_disassembles_as_intended_and_the_table_is_terminated(self):
        code, table = M.program()
        data, base, a, lines = bytes(code), 0x600, 0x600, []
        while a < base + len(data):
            n, mn, mode, op = D.decode(data, base, a)
            lines.append((a, mn))
            a += n
        self.assertEqual(lines[0], (0x600, "sei"))
        self.assertEqual(a, base + len(data))                                  # no instruction is cut off
        self.assertEqual(lines[-1][1], "jmp")
        self.assertEqual(len(table), 10 * len(M.CONFIGS) + 1)
        self.assertEqual(table[-1], 0)
        self.assertEqual(table[:10], [M.FRAMES, M.AUDF[1], 0xA0, 0, 0, M.AUDF[3], 0xA0, M.AUDF[4], 0xA0, 0])
        # the branch to `done` lands on the final block
        self.assertEqual(code[0x0F] + 0x10, 0x36)

    def test_every_configuration_uses_pure_tones_of_the_stated_volume(self):
        code, table = M.program()
        for i, (v1, v3, v4) in enumerate(M.CONFIGS):
            e = table[i * 10:(i + 1) * 10]
            self.assertEqual((e[2], e[6], e[8]), (0xA0 | v1, 0xA0 | v3, 0xA0 | v4))

    def test_tones_have_no_common_harmonic_below_5_khz(self):
        f = {ch: M.RATE_HC / (2 * (M.AUDF[ch] + 1)) for ch in (1, 3, 4)}
        for odd1 in range(1, 20, 2):
            for odd3 in range(1, 20, 2):
                self.assertGreater(abs(odd1 * f[1] - odd3 * f[3]), 3.0)


if __name__ == "__main__":
    unittest.main()
