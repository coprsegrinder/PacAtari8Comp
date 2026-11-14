"""Judge, in the WAVEFORM domain, the segments that the spectral audit (tools/analyze_tail_sound.py) cannot judge by pitch (OPEN-VERIFICATION.md OV-43).  Usage:
  python -I tools/check_segments_waveform.py <recording.wav> <trace.txt> <tail-summary.txt> [--anchor-samples n] [--summary-file out.txt] [--drift-limit-cents 20]

The spectral audit measures a pitch in a window of 12-13 ms; when a weak voice sits under a louder one, or another channel starts in the window, the pitch is "not resolved" (level still checked) and some
short segments are flagged.  The waveform comparison (tools/analyze_full_waveform.py) renders the recording from the register writes sample by sample, so over any segment the model and the recording
must agree edge by edge - a much stricter test of pitch than a spectral peak.  For EVERY segment of the audit's segment list (and in particular for the unresolved and the flagged ones) this tool measures
  * the normalised correlation of the recording with the model over the segment (limit 0.90);
  * the DRIFT: the lag of the recording against the model (found with a parabolic fit to +-3 samples) in the first half of the segment against the second half.  A voice of the wrong pitch walks
    away from the model by (pitch error x time): the drift over half a segment, divided by the time between the two halves, is the pitch error of whatever the segment holds, in cents.
The drift is descriptive (the lag search covers +-3 samples; a single voice 20 cents off already fails the correlation gate) and follows the loudest voice, so it cannot judge a WEAK voice (a unit test shows this).  For the tones the audit names - unresolved ones and the ones of flagged segments - the tool therefore also runs a
SHIFT TEST: the model is re-rendered with that one channel's edges inside the segment stretched by +-20 cents (and +-10, +-5, +-40 for the statistics) and the correlation of the recording with the true model
must beat the correlation with each shifted model.  (Inside a ghost-eaten sweep the model is rendered by Model.mixed with the high-pass latch; there the fires of the one channel are stretched in that renderer.)
Exit code 1 if an unresolved or flagged segment misses the correlation limit or drifts by more than the limit (default 20 cents), or if the recording prefers a model with a tone shifted by 20 cents.
"""
import contextlib
import io
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_full_waveform as A  # noqa: E402

SEG = re.compile(r"^\s+(\d+\.\d+) s\s+(\d+) ms\s+(.*?)\s+level\s+(\S+)\s+(ok|FAIL)\s*$")
UNRES = re.compile(r"^\s+(\d+\.\d+) s  channel (\d) expected ([\d.]+) Hz,")
CORR_LIMIT = 0.90


def parse_summary(path):
    segs, unres, in_list, in_unres = [], [], False, False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("Pitch not resolved"):
                in_unres, in_list = True, False
                continue
            if line.startswith("Segment list"):
                in_unres, in_list = False, True
                continue
            if in_unres:
                m = UNRES.match(line)
                if m:
                    unres.append(float(m.group(1)))
                elif line.strip() and not line.startswith(" "):
                    in_unres = False
            if in_list:
                m = SEG.match(line)
                if m:
                    segs.append(dict(t=float(m.group(1)), ms=int(m.group(2)), tones=m.group(3).strip(), ok=m.group(5) == "ok"))
    return segs, unres


def lag_of(a, b, maxlag=3):
    """lag (samples, fractional) of `a` against `b`: the shift of b that maximises the correlation, parabolic refinement"""
    n = len(a)
    sc = []
    for lag in range(-maxlag, maxlag + 1):
        if lag >= 0:
            u, v = a[lag:], b[:n - lag]
        else:
            u, v = a[:n + lag], b[-lag:]
        sc.append(float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-30)))
    k = int(np.argmax(sc))
    if 0 < k < len(sc) - 1:
        d = sc[k - 1] - 2 * sc[k] + sc[k + 1]
        frac = 0.5 * (sc[k - 1] - sc[k + 1]) / d if d != 0 else 0.0
    else:
        frac = 0.0
    return (k - maxlag) + frac, sc[k]


