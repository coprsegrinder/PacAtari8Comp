"""Tests of the sound analyzers themselves (OV-17): tools/analyze_tail_sound.py, tools/analyze_sound_events.py, tools/analyze_p2win.py.  Run:  python -I tests/test_sound_analyzers.py

Part 1 (no data needed): trace parsing, segment building and the tone model of analyze_tail_sound.py, trace parsing of analyze_sound_events.py, on small synthetic traces.
Part 2 (needs the recorded sessions in analysis/; skipped when they are missing): each analyzer must PASS on the real session and must FAIL when the session is damaged in one way:
  sound events : a wrong value in a ghost-eaten write; a missing siren write (on a level trace, which has the dot counter).
  tail sound   : a stretch of the recording silenced (a sound the registers ask for is missing); a stretch resampled 6 % (a wrong note); a tone added where the registers say silence;
                 a missing register write in the trace.
  p2win        : all KEY_OPTION events removed (check E); a high-score write from another PC (check F).
"""
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_sound_events as SE  # noqa: E402
import analyze_tail_sound as T  # noqa: E402
import analyze_tune_wav as W  # noqa: E402

FC = T.FRAME_CYC
TOOLS = os.path.join(ROOT, "tools")
WAV = os.path.join(ROOT, "analysis", "sound-events-recorded.wav")
TRACE = os.path.join(ROOT, "analysis", "raw-logs", "sound-events.txt")
LEVEL_TRACE = os.path.join(ROOT, "analysis", "raw-logs", "sound-level-L12.txt")
P2WIN = os.path.join(ROOT, "analysis", "raw-logs", "p2win.txt")
SUMMARY = os.path.join(ROOT, "analysis", "evidence-sound-events-summary.txt")
HLE_WAV = os.path.join(ROOT, "analysis", "ov42-hle-events.wav")
HLE_TRACE = os.path.join(ROOT, "analysis", "raw-logs", "ov42-hle-events.txt")


def sndw(addr, v, pc, f, vp, hp):
    return "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" % (addr, v, pc, f, vp, hp)


def run(tool, *args):
    r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, tool)] + [str(a) for a in args], capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout


class TailParse(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.p = os.path.join(self.d, "t.txt")

    def write(self, lines):
        with open(self.p, "w") as fh:
            fh.write("\n".join(lines) + "\n")

    def test_parse_trace(self):
        self.write([sndw(0xD200, 0x30, 0xB058, 10, 5, 20),
                    sndw(0xD20B, 0x00, 0xE8A5, 10, 6, 0),              # POTGO: not a sound register
                    "FR f=10 fc=1 t1=5", "FR f=11 fc=1 t1=",          # complete line, then a cut-off one
                    "TUNE f=12 x=0", "GHOST_EATEN f=13", "FOO f=14",
                    sndw(0xD201, 0xA8, 0xB05B, 9, 1, 1)])
        w, ev, last = T.parse_trace(self.p)
        self.assertEqual(w, [(9 * FC + 1 * 114 + 1, 1, 0xA8, 0xB05B), (10 * FC + 5 * 114 + 20, 0, 0x30, 0xB058)])      # sorted by time, POTGO dropped
        self.assertEqual(ev, [(12, "TUNE", 0), (13, "GHOST_EATEN", None)])
        self.assertEqual(last, 10)

    def test_segments_group_merge_and_state(self):
        c = 100 * FC
        w = [(c, 0, 0x30, 1), (c + 5, 1, 0xA8, 2),                        # one change (writes 5 cycles apart)
             (c + 20000, 1, 0xA8, 2),                                      # same state again: merged with the previous segment
             (c + 80000, 1, 0x00, 3)]                                      # the tone is switched off
        segs = T.build_segments(w)
        self.assertEqual(len(segs), 3)
        self.assertEqual(segs[1]["st"][:2], (0x30, 0xA8))
        self.assertEqual(segs[1]["c1"], c + 80000)                         # the state ends at the first write of the next group
        self.assertEqual(segs[2]["st"][:2], (0x30, 0x00))

    def test_expected_tones(self):
        st = [0] * 9
        st[2], st[3] = 0x40, 0xA4                                          # channel 2: pure tone, volume 4
        t, prob = T.expected_tones(tuple(st))
        self.assertEqual(prob, [])
        self.assertEqual(len(t), 1)
        self.assertAlmostEqual(t[0][1], T.BASE / (2 * 65), 6)
        self.assertEqual(t[0][2], 4)
        st[4], st[5] = 0x10, 0x03                                          # channel 3: distortion 0 -> not modelled
        self.assertTrue(T.expected_tones(tuple(st))[1])
        st[5] = 0x1F                                                       # volume-only
        self.assertTrue(any("volume-only" in p for p in T.expected_tones(tuple(st))[1]))
        st = [0] * 9
        st[0], st[1], st[8] = 0x10, 0xA8, 0x84                             # AUDCTL $84: channel 1 high-passed -> returned separately
        t, prob, hp = T.expected_tones(tuple(st), with_hp=True)
        self.assertEqual((t, prob, len(hp)), ([], [], 1))
        st[8] = 0x40                                                       # another AUDCTL bit: reported
        self.assertTrue(T.expected_tones(tuple(st))[1])

    def test_silent_channel_and_rest_give_no_tone(self):
        st = [0] * 9
        st[3] = 0xA0                                                       # volume 0
        st[4], st[5] = 0, 0xA8                                             # AUDF 0: a rest
        self.assertEqual(T.expected_tones(tuple(st)), ([], []))


class EventsParse(unittest.TestCase):
    def test_parse(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "e.txt")
        fr = "FR f=%d fc=1 fd=2 f2=3 e5=4 f7=5 f4=6 lives=3,3 lv=1 p=0 cyc=7 d34=9 d36=0 sl=0 t1=1"
        with open(p, "w") as fh:
            fh.write("\n".join([sndw(0xD200, 0x80, 0xB058, 20, 259, 52),     # vpos 259 >= 240: belongs to the routine of frame 20
                                sndw(0xD200, 0x80, 0xB058, 21, 3, 0),        # early in the next frame: still the routine of frame 20
                                sndw(0xD20F, 3, 0xE000, 21, 3, 1),           # not a register $D200-$D208 -> dropped
                                fr % 20, "FR f=21 fc=1 fd=2", "PELLET f=20", "TUNE f=5 x=0"]) + "\n")
        w, frm, ev = SE.parse(p)
        self.assertEqual([x["rf"] for x in w], [20, 20])
        self.assertEqual(len(w), 2)
        self.assertEqual(list(frm), [20])                                  # the cut-off FR line (no t1=) is ignored
        self.assertEqual(frm[20]["d34"], 9)
        self.assertEqual(frm[20]["lives"], [3, 3])
        self.assertEqual(ev, [("PELLET", 20, None), ("TUNE", 5, 0)])


def save_wav(path, x, rate):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    pcm = np.repeat(pcm[:, None], 2, axis=1).tobytes()
    hdr = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 2, rate, rate * 4, 4, 16) + b"data" + struct.pack("<I", len(pcm))
    with open(path, "wb") as fh:
        fh.write(hdr + pcm)


def mutated_trace(d, name, fn):
    out = os.path.join(d, name)
    with open(TRACE, encoding="utf-8", errors="replace") as fh, open(out, "w", encoding="utf-8") as oh:
        for line in fn(fh):
            oh.write(line)
    return out


