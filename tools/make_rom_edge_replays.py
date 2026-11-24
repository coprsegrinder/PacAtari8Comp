"""Stage 89 (edge cases): seeded replays of inputs the earlier games never produced, for tools/check_c_vs_rom.py (the C against the ROM, frame by frame).  Each profile stresses one thing; `mixed` switches
between all of them every 40-200 frames.  Nothing is recorded from any port: the inputs are chosen here, the game decides what happens.
  sticks    every one of the 16 stick values for both players, changing nearly every frame (diagonals, all four directions at once, none), the trigger at random, a two-player game
  console   the 8 values of the console keys (START, SELECT, OPTION and every combination), each held for 3-6 frames with at least 6 frames of nothing between (quicker changes are a race in the original: `tidy_console`), in the title, in play and in the game-over countdown (the OPTION key sets the start level)
  pause     the space bar (key code $21, held by the OS for three frames) and other key codes at random times, in every state
  clock     the OS clock starts at 250, 255 or 128, so that it wraps in the middle of a game
  rnd0 rnd1 rndalt   RANDOM always $00, always $FF, or alternating, in a normal game (the three places the game reads it)
  hold      START held for 700 frames from the title, then the trigger and START held in play
  idle      no input at all for thousands of frames (the copyright screen, the title, the attract timers), with the attract colour values changing
  mixed     one of the above every 40-200 frames
Usage: python -I tools/make_rom_edge_replays.py OUTDIR [--frames N] [--seeds N]   (writes OUTDIR/<profile>-<seed>.pmrp)"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_replay as MR  # noqa: E402

PROFILES = ["sticks", "console", "pause", "clock", "rnd0", "rnd1", "rndalt", "hold", "idle", "mixed"]
STICKS = [0x0E, 0x0D, 0x0B, 0x07, 0x0F, 0x0A, 0x06, 0x09, 0x05]
BASE = {"stick0": 0x0F, "stick1": 0x0F, "trig0": 1, "trig1": 1, "console": 7, "key": 0xFF, "keydelay": 0, "drkmsk": 0xFF, "colrsh": 0}


def segment(profile, rng, t0, n, state):
    """the input fields (a list of dicts without clock and random) of n frames of one profile starting at frame t0"""
    out = []
    for k in range(n):
        t = t0 + k
        f = dict(BASE)
        if profile == "sticks":
            f["stick0"] = rng.randrange(16)
            f["stick1"] = rng.randrange(16)
            f["trig0"] = rng.randrange(2)
            f["trig1"] = rng.randrange(2)
        elif profile == "console":
            if state.get("until", 0) <= t:
                state["console"] = rng.choice([7, 6, 5, 3, 4, 2, 1, 0]) if state.get("console", 7) == 7 else 7
                state["until"] = t + (rng.randrange(3, 7) if state["console"] != 7 else rng.randrange(6, 40))
            f["console"] = state.get("console", 7)           # (another profile may have used the shared "until" first)
            f["stick0"] = state.get("stick", 0x0F)
            if t % 30 == 0:
                state["stick"] = rng.choice(STICKS)
        elif profile == "pause":
            if state.get("until", 0) <= t:
                state["until"] = t + rng.randrange(20, 300)
                state["press"] = t
                state["code"] = 0x21 if rng.randrange(3) else rng.randrange(0x40)
            back = t - state.get("press", -99)
            if back == 0:
                f["key"] = state["code"]
            elif 1 <= back <= 3:
                f["keydelay"] = 4 - back
            if t % 25 == 0:
                state["stick"] = rng.choice(STICKS)
            f["stick0"] = state.get("stick", 0x0F)
        elif profile == "hold":
            f["console"] = 6 if (330 <= t < 1030 or 2000 <= t < 2300) else 7
            f["trig0"] = 0 if t >= 1100 else 1
            if t % 20 == 0:
                state["stick"] = rng.choice(STICKS)
            f["stick0"] = state.get("stick", 0x0F)
        elif profile == "idle":
            if t % 400 == 0:
                state["dm"] = rng.choice([0xFF, 0xF7, 0xFE, 0x00])
                state["cs"] = rng.choice([0, 1, 0x0E, 0xFF])
            f["drkmsk"] = state.get("dm", 0xFF)
            f["colrsh"] = state.get("cs", 0)
        else:                                            # a normal game: SELECT / START at fixed frames, a stick that changes
            if t < 330 and state.get("two") and 300 <= t < 304:
                f["console"] = 5
            if 330 <= t < 334:
                f["console"] = 6
            if t >= state.get("tnext", 0):
                state["stick"] = rng.choice(STICKS)
                state["tnext"] = t + rng.randrange(8, 40)
            f["stick0"] = state.get("stick", 0x0F)
            if state.get("two"):
                f["stick1"] = rng.choice(STICKS) if t % 7 == 0 else state.get("s1", 0x0F)
                state["s1"] = f["stick1"]
            f["trig0"] = 0 if rng.randrange(20) == 0 else 1
        out.append(f)
    return out


def tidy_console(fields):
    """Console keys that follow each other quickly are a RACE in the original, not an input with one answer: the main program reads CONSOL in loops of two or three instructions, the vertical-blank handler counts
    `KeyDebounce` down in between, and a restart (START) takes more than a frame, so what a change of the console in the frame after a press, or in the frames while the press is being handled, does depends on which
    instruction the interrupt lands on (on the real machine: at the clock cycle of the change).  The ROM harness's answer depends on where its instruction budget ends: with 10 neighbouring budgets the same
    inputs gave GameState 3 (the title) in some and 0 (the game) in others, with period three, the length of the debounce loop (docs/55 section 3).  The C takes one fixed answer, which is one of the ROM's.
    So the generated inputs avoid the race: every console value other than 'nothing' is held for at least 3 frames and followed by at least 6 frames of nothing, and no press is near a change of the attract values."""
    out = [f["console"] for f in fields]
    n = len(out)
    i = 0
    while i < n:
        if out[i] == 7:
            i += 1
            continue
        j = i
        while j + 1 < n and out[j + 1] == out[i]:
            j += 1
        while j - i + 1 < 3 and j + 1 < n:
            j += 1
            out[j] = out[i]
        for k in range(j + 1, min(n, j + 7)):
            out[k] = 7
        i = j + 7
    # a change of the attract values (DRKMSK, COLRSH) in the same frame as a console press, a trigger press or a key is the same kind of race: the main program rewrites DliColors from them at the top of every
    # pass, and whether it does so before or after it reads that input (or restarts the game, which takes more than a frame) depends on where in its pass it is when the frame begins; so no such input
    # is within three frames before or eight after such a change
    keep = [dict(f) for f in fields]
    for c in range(1, n):
        if (fields[c]["drkmsk"], fields[c]["colrsh"]) != (fields[c - 1]["drkmsk"], fields[c - 1]["colrsh"]):
            for q in range(max(0, c - 3), min(n, c + 8)):
                keep[q].update(trig0=1, trig1=1, key=0xFF, keydelay=0)
            lo, hi = max(0, c - 3), min(n, c + 8)
            k = lo
            while k < hi:
                if out[k] != 7:
                    a = k
                    while a > 0 and out[a - 1] == out[k]:
                        a -= 1
                    b = k
                    while b + 1 < n and out[b + 1] == out[k]:
                        b += 1
                    for q in range(a, b + 1):
                        out[q] = 7
                    k = b + 1
                else:
                    k += 1
    return [dict(f, console=c, trig0=k["trig0"], trig1=k["trig1"], key=k["key"], keydelay=k["keydelay"]) for f, c, k in zip(fields, out, keep)]


def make(path, profile, seed, frames):
    rng = random.Random(seed * 1000 + PROFILES.index(profile))
    clock0 = {"clock": rng.choice([250, 255, 128])}.get(profile) if profile == "clock" else 0
    two = seed % 2 == 1
    state = {"two": two}
    fields = []
    if profile == "mixed":
        t = 0
        while t < frames:
            p = "play" if t == 0 else rng.choice([x for x in PROFILES if x != "mixed"] + ["play"])
            n = 400 if t == 0 else rng.randrange(40, 200)          # the first segment starts a game (SELECT, START at frames 300-334)
            fields += segment(p, rng, t, n, state)
            t += n
        fields = fields[:frames]
    else:
        fields = segment(profile if profile not in ("clock", "rnd0", "rnd1", "rndalt") else "play", rng, 0, frames, state)
    fields = tidy_console(fields)
    out = []
    for t, f in enumerate(fields):
        f = dict(f)
        f["clock"] = (clock0 + t) & 0xFF
        if profile == "rnd0":
            f["random"] = bytes(64)
        elif profile == "rnd1":
            f["random"] = bytes([0xFF] * 64)
        elif profile == "rndalt":
            f["random"] = bytes([0x00 if (i + t) % 2 else 0xFF for i in range(64)])
        else:
            f["random"] = bytes(rng.randrange(256) for _ in range(64))
        out.append(f)
    MR.write_replay(path, out, seed=seed, start_clock=clock0 & 0xFF, with_random=True)


def main():
    a = sys.argv[1:]
    frames, seeds = 6000, 2
    if "--frames" in a:
        i = a.index("--frames")
        frames = int(a[i + 1])
        del a[i:i + 2]
    if "--seeds" in a:
        i = a.index("--seeds")
        seeds = int(a[i + 1])
        del a[i:i + 2]
    outdir = a[0]
    os.makedirs(outdir, exist_ok=True)
    for p in PROFILES:
        for s in range(1, seeds + 1):
            n = frames if p != "mixed" else frames
            make(os.path.join(outdir, "%s-%d.pmrp" % (p, s)), p, s, n)
            print("wrote %s-%d.pmrp" % (p, s))


if __name__ == "__main__":
    main()
