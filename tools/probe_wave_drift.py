"""Clock-ratio probe for a long recording (OPEN-VERIFICATION.md OV-46).  Altirra follows the sound card, so the number of audio samples per emulated CPU cycle differs a little from run to run
(about one sample in 150 s here), which shifts the model against the recording more and more.  The model itself is exact; this tool measures the shift.
Usage:  python -I tools/analyze_full_waveform.py <wav> <trace> --dump-signals sig.npz      (writes the band-passed model and recording)
        python -I tools/probe_wave_drift.py sig.npz [block_s]                                 (best lag per block, straight-line fit, the --rate-ppm to give analyze_full_waveform.py)
A real drift is a straight line of the best lag against time with correlation >= 0.99 in every block; anything else is not a clock ratio.
"""
import sys
import numpy as np

d = np.load(sys.argv[1])
xm, xr, rate = d["xm"].astype(float), d["xr"].astype(float), int(d["rate"])
blk = int(float(sys.argv[2] if len(sys.argv) > 2 else 30) * rate)
n = min(len(xm), len(xr))
T, L, C = [], [], []
for b in range(0, n - blk, blk * 2):
    a = xm[b + 16:b + blk - 16]
    if np.linalg.norm(a) < 1e-6:
        continue
    cs = []
    for lag in range(-16, 17):
        r = xr[b + 16 + lag:b + blk - 16 + lag]
        cs.append(np.dot(a, r) / (np.linalg.norm(a) * np.linalg.norm(r) + 1e-30))
    k = int(np.argmax(cs))
    frac = 0.0
    if 0 < k < len(cs) - 1:                      # parabola through the three points around the peak
        y0, y1, y2 = cs[k - 1], cs[k], cs[k + 1]
        frac = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-30)
    T.append((b + blk / 2) / rate); L.append(k - 16 + frac); C.append(cs[k])
    print("%7.0f s  best lag %+6.2f samples  correlation %.4f" % (T[-1], L[-1], C[-1]))
T, L, C = np.array(T), np.array(L), np.array(C)
good = C >= 0.99                                 # blocks that are a clean shifted copy; a block that is not (the end of the trace, a quiet stretch) is reported, not fitted
print("blocks not fitted (correlation < 0.99): %s" % [int(t) for t in T[~good]])
slope, icpt = np.polyfit(T[good], L[good], 1)
res = L[good] - (slope * T[good] + icpt)
print("fit over %d blocks: lag = %+.3f + %+.5f samples/s * t ;  residual max %.2f samples ;  min block correlation %.4f" % (good.sum(), icpt, slope, np.abs(res).max(), C[good].min()))
print("--rate-ppm %.4f   (the recording has %.3f ppm more samples per emulated cycle than the model assumes)" % (-slope / rate * 1e6, slope / rate * 1e6))
print("--anchor-samples %.2f   (the lag line at the time of the anchor, %.1f s here: the anchor is found to one sample only, and a drift can hide it; read the real anchor time from the 'time anchor' line of analyze_full_waveform.py and use intercept + slope * t)" % (icpt + slope * 2.1, 2.1))
