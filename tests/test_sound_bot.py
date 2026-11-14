"""Tests of the OV-46 tools: the clock-ratio probe (tools/probe_wave_drift.py) must recover a known drift, and the generated bot harness (tools/altirra_sound_bot2.cmd) must keep its promises:
it only reads game memory (no memory write except the bot's own table at $5000-$76FF, the STICK0 shadow $0278 and the CONSOL/STRIG shadows) and it contains no invulnerability or score poke.  Run: python -I tests/test_sound_bot.py"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Probe(unittest.TestCase):
    def test_recovers_drift(self):
        rate, secs = 44100, 400
        rng = np.random.default_rng(1)
        n = rate * secs
        xm = np.convolve(rng.standard_normal(n), np.ones(6) / 6, mode="same")      # a band-limited signal
        slope = 0.006                                                                  # the recording runs 0.006 samples per second late
        t = np.arange(n)
        xr = np.interp(t + slope * t / rate, t, xm)                                   # xr[i] = xm[i + lag(i)] with lag growing linearly... sign checked below
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.npz")
            np.savez_compressed(p, xm=xm.astype(np.float32), xr=xr.astype(np.float32), rate=rate)
            out = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "probe_wave_drift.py"), p], capture_output=True, text=True, check=True).stdout
        m = re.search(r"--rate-ppm (\S+)", out)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(abs(float(m.group(1))), slope / rate * 1e6, delta=0.01)
        self.assertIn("residual max", out)


class Harness(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "tools", "altirra_sound_bot2.cmd"), encoding="utf-8") as fh:
            self.text = fh.read()
        self.lines = [l for l in self.text.split("\n") if l and not l.startswith("#")]

    def test_no_aids(self):
        self.assertNotIn("$a936", self.text.lower())                     # the invulnerability skip of the aided sessions
        self.assertNotRegex(self.text, r"bp -n a923")
        for l in self.lines:
            for m in re.finditer(r"\beb\s+(\$?[0-9a-fA-F]+)", l):
                a = m.group(1).lstrip("$").lower()
                v = int(a, 16)
                self.assertTrue(v in (0x278, 0x284, 0x285) or 0x5000 <= v <= 0x76FF, "write outside the bot's own memory: %s" % l[:80])

    def test_table_inside_free_ram(self):
        addrs = [int(m.group(1), 16) for l in self.lines for m in [re.match(r'bp -n a537 "eb ([0-9a-f]{4}) ', l)] if m]
        self.assertEqual(min(addrs), 0x5000)
        self.assertLess(max(addrs), 0x7710)
        self.assertEqual(len(addrs), 179)


class TableAccess(unittest.TestCase):
    def run_tool(self, lines):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "l.txt")
            with open(p, "w") as fh:
                fh.write(chr(10).join(lines) + chr(10))
            return subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "analyze_table_access.py"), p], capture_output=True, text=True)

    def base(self):
        return ["NEWGAME f=458"] + ["TBLW a=$%04X v=$00 pc=$A537 f=458" % (0x5000 + i) for i in range(10000)] + ["TBLW a=$5000 v=$00 pc=$F140 f=12"]

    def test_clean_log_passes(self):
        r = self.run_tool(self.base())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_game_write_fails(self):
        r = self.run_tool(self.base() + ["TBLW a=$5123 v=$01 pc=$B3DE f=900"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT ALLOWED", r.stdout)

    def test_game_read_fails(self):
        r = self.run_tool(self.base() + ["TBLR a=$5123 pc=$A800 f=900"])
        self.assertEqual(r.returncode, 1)


class Ratio(unittest.TestCase):
    def test_default_is_the_half_colour_burst_clock(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import analyze_full_waveform as F
        want = (1789772.5 - 315e6 / 88 / 2) / (315e6 / 88 / 2) * 1e6
        self.assertAlmostEqual(F.AUDIO_RATIO_PPM_NTSC, want, delta=0.0005)


if __name__ == "__main__":
    unittest.main()
