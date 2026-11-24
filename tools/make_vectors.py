"""Stage 75b (docs/51 section 2 and 4): writes the vector files of the C port into resources/vectors/ (derived data, git-ignored).
A vector is one call of a port-form function: the World before (the whole state), the arguments, the RANDOM values it consumed, the World after, the return value and the ordered chip writes.
The vectors are recorded from the runs of the existing checkers (tools/check_core.py, check_ghost.py, check_pacman.py, check_score.py, check_sound.py, check_frame.py, check_draw.py, check_play.py):
every function of tools/core_ref.py (plain values) and every function of the World modules that takes `w` first is wrapped, and the outermost call of each is recorded.  A checker that finds a difference
against the ROM stops the whole run: a vector is only written from calls that the checkers compared with the ROM with 0 differences (the sets are the checkers' own runs).
Usage: python -I tools/make_vectors.py [--quick] [--out DIR] [--only check_a,check_b] [--identity]
  --identity   writes only the test sets identity.vec and broken.vec (World calls whose after-state is the before-state), for the runner's tests"""
import functools
import inspect
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vecfmt as V  # noqa: E402
import algorithm_models as A  # noqa: E402

ROOT = A.ROOT
WORLD_MODULES = ("core_ghost", "core_pacman", "core_score", "core_sound", "core_frame", "core_draw", "core_play", "core_app_init", "core_app_board", "core_app_frame")
CHECKERS = ("check_core", "check_ghost", "check_pacman", "check_score", "check_sound", "check_frame", "check_draw", "check_play", "check_app_init", "check_app_board", "check_app_frame")


class Tee:
    """an iterator of RANDOM values that remembers what was taken; other attributes (the checkers' counters) come from the wrapped object"""

    def __init__(self, it):
        self._it = it
        self.taken = []

    def __iter__(self):
        return self

    def __next__(self):
        v = next(self._it)
        self.taken.append(v & 0xFF)
        return v

    def __getattr__(self, name):
        return getattr(self._it, name)


class Recorder:
    def __init__(self, outdir):
        self.outdir = outdir
        self.depth = 0
        self.sets = {}
        self.base = None
        self.mutating = set()
        self.skipped = {}

    def writer(self, name, kind, w=None):
        s = self.sets.get(name)
        if s is None:
            if kind == V.KIND_WORLD:
                if self.base is None:
                    self.base = V.pack_state(base_world())
            s = V.SetWriter(os.path.join(self.outdir, name + ".vec"), kind, name, self.base if kind == V.KIND_WORLD else None)
            self.sets[name] = s
        return s

    def close(self):
        for s in self.sets.values():
            s.close()


def base_world():
    """the World every vector is stored against: the started machine (diffs are small because the checkers start from it)"""
    import core_world as W
    return W.World().load(A.started_machine().mem)


def wrap_world(rec, modname, fname, fn):
    key = modname + "." + fname

    @functools.wraps(fn)
    def wrapper(w, *args, **kw):
        if rec.depth:
            return fn(w, *args, **kw)
        if w.pokey:
            raise AssertionError(key + ": the chip-write log is not empty at the call")
        iargs, newargs, tees = [], [], []
        for a in args:
            if hasattr(a, "__next__"):
                t = Tee(a)
                tees.append(t)
                newargs.append(t)
            elif isinstance(a, (bool, int)):
                iargs.append(int(a))
                newargs.append(a)
            else:
                raise TypeError(key + ": argument not recordable: %r" % (a,))
        before = V.pack_state(w)
        rec.depth += 1
        try:
            r = fn(w, *newargs, **kw)
        finally:
            rec.depth -= 1
        after = V.pack_state(w)
        rnd = [v for t in tees for v in t.taken]
        ret = int(r) if isinstance(r, (bool, int)) else None
        rec.writer(key, V.KIND_WORLD).world(iargs, rnd, ret, before, after, list(w.pokey))
        return r
    return wrapper


def wrap_pure(rec, fname, fn):
    key = "core_ref." + fname

    @functools.wraps(fn)
    def wrapper(*args, **kw):
        if rec.depth:
            return fn(*args, **kw)
        if kw:
            raise TypeError(key + ": keyword arguments not recordable")
        tees = {i: Tee(a) for i, a in enumerate(args) if hasattr(a, "__next__")}
        call = [tees.get(i, a) for i, a in enumerate(args)]
        saved = [list(a) if isinstance(a, (list, tuple)) else a for a in call]
        rec.depth += 1
        try:
            r = fn(*call, **kw)
        finally:
            rec.depth -= 1
        now = [list(a) if isinstance(a, (list, tuple)) else a for a in call]
        if now != saved:
            rec.mutating.add(key)
        for i, t in tees.items():
            saved[i] = list(t.taken)                  # a RANDOM iterator is recorded as the values it gave
        rec.writer(key, V.KIND_PURE).pure(saved, r if not isinstance(r, tuple) else list(r))
        return r
    return wrapper


