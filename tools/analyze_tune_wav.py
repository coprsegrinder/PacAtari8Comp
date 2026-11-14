"""Measures a RECORDING of the start tune (Altirra: Record > Record Audio..., docs/21) and compares it with the ROM model.
Usage:  python -I tools/analyze_tune_wav.py <recording.wav> [--start SECONDS] [--summary-file out.txt]
Exit code 1 if a check fails.

What it does (no listening; everything is measured):
  1. Reads a PCM/float WAV (any channel count, 8/16/24/32 bit), mixes it to mono.
  2. Builds the expected tune from the ROM tables (tools/render_start_tune.py) at the recording's sample rate.
  3. Finds where the tune starts and fits the step length (nominal 4 frames = 66.76 ms) by maximising the spectral
     similarity of all 64 steps to the model.
  4. Per step: silent when the model is silent; cosine similarity of the spectrum to the model step (and whether the
     right step is the best match among all 64); for every voice that should sound, the measured pitch against
     the pitch the ROM table gives (in cents).
  5. Level of voice 1 against voice 2 where both sound (information only: Altirra's mixing is not linear).
Limits: it proves that the recording has the notes and timing the ROM tables say. It cannot say whether it sounds right.
"""
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_start_tune as R  # noqa: E402

STEP_S = R.STEP_S
LO_HZ, HI_HZ = 80.0, 3000.0
SEG_A, SEG_B = 0.15, 0.90          # part of each step that is analysed (the register writes happen at the start of a step)
NFFT = 8192
COS_MIN = 0.80                     # minimum spectral similarity of a step to the model
CENTS_MAX = 70.0                   # maximum pitch error (a semitone is 100)
SILENT_REL = 0.08                  # a silent step must have RMS below this fraction of the typical audible step
PERIOD_TOL = 0.01                  # step length may differ from the nominal by 1 %


