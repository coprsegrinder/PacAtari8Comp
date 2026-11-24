"""Stage 80c: the C POKEY model (src/c/audio) against Altirra's real audio, window by window, the way docs/22 checks the Python model (tools/analyze_full_waveform.py, OV-14).
For one recording and its trace of the sound-register writes (every write with its frame, scan line and cycle):
  1. tools/analyze_full_waveform.py is run (the Python model: its time anchor, the clock ratio of the audio path, the scale from Altirra's source, the band-pass and the windows);
  2. the same writes, with the same cycle stamps, go through the C program tests/audio_check (the C model renders PCM at the recording's sample rate from the same origin: the C code does its own
     timers, noise, high-pass pair, mixer table, AC coupling and box resampling; the polarity of every run is the RULE, nothing is fitted);
  3. the C signal is band-passed 100 Hz - 5 kHz like the recording and the Python model, and compared with the recording in windows of 50 ms: normalised correlation at lag 0, RMS ratio; and with the Python model.

With --rule the cycle stamps of the writes are NOT the recorded ones but the ones the port gives them (audio/write_clock.c: the writes of one frame get the measured cycles of their sequence of registers,
the core knowing no cycles; only the frame of each write and the order are taken from the trace): the waveform then matches in pitch, level and timing per frame but not in phase, so the windows are compared by their SPECTRA (the magnitudes of the 100 Hz - 5 kHz bins of a
Hann-windowed 50 ms window, normalised correlation) as well.
Usage: python -I tools/check_audio_c.py RECORDING.wav TRACE.txt [--summary-file out.txt] [--exe path] [--levels out_dir] [--rule]"""
import io
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import analyze_full_waveform as AFW  # noqa: E402
import analyze_ghost_sweep as G  # noqa: E402
import analyze_tail_sound as T  # noqa: E402
import pokey_noise as PN  # noqa: E402

CORR_OK = 0.90
NOISE_T0_NTSC_OSB = 22 * 29868 + 191 * 114 + 103


def run_python_model(wav, trace):
    """tools/analyze_full_waveform.py with its output captured: -> RESULT (c0, step, rate, xr, xm, ...) and the printed text"""
    saved, buf = sys.argv, io.StringIO()
    sys.argv = ["analyze_full_waveform.py", wav, trace, "--absolute-scale"]
    old = sys.stdout
    sys.stdout = buf
    try:
        AFW.main()
    finally:
        sys.stdout, sys.argv = old, saved
    return AFW.RESULT, buf.getvalue()


FRAME_CYC = 29868
WINDOW_SHIFT = 1000                         # the handler of frame f writes in [f * FRAME_CYC - 1000, (f + 1) * FRAME_CYC - 1000) (tools/make_c_write_clock.py)


def write_frames_file(path, sndw):
    """the writes grouped by the frame of the handler that made them, WITHOUT their cycles: "frame reg value" (what the core of the port logs); -> (first frame, last frame)"""
    frames = []
    with open(path, "w", encoding="utf-8") as fh:
        for (c, r, v, pc) in sndw:
            if r <= 8:
                f = (c + WINDOW_SHIFT) // FRAME_CYC
                frames.append(f)
                fh.write("%d %d %d" % (f, r, v) + chr(10))
    return min(frames), max(frames)


def spectral_rows(xr, xc, rate, win_ms=50.0):
    """per window: correlation of the magnitude spectra (100 Hz - 5 kHz, Hann window) and the RMS ratio"""
    wl = int(win_ms / 1000 * rate)
    hann = np.hanning(wl)
    f = np.fft.rfftfreq(wl, 1.0 / rate)
    sel = (f >= 100.0) & (f <= 5000.0)
    rows = []
    for i in range(len(xr) // wl):
        r, m = xr[i * wl:(i + 1) * wl], xc[i * wl:(i + 1) * wl]
        er, em = float(np.sqrt(np.mean(r ** 2))), float(np.sqrt(np.mean(m ** 2)))
        if er < 0.002 and em < 0.002:
            continue
        a, b = np.abs(np.fft.rfft(r * hann))[sel], np.abs(np.fft.rfft(m * hann))[sel]
        cc = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))) if a.any() and b.any() else 0.0
        rows.append((i * win_ms / 1000, cc, em / er if er > 0 else float("inf")))
    return rows