def measure(a, b):
    """-> (correlation, drift in cents) of the recording segment `a` against the model segment `b`"""
    corr = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))
    h = len(a) // 2
    l1, _ = lag_of(a[:h], b[:h])
    l2, _ = lag_of(a[h:], b[h:])
    cents = 1200 * np.log2(1 + (l2 - l1) / h) if h else 0.0
    return corr, float(cents)


def parse_tones(path):
    """-> ([(time, channel, None)], [(time, channel, ms)]): the unresolved tones and the 'channel k expected' problems of the audit's summary"""
    unres, prob, mode = [], [], None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("Pitch not resolved"):
                mode = "u"
                continue
            if line.startswith("PROBLEMS"):
                mode = "p"
                continue
            if line.startswith("Segment list"):
                mode = None
            m = UNRES.match(line) if mode == "u" else None
            if m:
                unres.append((float(m.group(1)), int(m.group(2)), None))
            m = re.match(r"^\s+segment at (\d+\.\d+) s \((\d+) ms\): channel (\d) expected", line) if mode == "p" else None
            if m:
                prob.append((float(m.group(1)), int(m.group(3)), int(m.group(2))))
    return unres, prob


def corr_of(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))


def shifted_model(t, d, k, delta, pad=0.025):
    """the model samples of the segment [t, t+d] (seconds) when channel k's edges inside the segment are stretched by `delta` (relative): -> (i0, i1, difference to add to the model)"""
    R = A.RESULT
    rate, c0, step, mod, ev, kk = R["rate"], R["c0"], R["step"], R["mod"], R["ev"], R["kk"]
    cpu = A.CPU
    c_a = c0 + t * rate * step
    c_b = c_a + d * rate * step
    pa, pb = c_a - pad * cpu, c_b + pad * cpu
    n = int((pb - pa) / step)
    ev2 = dict(ev)
    tt, ss = ev[k]
    t2 = tt.astype(np.float64).copy()
    m = (tt > c_a) & (tt < c_b)
    t2[m] = c_a + (tt[m] - c_a) * (1 + delta)
    ev2[k] = (np.maximum.accumulate(np.round(t2)).astype(np.int64), ss)
    b1, l1 = A.general_levels(mod, int(pa), int(pb), ev)
    b2, l2 = A.general_levels(mod, int(pa), int(pb), ev2)
    diff = A.band((A.G.render(b2, l2, pa, n, step) - A.G.render(b1, l1, pa, n, step)) * 2 * kk, rate, ac=True)
    i_pa = int(round((pa - c0) / step))
    i0 = int(round(t * rate))
    i1 = i0 + int(round(d * rate))
    return i0, i1, diff[i0 - i_pa:i1 - i_pa]


def shifted_model_sweep(t, d, k, delta, sp, pad=0.025):
    """as shifted_model() for a segment inside the ghost-eaten sweep sp = (c_a, c_b, c1, c3, c4) (rendered by Model.mixed with the high-pass latch): the fires of channel k inside the segment are stretched"""
    R = A.RESULT
    rate, c0, step, mod, kk = R["rate"], R["c0"], R["step"], R["mod"], R["kk"]
    cpu = A.CPU
    s_a = c0 + t * rate * step
    s_b = s_a + d * rate * step
    c_a, c_b, c1, c3, c4 = sp
    tim = mod.timers[k]
    orig = A.PN.edges

    def edges(timer, a, b):
        fs = orig(timer, a, b)
        if timer is tim:
            fs = [int(round(s_a + (f - s_a) * (1 + delta))) if s_a < f < s_b else f for f in fs]
        return fs
    out = []
    for stretched in (False, True):
        A.PN.edges = edges if stretched else orig
        try:
            out.append(mod.mixed(c_a, c_b, {1: c1, 3: c3, 4: c4}, 1, True, 1))
        finally:
            A.PN.edges = orig
    pa, pb = max(s_a - pad * cpu, c_a), min(s_b + pad * cpu, c_b)
    n = int((pb - pa) / step)
    r = [A.G.render(b, tt, pa, n, step) for (b, tt) in out]
    diff = A.band((r[1] - r[0]) * 2 * kk, rate, ac=True)
    i_pa = int(round((pa - c0) / step))
    i0 = int(round(t * rate))
    i1 = i0 + int(round(d * rate))
    full = np.zeros(i1 - i0)
    lo, hi = max(i_pa, i0), min(i_pa + len(diff), i1)
    if hi > lo:
        full[lo - i0:hi - i0] = diff[lo - i_pa:hi - i_pa]
    return i0, i1, full


