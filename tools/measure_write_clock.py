"""Stage 80c: measures where in a frame the game's sound-register writes happen (the numbers of src/c/audio/write_clock.h).
The traces of the recorded sessions (analysis/raw-logs: every write of $D200-$D208 with frame, scan line and cycle) are grouped by the frame of the handler that made them (the window
[f * 29868 - 1000, (f + 1) * 29868 - 1000) belongs to handler f); reported: how many frames, the cycle of the first write relative to the frame start (median, 10th and 90th percentile), the spacing of
consecutive writes, and the distinct sequences of registers with how often they occur.
Usage: python -I tools/measure_write_clock.py [trace names]"""
import collections
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import analyze_tail_sound as T  # noqa: E402

FRAME_CYC = 29868
WINDOW_SHIFT = 1000
TRACES = ["sound-events", "sound-events2", "sound-natural", "sound-level12-recorded", "sound-hp-recorded", "sound-hpd-recorded", "sound-bot", "sound-bot2", "sound-bot3", "sound-bot4", "sound-bot5"]


def frames_of(path):
    sndw, _, _ = T.parse_trace(path)
    out = collections.defaultdict(list)
    for (c, r, v, pc) in sndw:
        if r <= 8:
            out[(c + WINDOW_SHIFT) // FRAME_CYC].append((c, r, v))
    return out


def measure(names):
    firsts, spacings, seqs, nframes = [], [], collections.Counter(), 0
    for n in names:
        p = os.path.join(ROOT, "analysis", "raw-logs", n + ".txt")
        if not os.path.exists(p):
            continue
        for f, ws in frames_of(p).items():
            ws.sort()
            nframes += 1
            firsts.append(ws[0][0] - f * FRAME_CYC)
            spacings += [b[0] - a[0] for a, b in zip(ws, ws[1:])]
            seqs[tuple(r for _, r, _ in ws)] += 1
    return nframes, firsts, spacings, seqs


def main():
    names = sys.argv[1:] or TRACES
    n, firsts, spacings, seqs = measure(names)
    firsts.sort()
    spacings.sort()
    print("%d frames with sound writes in %d traces" % (n, len(names)))
    print("first write, cycles after the frame start: median %d, 10th percentile %d, 90th percentile %d" % (statistics.median(firsts), firsts[len(firsts) // 10], firsts[9 * len(firsts) // 10]))
    print("spacing of consecutive writes: median %d, 10th percentile %d, 90th percentile %d" % (statistics.median(spacings), spacings[len(spacings) // 10], spacings[9 * len(spacings) // 10]))
    print("%d distinct sequences of registers; the most frequent:" % len(seqs))
    for seq, c in seqs.most_common(8):
        print("  %7d  %s" % (c, list(seq)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