def install(rec):
    patched = []
    import core_ref
    for fname, fn in inspect.getmembers(core_ref, inspect.isfunction):
        if fn.__module__ == "core_ref" and not fname.startswith("_"):
            patched.append((core_ref, fname, fn))
            setattr(core_ref, fname, wrap_pure(rec, fname, fn))
    for modname in WORLD_MODULES:
        mod = __import__(modname)
        for fname, fn in inspect.getmembers(mod, inspect.isfunction):
            if fn.__module__ != modname or fname.startswith("_"):
                continue
            params = list(inspect.signature(fn).parameters)
            if params and params[0] == "w":
                patched.append((mod, fname, fn))
                setattr(mod, fname, wrap_world(rec, modname, fname, fn))
    return patched


def uninstall(patched):
    for mod, fname, fn in patched:
        setattr(mod, fname, fn)


def run_checkers(rec, quick, only=None):
    problems = []
    for name in CHECKERS:
        if only and name not in only:
            continue
        mod = __import__(name)
        lines, _ = mod.report(quick)
        n_before = sum(s.count for s in rec.sets.values())
        bad = [l for l in lines if re.search(r"\b[1-9]\d* differences\b", l)]
        problems += [name + ": " + l for l in bad]
        print("%-12s %7d calls recorded so far%s" % (name, n_before, "" if not bad else "  DIFFERENCES"), flush=True)
    return problems


def write_identity(outdir, n=20):
    """test sets for the runner: a World call that does nothing (the after-state equals the before-state), with arguments, RANDOM values and chip writes carried through"""
    import core_world as W
    rng = random.Random(75)
    base = V.pack_state(base_world())
    sets = {}
    for name in ("identity", "broken"):
        s = V.SetWriter(os.path.join(outdir, name + ".vec"), V.KIND_WORLD, name if name == "identity" else "broken_identity", base)
        sets[name] = s
    for k in range(n):
        w = W.World()
        for fname, addr, cnt in W.FIELDS:
            setattr(w, fname, rng.randrange(256) if cnt == 1 else [rng.randrange(256) for _ in range(cnt)])
        for e in V.EXTRA_ORDER:
            setattr(w, e, [rng.randrange(256) if rng.random() < 0.3 else 0 for _ in range(V.EXTRA_SIZE[e])])
        st = V.pack_state(w)
        for s in sets.values():
            s.world([k, -k, 70000 * k], [rng.randrange(256) for _ in range(0)], None, st, st, [])
    for s in sets.values():
        s.close()


def main():
    quick = "--quick" in sys.argv
    out = os.path.join(ROOT, "resources", "vectors")
    if "--out" in sys.argv:
        out = os.path.join(ROOT, sys.argv[sys.argv.index("--out") + 1])
    os.makedirs(out, exist_ok=True)
    if "--identity" in sys.argv:
        write_identity(out)
        print("wrote identity.vec, broken.vec in", out)
        return 0
    for f in os.listdir(out):
        if f.endswith(".vec"):
            os.remove(os.path.join(out, f))
    rec = Recorder(out)
    rec.base = V.pack_state(base_world())     # before any checker runs: building it runs the ROM's start-up, which must not happen while a checker has its chip-write hook installed
    patched = install(rec)
    try:
        only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
        problems = run_checkers(rec, quick, only)
    finally:
        uninstall(patched)
        rec.close()
    for n, s in sorted(rec.sets.items()):
        print("  %-40s %8d calls  (%s)" % (n, s.count, "pure" if s.kind == V.KIND_PURE else "world"))
    if rec.mutating:
        print("functions that change their arguments (the result only is recorded, the arguments as they were before the call):", sorted(rec.mutating))
    if problems:
        print("a checker found differences against the ROM: the vectors are NOT valid")
        for p in problems:
            print("  " + p)
        for f in os.listdir(out):
            if f.endswith(".vec"):
                os.remove(os.path.join(out, f))
        return 1
    print("%d sets, %d calls, in %s" % (len(rec.sets), sum(s.count for s in rec.sets.values()), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
