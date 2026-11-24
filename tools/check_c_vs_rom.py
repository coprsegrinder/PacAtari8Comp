"""Stage 86 (functional equivalence): the C port against the ROM itself, frame by frame, with nothing of the Python port in between.
The ROM runs on the concrete 6502 (tools/check_app.py RomApp: `Start` from the RUN address, then every frame the OS clock, the inputs of the frame, the deferred vertical-blank handler `$A5FD` between two
instructions of the main program and the main program to its next wait); the collision registers it reads are computed from ITS OWN memory by the GTIA model (tools/gtia_collisions.py, docs/50), with the latch
carried from frame to frame.  The C port (`pacman_a8 run REPLAY --states FILE`) gets the same replay: the same inputs and the same RANDOM bytes of every frame.  After every frame the whole state is compared:
the zero page (except the declared scratch bytes of the ROM's temporaries), the maze and its three copies, the title screen, the status rows, the shadows, the player-missile pages, the eight positions, the picture
buffers, the ordered chip writes and the number of RANDOM bytes read.
Usage: python -I tools/check_c_vs_rom.py REPLAY [--exe PATH_TO_pacman_a8] [--frames N] [--write FILE]
Exit code 0 when no frame differs."""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_collide as AC  # noqa: E402
import check_app as CA  # noqa: E402
import check_app_board as CAB  # noqa: E402
import check_ghost as CG  # noqa: E402
import core_app as APP  # noqa: E402
from collections import Counter  # noqa: E402
import core_draw as D  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402
import make_replay as MR  # noqa: E402
import platform_iface as PI  # noqa: E402
import vecfmt as V  # noqa: E402

ROOT = os.path.dirname(HERE)


class ReplayInputs(PI.GtiaCollisions):
    """the inputs of one frame from a replay record; the collision registers from the ROM's own state"""

    def __init__(self, charset):
        super().__init__(lambda w: D.scene(w, charset))
        self.f = None
        self.given = []

    def set(self, f):
        self.f = f
        self.given = list(f.get("random", b""))

    def stick(self, port):
        return self.f["stick0"] if port == 0 else self.f["stick1"]

    def trigger(self, port):
        return self.f["trig0"] if port == 0 else self.f["trig1"]

    def console(self):
        return self.f["console"]

    def key(self):
        return self.f["key"]

    def key_delay(self):
        return self.f["keydelay"]

    def clock(self):
        return self.f["clock"]

    def attract(self):
        return self.f["drkmsk"], self.f["colrsh"]


def read_states(path, n):
    """-> [(packed state, [(addr, value)], random reads)] for the frames of the C dump"""
    with open(path, "rb") as fh:
        b = fh.read()
    out, pos = [], 0
    for _ in range(n):
        st = b[pos:pos + V.STATE_SIZE]
        pos += V.STATE_SIZE
        (cnt,) = struct.unpack_from("<I", b, pos)
        pos += 4
        log = [(struct.unpack_from("<H", b, pos + 3 * k)[0], b[pos + 3 * k + 2]) for k in range(cnt)]
        pos += 3 * cnt
        (rr,) = struct.unpack_from("<I", b, pos)
        pos += 4
        out.append((st, log, rr))
    assert pos == len(b), "the dump has bytes left over"
    return out


def run(replay_path, exe, frames=None, write=None):
    with open(replay_path, "rb") as fh:
        rp = MR.read_replay(fh.read())
    fr = rp["frames"][:frames] if frames else rp["frames"]
    if not (rp["flags"] & MR.FLAG_RANDOM):
        raise SystemExit("the replay must carry the RANDOM bytes of every frame (a session replay): the ROM and the C must read the same values")
    states = os.path.join(ROOT, "build", "c86", os.path.basename(replay_path) + ".states")
    os.makedirs(os.path.dirname(states), exist_ok=True)
    r = subprocess.run([exe, "run", os.path.relpath(replay_path, ROOT), "--frames", str(len(fr)), "--states", os.path.relpath(states, ROOT)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("the C shell failed: " + r.stdout)
    cs = read_states(states, len(fr))
    clock0 = rp["start_clock"]
    p = ReplayInputs(AC.rom_charset())
    p.set(fr[0])
    rom = CA.RomApp(clock0)
    first, stats = None, {"frames": 0, "pokey writes": 0, "random bytes": 0, "frames with chip writes": 0}
    classes = Counter()
    try:
        for i, f in enumerate(fr):
            p.set(f)
            wrom = W.World().load(rom.m.mem)                       # the ROM's own state, before the frame: the registers the frame will read
            coll = p.collisions(wrom)
            classes[APP.frame_class(wrom)] += 1
            rom.frame(p, coll)
            wa = W.World().load(rom.m.mem)
            wa.pokey = list(CAB.LOG)
            p.frame_done(wa)                                        # the latch: what the ROM's frame left on the screen
            st, log, rr = cs[i]
            wc = V.unpack_state(st)
            wc.pokey = log
            d = CAB.diffs(rom.m, wc, CG.SCRATCH)
            if len(rom.m.random_reads) != rr:
                d.append("random %d != %d" % (len(rom.m.random_reads), rr))
            stats["frames"] += 1
            stats["pokey writes"] += len(log)
            stats["random bytes"] += rr
            stats["frames with chip writes"] += 1 if log else 0
            if d:
                first = (i, d[:8])
                break
    finally:
        C.Machine.wr = CAB._orig
        C.Machine.rd = __import__("check_play")._orig_rd
    lines = ["%s: %d of %d frames compared, %s" % (os.path.basename(replay_path), stats["frames"], len(fr), "NO DIFFERENCE" if first is None else "FIRST DIFFERENCE at frame %d: %s" % first),
             "  chip writes compared: %d (in %d frames), RANDOM bytes: %d" % (stats["pokey writes"], stats["frames with chip writes"], stats["random bytes"]),
             "  frame classes seen: " + ", ".join("%s %d" % kv for kv in sorted(classes.items(), key=lambda kv: str(kv[0])))]
    text = "\n".join(lines)
    print(text)
    if write:
        with open(write, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    return first is None


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    exe = os.path.join(ROOT, "build", "c82-gcc-Release", "shell", "pacman_a8.exe")
    frames = write = None
    path = None
    i = 0
    while i < len(a):
        if a[i] == "--exe":
            exe = os.path.abspath(a[i + 1])
            i += 2
        elif a[i] == "--frames":
            frames = int(a[i + 1])
            i += 2
        elif a[i] == "--write":
            write = a[i + 1]
            i += 2
        else:
            path = a[i]
            i += 1
    sys.exit(0 if run(path, exe, frames, write) else 1)


if __name__ == "__main__":
    main()