def shift_test(items, segs, cents_list=(5, 10, 20, 40)):
    """-> (rows, n_sweep): for each (time, channel, ms) outside the ghost-eaten sweeps, the correlation advantage of the true model over the best of the +-c cents shifted models"""
    R = A.RESULT
    xr, xm, rate, c0, step, sweeps = R["xr"], R["xm"], R["rate"], R["c0"], R["step"], R["sweeps"]
    rows, n_sweep = [], 0
    m0 = int(0.0005 * rate)
    for (t, k, ms) in items:
        if ms is None:
            sg = next((x for x in segs if abs(x["t"] - t) < 0.0015), None)
            if sg is None:
                continue
            ms = sg["ms"]
        d = ms / 1000.0
        c_a = c0 + t * rate * step
        sp = next((q for q in R.get("sweep_params", []) if q[0] <= c_a and c_a + d * rate * step <= q[1]), None)
        in_sweep = any(c_a < sw[1] and c_a + d * rate * step > sw[0] for sw in sweeps)
        if in_sweep and (sp is None or k not in (1, 3, 4)):
            n_sweep += 1                                          # not inside one sweep rendered by mixed() (straddles its edge, or channel 2)
            continue
        model_fn = (lambda t_, d_, k_, dl_: shifted_model_sweep(t_, d_, k_, dl_, sp)) if in_sweep else shifted_model
        i0, i1, _ = model_fn(t, d, k, 0.0)
        if i1 > len(xr) or i1 - i0 < 4 * m0:
            continue
        a, b = xr[i0:i1], xm[i0:i1]
        ct = corr_of(a[m0:-m0], b[m0:-m0])
        row = dict(t=t, k=k, ms=ms, ct=ct, sweep=in_sweep)
        for c in cents_list:
            dl = 2 ** (c / 1200.0) - 1
            vals = []
            for sgn in (1, -1):
                _, _, df = model_fn(t, d, k, sgn * dl)
                vals.append(corr_of(a[m0:-m0], (b + df)[m0:-m0]))
            row[c] = ct - max(vals)
        rows.append(row)
    return rows, n_sweep


