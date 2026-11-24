"""Stage 80d: replay files for the headless shell (src/c/shell/replay.h) - the Python side of the format.
  python -I tools/make_replay.py --from-vector resources/vectors/session_1p.vec OUT.pmrp [--hashes OUT.txt]
      the inputs of a recorded session (stage 79d: one record a frame of tools/make_app_sequences.py, whose Python program equals the ROM after every frame) become a replay that carries the frame's RANDOM bytes;
      --hashes writes the expected hash of the state after every frame (FNV-1a 64 bit of the packed state of the record's "after"), the thing the shell must reproduce
  python -I tools/make_replay.py --script SCRIPT.txt OUT.pmrp [--seed N] [--clock N]
      a replay from a text script: one line per run of frames, "COUNT [stick=N] [stick1=N] [trig0=N] [trig1=N] [console=N] [key=N] [keydelay=N] [drkmsk=N] [colrsh=N]" (numbers decimal or 0x..), the
      values stay until a later line changes them; the defaults are "nothing pressed" (stick $0F, triggers 1, console 7, key $FF, key delay 0, DRKMSK $FF, COLRSH 0); the clock counts frames from --clock;
      RANDOM comes from the model with the seed (the frames carry no RANDOM bytes); lines starting with # are comments
The reader `read_replay` and the writer `write_replay` are what tests/test_shell.py uses; the format is the one of replay.h."""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MAGIC = b"PMRP"
VERSION = 1
FLAG_RANDOM = 1
FIELDS = ("stick0", "stick1", "trig0", "trig1", "console", "key", "keydelay", "clock", "drkmsk", "colrsh")


def fnv1a32(data):
    h = 0x811C9DC5
    for b in data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def fnv1a64(data, h=0xCBF29CE484222325):
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def write_replay(path, frames, seed=0, start_clock=0, with_random=False):
    """frames: list of dicts with the FIELDS (and "random": bytes when with_random)"""
    out = bytearray(MAGIC)
    out += struct.pack("<HHIIB3x", VERSION, FLAG_RANDOM if with_random else 0, seed, len(frames), start_clock)
    for f in frames:
        out += bytes(f[k] & 0xFF for k in FIELDS)
        if with_random:
            r = bytes(f.get("random", b""))
            out += struct.pack("<H", len(r)) + r
    out += struct.pack("<I", fnv1a32(out))
    with open(path, "wb") as fh:
        fh.write(out)
    return bytes(out)


def read_replay(data):
    """-> dict(seed, start_clock, flags, frames=[dict]); raises ValueError for anything the C reader refuses"""
    if len(data) < 24 or data[:4] != MAGIC:
        raise ValueError("not a replay")
    version, flags, seed, n, clock = struct.unpack_from("<HHIIB", data, 4)
    if version != VERSION or flags & ~FLAG_RANDOM:
        raise ValueError("version or flags")
    if fnv1a32(data[:-4]) != struct.unpack_from("<I", data, len(data) - 4)[0]:
        raise ValueError("checksum")
    pos, frames = 20, []
    for _ in range(n):
        f = dict(zip(FIELDS, data[pos:pos + 10]))
        pos += 10
        if flags & FLAG_RANDOM:
            (k,) = struct.unpack_from("<H", data, pos)
            f["random"] = data[pos + 2:pos + 2 + k]
            pos += 2 + k
        frames.append(f)
    if pos != len(data) - 4:
        raise ValueError("bytes left over")
    return {"seed": seed, "start_clock": clock, "flags": flags, "frames": frames}


def from_vector(vec, out, hashes=None):
    import vecfmt as V
    _, _, _, recs = V.read_set(vec)
    frames, hs = [], []
    for r in recs:
        a = r["args"]
        frames.append({"stick0": a[1], "stick1": 0x0F, "trig0": a[2], "trig1": a[3], "console": a[4], "key": a[5], "keydelay": a[6], "clock": a[7], "drkmsk": a[8], "colrsh": a[9], "random": bytes(r["rnd"])})
        hs.append(fnv1a64(r["after"]))
    write_replay(out, frames, seed=0, start_clock=frames[0]["clock"], with_random=True)
    if hashes:
        with open(hashes, "w", encoding="utf-8", newline="\n") as fh:
            for i, h in enumerate(hs):
                fh.write("%d %016x\n" % (i, h))
    return hs


def from_script(script, out, seed=0, clock=0):
    cur = {"stick0": 0x0F, "stick1": 0x0F, "trig0": 1, "trig1": 1, "console": 7, "key": 0xFF, "keydelay": 0, "drkmsk": 0xFF, "colrsh": 0}
    alias = {"stick": "stick0"}
    frames, t = [], clock
    with open(script, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = line.split()
            count = int(parts[0], 0)
            for kv in parts[1:]:
                k, v = kv.split("=")
                k = alias.get(k, k)
                if k not in cur:
                    raise SystemExit("unknown field " + k)
                cur[k] = int(v, 0)
            for _ in range(count):
                frames.append(dict(cur, clock=t & 0xFF))
                t += 1
    write_replay(out, frames, seed=seed, start_clock=clock & 0xFF, with_random=False)
    return len(frames)


def main():
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "--from-vector":
        hs = from_vector(a[1], a[2], a[a.index("--hashes") + 1] if "--hashes" in a else None)
        print("wrote %s: %d frames" % (a[2], len(hs)))
        return 0
    if len(a) >= 3 and a[0] == "--script":
        n = from_script(a[1], a[2], int(a[a.index("--seed") + 1], 0) if "--seed" in a else 0, int(a[a.index("--clock") + 1], 0) if "--clock" in a else 0)
        print("wrote %s: %d frames" % (a[2], n))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
