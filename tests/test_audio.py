"""Stage 80c (docs/51, docs/22): the audio of the C port.
 * the C POKEY model (src/c/audio/pokey.c) renders Altirra's recordings from the register writes with their cycles: every 50 ms window of four recordings (a whole game's sounds, the ghost-eaten sweeps
   with the high-pass pair included) has a correlation of at least 0.90 with the recording (the check of docs/22), and equals the Python model that docs/22 verified (correlation >= 0.999 in every window);
 * the port's front end gives the writes of a frame their cycles from the write clock (the core logs no cycles): the waveform has the pitch, level and timing of each frame but not its phase, so the
   windows are compared by their spectra (>= 96 % have a spectrum correlation of 0.90 with the recording; the others are ghost-eaten sweeps, whose loudness depends on the phase between three channels);
 * the checks can fail: a model with the noise counters started at another cycle, one with a changed AUDF and one with shifted writes are caught.
The recordings and traces are local evidence (analysis/*.wav, analysis/raw-logs); without them the tests are skipped.  The pure C tests (pitch, level, mixer, front end) are `ctest audio_selftest`."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import test_c_ghost as TG  # noqa: E402

A = os.path.join(ROOT, "analysis")
EVENTS2 = (os.path.join(A, "sound-events2-recorded.wav"), os.path.join(A, "raw-logs", "sound-events2.txt"))
NATURAL = (os.path.join(A, "sound-natural-recorded.wav"), os.path.join(A, "raw-logs", "sound-natural.txt"))
HP = (os.path.join(A, "sound-hp-recorded.wav"), os.path.join(A, "raw-logs", "sound-hp-recorded.txt"))


def have(pair):
    return all(os.path.exists(p) for p in pair)


class Audio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")
        global CA
        import check_audio_c as CA
        cls.exe = {cc: os.path.join(f, "tests", "audio_check" + (".exe" if os.name == "nt" else "")) for cc, f in cls.folders}

    def run_check(self, pair, cc="clang", **kw):
        return CA.main([pair[0], pair[1], "--exe", self.exe[cc]] + kw.pop("extra", []), quiet=True, **kw)

    def test_exact_timing_reproduces_the_recordings(self):
        for pair in (EVENTS2, NATURAL):
            if not have(pair):
                self.skipTest("no recording " + pair[0])
        for cc, _ in self.folders:
            for pair in (EVENTS2, NATURAL):
                r = self.run_check(pair, cc)
                self.assertGreater(r["n"], 800)
                self.assertEqual(r["rec_frac"], 1.0, "%s %s: windows with a correlation below 0.90 (min %.3f)" % (cc, os.path.basename(pair[0]), r["rec_min"]))
                self.assertGreater(r["rec_min"], 0.95)
                self.assertGreater(r["py_min"], 0.99, "the C model equals the Python model of docs/22 (the rule for the polarity of a run against the fit)")
                self.assertTrue(0.99 < r["ratio_median"] < 1.01, r["ratio_median"])        # the level, from Altirra's own constants

    def test_the_ghost_eaten_sweeps_and_the_high_pass_pair(self):
        if not have(HP):
            self.skipTest("no recording " + HP[0])
        r = self.run_check(HP)
        self.assertGreater(r["n"], 3500)
        self.assertEqual(r["rec_frac"], 1.0, "min correlation %.3f" % r["rec_min"])
        self.assertGreater(r["py_median"], 0.9999)               # the Python model fits the polarity of a run to the recording, the C model uses the rule: they differ in a few windows
        self.assertGreater(r["py_ge99"], 0.99)

    def test_the_front_end_with_the_write_clock_has_the_spectrum_of_the_recording(self):
        if not have(EVENTS2):
            self.skipTest("no recording")
        for cc, _ in self.folders:
            r = self.run_check(EVENTS2, cc, extra=["--rule"])
            self.assertGreaterEqual(r["spec_frac"], 0.96, "%s: windows with a spectrum correlation of 0.90: %.3f" % (cc, r["spec_frac"]))
            self.assertTrue(0.99 < r["ratio_median"] < 1.01 or r["ratio_median"] == 0.0, r["ratio_median"])

    def test_the_checks_can_fail(self):
        if not have(NATURAL):
            self.skipTest("no recording")
        good = self.run_check(NATURAL)
        self.assertEqual(good["rec_frac"], 1.0)
        # the noise counters started at another cycle: the polarity of tone runs differs
        bad = self.run_check(NATURAL, noise_delta=7)
        self.assertLess(bad["rec_frac"], 0.97, "another start of the noise counters must be caught")

        def audf_plus_one(sndw):
            return [(c, r, v + 1 if r == 2 and v < 255 else v, pc) for (c, r, v, pc) in sndw]
        bad = self.run_check(NATURAL, mutate=audf_plus_one)
        self.assertLess(bad["rec_frac"], 0.6, "a channel one AUDF step off must be caught")

        def later(sndw):
            return [(c + 20000, r, v, pc) for (c, r, v, pc) in sndw]
        bad = self.run_check(NATURAL, mutate=later)
        self.assertLess(bad["rec_frac"], 0.6, "every write 11 ms late must be caught")


if __name__ == "__main__":
    unittest.main()
