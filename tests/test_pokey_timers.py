"""Tests of tools/pokey_timers.py: the fire rules read from the debugger's .pokey output (docs/22-sound.md, OPEN-VERIFICATION.md OV-13).  Run:  python -I tests/test_pokey_timers.py
The rules themselves were validated against 4,091 live .pokey dumps (16,364 channel readings, all exact): python -I tools/analyze_ghost_sweep.py --validate-timers <trace>.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import pokey_timers as PT  # noqa: E402

PH = 26


class Timers(unittest.TestCase):
    def test_before_any_write_the_period_is_28(self):
        t = PT.Timer([(5000, 0)], PH)
        self.assertEqual(t.pending(0), 26)
        self.assertEqual(t.pending(26), 54)                 # strictly after
        self.assertEqual(t.fires(0, 120), [26, 54, 82, 110])
        self.assertEqual(t.count(110) - t.count(26), 3)     # before the first write every grid point is a fire: 54, 82, 110

    def test_a_write_changes_only_the_reload_at_the_pending_fire(self):
        t = PT.Timer([(1000, 10)], PH)
        # the pending fire at the write (grid point after 1000) still comes at 1006 and reloads with the NEW value: 1006 + 11 x 28
        self.assertEqual(t.pending(1000), 1006)
        self.assertEqual(t.fires(1000, 2000), [1006, 1314, 1622, 1930])

    def test_second_write_does_not_move_the_pending_fire(self):
        t = PT.Timer([(1000, 10), (1100, 3)], PH)
        self.assertEqual(t.pending(1100), 1314)              # fire 1006 is past; 1314 was scheduled with the old value and stays
        self.assertEqual(t.fires(1000, 1500), [1006, 1314, 1426])      # at 1314 the reload uses AUDF = 3: 1314 + 4 x 28
        self.assertEqual(t.pending(1314), 1426)

    def test_fires_are_on_the_grid_and_counts_match(self):
        t = PT.Timer([(1000, 10), (1100, 3), (2000, 0), (2100, 7)], PH)
        fs = t.fires(1000, 6000)
        self.assertTrue(all((f - PH) % PT.TICK == 0 for f in fs))
        n0 = t.count(999)
        self.assertEqual(t.count(5999) - n0, len(fs))

    def test_a_write_on_the_cycle_of_a_fire_comes_after_the_fire(self):
        # AUDF = 0 (period 28) until a write of 125 exactly on a fire cycle: that fire still reloads with 0, so the next one is 28 cycles later; fires(), count() and pending() must agree, whatever `a` is
        t = PT.Timer([(100, 0), (1006 + 28 * 3, 125)], PH)
        c = 1006 + 28 * 3
        self.assertEqual(t.pending(c), c + 28)
        for a in (c - 100, c - 28, c - 1, c, c + 1, c + 20):
            fs = t.fires(a, c + 300)
            self.assertEqual(fs, [f for f in t.fires(c - 200, c + 300) if f >= a], a)
            self.assertEqual(len(fs), t.count(c + 299) - t.count(a - 1), a)
        self.assertIn(c + 28, t.fires(c - 28, c + 300))
        self.assertEqual(t.fires(c, c + 28 + 126 * 28 + 1)[:3], [c, c + 28, c + 28 + 126 * 28])

    def test_a_fire_on_the_cycle_of_a_write_is_not_an_edge_but_stays_a_fire(self):
        c = 1006 + 28 * 3
        t = PT.Timer([(100, 0), (c, 125), (c + 5000, 3)], PH)
        self.assertEqual(t.coinc, [c])
        self.assertIn(c, t.fires(c - 100, c + 100))
        self.assertNotIn(c, t.edges(c - 100, c + 100))
        self.assertEqual(t.edges(c - 100, c + 100), [f for f in t.fires(c - 100, c + 100) if f != c])
        self.assertEqual(t.count(c + 99) - t.edge_count(c + 99), 1)
        self.assertEqual(t.count(c - 1), t.edge_count(c - 1))
        # a write that does not meet a fire changes nothing
        t2 = PT.Timer([(100, 0), (c + 3, 125)], PH)
        self.assertEqual(t2.coinc, [])
        self.assertEqual(t2.edges(0, 5000), t2.fires(0, 5000))

    def test_audf_zero_stretch_counts_every_tick(self):
        t = PT.Timer([(100, 0), (100000, 5)], PH)
        # between the writes the channel fires on every grid point (period 28); count() does not iterate, fires() does: they must agree
        n = t.count(99999) - t.count(100)
        self.assertEqual(n, len(t.fires(101, 100000)))
        self.assertEqual(n, len([c for c in range(26, 100000, 28) if 101 <= c < 100000]))
        self.assertEqual(t.fires(100, 400), [c for c in range(26, 400, 28) if c >= 100])

    def test_audctl_change_drops_the_coincident_fire(self):
        """OV-42c: a write that CHANGES AUDCTL (UpdateTimerCounter + FlushDeferredTimerEvents of all timers) gives no edge to a fire on its cycle, like a changing AUDF write."""
        t = PT.Timer([(1000, 1)], PH)
        c = t.fires(0, 400)[3]
        t2 = PT.Timer([(1000, 1)], PH, ctl_changes=[c])
        self.assertIn(c, t.edges(0, 400))
        self.assertNotIn(c, t2.edges(0, 400))
        self.assertEqual(t2.fires(0, 400), t.fires(0, 400))              # the timer itself keeps its schedule
        self.assertEqual(t.edge_count(400) - t2.edge_count(400), 1)
        t3 = PT.Timer([(1000, 1)], PH, ctl_changes=[c + 1])               # off the fire's cycle: nothing dropped
        self.assertEqual(t3.edges(0, 400), t.edges(0, 400))


if __name__ == "__main__":
    unittest.main()