def main():
    args = list(sys.argv[1:])
    anchor, out_path, limit = 0, None, 20.0
    for flag, conv in (("--anchor-samples", int), ("--summary-file", str), ("--drift-limit-cents", float)):
        if flag in args:
            i = args.index(flag)
            val = conv(args[i + 1])
            del args[i:i + 2]
            if flag == "--anchor-samples":
                anchor = val
            elif flag == "--summary-file":
                out_path = val
            else:
                limit = val
    wav, trace, summary = args[0], args[1], args[2]
    argv = [sys.argv[0], wav, trace, "--summary-file", os.devnull] + (["--anchor-samples", str(anchor)] if anchor else [])
    saved = sys.argv
    sys.argv = argv
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            A.main()
        except SystemExit:
            pass
    sys.argv = saved
    xr, xm, rate = A.RESULT["xr"], A.RESULT["xm"], A.RESULT["rate"]
    segs, unres_t = parse_summary(summary)
    out = []
    P = lambda *a: out.append(" ".join(str(v) for v in a))
    rows = []
    for k, s in enumerate(segs):
        end = segs[k + 1]["t"] if k + 1 < len(segs) else s["t"] + s["ms"] / 1000.0
        d = min(end - s["t"], s["ms"] / 1000.0 + 0.002)
        i0, i1 = int(round(s["t"] * rate)), int(round((s["t"] + d) * rate))
        if i1 > len(xr) or i1 - i0 < int(0.010 * rate):
            continue
        a, b = xr[i0:i1], xm[i0:i1]
        if np.sqrt(np.mean(a ** 2)) < 0.002 and np.sqrt(np.mean(b ** 2)) < 0.002:
            continue                                                      # silence
        corr, cents = measure(a, b)
        is_unres = any(abs(t - s["t"]) < 0.0015 for t in unres_t)
        rows.append(dict(t=s["t"], ms=d * 1000, corr=corr, cents=cents, unres=is_unres, flagged=not s["ok"], tones=s["tones"]))
    P("Segments of the audit's list compared in the waveform domain: %d (silence skipped); recording %s" % (len(rows), os.path.basename(wav)))

    def stat(name, sel):
        r = [x for x in rows if sel(x)]
        if not r:
            P("  %-34s none" % name)
            return []
        c = np.array([x["corr"] for x in r])
        d = np.array([abs(x["cents"]) for x in r])
        P("  %-34s %5d segs  correlation >= %.2f in %5d (%.1f%%), min %.3f, median %.4f;  drift: median %.2f cents, 95%% within %.1f, max %.1f" % (
            name, len(r), CORR_LIMIT, int((c >= CORR_LIMIT).sum()), 100.0 * (c >= CORR_LIMIT).mean(), c.min(), np.median(c), np.median(d), np.percentile(d, 95), d.max()))
        return r
    stat("all segments", lambda x: True)
    stat("segments of 12-40 ms", lambda x: x["ms"] < 40)
    stat("segments of 40 ms or more", lambda x: x["ms"] >= 40)
    ru = stat("pitch not resolved by the audit", lambda x: x["unres"])
    rf = stat("flagged by the audit (FAIL)", lambda x: x["flagged"])
    bad = [x for x in ru + rf if x["corr"] < CORR_LIMIT or abs(x["cents"]) > limit]
    worst = sorted(rows, key=lambda x: x["corr"])[:8]
    P("\nWeakest 8 segments by correlation (time s, length ms, correlation, drift cents, audit state):")
    for x in worst:
        P("  %9.3f s %5.1f ms  corr %.3f  drift %+6.1f cents  %s  %s" % (x["t"], x["ms"], x["corr"], x["cents"], "unresolved" if x["unres"] else ("flagged" if x["flagged"] else "ok"), x["tones"][:60]))
    unres_items, prob_items = parse_tones(summary)
    srows, n_sw = shift_test(unres_items, segs)
    prows, n_sw2 = shift_test(prob_items, segs)
    P("\nShift test (the true model against the model with one channel's tone stretched by +-c cents; positive = the recording prefers the true model):")
    for name, rr, nsw in (("unresolved tones", srows, n_sw), ("tones of flagged segments", prows, n_sw2)):
        if not rr:
            P("  %-28s none tested (%d inside sweeps)" % (name, nsw))
            continue
        parts = []
        for c in (5, 10, 20, 40):
            v = np.array([r[c] for r in rr])
            parts.append("%d cents: %d/%d (min %+.4f)" % (c, int((v > 0).sum()), len(v), v.min()))
        P("  %-28s %3d tested, %d not testable;  prefers the true model at  %s" % (name, len(rr), nsw, ";  ".join(parts)))
        sw_rows = [r for r in rr if r["sweep"]]
        if sw_rows:
            parts = []
            for c in (5, 10, 20, 40):
                v = np.array([r[c] for r in sw_rows])
                parts.append("%d cents: %d/%d (min %+.4f, median %+.4f)" % (c, int((v > 0).sum()), len(v), v.min(), np.median(v)))
            P("    of which inside ghost-eaten sweeps: %d;  %s" % (len(sw_rows), ";  ".join(parts)))
    shift_bad = [r for r in srows + prows if r[20] <= 0]
    P("\nUnresolved or flagged segments outside the limits (correlation >= %.2f, drift <= %.0f cents): %d" % (CORR_LIMIT, limit, len(bad)))
    for x in bad[:20]:
        P("  %9.3f s %5.1f ms  corr %.3f  drift %+6.1f cents  %s" % (x["t"], x["ms"], x["corr"], x["cents"], x["tones"][:60]))
    for r in shift_bad[:10]:
        P("  shift test: %.3f s channel %d (%.0f ms): the recording prefers a model shifted by 20 cents (advantage %+.4f)" % (r["t"], r["k"], r["ms"], r[20]))
    P("\nPROBLEMS: " + ("none" if not (bad or shift_bad) else "%d" % (len(bad) + len(shift_bad))))
    text = "\n".join(out)
    print(text)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if (bad or shift_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