def load_wav(path):
    """Minimal RIFF reader -> (mono float32 array in -1..1, rate)."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    pos, fmt, raw = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            tag, ch, rate, _, _, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:
                tag = struct.unpack("<H", body[24:26])[0]
            fmt = (tag, ch, rate, bits)
        elif cid == b"data":
            raw = body if size <= len(data) - pos - 8 else data[pos + 8:]
            break
        pos += 8 + size + (size & 1)
    if fmt is None or raw is None:
        raise ValueError("fmt or data chunk missing")
    tag, ch, rate, bits = fmt
    if tag == 1 and bits == 8:
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128.0) / 128.0
    elif tag == 1 and bits == 16:
        x = np.frombuffer(raw[:len(raw) // 2 * 2], "<i2").astype(np.float32) / 32768.0
    elif tag == 1 and bits == 24:
        n = len(raw) // 3
        b = np.frombuffer(raw[:n * 3], np.uint8).reshape(n, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        x = v.astype(np.float32) / (1 << 23)
    elif tag == 1 and bits == 32:
        x = np.frombuffer(raw[:len(raw) // 4 * 4], "<i4").astype(np.float32) / 2147483648.0
    elif tag == 3 and bits == 32:
        x = np.frombuffer(raw[:len(raw) // 4 * 4], "<f4").astype(np.float32)
    else:
        raise ValueError("unsupported WAV format tag=%d bits=%d" % (tag, bits))
    x = x[:len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
    return x - np.median(x), rate


class Spec:
    """Magnitude spectra of the analysed part of step i for a given signal and (t0, period)."""

    def __init__(self, x, rate):
        self.x, self.rate = x, rate
        self.freqs = np.fft.rfftfreq(NFFT, 1.0 / rate)
        self.band = (self.freqs >= LO_HZ) & (self.freqs <= HI_HZ)

    def seg(self, t0, period, i):
        a = int(round((t0 + (i + SEG_A) * period) * self.rate))
        b = int(round((t0 + (i + SEG_B) * period) * self.rate))
        if a < 0 or b > len(self.x) or b - a < 64:
            return None
        s = self.x[a:b]
        return s * np.hanning(len(s))

    def mag(self, t0, period, i):
        s = self.seg(t0, period, i)
        if s is None:
            return None, 0.0
        return np.abs(np.fft.rfft(s, NFFT)), float(np.sqrt(np.mean(self.x[int(round((t0 + (i + SEG_A) * period) * self.rate)):int(round((t0 + (i + SEG_B) * period) * self.rate))] ** 2)))


def cos(a, b, band=None):
    if band is not None:
        a, b = a[band], b[band]
    a, b = np.sqrt(a), np.sqrt(b)
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d > 0 else 0.0


def peak_near(spec, mag, f, tol=0.06):
    """Interpolated peak frequency and its height relative to the median of the band, within +-6 % of f."""
    fr = spec.freqs
    m = (fr >= f * (1 - tol)) & (fr <= f * (1 + tol))
    if not m.any():
        return None, 0.0
    idx = np.where(m)[0]
    k = idx[int(np.argmax(mag[idx]))]
    if 0 < k < len(mag) - 1 and mag[k - 1] > 0 and mag[k + 1] > 0 and mag[k] > 0:
        a, b, c = np.log(mag[k - 1]), np.log(mag[k]), np.log(mag[k + 1])
        den = a - 2 * b + c
        d = 0.5 * (a - c) / den if den != 0 else 0.0
    else:
        d = 0.0
    fpk = (k + d) * spec.rate / NFFT
    med = float(np.median(mag[spec.band])) + 1e-12
    return float(fpk), float(mag[k] / med)


def analyze(x, rate, start=0.0):
    """Returns a dict with the fit, the per-step rows and the problems."""
    ref, t1, t2 = R.render(rate)
    ref = np.array(ref, np.float32)
    rs, ss = Spec(ref, rate), Spec(x, rate)
    P0 = STEP_S
    freq = lambda f: 0.0 if f == 0 else R.BASE / (2.0 * (f + 1))
    # model spectra per step (reference timing is exact: t0 = 0, nominal period)
    mm = [rs.mag(0.0, P0, i) for i in range(64)]
    mspec = [m[0] for m in mm]
    mrms = np.array([m[1] for m in mm])
    audible = mrms > 0.05 * mrms.max()
    # onset: first time the 5 ms envelope exceeds 10 % of the peak after `start`
    env = np.convolve(np.abs(x), np.ones(max(1, int(0.005 * rate))) / max(1, int(0.005 * rate)), "same")
    s0 = int(start * rate)
    thr = 0.10 * float(np.percentile(env[s0:], 99.9)) if len(env) > s0 else 0
    above = np.where(env[s0:] > thr)[0]
    if len(above) == 0:
        return dict(error="no sound above the threshold in the recording")
    onset = (above[0] + s0) / rate
    # typical level of an audible step (from the model timing in the recording is unknown yet: use the loudest 5 % of 10 ms blocks)
    blk = max(1, int(0.010 * rate))
    nb = len(x) // blk
    lv = np.sqrt(np.mean(x[:nb * blk].reshape(nb, blk) ** 2, axis=1))
    typ_level = float(np.percentile(lv[lv > 0], 90)) if (lv > 0).any() else 1.0
    silent_idx = [i for i in range(64) if not audible[i]]

    def fit_score(t0, P):
        """Mean spectral similarity of the audible steps minus a penalty for sound inside the silent steps."""
        tot, n = 0.0, 0
        for i in range(64):
            if not audible[i]:
                continue
            m, _ = ss.mag(t0, P, i)
            if m is None:
                return None
            tot += cos(m, mspec[i], ss.band)
            n += 1
        pen = 0.0
        for i in silent_idx:
            m, rms = ss.mag(t0, P, i)
            if m is None:
                return None
            pen += min(1.0, rms / typ_level)
        return tot / n - (pen / max(1, len(silent_idx)))

    best = None
    for scale in np.arange(0.990, 1.0105, 0.002):
        P = P0 * scale
        for t0 in np.arange(onset - 1.2 * P, onset + 0.3 * P, P / 20.0):
            sc = fit_score(t0, P)
            if sc is not None and (best is None or sc > best[0]):
                best = (sc, t0, P)
    if best is None:
        return dict(error="the recording is shorter than the tune after the detected start")
    # fine search around the coarse optimum
    _, c0, cP = best
    for scale in np.arange(cP / P0 - 0.002, cP / P0 + 0.00201, 0.0005):
        P = P0 * scale
        for t0 in np.arange(c0 - P / 20.0, c0 + P / 20.0 + 1e-9, P / 100.0):
            sc = fit_score(t0, P)
            if sc is not None and sc > best[0]:
                best = (sc, t0, P)
    score, t0, P = best
    rows, problems = [], []
    rms_rec = []
    for i in range(64):
        m, rms = ss.mag(t0, P, i)
        rms_rec.append(rms)
    typical = float(np.median([r for r, a in zip(rms_rec, audible) if a])) or 1e-9
    ratios_rec, ratios_mod = [], []
    for i in range(64):
        m, rms = ss.mag(t0, P, i)
        f1, f2 = freq(t1[i]), freq(t2[i])
        row = dict(i=i, f1=f1, f2=f2, rms=rms / typical)
        if not audible[i]:
            row["kind"] = "silent"
            row["ok"] = rms < SILENT_REL * typical
            if not row["ok"]:
                problems.append("step %d should be silent but has level %.2f of a typical step" % (i, rms / typical))
        else:
            c = cos(m, mspec[i], ss.band)
            others = [cos(m, mspec[j], ss.band) for j in range(64) if audible[j]]
            row.update(kind="tone", cos=c, best_other=max(others), pitch=[])
            ok = c >= COS_MIN and c >= max(others) - 0.03
            for v, f in ((1, f1), (2, f2)):
                if f > 0:
                    fp, h = peak_near(ss, m, f)
                    cents = 1200.0 * np.log2(fp / f) if fp else None
                    row["pitch"].append((v, f, fp, cents, h))
                    if fp is None or h < 4.0 or abs(cents) > CENTS_MAX:
                        ok = False
                        problems.append("step %d voice %d: expected %.1f Hz, measured %s (peak %.1fx the noise)" % (i, v, f, "%.1f Hz (%+.0f cents)" % (fp, cents) if fp else "nothing", h))
            if f1 > 0 and f2 > 0:
                a1, a2 = peak_near(ss, m, f1)[1], peak_near(ss, m, f2)[1]
                b1, b2 = peak_near(rs, mspec[i], f1)[1], peak_near(rs, mspec[i], f2)[1]
                if a2 > 0 and b2 > 0:
                    ratios_rec.append(a1 / a2)
                    ratios_mod.append(b1 / b2)
            row["ok"] = ok
            if c < COS_MIN or c < max(others) - 0.03:
                problems.append("step %d: spectrum similarity %.2f to the model, best match among the 64 steps %.2f" % (i, c, max(others)))
        rows.append(row)
    if abs(P / P0 - 1) > PERIOD_TOL:
        problems.append("step length %.2f ms differs by %.2f %% from the nominal 4 frames" % (P * 1000, (P / P0 - 1) * 100))
    return dict(score=score, t0=t0, P=P, P0=P0, onset=onset, rows=rows, problems=problems,
                level=(float(np.median(ratios_rec)) if ratios_rec else None, float(np.median(ratios_mod)) if ratios_mod else None),
                tail_rms=float(np.sqrt(np.mean(x[int((t0 + 64 * P + 0.1) * rate):] ** 2))) / typical if len(x) > int((t0 + 64 * P + 0.1) * rate) + 100 else None,
                duration=len(x) / rate)


def report(res, rate, out):
    P = lambda *a: out.append(" ".join(str(x) for x in a))
    if "error" in res:
        P("ERROR:", res["error"])
        return
    P("Recording: %.2f s at %d Hz.  First sound at %.3f s; the tune is fitted to start at %.3f s (fit score = mean similarity of the audible steps minus the share of sound inside the silent steps: %.3f)." % (res["duration"], rate, res["onset"], res["t0"], res["score"]))
    P("Step length: %.2f ms measured, %.2f ms nominal (4 frames at the frame rate of the video standard, 59.9227 Hz NTSC) -> %+.2f %%;  tune length %.2f s." % (res["P"] * 1000, res["P0"] * 1000, (res["P"] / res["P0"] - 1) * 100, 64 * res["P"]))
    P("\nStep  kind    model Hz (voice1 / voice2)   measured Hz (cents)            similarity  level  result")
    for r in res["rows"]:
        if r["kind"] == "silent":
            P("%3d   silent  -                           -                              -           %.2f   %s" % (r["i"], r["rms"], "ok" if r["ok"] else "NOT SILENT"))
            continue
        ms = "  ".join("v%d %.0f (%+.0f)" % (v, fp, c) if fp else "v%d none" % v for (v, f, fp, c, h) in r["pitch"])
        P("%3d   tone    %-7s / %-7s            %-30s %.2f        %.2f   %s" % (r["i"], "%.0f" % r["f1"] if r["f1"] else "rest", "%.0f" % r["f2"] if r["f2"] else "rest", ms, r["cos"], r["rms"], "ok" if r["ok"] else "FAIL"))
    t = [r for r in res["rows"] if r["kind"] == "tone"]
    cents = [abs(p[3]) for r in t for p in r["pitch"] if p[3] is not None]
    P("\nPitch: %d voice-steps measured, mean error %.1f cents, worst %.1f cents (limit %.0f; a semitone is 100)." % (len(cents), np.mean(cents) if cents else 0, max(cents) if cents else 0, CENTS_MAX))
    P("Steps: %d audible ok %d, silent ok %d of %d." % (len(t), sum(1 for r in t if r["ok"]), sum(1 for r in res["rows"] if r["kind"] == "silent" and r["ok"]), 64))
    if res["level"][0] is not None:
        P("Level of voice 1 against voice 2 where both sound (peak heights, median): recording %.2f, model %.2f  (information only: the emulator's mixing is not linear)." % res["level"])
    if res["tail_rms"] is not None:
        P("After the 64 steps: level %.2f of a typical step." % res["tail_rms"])
    P("\nPROBLEMS:", "none" if not res["problems"] else "")
    for p in res["problems"]:
        P("  " + p)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    path = args[0]
    start = float(args[args.index("--start") + 1]) if "--start" in args else 0.0
    summ = args[args.index("--summary-file") + 1] if "--summary-file" in args else None
    x, rate = load_wav(path)
    res = analyze(x, rate, start)
    out = []
    report(res, rate, out)
    text = "\n".join(out)
    print(text)
    if summ:
        with open(summ, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if ("error" in res or res["problems"]) else 0


if __name__ == "__main__":
    sys.exit(main())
