"""OV-48: the clock ratio of every long recording.  For each recording: tools/analyze_full_waveform.py at its default settings (and at --rate-ppm P when P is given) with --dump-signals, then tools/probe_wave_drift.py on the dump.
Usage:  python -I tools/ov48_ratio_table.py <scratch_dir> [P] [name ...]        prints one line per recording; --rate-ppm P is applied to the NTSC ones when P is given.
Hypothesis under test: Altirra's NTSC audio path counts 1,789,772.5 Hz (3,579,545 / 2), the model uses 315/88/2 MHz = 1,789,772.727 Hz, so the ratio is (1789772.5 - 1789772.7273) / 1789772.7273 = -0.1270 ppm."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECS = {  # name: (wav, trace, extra arguments)
    "sound-bot (C-33, 778 s)": ("sound-bot-recorded.wav", "sound-bot.txt", []),
    "sound-bot2 (C-34, 1502 s)": ("sound-bot2-recorded.wav", "sound-bot2.txt", []),
    "sound-bot3 (C-35, 1502 s)": ("sound-bot3-recorded.wav", "sound-bot3.txt", []),
    "sound-bot4 (C-36, 1152 s)": ("sound-bot4-recorded.wav", "sound-bot4.txt", []),
    "sound-bot5 (C-37, 902 s)": ("sound-bot5-recorded.wav", "sound-bot5.txt", []),
    "sound-events (C-13, 176 s)": ("sound-events-recorded.wav", "sound-events.txt", []),
    "sound-events2 (178 s)": ("sound-events2-recorded.wav", "sound-events2.txt", []),
    "sound-hp (222 s)": ("sound-hp-recorded.wav", "sound-hp-recorded.txt", []),
    "ov42-hle-events (PAL?)": ("ov42-hle-events.wav", "ov42-hle-events.txt", []),
    "ov42-pal-events (PAL)": ("ov42-pal-events.wav", "ov42-pal-events.txt", []),
    "ov42-palos-events (PAL OS)": ("ov42-palos-events.wav", "ov42-palos-events.txt", []),
    "sound-natural (73 s)": ("sound-natural-recorded.wav", "sound-natural.txt", []),
}


def run(args):
    r = subprocess.run([sys.executable, "-I"] + args, capture_output=True, text=True, cwd=ROOT)
    return r.stdout + r.stderr


def stats(txt):
    m = re.search(r"Windows of 50 ms with sound in either signal: (\d+)\.  Correlation at lag 0: median ([\d.]+), 5th percentile ([\d.]+), min (-?[\d.]+);  >= 0.90 in (\d+)", txt)
    return m and (int(m.group(1)), float(m.group(2)), float(m.group(4)), int(m.group(5)))


scratch = sys.argv[1]
ppm = sys.argv[2] if len(sys.argv) > 2 and re.match(r"-?[\d.]+$", sys.argv[2]) else None
names = [a for a in sys.argv[2:] if a in RECS] or list(RECS)
for name in names:
    wav, trace, extra = RECS[name]
    wav, trace = os.path.join("analysis", wav), os.path.join("analysis", "raw-logs", trace)
    if not (os.path.exists(os.path.join(ROOT, wav)) and os.path.exists(os.path.join(ROOT, trace))):
        print(name, "missing"); continue
    for label, add in (("default", []), ("ppm %s" % ppm, ["--rate-ppm", ppm])) if ppm else (("default", []),):
        dump = os.path.join(scratch, "d.npz")
        out = run(["tools/analyze_full_waveform.py", wav, trace, "--dump-signals", dump] + add + extra)
        st = stats(out)
        pr = run(["tools/probe_wave_drift.py", dump]) if os.path.exists(dump) else ""
        m = re.search(r"--rate-ppm (\S+)", pr)
        res = re.search(r"residual max ([\d.]+) samples", pr)
        print("%-30s %-10s windows %s  median/min %s  >=0.90 %s | probe: ratio %s ppm (residual %s)" % (name, label, st and st[0], st and "%.4f/%.4f" % (st[1], st[2]), st and st[3], m and m.group(1), res and res.group(1)), flush=True)
        if os.path.exists(dump):
            os.remove(dump)