@unittest.skipUnless(os.path.exists(TRACE), "recorded session not available")
class EventsOnRealSession(unittest.TestCase):
    def test_pass_and_fail(self):
        d = tempfile.mkdtemp()
        rc, out = run("analyze_sound_events.py", TRACE)
        self.assertEqual(rc, 0, out[-500:])
        self.assertIn("PROBLEMS: none", out)

        def wrong_value(fh):
            done = False
            for line in fh:
                if not done and "pc=$B058" in line and line.startswith("SNDW a=$D200"):
                    line, done = re.sub(r"v=\$[0-9A-F]{2}", "v=$81", line, count=1), True
                yield line
        rc, out = run("analyze_sound_events.py", mutated_trace(d, "wrong.txt", wrong_value))
        self.assertEqual(rc, 1, "a wrong ghost-eaten value must be reported")

    @unittest.skipUnless(os.path.exists(LEVEL_TRACE), "level session not available")
    def test_siren_judged_on_a_trace_with_the_dot_counter(self):
        # sound-events.txt has no dot counter, so the siren is not judged there; the level sessions have it
        d = tempfile.mkdtemp()
        rc, out = run("analyze_sound_events.py", LEVEL_TRACE)
        self.assertEqual(rc, 0, out[-500:])
        self.assertIn("siren: ", out)

        def missing_siren(fh):
            n = 0
            for line in fh:
                if line.startswith("SNDW a=$D202") and "pc=$B546" in line:
                    n += 1
                    if n == 500:
                        continue
                yield line
        out_p = os.path.join(d, "missing.txt")
        with open(LEVEL_TRACE, encoding="utf-8", errors="replace") as fh, open(out_p, "w", encoding="utf-8") as oh:
            for line in missing_siren(fh):
                oh.write(line)
        rc, out = run("analyze_sound_events.py", out_p)
        self.assertEqual(rc, 1, "a missing siren write must be reported")


@unittest.skipUnless(os.path.exists(TRACE) and os.path.exists(WAV), "recorded session not available")
class TailOnRealSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x, cls.rate = W.load_wav(WAV)
        cls.d = tempfile.mkdtemp()

    def judged(self, x, trace=TRACE):
        p = os.path.join(self.d, "m.wav")
        save_wav(p, x, self.rate)
        return run("analyze_tail_sound.py", p, trace)

    def test_unmodified_passes(self):
        rc, out = run("analyze_tail_sound.py", WAV, TRACE)
        self.assertEqual(rc, 0, out[-500:])
        self.assertIn("PROBLEMS: none", out)

    def test_missing_sound_is_reported(self):
        x = np.array(self.x, dtype=np.float64)
        x[int(100 * self.rate):int(101 * self.rate)] = 0.0
        rc, out = self.judged(x)
        self.assertEqual(rc, 1)
        self.assertRegex(out, r"segment at 10[01]\.\d+ s")

    def test_wrong_note_is_reported(self):
        x = np.array(self.x, dtype=np.float64)
        a, b = int(100 * self.rate), int(102 * self.rate)
        x[a:b] = np.interp(np.arange(a, b) * 1.06, np.arange(len(x)), x)       # the same 2 s played 6 % too high
        rc, out = self.judged(x)
        self.assertEqual(rc, 1)
        self.assertRegex(out, r"segment at 10[012]\.\d+ s")

    def test_sound_without_register_is_reported(self):
        # a 440 Hz tone added 2-3 s into the recording, where the registers say silence (before the start tune)
        x = np.array(self.x, dtype=np.float64)
        t = np.arange(int(1.0 * self.rate)) / self.rate
        x[int(2 * self.rate):int(3 * self.rate)] += 0.2 * np.sin(2 * np.pi * 440 * t)
        rc, out = self.judged(x)
        self.assertEqual(rc, 1)

    def test_missing_register_write_is_reported(self):
        n = [0]

        def drop(fh):
            for line in fh:
                if line.startswith("SNDW a=$D202") and "pc=$B546" in line:
                    n[0] += 1
                    if 2000 <= n[0] < 2010:
                        continue
                yield line
        rc, out = self.judged(self.x, mutated_trace(self.d, "t2.txt", drop))
        self.assertEqual(rc, 1)


