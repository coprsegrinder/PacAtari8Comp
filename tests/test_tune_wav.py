"""Tests of tools/analyze_tune_wav.py on synthetic recordings (no emulator needed). Run:  python -I tests/test_tune_wav.py
A correct tune (different sample rate, lead-in silence, stretched step length, noise, stereo 16 bit) must pass;
a tune with a wrong note, a tune with a missing note and silence must be reported.
"""
import os
import struct
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_tune_wav as W  # noqa: E402
import render_start_tune as R  # noqa: E402


def write_wav(path, x, rate, channels=2):
    x = np.clip(x, -1, 1)
    pcm = (np.repeat(x[:, None], channels, axis=1) * 30000).astype("<i2").tobytes()
    hdr = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * 2 * channels, 2 * channels, 16) + b"data" + struct.pack("<I", len(pcm))
    with open(path, "wb") as fh:
        fh.write(hdr + pcm)


def make(rate=48000, lead=0.7, stretch=1.0, noise=0.01, edit=None, seed=1):
    out, t1, t2 = R.render(rate)
    out = np.array(out, np.float32)
    if edit:
        r2 = R
        t1, t2 = list(t1), list(t2)
        edit(t1, t2)
        # re-render with modified tables
        ph, o = {1: 0.0, 2: 0.0}, []
        for n in range(len(out)):
            xx = min(63, int(n / rate / R.STEP_S))
            s = 0.0
            for ch, tbl in ((1, t1), (2, t2)):
                if tbl[xx] == 0:
                    continue
                ph[ch] = (ph[ch] + R.BASE / (2.0 * (tbl[xx] + 1)) / rate) % 1.0
                s += (R.VOL[ch] / 15.0) * (1.0 if ph[ch] < 0.5 else -1.0)
            o.append(s * 0.5)
        out = np.array(o, np.float32)
    if stretch != 1.0:
        n = int(len(out) * stretch)
        out = np.interp(np.linspace(0, len(out) - 1, n), np.arange(len(out)), out).astype(np.float32)
    rng = np.random.default_rng(seed)
    x = np.concatenate([np.zeros(int(lead * rate), np.float32), out, np.zeros(int(0.5 * rate), np.float32)])
    return x + rng.normal(0, noise, len(x)).astype(np.float32)


class Tune(unittest.TestCase):
    def run_file(self, x, rate):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.wav")
            write_wav(p, x, rate)
            y, r = W.load_wav(p)
        self.assertEqual(r, rate)
        return W.analyze(y, r)

    def test_correct_tune_passes(self):
        for rate, lead, stretch in ((48000, 0.7, 1.0), (44100, 1.3, 1.004), (22050, 0.2, 0.997)):
            res = self.run_file(make(rate, lead, stretch), rate)
            self.assertEqual(res["problems"], [], (rate, res["problems"][:3]))
            self.assertAlmostEqual(res["t0"], lead, delta=0.04)
            self.assertAlmostEqual(res["P"] / res["P0"], stretch, delta=0.0025)

    def test_wrong_note_is_reported(self):
        def e(t1, t2):
            t1[5] = 70      # G4 -> a different note (step 5)
        res = self.run_file(make(48000, edit=e), 48000)
        self.assertTrue(any(p.startswith(("step 5:", "step 5 ")) for p in res["problems"]), res["problems"][:5])

    def test_missing_note_is_reported(self):
        def e(t1, t2):
            t2[16] = 0      # bass note of step 16 missing
        res = self.run_file(make(48000, edit=e), 48000)
        self.assertTrue(any(p.startswith(("step 16:", "step 16 ")) for p in res["problems"]), res["problems"][:5])

    def test_wrong_step_length_is_reported(self):
        res = self.run_file(make(48000, stretch=1.03), 48000)
        self.assertTrue(res["problems"])

    def test_silence_is_an_error(self):
        res = self.run_file(np.zeros(48000, np.float32), 48000)
        self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
