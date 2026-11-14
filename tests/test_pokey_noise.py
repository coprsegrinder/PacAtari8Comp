"""Tests of tools/pokey_noise.py: the start state of a channel's output flip-flop when it enters a pure tone (docs/22-sound.md, OPEN-VERIFICATION.md OV-13a).  Run:  python -I tests/test_pokey_noise.py
The rule itself was checked against Altirra's real audio: 108 of 110 start bits of 55 ghost-eaten sweeps in three independent recordings (analysis/evidence-ghost-sweep-*.txt).
"""
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_ghost_sweep as G  # noqa: E402
import pokey_noise as PN  # noqa: E402


def writes(*items):
    return sorted((c, r, v, 0) for (c, r, v) in items)


class Tables(unittest.TestCase):
    def test_t0_is_the_skctl_write_of_the_boot(self):
        self.assertEqual(PN.T0, 22 * 29868 + 191 * 114 + 103)
        self.assertEqual(PN.T0, 678973)

    def test_polynomial_tables_have_the_maximal_period_and_balance(self):
        self.assertEqual(len(PN.S17), 131071)
        self.assertEqual(int(PN.S17.sum()), 65535)                 # XNOR registers never reach the all-ones state: 2^16 - 1 ones in one period
        self.assertEqual(int(PN.S9.sum()), 255)
        self.assertEqual(int(PN.S5.sum()), 15)
        for s, n in ((PN.S5, 31), (PN.S9, 511)):
            # no shorter period than n: the sequence is not invariant under any rotation by a proper divisor-free shift
            self.assertTrue(all(any(s[(i + d) % n] != s[i] for i in range(n)) for d in range(1, n)))

    def test_indices_follow_the_cycle_and_the_channel(self):
        f = 700000
        self.assertEqual(PN.source_bit("p17", f + 131071, 3), PN.source_bit("p17", f, 3))
        self.assertEqual(PN.source_bit("p9", f + 511, 0), PN.source_bit("p9", f, 0))
        self.assertEqual(PN.poly5_pass(f + 31, 2), PN.poly5_pass(f, 2))
        # channel c is sampled one table position earlier per channel number: fire f of channel c+1 reads the entry of fire f-1 of channel c
        self.assertEqual(PN.source_bit("p17", f, 1), PN.source_bit("p17", f - 1, 0))


def reference_state(model, k, w, delay=PN.AUDIO_DELAY):
    """the flip-flop of channel k before cycle w by applying Altirra's rules at every single fire (None while it has never been set)"""
    st = None
    for f in PN.edges(model.timers[k], 0, w):
        probe = f + delay
        if probe >= w:
            probe = w                                             # the fires of the last `delay` cycles run in the mode written at w
        a = model.audc[k].at(probe)
        ctl = model.ctl.at(probe)
        cn = PN.audcn(a)
        gated = not (cn & 0x80)
        if gated and not PN.poly5_pass(f, k - 1):
            continue
        if cn & 0x20:
            st = None if st is None else st ^ 1
        else:
            st = PN.source_bit("p9" if ctl & 0x80 else "p17", f, k - 1)
    return st


class Walk(unittest.TestCase):
    def test_idle_noise_then_tone_starts_at_the_poly_bit_of_the_last_gated_fire(self):
        w = 900000
        m = G.Model(writes((w, 7, 0xA8)))                          # channel 4 idle (AUDC = 0, AUDF = 0) until the tone is written
        v, kind = PN.noise_state_before(m, 4, w)
        self.assertEqual(kind, "p17")
        last = [f for f in m.timers[4].fires(w - 2000, w - PN.AUDIO_DELAY) if PN.poly5_pass(f, 3)][-1]
        self.assertEqual(v, PN.source_bit("p17", last, 3) ^ (len([f for f in m.timers[4].fires(w - PN.AUDIO_DELAY, w)]) & 1))

    def test_fire_in_the_last_two_cycles_toggles_instead_of_sampling(self):
        # find a write cycle with a fire 1 cycle before it: the flip-flop must then be the inverse of the state without that fire
        base = G.Model(writes())
        fire = [f for f in base.timers[4].fires(900000, 901000)][3]
        m = G.Model(writes((fire + 1, 7, 0xA8)))
        v, _ = PN.noise_state_before(m, 4, fire + 1)
        v0, _ = PN.noise_state_before(m, 4, fire + 1, delay=0)
        self.assertEqual(v, reference_state(m, 4, fire + 1))
        self.assertNotEqual(v, v0)

    def test_a_fire_on_the_cycle_of_an_audf_write_is_not_an_edge(self):
        # (OV-13c / OV-14) find a gated fire whose poly17 bit differs from that of the previous gated fire, write AUDF on exactly that cycle, start the tone 16 cycles later
        base = G.Model(writes())
        fs = base.timers[4].fires(900000, 903000)
        gated = [f for f in fs if PN.poly5_pass(f, 3)]
        pair = next((a, b) for a, b in zip(gated, gated[1:]) if PN.source_bit("p17", a, 3) != PN.source_bit("p17", b, 3) and b - a < 200)
        a, b = pair
        m = G.Model(writes((b, 6, 0x80), (b + 16, 7, 0xA8)))
        v, _ = PN.noise_state_before(m, 4, b + 16)
        self.assertEqual(v, PN.source_bit("p17", a, 3))              # the previous gated fire decides; the fire on the write cycle (value of b) is skipped
        PN.COINCIDENT_FIRE_IS_EDGE = True
        try:
            v2, _ = PN.noise_state_before(m, 4, b + 16)
        finally:
            PN.COINCIDENT_FIRE_IS_EDGE = False
        self.assertEqual(v2, PN.source_bit("p17", b, 3))

    def test_matches_the_fire_by_fire_reference_on_random_histories(self):
        rnd = random.Random(1)
        checked = 0
        for trial in range(60):
            items = []
            t = 1000
            for _ in range(rnd.randint(2, 7)):
                t += rnd.randint(50, 60000)
                items.append((t, 6, rnd.choice([0, 0, 1, 3, 17, 125, 128])))
                t += rnd.randint(0, 40)
                items.append((t, 7, rnd.choice([0x00, 0x10, 0x28, 0x80, 0xA0, 0xA4, 0xA8, 0x00])))
                if rnd.random() < 0.4:
                    t += rnd.randint(0, 40)
                    items.append((t, 8, rnd.choice([0x00, 0x84, 0x80, 0x04])))
            w = t + rnd.randint(1, 70000)
            items.append((w, 7, 0xA8))
            m = G.Model(writes(*items))
            ref = reference_state(m, 4, w)
            v, kind = PN.noise_state_before(m, 4, w)
            if ref is None:
                self.assertIsNone(v)
                continue
            self.assertEqual(v, ref, "trial %d" % trial)
            checked += 1
        self.assertGreater(checked, 40)

    def test_start_constant_includes_the_parity_of_the_fires_and_the_fitted_polarity(self):
        w = 900500
        m = G.Model(writes((w, 7, 0xA8), (w + 6000, 7, 0x00)))
        c = PN.start_constant(m, 4, w - 100, w + 5000)
        v, _ = PN.noise_state_before(m, 4, w)
        par = PN.ecount(m.timers[4], w - 1) & 1
        self.assertEqual(c, v ^ par ^ 1)
        self.assertIsNone(PN.start_constant(G.Model(writes((w, 7, 0x00))), 4, w - 100, w + 5000))     # no tone in the window


if __name__ == "__main__":
    unittest.main()