@unittest.skipUnless(os.path.exists(P2WIN), "recorded session not available")
class P2winOnRealSession(unittest.TestCase):
    def test_pass_and_fail(self):
        d = tempfile.mkdtemp()
        rc, out = run("analyze_p2win.py", P2WIN)
        self.assertEqual((rc, "PROBLEMS: none" in out), (0, True), out[-400:])
        out_p = os.path.join(d, "no_option.txt")
        with open(P2WIN, encoding="utf-8", errors="replace") as fh, open(out_p, "w", encoding="utf-8") as oh:
            for line in fh:
                if not line.startswith("KEY_OPTION"):
                    oh.write(line)
        rc, out = run("analyze_p2win.py", out_p)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)
        out_q = os.path.join(d, "hsw.txt")
        done = False
        with open(P2WIN, encoding="utf-8", errors="replace") as fh, open(out_q, "w", encoding="utf-8") as oh:
            for line in fh:
                m = re.match(r"HSW pc=\$AB3E f=(\d+)", line)
                if m and int(m.group(1)) > 1000 and not done:
                    line, done = line.replace("$AB3E", "$1234"), True
                oh.write(line)
        self.assertTrue(done)
        rc, out = run("analyze_p2win.py", out_q)
        self.assertEqual(rc, 1)


class LagDrift(unittest.TestCase):
    """tools/check_segments_waveform.py (OV-43): the drift measure on synthetic signals."""

    @staticmethod
    def two_voices(f1, f2, n=600, rate=44100, a2=0.3):
        t = np.arange(n) / rate
        return np.sign(np.sin(2 * np.pi * f1 * t)) + a2 * np.sign(np.sin(2 * np.pi * f2 * t + 0.7))

    def test_equal_signals_have_no_drift(self):
        import check_segments_waveform as CS
        a = self.two_voices(400, 1000)
        corr, cents = CS.measure(a, a)
        self.assertGreater(corr, 0.999)
        self.assertLess(abs(cents), 0.5)

    def test_a_single_voice_of_wrong_pitch_fails_the_correlation_gate(self):
        """the drift is descriptive (its lag search covers +-3 samples); a single voice 20 cents off already drops the segment's correlation below the 0.90 gate"""
        import check_segments_waveform as CS
        rate = 44100
        for err_cents in (20.0, -20.0, 40.0):
            t = np.arange(900) / rate
            rec = np.sign(np.sin(2 * np.pi * 400 * 2 ** (err_cents / 1200) * t))
            mod = np.sign(np.sin(2 * np.pi * 400 * t))
            corr, cents = CS.measure(rec, mod)
            self.assertLess(corr, CS.CORR_LIMIT, (err_cents, corr))

    def test_the_drift_follows_the_loud_voice_not_the_weak_one(self):
        """the limit that the shift test exists for: a weak voice of wrong pitch under an exact loud one does not show in the drift"""
        import check_segments_waveform as CS
        rec = self.two_voices(400, 1000 * 2 ** (20 / 1200))
        mod = self.two_voices(400, 1000)
        corr, cents = CS.measure(rec, mod)
        self.assertLess(abs(cents), 4.0)


