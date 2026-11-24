"""OV-64: the longest path of the vertical-blank handler with SETS OF VALUES for the four ghost-state bytes (tools/wcet_sets/wcet_sets.cpp).
Writes the input of the C++ program for a frame class, runs it, prints its answer.
Usage: python -I tools/wcet_sets.py --class "play" [--ghosts 1|0] [--correlate 1|0] [--limit N]
  --ghosts 0: the ghost bytes are not followed at all (the model of tools/static_wcet.py, to check the C++ against it); --correlate 0: followed, but a read of a byte with several values is unknown."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import static_wcet as W  # noqa: E402

ROOT = os.path.dirname(HERE)
EXE = os.path.join(HERE, "wcet_sets", "wcet_sets.exe")
PROGRAM = os.path.join(HERE, "wcet_sets", "program.txt")
DOMAIN_PROOF = list(range(0x00, 0xE5))           # the values GhostState reached in the search of docs/34 (analysis/evidence-state-proof-summary.txt: 00..E4): an over-approximation (the increment at $A800 chains)
DOMAIN_REAL = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x42, 0x44, 0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0]   # the closure of the writers' (old, new) pairs of that proof from 0, with the increment at $A800 only on 0 (docs/39 5b)
DOMAIN = DOMAIN_REAL


def ensure_program():
    if not os.path.isfile(PROGRAM):
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "wcet_sets", "dump_program.py"), PROGRAM], check=True, capture_output=True)


def build():
    if not os.path.isfile(EXE):
        subprocess.run(["g++", "-O2", "-std=c++17", "-o", EXE, os.path.join(HERE, "wcet_sets", "wcet_sets.cpp")], check=True)


def make_input(cls, ghosts=True, correlate=True, limit=20_000_000, path=None, nghost=4, ghost_init=None):
    ensure_program()
    init = W.CLASSES[cls]
    track = [a for a in W.TRACK]
    lines = ["ENTRY a5fd", "ROMFILE " + os.path.join(ROOT, "original", "Pac-Man.rom").replace("\\", "/")]
    with open(PROGRAM) as fh:
        lines.append(fh.read().rstrip())
    lines.append("TRACK %d" % len(track))
    for a in track:
        lines.append("%d %d" % (a, init.get(a, -1)))
    lines.append("DOMAIN %d %s" % (len(DOMAIN), " ".join(str(v) for v in DOMAIN)))
    for g in range(4):
        vals = DOMAIN if ghost_init is None else [ghost_init[g]]               # init: one starting value for each ghost byte (a concrete assignment)
        lines.append("GHOST %d %d %s" % (g, len(vals), " ".join(str(v) for v in vals)))
    lines.append("ANNOT %d" % len(W.ANNOT))
    for pc, (owner, bound, why) in sorted(W.ANNOT.items()):
        lines.append("%d %d" % (pc, bound))
    lines.append("GHOSTS %d" % (1 if ghosts else 0))
    lines.append("GHOSTN %d" % nghost)
    lines.append("CORRELATE %d" % (1 if correlate else 0))
    lines.append("LIMIT %d" % limit)
    path = path or os.path.join(HERE, "wcet_sets", "input_%s.txt" % cls.replace(" ", "_"))
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def run(cls, **kw):
    build()
    path = make_input(cls, **kw)
    r = subprocess.run([EXE, path], capture_output=True, text=True)
    return r.stdout, r.stderr


if __name__ == "__main__":
    a = sys.argv
    cls = a[a.index("--class") + 1] if "--class" in a else "play"
    kw = {}
    if "--ghosts" in a:
        kw["ghosts"] = a[a.index("--ghosts") + 1] != "0"
    if "--correlate" in a:
        kw["correlate"] = a[a.index("--correlate") + 1] != "0"
    if "--init" in a:
        kw["ghost_init"] = [int(x, 16) for x in a[a.index("--init") + 1].split(",")]
    if "--nghost" in a:
        kw["nghost"] = int(a[a.index("--nghost") + 1])
    if "--limit" in a:
        kw["limit"] = int(a[a.index("--limit") + 1])
    out, err = run(cls, **kw)
    print("class", cls, kw)
    print(out.strip())
    if err.strip():
        print(err.strip()[-300:])