def write_file(path, sndw):
    with open(path, "w", encoding="utf-8") as fh:
        for (c, r, v, pc) in sndw:
            if r <= 8:
                fh.write("%d %d %d\n" % (c, r, v))


def read_floats(path):
    with open(path, "rb") as fh:
        return np.frombuffer(fh.read(), dtype="<f4").astype(np.float64)


def windows(xr, xm, rate, win_ms=50.0):
    wl = int(win_ms / 1000 * rate)
    rows = []
    for i in range(len(xr) // wl):
        a, b = i * wl, (i + 1) * wl
        r, m = xr[a:b], xm[a:b]
        er, em = float(np.sqrt(np.mean(r ** 2))), float(np.sqrt(np.mean(m ** 2)))
        if er < 0.002 and em < 0.002:
            continue
        if i == 0 and er < 0.002:
            continue
        cc = float(np.dot(r, m) / (np.linalg.norm(r) * np.linalg.norm(m))) if er > 0 and em > 0 else 0.0
        rows.append((i * win_ms / 1000, cc, em / er if er > 0 else float("inf")))
    return rows


def main(argv=None, mutate=None, noise_delta=0, quiet=False):
    """mutate(sndw) -> sndw changes the writes that the C model gets (negative controls); noise_delta moves the start of the noise counters"""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(__doc__)
        return 2
    wav, trace = args[0], args[1]
    summary = args[args.index("--summary-file") + 1] if "--summary-file" in args else None
    exe = args[args.index("--exe") + 1] if "--exe" in args else os.path.join(ROOT, "build", "c-clang", "tests", "audio_check" + (".exe" if os.name == "nt" else ""))
    levels_dir = args[args.index("--levels") + 1] if "--levels" in args else None
    res, ptext = run_python_model(wav, trace)
    sndw, _, _ = T.parse_trace(trace)
    if mutate is not None:
        sndw = mutate(sndw)
    t0 = G.V.skctl_t0(trace)
    if t0 is None:
        if G.V.PAL:
            raise SystemExit("PAL trace without the SKCTL write: the noise generators cannot be placed")
        t0 = NOISE_T0_NTSC_OSB                            # a trace that does not log $D20F: the NTSC OS-B machine, as analyze_full_waveform assumes
    phase = (26 + t0 - NOISE_T0_NTSC_OSB) % 28           # the residue of the fire grid (analyze_full_waveform sets G.PHASE the same way)
    work = os.path.join(ROOT, "build", "t80c")
    os.makedirs(work, exist_ok=True)
    rel = lambda p: os.path.relpath(p, ROOT)
    wfile, ofile = os.path.join(work, "writes.txt"), os.path.join(work, "out.f32")
    use_rule = "--rule" in args
    write_file(wfile, sndw)
    ffile = os.path.join(work, "frames.txt")
    first_f, last_f = write_frames_file(ffile, sndw)
    rate, c0, step = res["rate"], res["c0"], res["step"]
    rate_eff = G.CPU / step                                   # the C step is CPU / rate_eff cycles: the same as the Python step (clock ratio of the audio path included)
    cmd = [exe, rel(wfile), rel(ofile), repr(rate_eff), str(int(t0)), str(int(t0) + int(noise_delta)), str(int(phase)), repr(float(c0)), str(int(res["c_end"]))]
    if use_rule:
        last_f = int(res["c_end"] // FRAME_CYC) + 1
        cmd = [exe, "--frames", rel(ffile), rel(ofile), repr(rate_eff), str(first_f), str(last_f), repr(float(c0))]
    elif levels_dir:
        os.makedirs(levels_dir, exist_ok=True)
        cmd.append(rel(os.path.join(levels_dir, "levels.txt")))
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("audio_check failed: " + r.stdout + r.stderr)
    if " 0 samples dropped" not in r.stdout:
        raise SystemExit("the C sample ring overflowed: " + r.stdout)
    y = read_floats(ofile)
    n_use = len(res["xr"])
    y = np.pad(y, (0, max(0, n_use - len(y))))[:n_use]
    xc = AFW.band(y, rate)                                    # 100 Hz - 5 kHz, like the recording and the Python model; the AC coupling is already in the C signal
    rows_rec = windows(res["xr"], xc, rate)
    rows_py = windows(res["xm"], xc, rate)
    cs = np.array([r_[1] for r_ in rows_rec])
    cp = np.array([r_[1] for r_ in rows_py])
    rs = np.array([r_[2] for r_ in rows_rec])
    good = cs >= CORR_OK
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    P("Recording %.2f s, %d samples compared; C model: %s" % (len(res["xr"]) / rate, n_use, r.stdout.strip()))
    P("Windows of 50 ms with sound in either signal: %d" % len(cs))
    rg = rs[good] if good.any() else np.array([0.0])
    P("C model against the RECORDING: correlation median %.4f, 5th percentile %.4f, min %.4f; >= %.2f in %d (%.1f %%); RMS ratio C / recording over the good windows: median %.3f, 5-95 %%: %.3f..%.3f" % (
        np.median(cs), np.percentile(cs, 5), cs.min(), CORR_OK, int(good.sum()), 100.0 * good.mean(), np.median(rg), np.percentile(rg, 5), np.percentile(rg, 95)))
    pg = cp >= CORR_OK
    P("C model against the PYTHON model (docs/22, fitted polarity per run): correlation median %.4f, 5th percentile %.4f; >= %.2f in %d (%.1f %%)" % (np.median(cp), np.percentile(cp, 5), CORR_OK, int(pg.sum()), 100.0 * pg.mean()))
    rows_py_rec = windows(res["xr"], res["xm"], rate)
    cpy = np.array([r_[1] for r_ in rows_py_rec])
    P("(the Python model against the recording: >= %.2f in %.1f %% of %d windows)" % (CORR_OK, 100.0 * (cpy >= CORR_OK).mean(), len(cpy)))
    sp_rows = spectral_rows(res["xr"], xc, rate)
    sc = np.array([r_[1] for r_ in sp_rows])
    P("Spectra of the 50 ms windows (magnitudes, 100 Hz - 5 kHz, phase ignored), C model against the recording: correlation median %.4f, 5th percentile %.4f, min %.4f; >= %.2f in %.1f %% of %d windows" % (
        np.median(sc), np.percentile(sc, 5), sc.min(), CORR_OK, 100.0 * (sc >= CORR_OK).mean(), len(sc)))
    bad = sorted(rows_rec, key=lambda r_: r_[1])[:10]
    P("worst 10 windows against the recording (time s, correlation, RMS ratio): " + "; ".join("%.2f %.3f %.2f" % b for b in bad))
    text = "\n".join(out)
    if not quiet:
        print(text)
    if summary:
        with open(summary, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return {"rec_frac": float(good.mean()), "py_frac": float(pg.mean()), "spec_frac": float((sc >= CORR_OK).mean()), "spec_min": float(sc.min()), "n": len(cs), "ratio_median": float(np.median(rs[good])) if good.any() else 0.0, "py_ge99": float((cp >= 0.99).mean()), "py_median": float(np.median(cp)), "py_min": float(cp.min()), "rec_min": float(cs.min()), "text": text}


if __name__ == "__main__":
    r = main()
    sys.exit(0 if isinstance(r, dict) else r)