@unittest.skipUnless(os.path.exists(TRACE) and os.path.exists(WAV) and os.path.exists(SUMMARY), "recorded session not available")
class SegmentsOnRealSession(unittest.TestCase):
    """OV-43: the tool passes the real session (shift test included) and fails when the model's registers are damaged."""

    def test_pass_and_shift_test_sensitivity(self):
        rc, out = run("check_segments_waveform.py", WAV, TRACE, SUMMARY, "--summary-file", os.devnull)
        self.assertEqual(rc, 0, out[-1500:])
        self.assertIn("PROBLEMS: none", out)
        m = re.search(r"unresolved tones\s+(\d+) tested.*?20 cents: (\d+)/(\d+).*?40 cents: (\d+)/(\d+) \(min \+([\d.]+)\)", out)
        self.assertIsNotNone(m, out[-1500:])
        self.assertGreaterEqual(int(m.group(1)), 30)
        self.assertEqual(m.group(2), m.group(3))                       # the true model beats every +-20 cents shift
        self.assertEqual(m.group(4), m.group(5))
        self.assertGreater(float(m.group(6)), 0.004)                   # and by a clear margin at 40 cents

    def test_damaged_registers_fail(self):
        def siren_plus_one(lines):
            n = 0
            for line in lines:
                if line.startswith("SNDW") and "a=$D202" in line and "pc=$B546" in line:
                    n += 1
                    if n % 3 == 0:
                        line = re.sub(r"v=\$([0-9A-F]{2})", lambda m: "v=$%02X" % (int(m.group(1), 16) + 1), line, count=1)
                yield line
        with tempfile.TemporaryDirectory() as d:
            q = mutated_trace(d, "siren_plus_one.txt", siren_plus_one)
            rc, out = run("check_segments_waveform.py", WAV, q, SUMMARY, "--summary-file", os.devnull)
            self.assertEqual(rc, 1, out[-800:])


class DiscreteAc(unittest.TestCase):
    """OV-44: the model's AC coupling is Altirra's pair of discrete one-pole high-pass stages, not the continuous-time form."""

    def test_matches_the_difference_equation(self):
        import analyze_full_waveform as AF
        import analyze_ghost_sweep as G
        rate = 44100.0
        n = 8192
        t = np.arange(n) / rate
        f0 = round(200.0 * n / rate) * rate / n                    # a whole number of cycles in the array
        x = np.sin(2 * np.pi * f0 * t)
        y = AF.band(x, rate, lo=1.0, hi=20000.0, ac=True)
        gain = float(np.sqrt(np.mean(y[n // 4:] ** 2)) / np.sqrt(np.mean(x[n // 4:] ** 2)))
        w = 2 * np.pi * f0 / G.HALF_CYCLE_RATE
        z1 = np.exp(-1j * w)
        expect = 1.0
        for c in (np.exp(-1.0 / (63920.0 * G.AC_TAU)), 1.0 - 0.00063413100049954767):
            expect *= abs((1 - z1) / (1 - c * z1))
        self.assertAlmostEqual(gain, expect, delta=0.002)
        wc = 2 * np.pi * f0 * G.AC_TAU
        self.assertGreater(abs(wc / np.sqrt(1 + wc * wc) - expect), 0.002)      # and it is NOT the continuous-time form (0.36 % apart at 200 Hz)


@unittest.skipUnless(os.path.exists(TRACE) and os.path.exists(WAV), "recorded session not available")
class AbsoluteScaleOnRealSession(unittest.TestCase):
    def test_level_ratio(self):
        rc, out = run("analyze_full_waveform.py", WAV, TRACE, "--absolute-scale", "--summary-file", os.devnull)
        m = re.search(r"RMS ratio model / recording over the windows with correlation >= 0.90: median ([\d.]+)", out)
        self.assertIsNotNone(m, out[-500:])
        self.assertAlmostEqual(float(m.group(1)), 1.0, delta=0.003)            # 0.995 before OV-44 (continuous-time AC coupling), 0.999 with Altirra's discrete stages


@unittest.skipUnless(os.path.exists(HLE_WAV) and os.path.exists(HLE_TRACE), "OV-42 session (built-in OS) not available")
class WaveformOnHleSession(unittest.TestCase):
    """OV-42a: two ghost-eaten sweeps of this session begin inside a channel-1 tone (the first half frame was inverted while the constant of channel 1 was fixed at 0)."""

    def test_every_window_correlates(self):
        rc, out = run("analyze_full_waveform.py", HLE_WAV, HLE_TRACE, "--anchor-samples", 1, "--summary-file", os.devnull)
        m = re.search(r">= 0.90 in (\d+) \(([\d.]+)%\)", out)
        self.assertIsNotNone(m, out[-400:])
        self.assertEqual(m.group(2), "100.0", out[-1500:])


if __name__ == "__main__":
    unittest.main()
