"""Renders the start tune of a game (docs/21) to a WAV file you can listen to.  Usage:  python -I tools/render_start_tune.py [out.wav]

Source: the ROM only (TuneAudf1 $BC50, TuneAudf2 $BC90) and the loop at $A7D3, which every 4th frame writes
AUDF1 := tbl1[x], AUDC1 := $A8 (pure tone, volume 8), AUDF2 := tbl2[x], AUDC2 := $A4 (pure tone, volume 4), x = 0..63.
POKEY model (an approximation, NOT a recording of the emulator):
  - 64 kHz base clock (NTSC 1,789,773 Hz / 28 = 63,921 Hz), AUDCTL without the 1.79 MHz / 16-bit bits -> a pure-tone channel toggles every (AUDF+1) base ticks, f = 63921 / (2 * (AUDF + 1)).
  - AUDF = 0 gives about 32 kHz, which is not audible: it is rendered as silence (a rest).
  - Channels 3 and 4, the high-pass filter bit of AUDCTL and the volume curve of a real TV are not modelled.
  - One step = 4 frames = 4 / 59.9227 s (NTSC).
"""
import os
import struct
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

RATE = 44100
import video as V  # noqa: E402
BASE = V.CPU / 28.0 if V.PAL else 1789773 / 28.0
STEP_S = 4 / V.FRAME_HZ if V.PAL else 4 / 59.9227
VOL = {1: 8, 2: 4}


def render(rate=RATE):
    t1 = [S.rd(0xBC50 + i) for i in range(64)]
    t2 = [S.rd(0xBC90 + i) for i in range(64)]
    out = []
    ph = {1: 0.0, 2: 0.0}
    n_total = int(round(64 * STEP_S * rate))
    for n in range(n_total):
        x = min(63, int(n / rate / STEP_S))
        s = 0.0
        for ch, tbl in ((1, t1), (2, t2)):
            f = tbl[x]
            if f == 0:
                continue
            freq = BASE / (2.0 * (f + 1))
            ph[ch] = (ph[ch] + freq / rate) % 1.0
            s += (VOL[ch] / 15.0) * (1.0 if ph[ch] < 0.5 else -1.0)
        out.append(max(-1.0, min(1.0, s * 0.5)))
    return out, t1, t2


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "analysis", "start-tune.wav")
    out, t1, t2 = render()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(v * 30000)) for v in out))
    print("wrote %s: %.2f s" % (path, len(out) / RATE))
    names = "C C# D D# E F F# G G# A A# B".split()
    import math

    def note(f):
        if f == 0:
            return "-"
        fr = BASE / (2.0 * (f + 1))
        m = int(round(69 + 12 * math.log2(fr / 440.0)))
        return "%s%d(%dHz)" % (names[m % 12], m // 12 - 1, round(fr))
    for i in range(0, 64, 8):
        print("steps %2d-%2d  voice 1: %s" % (i, i + 7, " ".join(note(f) for f in t1[i:i + 8])))
        print("             voice 2: %s" % " ".join(note(f) for f in t2[i:i + 8]))


if __name__ == "__main__":
    main()
