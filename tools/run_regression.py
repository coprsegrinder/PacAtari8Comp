"""Stage 89 (regression): one command that re-runs the verification of the C port, so that a later change cannot break what was verified without being noticed.
  quick (default, about 10 minutes): build with gcc (Release, strict C99, -Werror) -> ctest (36 tests) -> the golden games: every replay of the set below is played by the built shell with the renderer and the sound
          chip on, and its state hash, run digest, video digest and audio digest must equal the line of analysis/golden-digests.txt (made by --update-golden from a build verified against the ROM) -> the Python
          tests of the C port (tests/test_c_*.py are long and left to --full; the shell, behaviour and C-against-ROM tests run).
  --full  adds: every test module of the project (about 35 minutes), the same with clang, the C against the ROM frame by frame on every golden replay (tools/check_c_vs_rom.py: the whole state, every frame), and the Linux build and tests in WSL
          (tools/build_test_posix.sh) when WSL is there; with --sanitizers the Linux run is made with AddressSanitizer and UndefinedBehaviorSanitizer.
The golden set (all made here, deterministically, no port involved): the four sessions of the 79d vectors, six seeded random games (tools/make_rom_fuzz_replays.py), and the edge replays of stage 89
(tools/make_rom_edge_replays.py: every profile, two seeds).  The three games played on purpose of stage 87 and the long ones of stage 89 need the ROM played for tens of minutes and are not regenerated: add
their .pmrp files to build/regress/replays/ by hand and they join the set (their lines are in the golden file when it was made with them).
Usage: python -I tools/run_regression.py [--full] [--sanitizers] [--update-golden] [--keep-going]
Exit code 0 when every step passed; the summary is printed and written to build/regress/summary.txt."""
import glob
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
GOLDEN = os.path.join(ROOT, "analysis", "golden-digests.txt")
WORK = os.path.join(ROOT, "build", "regress")
REPLAYS = os.path.join(WORK, "replays")
EXE = "pacman_a8.exe" if os.name == "nt" else "pacman_a8"
RESULTS = []


