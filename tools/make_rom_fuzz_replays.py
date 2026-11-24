"""Stage 86: seeded replays for tools/check_c_vs_rom.py that are NOT made by the Python port: a random stick for each player (changing every 8-40 frames), the console keys (SELECT for two players on odd seeds, then START),
the trigger now and then, the clock counting frames, 64 random RANDOM bytes a frame (the ROM and the C read the same ones).  The game decides what happens (deaths, ghosts eaten, levels), nothing is recorded from any port.
Usage: python -I tools/make_rom_fuzz_replays.py OUTDIR SEED [SEED ...] [--frames N]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_replay as MR  # noqa: E402

STICKS = [0x0E, 0x0D, 0x0B, 0x07, 0x0F, 0x0A, 0x06, 0x09, 0x05]


def make(path, seed, frames):
    rng = random.Random(seed)
    two = seed % 2 == 1
    cur = [0x0F, 0x0F]
    until = [0, 0]
    out = []
    for t in range(frames):
        for p in (0, 1):
            if t >= until[p]:
                cur[p] = rng.choice(STICKS)
                until[p] = t + rng.randrange(8, 40)
        console = 7
        if two and 300 <= t < 304:
            console = 5                                  # SELECT: two players
        elif 330 <= t < 334:
            console = 6                                  # START
        trig = 0 if rng.randrange(20) == 0 else 1
        out.append({"stick0": cur[0], "stick1": cur[1] if two else 0x0F, "trig0": trig, "trig1": 1, "console": console, "key": 0xFF, "keydelay": 0, "clock": t & 0xFF,
                    "drkmsk": 0xFF, "colrsh": 0, "random": bytes(rng.randrange(256) for _ in range(64))})
    MR.write_replay(path, out, seed=seed, start_clock=0, with_random=True)


def main():
    a = sys.argv[1:]
    frames = 12000
    if "--frames" in a:
        i = a.index("--frames")
        frames = int(a[i + 1])
        del a[i:i + 2]
    outdir, seeds = a[0], [int(x) for x in a[1:]]
    os.makedirs(outdir, exist_ok=True)
    for s in seeds:
        make(os.path.join(outdir, "fuzz%d.pmrp" % s), s, frames)
        print("wrote fuzz%d.pmrp" % s)


if __name__ == "__main__":
    main()
