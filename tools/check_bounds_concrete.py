"""OV-64: the static bounds of tools/static_wcet.py against the CONCRETE 6502: random frames of every class (tools/algorithm_models7.py frame_setup, the dispatcher variables set to the class) run on tools/cpu6502.py with the
instruction cycles counted exactly (tools/fuzz_concrete.py Counter); no frame may cost more than the bound of its class.  The ratio of the heaviest frame found to the bound shows how tight each bound is.
Usage: python -I tools/check_bounds_concrete.py [--n 300] [--seed 1] [--write analysis/evidence-bounds-concrete-summary.txt]"""
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import algorithm_models as A      # noqa: E402
import fuzz_concrete as F         # noqa: E402
import static_wcet as W           # noqa: E402

# (class name, the class of tools/static_wcet.py CLASSES whose variables it sets, bound from analysis/evidence-wcet-summary.txt / docs/39)
CLASSES = ["copyright setup", "copyright wait", "title menu", "title after game", "paused", "board start", "start idle", "game-over countdown",
           "level end 0", "level end 1", "level end 2", "level end 3", "level end 4", "turn control", "death", "eaten pause", "play", "start tune", "ready wait"]
STAGE_BOUND = {"level end 0": 6096, "level end 1": 3197, "level end 2": 3165, "level end 3": 10322, "level end 4": 14846}


def bounds_from_table():
    out = {}
    with open(os.path.join(ROOT, "analysis", "evidence-wcet-summary.txt"), encoding="utf-8") as fh:
        for ln in fh.read().splitlines()[2:]:
            name, rest = ln[:20].strip(), ln[20:].split()
            if name and rest and rest[0].isdigit():
                out[name] = int(rest[0])
    out.update(STAGE_BOUND)
    return out


def frame_of_class(base, rng, cls):
    m = F.build(base, rng)
    for k, v in W.CLASSES[cls].items():
        m.mem[k] = v
    if cls == "level end 4":
        for k, v in W.start_positions().items():
            m.mem[k] = v
    if cls == "start idle":
        m.mem[0x21] = 0
    m.mem[0x2B] = rng.randrange(2)                                  # the current player, as the static search assumes
    return m


def check(n=300, seed=1):
    bounds = bounds_from_table()
    base = A.started_machine()
    rng = random.Random(seed)
    counter = F.Counter()
    counter.install()
    rows = []
    try:
        for cls in CLASSES:
            top = 0
            for _ in range(n):
                m = frame_of_class(base, rng, cls)
                c = F.cost_of(m, counter)
                top = max(top, c)
            rows.append((cls, bounds[cls], top))
    finally:
        counter.remove()
    return rows


def main():
    a = sys.argv
    n = int(a[a.index("--n") + 1]) if "--n" in a else 300
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 1
    rows = check(n, seed)
    L = ["Static bounds against random concrete frames (tools/check_bounds_concrete.py, %d frames a class, seed %d): the instruction cycles of the heaviest frame found, and its share of the bound" % (n, seed),
         "class | static bound | heaviest concrete frame | share | above the bound?"]
    bad = 0
    for cls, b, top in rows:
        over = top > b
        bad += over
        L.append("%-20s %6d %6d %5.0f%%  %s" % (cls, b, top, 100.0 * top / b, "YES" if over else "no"))
    L.append("frames above their bound: %d classes" % bad)
    txt = chr(10).join(L) + chr(10)
    if "--write" in a:
        with open(os.path.join(ROOT, a[a.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