def step(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  (" + detail + ")") if detail else ""), flush=True)
    return ok


def run(cmd, cwd=ROOT, timeout=3600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def build(cc):
    d = os.path.join(WORK, cc)
    r = run(["cmake", "-S", "src/c", "-B", d, "-G", "Ninja", "-DCMAKE_C_COMPILER=" + cc, "-DCMAKE_BUILD_TYPE=Release"])
    if r.returncode != 0:
        step("configure " + cc, False, r.stdout[-200:] + r.stderr[-200:])
        return None
    r = run(["cmake", "--build", d])
    warn = len(re.findall(r"warning|error", r.stdout + r.stderr, re.I))
    if not step("build %s (strict C99, -Werror)" % cc, r.returncode == 0 and warn == 0, "%d warnings or errors" % warn):
        return None
    return d


def ctest(d, cc):
    r = run(["ctest", "--test-dir", d])
    m = re.search(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)", r.stdout)
    step("ctest %s" % cc, r.returncode == 0 and m is not None and m.group(2) == "0", m.group(0) if m else "no result")


def make_replays():
    """-> {name: path}; every file is made here, deterministically"""
    import make_replay as MR
    import make_rom_edge_replays as ED
    import make_rom_fuzz_replays as FZ
    os.makedirs(REPLAYS, exist_ok=True)
    out = {}
    vec = os.path.join(ROOT, "resources", "vectors")
    for n in ("clock", "keys", "1p", "2p"):
        v = os.path.join(vec, "session_%s.vec" % n)
        if os.path.exists(v):
            p = os.path.join(REPLAYS, "session-%s.pmrp" % n)
            MR.from_vector(v, p)
            out["session-" + n] = p
    for s in range(1, 7):
        p = os.path.join(REPLAYS, "fuzz%d.pmrp" % s)
        FZ.make(p, s, 12000)
        out["fuzz%d" % s] = p
    for prof in ED.PROFILES:
        for s in (1, 2):
            p = os.path.join(REPLAYS, "edge-%s-%d.pmrp" % (prof, s))
            ED.make(p, prof, s, 6000)
            out["edge-%s-%d" % (prof, s)] = p
    for f in sorted(os.listdir(REPLAYS)):                           # replays added by hand (the games played on purpose)
        n = f[:-5]
        if f.endswith(".pmrp") and n not in out and n.startswith(("bot", "long")):
            out[n] = os.path.join(REPLAYS, f)
    return out


def digests(exe, path):
    r = run([exe, "run", os.path.relpath(path, ROOT), "--video", "--audio"])
    d = {}
    for key, pat in (("frames", r"frames run: (\d+) of"), ("state", r"final state hash: (\w+)"), ("run", r"run digest: (\w+)"), ("video", r"video digest: (\w+)"), ("audio", r"audio digest: (\w+)")):
        m = re.search(pat, r.stdout)
        d[key] = m.group(1) if m else "?"
    return d


def read_golden():
    g = {}
    if os.path.exists(GOLDEN):
        with open(GOLDEN, encoding="utf-8") as fh:
            for line in fh:
                if line.strip() and not line.startswith("#"):
                    p = line.split()
                    g[p[0]] = p[1:]
    return g


def golden_games(d, cc, replays, update):
    exe = os.path.join(d, "shell", EXE)
    gold = read_golden()
    new, bad = {}, []
    t0 = time.time()
    for name, path in replays.items():
        x = digests(exe, path)
        line = [x["frames"], x["state"], x["run"], x["video"], x["audio"]]
        new[name] = line
        if not update and name in gold and gold[name] != line:
            bad.append(name)
        if not update and name not in gold:
            bad.append(name + " (not in the golden file)")
    if update:
        with open(GOLDEN, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# golden digests of the games of tools/run_regression.py (stage 89): name, frames, state hash after the last frame, run digest (hash over every frame's state hash), video digest, audio digest\n")
            fh.write("# made by `python -I tools/run_regression.py --update-golden` from a build that equals the ROM on every one of these games (tools/check_c_vs_rom.py); NTSC\n")
            for name in sorted(new):
                fh.write("%s %s\n" % (name, " ".join(new[name])))
        step("golden digests written (%d games)" % len(new), True, GOLDEN)
        return
    missing = [n for n in gold if n not in new and not n.startswith(("bot", "long"))]
    step("golden games with %s (%d games, %d frames, %.0f s)" % (cc, len(new), sum(int(v[0]) for v in new.values() if v[0].isdigit()), time.time() - t0), not bad and not missing,
         ("differ: " + ", ".join(bad[:6])) if bad else ("not played: " + ", ".join(missing[:6])) if missing else "state, run, video and audio digests equal")


# every test that says a generated chapter or a generated source is current: they take about 30 seconds together, and each caught a stale chapter at some time (stage 98: docs/32 had been stale since a harness was added in stage 80b)
FRESHNESS = ["test_behaviour_docs", "test_binary_docs", "test_build_docs", "test_c_world", "test_cfg", "test_constants", "test_correlation", "test_data_docs", "test_functions", "test_io", "test_locals", "test_original_architecture", "test_pointers",
             "test_relationships", "test_resources_docs", "test_source_docs", "test_stack", "test_states", "test_structures", "test_testing_docs", "test_tracing", "test_two_players", "test_variables"]


def python_tests(full):
    mods = ["tests.test_shell", "tests.test_behaviour", "tests.test_c_vs_rom", "tests.test_correlation", "tests.test_regression", "tests.test_source_docs", "tests.test_original_architecture", "tests.test_binary_docs", "tests.test_data_docs", "tests.test_behaviour_docs", "tests.test_resources_docs", "tests.test_build_docs", "tests.test_testing_docs"]
    mods += ["tests." + m for m in FRESHNESS if "tests." + m not in mods]
    if full:                                                  # every test module of the project (about 35 minutes)
        mods = ["tests." + os.path.basename(p)[:-3] for p in sorted(glob.glob(os.path.join(ROOT, "tests", "test_*.py")))]
    r = run([sys.executable, "-m", "unittest"] + mods, timeout=14400)
    m = re.search(r"Ran (\d+) tests", r.stderr)
    step("python tests (%d modules)" % len(mods), r.returncode == 0, (m.group(0) if m else "") + ("" if r.returncode == 0 else " " + r.stderr[-300:]))


def rom_compare(d, replays):
    exe = os.path.join(d, "shell", EXE)
    import check_c_vs_rom as X
    total, bad = 0, []
    for name, path in replays.items():
        try:
            ok = X.run(path, exe)
        except SystemExit as e:
            ok = False
            print(e)
        total += 1
        if not ok:
            bad.append(name)
    step("C against the ROM, frame by frame, %d games" % total, not bad, ("differ: " + ", ".join(bad)) if bad else "no difference in any frame")


def linux(sanitize):
    r = run(["wsl", "-e", "bash", "-c", "echo ok"], timeout=120)
    if r.returncode != 0 or "ok" not in r.stdout.replace("\x00", ""):
        step("linux (WSL)", True, "skipped: no WSL here")
        return
    extra = " -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=undefined" if sanitize else ""
    posix = "/mnt/" + ROOT[0].lower() + ROOT[2:].replace("\\", "/")
    r = run(["wsl", "-e", "bash", "-c", 'cd "%s" && sh tools/build_test_posix.sh gcc build/regress/posix%s' % (posix, extra)], timeout=7200)
    out = r.stdout.replace("\x00", "")
    m = re.search(r"RESULT: (\d+) passed, (\d+) failed", out)
    step("linux gcc%s: build and tests" % (" with sanitizers" if sanitize else ""), r.returncode == 0 and m is not None and m.group(2) == "0", m.group(0) if m else out[-200:])


def main():
    a = sys.argv[1:]
    full, update = "--full" in a, "--update-golden" in a
    os.makedirs(WORK, exist_ok=True)
    t0 = time.time()
    replays = make_replays()
    step("replays made (%d)" % len(replays), len(replays) >= 30)
    d = build("gcc") or build("clang")
    if d is None:
        sys.exit(1)
    cc = os.path.basename(d)
    if not update:
        ctest(d, cc)
    golden_games(d, cc, replays, update)
    if not update:
        python_tests(full)
    if full and not update:
        c2 = build("clang") if cc != "clang" else build("gcc")
        if c2:
            ctest(c2, os.path.basename(c2))
            golden_games(c2, os.path.basename(c2), replays, False)
        rom_compare(d, replays)
        linux("--sanitizers" in a)
        if "--sanitizers" not in a:
            linux(True)
    ok = all(r[1] for r in RESULTS)
    text = "\n".join("%s  %s%s" % ("PASS" if r[1] else "FAIL", r[0], ("  (" + r[2] + ")") if r[2] else "") for r in RESULTS) + "\n%s: %d steps, %d failed, %.0f s\n" % ("ALL PASSED" if ok else "FAILURES", len(RESULTS), sum(1 for r in RESULTS if not r[1]), time.time() - t0)
    with open(os.path.join(WORK, "summary.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
