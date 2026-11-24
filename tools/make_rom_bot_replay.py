"""Stage 87 (OV-70): a replay made by a player that plays ON PURPOSE, so that input alone reaches the two frame classes no random game reaches: the eaten pause (a ghost eaten after a power pellet) and the level end.
The player is not a port and knows nothing of the C: it plays the ROM on the concrete 6502 (tools/check_app.py RomApp, the collision registers computed from the ROM's own memory) and at every decision looks ahead
by running the ROM itself: it saves the machine, holds each of the four stick directions for a number of frames, scores what happened (dots eaten, a ghost eaten, a death) and restores the machine.  The stick
it chose is all that is recorded: the replay holds the inputs of every frame (stick, trigger, console, clock) and the RANDOM bytes the real run read.  Whatever the replay then does in the C port is up to the C port.
Usage: python -I tools/make_rom_bot_replay.py OUT.pmrp --seed N [--frames N] [--stop-after-levels K] [--two]
It stops when the board has been cleared K times (default 1) or after --frames frames."""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_collide as AC  # noqa: E402
import check_app as CA  # noqa: E402
import check_app_board as CAB  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402
import make_replay as MR  # noqa: E402
import platform_iface as PI  # noqa: E402
from check_c_vs_rom import ReplayInputs  # noqa: E402

DIRS = {1: 0x0E, 2: 0x0D, 4: 0x0B, 8: 0x07}                 # direction bit -> the stick value (the pressed direction is a 0 bit)
STEP = {1: (-1, 0), 2: (1, 0), 4: (0, -1), 8: (0, 1)}      # direction bit -> (row, column) of the next maze cell
MAZE = 0x0C00
ROW = 0x28
PLAY_AHEAD = 22                                           # frames looked ahead for each direction
DECIDE_EVERY = 6                                          # frames between two decisions


def snapshot(m, p):
    return (bytes(m.mem), (m.a, m.x, m.y, m.s, m.pc, m.c, m.z, m.n, m.v, m.d, m.i), list(p.latch))


def restore(m, p, s):
    m.mem[:] = s[0]
    m.a, m.x, m.y, m.s, m.pc, m.c, m.z, m.n, m.v, m.d, m.i = s[1]
    p.latch = list(s[2])


def walkable(code):
    return code in (0, 1, 2)


def cells(mem):
    ptr = mem[0x80] | mem[0x81] << 8
    off = ptr - MAZE
    return off // ROW, off % ROW


def dist_map(mem, sources):
    """breadth-first distance (in cells) from the nearest of the source cells over the walkable cells of the maze"""
    dist = {}
    queue = []
    for c in sources:
        dist[c] = 0
        queue.append(c)
    for r, c in queue:
        for dr, dc in STEP.values():
            n = (r + dr, c + dc)
            if n in dist or not (0 <= n[0] < 25 and 0 <= n[1] < ROW):
                continue
            if not walkable(mem[MAZE + n[0] * ROW + n[1]]):
                continue
            dist[n] = dist[(r, c)] + 1
            queue.append(n)
    return dist


def ghost_cells(mem, pac, frightened):
    """the cells of the ghosts (all those frightened, or all the others that are not eyes) from their pixel positions relative to Pac-Man's"""
    out = []
    px, py = mem[0x8A + 4], mem[0x85 + 4]
    for g in range(4):
        st = mem[0xCE + g]
        eyes = st & 0x40
        fr = bool(st & 0x80)
        if eyes or fr != frightened or st == 0x00:
            continue
        gx, gy = mem[0x8A + g], mem[0x85 + g]
        dx = ((gx - px + 128) & 0xFF) - 128
        dy = ((gy - py + 128) & 0xFF) - 128
        r0, c0 = cells(mem)
        out.append((r0 + round(dy / 8), c0 + round(dx / 4)))
    return out


def dots(mem):
    return [(r, c) for r in range(25) for c in range(ROW) if mem[MAZE + r * ROW + c] in (1, 2)]


def count(mem):
    return mem[0x34 + mem[0x2B]] | mem[0x36 + mem[0x2B]] << 8


