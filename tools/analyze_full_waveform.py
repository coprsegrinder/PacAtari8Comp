"""The WHOLE recording rendered from the register writes and compared with Altirra's real audio, window by window (docs/22-sound.md, OPEN-VERIFICATION.md OV-14).  Usage:
  python -I tools/analyze_full_waveform.py <recording.wav> <trace.txt> [--summary-file out.txt] [--window-ms 50] [--absolute-scale] [--anchor-samples n]

Why: the spectral checks of tools/analyze_tail_sound.py need a clear pitch peak in a 12 ms window; they cannot resolve a weak voice under a louder one, a window with an onset, or a fast sweep (OV-14 a-c).
A waveform comparison has none of those limits.  Everything audible in this game is a pure tone on channels 1-4 (AUDC $A1-$A8; idle = $00 with volume 0) with AUDCTL = $00, or $84 during the ghost-eaten
sweep, so the model needs nothing but what is already verified:
  - fire times of every channel from the AUDF writes (tools/pokey_timers.py, exact against the debugger);
  - the flip-flop of a channel entering a tone starts at the poly bit of its last gated fire (tools/pokey_noise.py, OV-13a) and toggles at every fire;
  - the ghost-eaten sweep windows use the high-pass model of tools/analyze_ghost_sweep.py (OV-13);
  - the mix is Altirra's non-linear mixer with AC coupling (OV-13b).
The rendering is compared with the recording in windows of 50 ms (both band-passed 100 Hz - 5 kHz): normalised correlation at lag 0 (the time anchor is the first fire of the start tune; the global offset
was measured as 0.00-0.02 ms), and the RMS ratio.  Windows in which both are silent are not counted.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ghost_sweep as G  # noqa: E402
import analyze_tail_sound as T  # noqa: E402
import analyze_tune_wav as W  # noqa: E402
import pokey_noise as PN  # noqa: E402

CPU, FC = G.CPU, G.FRAME_CYC
# OV-48 / C-40: the recordings hold 0.1270 ppm more samples per emulated CPU cycle than the model's 315/88/2 MHz gives: (1,789,772.5 - 1,789,772.7273) / 1,789,772.7273.  Measured -0.1267, -0.1268, -0.1273, -0.1274 ppm
# on four recordings (tools/ov48_ratio_table.py), and 0.0000-0.0004 ppm left after applying it.
AUDIO_RATIO_PPM_NTSC = -0.1270
CORR_OK = 0.90
DISCRETE_AC = "--continuous-ac" not in sys.argv   # OV-44: Altirra's AC coupling is two discrete one-pole high-pass stages; --continuous-ac gives the earlier continuous-time form
CH2_RUNS = {}                  # channel-2 runs and which of them were complemented (scratch scripts)
RESULT = {}                    # filled by main() for scratch scripts


def tone_runs(model, k, c_end):
    t, v = model.audc[k].t[1:], model.audc[k].v[1:]
    runs, start = [], None
    for c, val in zip(t, v):
        tone = (val >> 5) == 5
        if tone and start is None:
            start = c
        elif not tone and start is not None:
            runs.append((start, c))
            start = None
    if start is not None:
        runs.append((start, c_end))
    return runs


def run_events(model, k, w0, w1, flip=0):
    """breakpoints (times, states) of the output flip-flop of channel k during the tone run [w0, w1) (and 0 afterwards); `flip` complements the whole run"""
    v, kind = PN.noise_state_before(model, k, w0)
    if v is None:
        v = 0
    tim = model.timers[k]
    # OV-14d (closed): the state of the flip-flop at the start of a run is the poly bit of the last gated fire, XOR a constant per channel pair (1 for channels 3/4, the polarity fitted on the sweeps; 0 for channels 1/2,
    # whose output is the flip-flop XOR the high-pass flip-flop, which sits at 1).  The earlier line also XORed the parity of ALL fires since reset (`ecount`), which belongs to the constant of the sweep model
    # (output = constant XOR parity of all fires) and not to a state; that made the polarity of every run a coin toss (31 of 58) - start_state_test.py: with the parity the rule is wrong in 0 or 224 of 224 trials.
    s0 = v ^ (1 if k in (3, 4) else 0) ^ flip
    fires = PN.edges(tim, w0, w1)
    ts, ss = [w0], [s0]
    for i, f in enumerate(fires):
        ts.append(f); ss.append(s0 ^ ((i + 1) & 1))
    ts.append(w1); ss.append(0)
    return ts, ss


def channel_events(model, k, c_end, flips=()):
    """-> (times, states) of the output flip-flop of channel k during its tone runs (state 0 outside), as breakpoints; `flips` = run starts whose polarity is complemented"""
    ts, ss = [0], [0]
    for (w0, w1) in tone_runs(model, k, c_end):
        t_, s_ = run_events(model, k, w0, w1, 1 if w0 in flips else 0)
        ts += t_; ss += s_
    return np.array(ts, dtype=np.int64), np.array(ss, dtype=np.int8)


def general_levels(model, c_a, c_b, ev):
    """piecewise-constant mixed level (volume units, Altirra mixer) on [c_a, c_b) from the per-channel events `ev` = {k: (times, states)}"""
    bps = {c_a, c_b}
    for k in (1, 2, 3, 4):
        tt = ev[k][0]
        bps.update(tt[(tt >= c_a) & (tt < c_b)].tolist())
        bps.update(c for c in model.audc[k].t[1:] if c_a <= c < c_b)
    bps = np.array(sorted(bps), dtype=np.int64)
    nb = np.zeros((3, len(bps)))
    allb = np.zeros((3, len(bps)))
    lin = np.zeros(len(bps))
    vsum = np.zeros(len(bps))
    for k in (1, 2, 3, 4):
        tt, ss = ev[k]
        st = ss[np.clip(np.searchsorted(tt, bps, side="right") - 1, 0, len(ss) - 1)].astype(np.float64)
        ac = np.array(model.audc[k].v)[np.clip(np.searchsorted(np.array(model.audc[k].t), bps, side="right") - 1, 0, len(model.audc[k].v) - 1)]
        vol = np.where((ac >> 5) == 5, ac & 15, 0).astype(np.int64)
        nb[0] += st * (vol & 1)
        nb[1] += st * ((vol >> 1) & 1)
        nb[2] += st * (((vol >> 2) & 1) + 2 * ((vol >> 3) & 1))
        lin += st * vol
        va = vol.astype(np.int64)
        allb[0] += va & 1
        allb[1] += (va >> 1) & 1
        allb[2] += ((va >> 2) & 1) + 2 * ((va >> 3) & 1)
        vsum += va
    if getattr(model, "mixer", "altirra") == "invtable":        # OV-13e: the table is indexed by the channels that are LOW
        return bps, -G.altirra_level(allb[0] - nb[0], allb[1] - nb[1], allb[2] - nb[2])
    if getattr(model, "mixer", "altirra") == "peakgain":      # OV-13d: the linear sum, scaled by the gain of Altirra's curve at the configuration's peak level
        return bps, lin * np.where(vsum > 0, G.altirra_level(allb[0], allb[1], allb[2]) / np.maximum(vsum, 1), 1.0)
    return bps, G.altirra_level(nb[0], nb[1], nb[2])


def band(x, rate, lo=100.0, hi=5000.0, ac=False):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / rate)
    if ac:
        if DISCRETE_AC:
            # Altirra's two high-pass stages at the 63,920 Hz sample rate of its renderer (OV-44): the POKEY reference decay (pokey.cpp: coefficient exp(-1/(63920 tau)) in
            # PostFilter: y[n] = c y[n-1] + x[n] - x[n-1]) and the audio filter's own (audiofilters.cpp: mHiCoeff = 0.000634131, y = x - accum, accum += k y).  Both are
            # H(z) = (1 - z^-1) / (1 - c z^-1); the continuous-time form below differs from them by 0.36 % at 200 Hz.
            z1 = np.exp(-2j * np.pi * f / G.HALF_CYCLE_RATE)
            for c in (np.exp(-1.0 / (63920.0 * G.AC_TAU)), 1.0 - 0.00063413100049954767179657139255229):
                X = X * (1 - z1) / (1 - c * z1)
        else:
            w = 2 * np.pi * f * G.AC_TAU
            X = X * (1j * w / (1 + 1j * w))
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, n)


def main():
    args = list(sys.argv[1:])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file"); summ = args[i + 1]; del args[i:i + 2]
    win_ms = 50.0
    mixer = "invtable"
    if "--mixer" in args:
        i = args.index("--mixer"); mixer = args[i + 1]; del args[i:i + 2]
    absolute = "--absolute-scale" in args          # OV-15a: the scale of the model from Altirra's source (2.1 x UNIT x 0.5), not from the start tune of the same recording
    if absolute:
        args.remove("--absolute-scale")
    anchor_shift = 0
    if "--anchor-samples" in args:
        i = args.index("--anchor-samples"); anchor_shift = float(args[i + 1]); del args[i:i + 2]
    DUMP = None
    rate_ppm = None                                  # the audio-path clock ratio (OPEN-VERIFICATION.md OV-48 / C-40): default AUDIO_RATIO_PPM_NTSC, 0 for PAL (measured 0.0002 ppm, OV-51 / C-42); --rate-ppm x overrides, --rate-ppm 0 gives the old model
    if "--rate-ppm" in args:
        i = args.index("--rate-ppm"); rate_ppm = float(args[i + 1]); del args[i:i + 2]
    if "--dump-signals" in args:
        i = args.index("--dump-signals"); DUMP = args[i + 1]; del args[i:i + 2]
    if "--window-ms" in args:
        i = args.index("--window-ms"); win_ms = float(args[i + 1]); del args[i:i + 2]
    wav, trace = args[0], args[1]
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    x, rate = W.load_wav(wav)
    sndw, events, last_frame = T.parse_trace(trace)
    t0_trace = G.V.skctl_t0(trace)                   # the cycle of the OS's SKCTL := 3 is the zero of the noise generators and of the 64 kHz grid; it differs with the video standard and the OS (OV-42)
    if t0_trace is not None:
        PN.T0 = t0_trace
        G.PHASE = (26 + PN.T0 - 22 * 29868 - 191 * 114 - 103) % 28   # pokey.cpp: mLast64KHzTime = t + 22 - 28 (NTSC OS-B: T0 = 678,973, phase 26)
    elif G.V.PAL:
        raise SystemExit("PAL trace without the SKCTL write ($D20F) - cannot place the noise generators")
    f_tune = next(f for (f, n, v) in events if n == "TUNE" and v == 0)
    c_w2 = next(c for (c, r, v, pc) in sndw if pc == 0xA7E8 and c // FC == f_tune)
    res = W.analyze(x, rate)
    ss_ = W.Spec(x, rate)
    kk = float(np.median([ss_.mag(res["t0"], res["P"], row["i"])[1] / (8 if row["f1"] > 0 else 4) for row in res["rows"] if row["kind"] == "tone" and (row["f1"] > 0) != (row["f2"] > 0)]))
    kk_meas = kk
    if absolute:
        kk = 0.5 * 2.1 * G.UNIT / 2.0                          # p-p of one volume unit = 2.1 x UNIT (pokey.cpp, kLinearSlope) x 0.5 (Altirra's 'Audio: Volume' setting, default 0.5f in settings.cpp, 0x3F000000 in the ini, which ATAudioOutput::SetVolume hands to ATAudioFilter::mScale: located in OV-44)
    i0, i1 = int((res["t0"] - 0.03) * rate), int((res["t0"] + 0.03) * rate)
    t_w2 = (i0 + int(np.where(np.abs(x[i0:i1]) > 0.5 * kk_meas * 4)[0][0])) / rate
    if rate_ppm is None:
        rate_ppm = 0.0 if G.V.PAL else AUDIO_RATIO_PPM_NTSC
    step = CPU / rate * (1 + rate_ppm * 1e-6)
    c0 = c_w2 - t_w2 * rate * step - anchor_shift * step                # cycle of sample 0 (the anchor is found to one sample; --anchor-samples n corrects it by n samples when the lag table below peaks at n)
    c_end_trace = (last_frame - 1) * FC
    n_use = min(len(x), int((c_end_trace - c0) / step))
    P("Recording %.2f s; one volume unit k = %.5f; time anchor: first fire of the start tune at %.4f s; compared up to %.2f s (end of the complete trace)." % (len(x) / rate, kk, t_w2, n_use / rate))
    mod = G.Model(sndw)
    mod.mixer = mixer
    ev = {k: channel_events(mod, k, int(c_end_trace + 10 * FC)) for k in (1, 2, 3, 4)}
    sweeps_pre = []
    for (c, r, v, pc) in sndw:
        if pc == 0xA8EE:
            c_e = next((c2 for (c2, r2, v2, pc2) in sndw if pc2 == 0xB088 and c2 > c), None)
            if c_e is not None and c_e < c_end_trace:
                sweeps_pre.append((c, c_e))
    # Polarity of every tone run outside the sweeps: the start-state rule of OV-13a predicts it; it is right in every run (OV-14d, closed; before the fix of run_events it looked like chance), the
    # polarity of each run is still FITTED here as a check (whichever of the two gives the higher correlation with the recording over the run, all channels mixed) and the number of runs in which the rule was right is reported.
    xr_all = band(np.asarray(x[:n_use], dtype=np.float64), rate)
    CH2_RUNS.update(decided={})
    for kch in (2, 1, 3, 4, 2, 1):                    # second pass for channels 2 and 1: each is re-fitted against the other's fitted polarity
        flips, n_runs, n_rule = set(), 0, 0
        for (w0, w1) in tone_runs(mod, kch, int(c_end_trace + 10 * FC)):
            a_c, b_c = max(w0, int(c0 + 2 * rate * step)), min(w1, int(c_end_trace))
            if b_c - a_c < 4 * 0.05 * CPU:
                continue
            if any(a_c < sw[1] and b_c > sw[0] for sw in sweeps_pre):
                continue
            best = None
            for fl in (0, 1):
                ev_l = dict(ev)
                t_, s_ = run_events(mod, kch, w0, w1, fl)
                ev_l[kch] = (np.array([0] + t_, dtype=np.int64), np.array([0] + s_, dtype=np.int8))
                bb, tt = general_levels(mod, a_c, b_c, ev_l)
                n_ = min(int((b_c - a_c) / step) - 1, n_use - int(round((a_c - c0) / step)))
                if n_ < 4 * 0.05 * rate:
                    break
                sig = band(G.render(bb, tt, a_c, n_, step) * 2 * kk, rate, ac=True)
                i_a = int(round((a_c - c0) / step))
                rr = xr_all[i_a:i_a + n_]
                sc = float(np.dot(rr, sig) / (np.linalg.norm(rr) * np.linalg.norm(sig) + 1e-30))
                if best is None or sc > best[0]:
                    best = (sc, fl)
            if best is None:
                continue
            n_runs += 1
            if kch == 2:
                CH2_RUNS["decided"][w0] = (best[1], best[0])
            if best[1]:
                flips.add(w0)
            else:
                n_rule += 1
        ev[kch] = channel_events(mod, kch, int(c_end_trace + 10 * FC), flips)
        P("Channel %d tone runs (>= 4 windows, not inside a sweep): %d; the polarity predicted by the start-state rule is the better one in %d, the complement in %d%s." % (
            kch, n_runs, n_rule, n_runs - n_rule, " (OV-14d closed: the rule is right)" if kch == 2 else ""))
    # ghost-eaten sweeps: the high-pass model (OV-13) with the predicted start bits
    sweeps = []
    for (c, r, v, pc) in sndw:
        if pc == 0xA8EE:
            c_e = next((c2 for (c2, r2, v2, pc2) in sndw if pc2 == 0xB088 and c2 > c), None)
            if c_e is not None and c_e < c_end_trace:
                sweeps.append((c, c_e))
    parts_b, parts_t = [], []
    sweep_params = []                                              # (c_a, c_b, c1, c3, c4) of the sweeps rendered by mod.mixed (tools/check_segments_waveform.py)
    cur = 0
    for (c_a, c_b) in sweeps:
        if c_a > cur:
            b, t = general_levels(mod, cur, c_a, ev); parts_b.append(b[:-1]); parts_t.append(t[:-1])
        c3, c4 = PN.start_constant(mod, 3, c_a, c_b), PN.start_constant(mod, 4, c_a, c_b)
        if c3 is None or c4 is None:
            b, t = general_levels(mod, c_a, c_b, ev)
        else:
            # Channel 1's flip-flop constant is 0 when the sweep starts it (its tone entry is inside the sweep); when it is ALREADY in pure tone at the ghost-eaten start (the siren, the
            # bonus sweep), its state is the one of its ordinary run (the start-state rule of OV-14d, as fitted above) and the constant follows from it (OV-42a: with constant 0 the
            # first half frame of such a sweep, until channels 3/4 join, was inverted in 2 of 3 sweeps that begin inside a channel-1 tone).
            c1 = 0
            if PN.audcn(mod.audc[1].at(c_a - 1)) >> 5 == 5 and (mod.audc[1].at(c_a - 1) & 15):
                t1, s1 = ev[1]
                st1 = int(s1[max(int(np.searchsorted(t1, c_a - 1, side="right")) - 1, 0)])
                c1 = st1 ^ mod.parity(1, c_a - 1)
            b, t = mod.mixed(c_a, c_b, {1: c1, 3: c3, 4: c4}, 1, True, 1)
            sweep_params.append((c_a, c_b, c1, c3, c4))
        parts_b.append(b[:-1]); parts_t.append(t[:-1])
        cur = c_b
    b, t = general_levels(mod, cur, int(c_end_trace), ev)
    parts_b.append(b); parts_t.append(t)
    bps = np.concatenate(parts_b); total = np.concatenate(parts_t)
    keep = np.concatenate([[True], np.diff(bps) > 0])
    bps, total = bps[keep], total[keep]
    P("Model: %d level breakpoints, %d ghost-eaten sweeps use the high-pass model." % (len(bps), len(sweeps)))
    model_sig = G.render(bps, total, c0, n_use, step) * 2 * kk              # volume units -> recording units (one unit = 2k peak to peak ... as in analyze_ghost_sweep: the scale is 2k)
    xm = band(model_sig, rate, ac=True)
    xr = band(np.asarray(x[:n_use], dtype=np.float64), rate)
    if DUMP:                                         # for the drift probe (tools/probe_wave_drift.py): the model and the recording after the same band-pass
        np.savez_compressed(DUMP, xm=xm.astype(np.float32), xr=xr.astype(np.float32), rate=rate)
    wl = int(win_ms / 1000 * rate)
    nw = n_use // wl
    rows = []
    for i in range(nw):
        a, b = i * wl, (i + 1) * wl
        r, m = xr[a:b], xm[a:b]
        er, em = float(np.sqrt(np.mean(r ** 2))), float(np.sqrt(np.mean(m ** 2)))
        if er < 0.002 and em < 0.002:
            continue
        if i == 0 and er < 0.002:                    # the band-pass / AC-coupling filters of the two signals start up differently at sample 0 (a spike of 0.01-0.02 that decays within 5 ms); the recording itself is inaudible there (OV-42c)
            continue
        cc = float(np.dot(r, m) / (np.linalg.norm(r) * np.linalg.norm(m))) if er > 0 and em > 0 else 0.0
        rows.append((i * win_ms / 1000, cc, em / er if er > 0 else float("inf"), er, em))
    cs = np.array([r[1] for r in rows]); rs = np.array([r[2] for r in rows])
    RESULT.update(xr=xr, xm=xm)
    RESULT.update(rows=rows, c0=c0, step=step, rate=rate, mod=mod, win_ms=win_ms, c_end=c_end_trace)
    RESULT.update(ev=ev, kk=kk, sweeps=sweeps, sweep_params=sweep_params)                    # for tools/check_segments_waveform.py (OV-43)
    P("\nWindows of %.0f ms with sound in either signal: %d.  Correlation at lag 0: median %.4f, 5th percentile %.4f, min %.4f;  >= %.2f in %d (%.1f%%), >= 0.80 in %d (%.1f%%)." % (
        win_ms, len(rows), np.median(cs), np.percentile(cs, 5), cs.min(), CORR_OK, int((cs >= CORR_OK).sum()), 100.0 * (cs >= CORR_OK).mean(), int((cs >= 0.8).sum()), 100.0 * (cs >= 0.8).mean()))
    good = cs >= CORR_OK
    P("RMS ratio model / recording over the windows with correlation >= %.2f: median %.3f, 5-95%%: %.3f..%.3f." % (CORR_OK, np.median(rs[good]), np.percentile(rs[good], 5), np.percentile(rs[good], 95)))
    # global lag check: correlation of the whole thing at a few lags
    for lag in (-2, -1, 0, 1, 2):
        a_, b_ = (xr[max(lag, 0):n_use + min(lag, 0)], xm[max(-lag, 0):n_use - max(lag, 0)])
        m_ = min(len(a_), len(b_))
        P("  whole-recording correlation at lag %+d samples (%+.3f ms): %.4f" % (lag, lag / rate * 1000, float(np.dot(a_[:m_], b_[:m_]) / (np.linalg.norm(a_[:m_]) * np.linalg.norm(b_[:m_])))))
    bad = [r for r in rows if r[1] < CORR_OK]
    P("\nWindows below %.2f: %d.  Worst 25 (time s, frame, correlation, rms ratio):" % (CORR_OK, len(bad)))
    for r in sorted(bad, key=lambda r: r[1])[:25]:
        fr = int((c0 + r[0] * rate * step) // FC)
        P("  %8.3f s  frame %6d  corr %.3f  ratio %.2f" % (r[0], fr, r[1], r[2]))
    # grouping of the bad windows by the sound that is playing: which channels are in tone mode
    from collections import Counter
    def active(t_s):
        c = c0 + t_s * rate * step
        return tuple(k for k in (1, 2, 3, 4) if (mod.audc[k].at(int(c)) >> 5) == 5 and (mod.audc[k].at(int(c)) & 15) > 0)
    allc, badc = Counter(active(r[0]) for r in rows), Counter(active(r[0]) for r in bad)
    # single-channel windows: the sign of the correlation only says which way the flip-flop started (OV-14d); |correlation| says whether pitch, timing and level of the tone are right
    single = [r for r in rows if len(active(r[0])) == 1]
    if single:
        a_ = np.array([abs(r[1]) for r in single]); sg = np.array([r[1] for r in single])
        P("Single-channel windows (%d): |correlation| median %.4f, 5th percentile %.4f; >= %.2f in %d (%.1f%%); signed >= %.2f in %d (%.1f%%), inverted (<= -%.2f) in %d (%.1f%%)." % (
            len(single), np.median(a_), np.percentile(a_, 5), CORR_OK, int((a_ >= CORR_OK).sum()), 100.0 * (a_ >= CORR_OK).mean(),
            CORR_OK, int((sg >= CORR_OK).sum()), 100.0 * (sg >= CORR_OK).mean(), CORR_OK, int((sg <= -CORR_OK).sum()), 100.0 * (sg <= -CORR_OK).mean()))
        lo = [r for r in single if abs(r[1]) < CORR_OK]
        P("Single-channel windows with |correlation| < %.2f: %d; their RMS ratio median %.2f; first 12 (time s, frame, channels, correlation, rms ratio):" % (CORR_OK, len(lo), np.median([r[2] for r in lo]) if lo else 0.0))
        for r in lo[:12]:
            P("  %8.3f s  frame %6d  ch%s  corr %+.3f  ratio %.2f" % (r[0], int((c0 + r[0] * rate * step) // FC), active(r[0]), r[1], r[2]))
    P("\nBy audible channels (tone mode with volume > 0): windows, of which below %.2f:" % CORR_OK)
    for key, n in sorted(allc.items(), key=lambda kv: -kv[1]):
        P("  channels %-12s %5d windows, %4d below" % (key, n, badc.get(key, 0)))
    # by game event: the windows in the 1.5 s after each event of the trace (the sound that event starts)
    import bisect as _bs
    ev_frames = sorted((f, n) for (f, n, v) in events)
    ev_f = [f for f, n in ev_frames]
    labels, good = Counter(), Counter()
    for r in rows:
        fr = int((c0 + r[0] * rate * step) // FC)
        j = _bs.bisect_right(ev_f, fr) - 1
        lab = ev_frames[j][1] if j >= 0 and fr - ev_f[j] <= 90 else "(no event in the previous 1.5 s)"
        labels[lab] += 1
        good[lab] += int(r[1] >= CORR_OK)
    P("\nBy game event (windows in the 1.5 s after the latest event): windows, with correlation >= %.2f:" % CORR_OK)
    for lab, n in sorted(labels.items(), key=lambda kv: -kv[1]):
        P("  %-34s %5d windows, %5.1f%%" % (lab, n, 100.0 * good[lab] / n))
    text = "\n".join(out)
    print(text)
    if summ:
        open(summ, "w", encoding="utf-8").write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
