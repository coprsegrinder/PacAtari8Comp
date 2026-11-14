"""Tests of the waveform model of tools/analyze_ghost_sweep.py on synthetic register histories with known answers (docs/22-sound.md, OPEN-VERIFICATION.md OV-13).  Run:  python -I tests/test_ghost_sweep_model.py
The model itself was checked against Altirra's real audio: 87 ghost-eaten sweeps in four recordings (analysis/evidence-ghost-sweep-*.txt).
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_ghost_sweep as G  # noqa: E402


def writes(*items):
    """items: (cycle, register 0-8, value) -> the (cycle, reg, value, pc) tuples of a parsed trace"""
    return sorted((c, r, v, 0) for (c, r, v) in items)


def level_at(bps, total, c):
    return total[np.searchsorted(bps, c, side="right") - 1]


class Model(unittest.TestCase):
    def test_single_tone_toggles_at_every_fire_and_the_constant_inverts_it(self):
        w = writes((1000, 6, 10), (1010, 7, 0xA8))                    # channel 4: AUDF = 10 (period 11 ticks = 308 cycles), pure tone, volume 8
        m = G.Model(w)
        fires = m.timers[4].fires(5000, 12000)
        for c4 in (0, 1):
            bps, total = m.mixed(5000, 12000, {1: 0, 3: 0, 4: c4}, 0, True, 1)
            levels = [level_at(bps, total, f + 1) for f in fires]
            self.assertEqual(set(levels), {0.0, 8.0})
            self.assertTrue(all(a != b for a, b in zip(levels, levels[1:])), "the level must change at every fire")
            if c4 == 0:
                first = levels
        bps0, t0 = m.mixed(5000, 12000, {1: 0, 3: 0, 4: 0}, 0, True, 1)
        bps1, t1 = m.mixed(5000, 12000, {1: 0, 3: 0, 4: 1}, 0, True, 1)
        for f in fires:
            self.assertEqual(level_at(bps0, t0, f + 1) + level_at(bps1, t1, f + 1), 8.0)      # the other polarity is the complement

    def test_period_follows_the_audf_at_the_fire(self):
        w = writes((1000, 6, 10), (1010, 7, 0xA8), (3000, 6, 3))
        m = G.Model(w)
        fires = m.timers[4].fires(1000, 8000)
        gaps = [b - a for a, b in zip(fires, fires[1:])]
        self.assertIn(11 * 28, gaps)
        self.assertIn(4 * 28, gaps)                                   # after the first fire past the write at 3000 the period is 4 ticks
        k = gaps.index(4 * 28)
        self.assertTrue(all(g == 11 * 28 for g in gaps[:k - 1]))

    def test_high_pass_channel_with_a_locked_partner_is_constant(self):
        # channel 1 and channel 3 run in lock-step (same AUDF, same phase): the latch follows channel 1 at every channel-3 fire, so channel 1 XOR latch is constant (0),
        # and the audible output is the high-pass polarity constant times the volume of channel 1.
        w = writes((1000, 0, 10), (1000, 4, 10), (1010, 1, 0xA8), (1010, 8, 0x84))
        m = G.Model(w)
        for hpc in (0, 1):
            bps, total = m.mixed(6000, 14000, {1: 0, 3: 0, 4: 0}, 0, True, hpc)
            inside = [level_at(bps, total, c) for c in range(6200, 13800, 97)]
            self.assertEqual(set(inside), {8.0 * hpc})
        # without the filter channel 1 is an ordinary tone
        bps, total = m.mixed(6000, 14000, {1: 0, 3: 0, 4: 0}, 0, False, 0)
        self.assertEqual({level_at(bps, total, c) for c in range(6200, 13800, 97)}, {0.0, 8.0})

    def test_volume_zero_and_other_distortions_are_silent(self):
        w = writes((1000, 6, 10), (1010, 7, 0x00))
        m = G.Model(w)
        bps, total = m.mixed(5000, 9000, {1: 0, 3: 0, 4: 0}, 0, True, 1)
        self.assertEqual(float(np.max(total)), 0.0)
        w = writes((1000, 6, 10), (1010, 7, 0x28))                    # distortion 001 (poly): not a pure tone, not modelled -> silent in this model
        m = G.Model(w)
        bps, total = m.mixed(5000, 9000, {1: 0, 3: 0, 4: 0}, 0, True, 1)
        self.assertEqual(float(np.max(total)), 0.0)


if __name__ == "__main__":
    unittest.main()