def run(out, seed, frames, levels, two):
    rng = random.Random(seed)
    sim_rng = random.Random(seed + 7919)
    cs = AC.rom_charset()
    p = ReplayInputs(cs)
    rec = []
    base = {"stick0": 0x0F, "stick1": 0x0F, "trig0": 1, "trig1": 1, "console": 7, "key": 0xFF, "keydelay": 0, "clock": 0, "drkmsk": 0xFF, "colrsh": 0}
    rom = CA.RomApp(0)
    m = rom.m

    def one(f, record):
        f = dict(f)
        f["random"] = bytes((rng if record else sim_rng).randrange(256) for _ in range(64))
        p.set(f)
        coll = p.collisions(W.World().load(m.mem))
        rom.frame(p, coll)
        w = W.World().load(m.mem)
        w.pokey = list(CAB.LOG)
        p.frame_done(w)
        if record:
            f["random"] = bytes(f["random"])
            rec.append(f)

    def frame_inputs(t, stick):
        f = dict(base)
        f["clock"] = t & 0xFF
        f["stick0"] = stick
        if two:
            f["stick1"] = stick
        if two and 300 <= t < 304:
            f["console"] = 5
        elif 330 <= t < 334:
            f["console"] = 6
        return f

    t = 0
    stick = 0x0F
    levels_done = 0
    seen = {"eaten pause": 0, "level end": 0, "frames": 0}
    last_level = None
    try:
        while t < frames:
            mem = m.mem
            playing = mem[0x19] == 0 and mem[0x21] == 1 and mem[0x24] == 0 and mem[0xED] == 0 and not mem[0x26] and not mem[0xE5] and not mem[0x20]
            if playing and t % DECIDE_EVERY == 0:
                snap = snapshot(m, p)
                best, best_v = None, None
                fright = mem[0xFC] != 0
                lives0 = mem[0x2C + mem[0x2B]]
                c0 = count(mem)
                tgt = ghost_cells(mem, cells(mem), True) if fright else []
                dm = dist_map(mem, tgt if tgt else dots(mem) or [cells(mem)])
                for d, sv in DIRS.items():
                    restore(m, p, snap)
                    ate = died = 0
                    tt = t
                    for k in range(PLAY_AHEAD):
                        one(frame_inputs(tt, sv), False)
                        tt += 1
                        if m.mem[0xE5]:
                            ate = 1
                        if m.mem[0xED] or m.mem[0x2C + m.mem[0x2B]] < lives0:
                            died = 1
                            break
                    gain = count(m.mem) - c0
                    near = 99
                    for gc in ghost_cells(m.mem, cells(m.mem), False):
                        near = min(near, abs(gc[0] - cells(m.mem)[0]) + abs(gc[1] - cells(m.mem)[1]))
                    v = -1000000 * died + 20 * gain + 5000 * ate - dm.get(cells(m.mem), 60) - (60 if near < 3 else 0)
                    if m.mem[0x26]:
                        v += 100000
                    if best_v is None or v > best_v:
                        best, best_v = sv, v
                restore(m, p, snap)
                stick = best
            elif not playing:
                stick = 0x0F
            one(frame_inputs(t, stick), True)
            t += 1
            mem = m.mem
            if mem[0xE5] and not seen["eaten pause"]:
                seen["eaten pause"] = t
            if mem[0x26] and not seen["level end"]:
                seen["level end"] = t
            lv = mem[0x30 + mem[0x2B]]
            if last_level is not None and lv != last_level:
                levels_done += 1
                if levels_done >= levels:
                    for _ in range(300):
                        one(frame_inputs(t, 0x0F), True)
                        t += 1
                    break
            last_level = lv
            if t % 600 == 0:
                print("frame %d lives %d dots %d level %d score %s eaten-pause-first %s level-end-first %s" % (t, mem[0x2C], count(mem), lv, "".join("%x" % (b & 15) for b in mem[0x2000:0x2000]), seen["eaten pause"], seen["level end"]), flush=True)
    finally:
        C.Machine.wr = CAB._orig
        C.Machine.rd = __import__("check_play")._orig_rd
    MR.write_replay(out, rec, seed=seed, start_clock=0, with_random=True)
    print("wrote %s: %d frames, eaten pause first at %s, level end first at %s, levels cleared %d" % (out, len(rec), seen["eaten pause"], seen["level end"], levels_done))


def main():
    a = sys.argv[1:]
    out = a[0]
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 1
    frames = int(a[a.index("--frames") + 1]) if "--frames" in a else 20000
    levels = int(a[a.index("--stop-after-levels") + 1]) if "--stop-after-levels" in a else 1
    run(out, seed, frames, levels, "--two" in a)


if __name__ == "__main__":
    main()
